from sqlalchemy import Column, String, UUID, DateTime
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Department(Base):
    """Department model for admin panel management."""
    __tablename__ = "departments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
