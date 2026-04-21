from sqlalchemy import Column, String, UUID, DateTime, Text, ForeignKey, BigInteger
from datetime import datetime, timezone
import uuid

from app.core.database import BaseModel


class Document(BaseModel):
    """Document model - file storage with public visibility."""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(Text, nullable=False)
    original_filename = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(Text, nullable=False)
    storage_path = Column(Text, nullable=False)
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
