import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.contact import Contact
from app.models.daily_call import DailyCall
from app.models.call_notes_file import CallNotesFile
from app.models.document import Document
from app.schemas.daily_call import DailyCallCreate, DailyCallUpdate, DailyCallResponse, DailyCallListResponse
from app.schemas.daily_call import CallNotesListResponse
from app.schemas.document import DocumentResponse
from app.services.daily_call_reminder_service import (
    ensure_daily_call_reminders_for_daily_call,
    _now_utc,
    REMINDER_30_TITLE,
    REMINDER_5_TITLE,
)
from app.models.notification import Notification


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/daily-calls", tags=["Daily Calls"])

MAX_CALL_NOTE_FILE_SIZE_BYTES = 20 * 1024 * 1024


def _ensure_upload_dir() -> Path:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _create_document_from_bytes(
    *,
    db: Session,
    current_user: User,
    file_bytes: bytes,
    original_filename: str,
    mime_type: str,
) -> Document:
    upload_dir = _ensure_upload_dir()

    storage_uuid = str(uuid.uuid4())
    storage_path = upload_dir / storage_uuid

    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    doc = Document(
        filename=storage_uuid,
        original_filename=original_filename,
        file_size_bytes=len(file_bytes),
        mime_type=mime_type,
        storage_path=str(storage_path),
        uploaded_by_user_id=current_user.id,
    )
    db.add(doc)
    db.flush()  # obtain doc.id
    return doc


def _create_call_notes_link(
    *,
    db: Session,
    daily_call: DailyCall,
    document: Document,
    created_at: datetime,
) -> CallNotesFile:
    expires_at = created_at + timedelta(days=7)
    link = CallNotesFile(
        daily_call_id=daily_call.id,
        file_id=document.id,
        document_id=document.id,  # Backward-compat for DBs still enforcing NOT NULL
        created_at=created_at,
        expires_at=expires_at,
    )
    db.add(link)
    db.flush()
    return link


@router.post("", response_model=DailyCallResponse, status_code=status.HTTP_201_CREATED)
def schedule_daily_call(
    daily_call_data: DailyCallCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Contact ownership (hard requirement)
    contact = db.query(Contact).filter(Contact.id == daily_call_data.contact_id, Contact.user_id == current_user.id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this contact")

    daily_call = DailyCall(
        contact_id=daily_call_data.contact_id,
        user_id=current_user.id,
        next_call_at=daily_call_data.next_call_at,
    )

    db.add(daily_call)
    db.flush()
    db.refresh(daily_call)

    now = _now_utc()
    ensure_daily_call_reminders_for_daily_call(db, daily_call, now)

    db.commit()
    db.refresh(daily_call)
    return daily_call


@router.get("", response_model=DailyCallListResponse)
def list_daily_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List current user's scheduled calls only, sorted by next_call_at ASC.
    """
    query = db.query(DailyCall).filter(DailyCall.user_id == current_user.id)
    total = query.count()

    daily_calls = (
        query.order_by(DailyCall.next_call_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Proactive reminders (deduped): if user views calls close to reminder time.
    now = _now_utc()
    for daily_call in daily_calls:
        ensure_daily_call_reminders_for_daily_call(db, daily_call, now)

    db.commit()
    return DailyCallListResponse(daily_calls=daily_calls, total=total, page=page, page_size=page_size)


@router.put("/{daily_call_id}", response_model=DailyCallResponse)
def update_daily_call(
    daily_call_id: str,
    daily_call_data: DailyCallUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    daily_call = db.query(DailyCall).filter(DailyCall.id == daily_call_id, DailyCall.user_id == current_user.id).first()
    if not daily_call:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this daily call")

    if daily_call_data.next_call_at is not None:
        # If the schedule changes, remove old reminder notifications for this DailyCall
        # so we don't show stale reminders.
        db.query(Notification).filter(
            Notification.entity_type == "DailyCall",
            Notification.entity_id == daily_call.id,
            Notification.notification_type == "STATUS_CHANGE",
            Notification.title.in_([REMINDER_30_TITLE, REMINDER_5_TITLE]),
        ).delete(synchronize_session=False)
        daily_call.next_call_at = daily_call_data.next_call_at

    if daily_call_data.call_note is not None:
        # Store text note as a short-lived file.
        note_bytes = daily_call_data.call_note.encode("utf-8")
        if len(note_bytes) > MAX_CALL_NOTE_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Call note exceeds maximum size",
            )

        now = _now_utc()
        doc = _create_document_from_bytes(
            db=db,
            current_user=current_user,
            file_bytes=note_bytes,
            original_filename=f"call_note_{daily_call.id}.doc",
            mime_type="application/msword",
        )
        _create_call_notes_link(db=db, daily_call=daily_call, document=doc, created_at=now)

    # Reminder scheduling depends on next_call_at.
    now = _now_utc()
    ensure_daily_call_reminders_for_daily_call(db, daily_call, now)

    db.commit()
    db.refresh(daily_call)
    return daily_call


@router.delete("/{daily_call_id}", status_code=status.HTTP_200_OK)
def delete_daily_call(
    daily_call_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    daily_call = db.query(DailyCall).filter(DailyCall.id == daily_call_id, DailyCall.user_id == current_user.id).first()
    if not daily_call:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this daily call")

    # Delete any linked note files + their stored document records first
    note_links = db.query(CallNotesFile).filter(CallNotesFile.daily_call_id == daily_call.id).all()
    file_ids = [link.file_id for link in note_links]

    if file_ids:
        docs = db.query(Document).filter(Document.id.in_(file_ids)).all()
        docs_by_id = {d.id: d for d in docs}

        # Remove from disk best-effort.
        for doc in docs:
            try:
                if doc.storage_path and os.path.exists(doc.storage_path):
                    os.remove(doc.storage_path)
            except OSError:
                logger.exception("Failed removing stored document file")

        for link in note_links:
            db.delete(link)
        for doc in docs:
            db.delete(doc)

    db.delete(daily_call)
    db.commit()

    return {"message": "Daily call deleted successfully", "daily_call_id": daily_call_id}


@router.get("/{daily_call_id}/call-notes", response_model=CallNotesListResponse)
def list_call_notes_files(
    daily_call_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List temporary call-note files (private to the DailyCall owner).
    The response includes:
    - expires_at from `call_notes_files.expires_at`
    - document linkage via `call_notes_files.file_id` (documents.id)
    """
    rows = (
        db.query(CallNotesFile, Document)
        .join(DailyCall, DailyCall.id == CallNotesFile.daily_call_id)
        .join(Document, Document.id == CallNotesFile.file_id)
        .filter(
            DailyCall.id == daily_call_id,
            DailyCall.user_id == current_user.id,
        )
        .all()
    )

    if not rows:
        # Don't leak whether the daily_call exists for another user.
        daily_call = db.query(DailyCall).filter(DailyCall.id == daily_call_id, DailyCall.user_id == current_user.id).first()
        if not daily_call:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this daily call")
        # DailyCall exists but has no files.
        return CallNotesListResponse(files=[])

    files = []
    for link, doc in rows:
        files.append(
            {
                "id": link.id,
                "file_id": link.file_id,
                "document_id": link.file_id,  # alias for the frontend
                "expires_at": link.expires_at,
                "original_filename": doc.original_filename,
                "filename": doc.filename,
            }
        )

    return CallNotesListResponse(files=files)


@router.post("/{daily_call_id}/notes", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_call_notes_file(
    daily_call_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    daily_call = (
        db.query(DailyCall)
        .filter(DailyCall.id == daily_call_id, DailyCall.user_id == current_user.id)
        .first()
    )
    if not daily_call:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this daily call")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_CALL_NOTE_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds maximum allowed size (20MB)",
        )

    now = _now_utc()
    original_filename = file.filename or f"call_notes_{daily_call.id}.doc"
    mime_type = file.content_type or "application/msword"

    doc = _create_document_from_bytes(
        db=db,
        current_user=current_user,
        file_bytes=file_bytes,
        original_filename=original_filename,
        mime_type=mime_type,
    )
    _create_call_notes_link(db=db, daily_call=daily_call, document=doc, created_at=now)

    db.commit()
    db.refresh(doc)
    return doc

