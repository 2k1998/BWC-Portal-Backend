from sqlalchemy import Column, String, ForeignKey, DateTime, Index, Boolean, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.core.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 1. Foreign Keys with RESTRICT
    recipient_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    
    # 2. Entity Links (Loose coupling, RESTRICT logic handled by logic/service)
    # entity_id is just a UUID column, NOT a ForeignKey, to ensure persistence even if Entity is force-deleted.
    entity_type = Column(String, nullable=False) 
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    link = Column(String, nullable=False)
    
    # 3. Text Enum replacements
    # Allowed: "Unread" | "Read"
    read_status = Column(String, default="Unread", nullable=False)
    
    # Allowed: "ASSIGNMENT" | "STATUS_CHANGE" | "COMMENT"
    notification_type = Column(String, nullable=False)
    
    # 4. UTC Timestamp
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)

    # Relationships
    recipient = relationship("User", foreign_keys=[recipient_user_id])
    actor = relationship("User", foreign_keys=[actor_user_id])

    # Indexes
    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('ASSIGNMENT', 'STATUS_CHANGE', 'COMMENT')",
            name="ck_notification_type_valid"
        ),
        CheckConstraint(
            "read_status IN ('Unread', 'Read')",
            name="ck_notification_read_status_valid"
        ),
        Index("ix_notifications_recipient_read", "recipient_user_id", "read_status"), # For Count Efficiency
        Index("ix_notifications_actor_user_id", "actor_user_id"),
        Index("ix_notifications_created_at", "created_at"),
    )
