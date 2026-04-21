from sqlalchemy import Column, String, ForeignKey, UUID, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class UserAuditLog(Base):
    """Audit log for user management actions."""
    __tablename__ = "user_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    action = Column(String, nullable=False)
    before_json = Column(JSON, nullable=True)
    after_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    admin_user = relationship("User", foreign_keys=[admin_user_id], back_populates="audit_logs_as_admin")
    target_user = relationship("User", foreign_keys=[target_user_id], back_populates="audit_logs_as_target")
