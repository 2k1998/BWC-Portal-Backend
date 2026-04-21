from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class CallNotesFile(Base):
    """Temporary call note file reference — expires after 7 days."""
    __tablename__ = "call_notes_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    daily_call_id = Column(UUID(as_uuid=True), ForeignKey('daily_calls.id', ondelete='RESTRICT'), nullable=False)
    # Per Phase 12 contract: this links to the existing file storage table.
    # This codebase currently stores files in the `documents` table, so the FK targets `documents.id`.
    file_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='RESTRICT'), nullable=False)
    # Backward-compat for partially migrated DBs:
    # older schema used `document_id` (NOT NULL). We populate it whenever possible.
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='RESTRICT'), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
