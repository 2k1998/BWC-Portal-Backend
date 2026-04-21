from pydantic import BaseModel
from typing import List
from datetime import datetime
from uuid import UUID


class DocumentResponse(BaseModel):
    """Schema for document response."""
    id: UUID
    filename: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    storage_path: str
    uploaded_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
