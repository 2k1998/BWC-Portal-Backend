from sqlalchemy import Column, String, UUID, DateTime
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Page(Base):
    """Page model for permission management."""
    __tablename__ = "pages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String, unique=True, nullable=False)  # Corrected from 'name' per user feedback
    key = Column(String, unique=True, nullable=False, index=True)  # Corrected from 'slug' per user feedback
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
