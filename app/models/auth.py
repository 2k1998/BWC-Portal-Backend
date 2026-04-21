from sqlalchemy import Column, String, ForeignKey, UUID, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta
import uuid

from app.core.database import Base
from app.core.config import settings


class AuthRefreshToken(Base):
    """Refresh token model for JWT authentication."""
    __tablename__ = "auth_refresh_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
