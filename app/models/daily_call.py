from sqlalchemy import Column, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import BaseModel


class DailyCall(BaseModel):
    """DailyCall model — call scheduling per contact."""
    __tablename__ = "daily_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(UUID(as_uuid=True), ForeignKey('contacts.id', ondelete='RESTRICT'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    next_call_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index('ix_daily_calls_user_id', 'user_id'),
        Index('ix_daily_calls_contact_id', 'contact_id'),
        Index('ix_daily_calls_next_call_at', 'next_call_at'),
    )
