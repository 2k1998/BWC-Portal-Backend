from sqlalchemy import Column, String, UUID, DateTime, Text, ForeignKey
from datetime import datetime, timezone
import uuid

from app.core.database import BaseModel


class Event(BaseModel):
    """Event model - core event management system with public visibility."""
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    location = Column(Text, nullable=False)
    event_datetime = Column(DateTime(timezone=True), nullable=False)
    event_start_at = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
