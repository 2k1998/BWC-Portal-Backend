from sqlalchemy import Column, String, ForeignKey, UUID, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid

from app.core.database import BaseModel


class UserPagePermission(BaseModel):
    """User page permission model."""
    __tablename__ = "user_page_permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="RESTRICT"), nullable=False, index=True)
    access = Column(String, nullable=False)  # 'none', 'read', 'full' - validated at application level
    
    # Unique constraint on user_id + page_id
    __table_args__ = (
        UniqueConstraint('user_id', 'page_id', name='uq_user_page'),
    )
    
    # Relationships
    user = relationship("User", back_populates="page_permissions")
    page = relationship("Page")
