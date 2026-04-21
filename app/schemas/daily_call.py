from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class DailyCallCreate(BaseModel):
    contact_id: UUID
    next_call_at: datetime


class DailyCallUpdate(BaseModel):
    next_call_at: Optional[datetime] = None
    # Optional text note stored as a file (document) with 7-day retention.
    call_note: Optional[str] = None


class DailyCallResponse(BaseModel):
    id: UUID
    contact_id: UUID
    user_id: UUID
    next_call_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DailyCallListResponse(BaseModel):
    daily_calls: List[DailyCallResponse]
    total: int
    page: int
    page_size: int


class CallNoteFileOut(BaseModel):
    """
    Call notes are stored as short-lived Document files linked through call_notes_files.

    Phase 12 contract:
    - Expiry is driven by `call_notes_files.expires_at`
    - The link uses `call_notes_files.file_id` (points to `documents.id`)
    """

    id: UUID  # call_notes_files.id
    file_id: UUID  # documents.id
    # Alias used by the frontend for backward compatibility.
    # In Phase 12, `document_id` is effectively the same value as `file_id`.
    document_id: UUID
    expires_at: datetime  # call_notes_files.expires_at
    original_filename: str  # documents.original_filename
    filename: str  # documents.filename


class CallNotesListResponse(BaseModel):
    files: List[CallNoteFileOut]
