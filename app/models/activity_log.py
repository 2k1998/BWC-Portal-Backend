from sqlalchemy import Column, String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import BaseModel

class ActivityLog(BaseModel):
    """
    Immutable log of system activity for auditing purposes.
    Tracks creation, updates, and deletion of key entities.
    """
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String, nullable=False, index=True)  # Task, Project, Event, Document, User
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    action_type = Column(String, nullable=False)  # CREATE, UPDATE, DELETE, STATUS_CHANGE, TRANSFER
    
    # Who performed the action (RESTRICT delete to preserve history)
    performed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # State snapshots (REDACTED secrets)
    # Using JSONB for Postgres performance
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False, index=True)

    # Relationship to user
    performed_by = relationship("User", foreign_keys=[performed_by_user_id])
