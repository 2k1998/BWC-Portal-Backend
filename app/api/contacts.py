import csv
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.contact import Contact
from app.models.daily_call import DailyCall
from app.models.company import Company
from app.schemas.contact import (
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    ContactListResponse,
)
from app.utils.activity_logger import log_activity


router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_data: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a contact for the current user.
    """
    if contact_data.company_id is not None:
        company = db.query(Company).filter(Company.id == contact_data.company_id).first()
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    contact = Contact(
        user_id=current_user.id,
        first_name=contact_data.first_name,
        last_name=contact_data.last_name,
        phone=contact_data.phone,
        email=contact_data.email,
        company_name=contact_data.company_name,
        company_id=contact_data.company_id,
        notes=contact_data.notes,
    )

    db.add(contact)
    db.commit()
    db.refresh(contact)

    # Activity Log
    log_activity(
        db=db,
        entity_type="Contact",
        entity_id=str(contact.id),
        action_type="CREATE",
        performed_by_user_id=str(current_user.id),
        old_value=None,
        new_value={
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "phone": contact.phone,
            "email": contact.email,
            "company_name": contact.company_name,
            "company_id": str(contact.company_id) if contact.company_id else None,
            "notes": contact.notes,
        },
    )
    db.commit()

    return contact


@router.get("", response_model=ContactListResponse)
def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by first/last name or phone"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List current user's contacts only (paginated + optional search).
    """
    query = db.query(Contact).filter(Contact.user_id == current_user.id)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Contact.first_name.ilike(like),
                Contact.last_name.ilike(like),
                Contact.phone.ilike(like),
            )
        )

    total = query.count()
    contacts = (
        query.order_by(Contact.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ContactListResponse(contacts=contacts, total=total, page=page, page_size=page_size)


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a single contact; enforce strict ownership.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.user_id == current_user.id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this contact")
    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: str,
    contact_data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Edit a contact owned by the current user.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.user_id == current_user.id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this contact")

    old_snapshot = {
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "phone": contact.phone,
        "email": contact.email,
        "company_name": contact.company_name,
        "company_id": str(contact.company_id) if contact.company_id else None,
        "notes": contact.notes,
    }

    if contact_data.company_id is not None:
        # If explicitly setting company_id, validate it exists.
        company = db.query(Company).filter(Company.id == contact_data.company_id).first()
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if contact_data.first_name is not None:
        contact.first_name = contact_data.first_name
    if contact_data.last_name is not None:
        contact.last_name = contact_data.last_name
    if contact_data.phone is not None:
        contact.phone = contact_data.phone
    if contact_data.email is not None:
        contact.email = contact_data.email
    if contact_data.company_name is not None:
        contact.company_name = contact_data.company_name
    if contact_data.company_id is not None:
        contact.company_id = contact_data.company_id
    if contact_data.notes is not None:
        contact.notes = contact_data.notes

    db.commit()
    db.refresh(contact)

    new_snapshot = {
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "phone": contact.phone,
        "email": contact.email,
        "company_name": contact.company_name,
        "company_id": str(contact.company_id) if contact.company_id else None,
        "notes": contact.notes,
    }

    log_activity(
        db=db,
        entity_type="Contact",
        entity_id=str(contact.id),
        action_type="UPDATE",
        performed_by_user_id=str(current_user.id),
        old_value=old_snapshot,
        new_value=new_snapshot,
    )
    db.commit()

    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_200_OK)
def delete_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a contact. Blocked if it is referenced by any DailyCall of the current user.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.user_id == current_user.id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this contact")

    referenced = (
        db.query(DailyCall.id)
        .filter(
            DailyCall.contact_id == contact.id,
            DailyCall.user_id == current_user.id,
        )
        .first()
    )
    if referenced:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete contact: it is referenced by daily calls",
        )

    snapshot = {
        "id": str(contact.id),
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "phone": contact.phone,
    }

    db.delete(contact)
    db.commit()

    log_activity(
        db=db,
        entity_type="Contact",
        entity_id=str(contact.id),
        action_type="DELETE",
        performed_by_user_id=str(current_user.id),
        old_value=snapshot,
        new_value=None,
    )
    db.commit()

    return {"message": "Contact deleted successfully"}


@router.post("/import-csv", status_code=status.HTTP_201_CREATED)
async def import_contacts_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import contacts from a CSV upload for the current user only.
    - Try UTF-8 first, fallback to Windows-1253 (Greek encoding).
    - Expected columns: first_name, last_name, phone, email(optional), company_name(optional)
    """
    raw = await file.read()

    encoding_used = "utf-8"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        encoding_used = "windows-1253"
        text = raw.decode("windows-1253")

    reader = csv.DictReader(StringIO(text))

    imported = 0
    skipped = 0
    contacts: list[Contact] = []

    for row in reader:
        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()
        phone = (row.get("phone") or "").strip()
        email = (row.get("email") or "").strip() or None
        company_name = (row.get("company_name") or "").strip() or None

        if not first_name or not last_name or not phone:
            skipped += 1
            continue

        contacts.append(
            Contact(
                user_id=current_user.id,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                company_name=company_name,
                company_id=None,  # CSV imports company_name only (free text)
                notes=None,
            )
        )
        imported += 1

    if contacts:
        db.add_all(contacts)

    db.commit()

    resp = {"imported": imported, "skipped": skipped}
    if encoding_used != "utf-8":
        resp["warning"] = "Non-UTF8 encoding detected; CSV was decoded using Windows-1253."

    return resp

