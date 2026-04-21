from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class EventCreate(BaseModel):
    """Schema for creating a new event."""
    title: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    event_datetime: datetime
    description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Company Annual Meeting",
                "location": "Main Office Conference Room",
                "event_datetime": "2026-03-15T14:00:00Z",
                "description": "Annual company-wide meeting to discuss Q1 results"
            }
        }


class EventUpdate(BaseModel):
    """Schema for updating an event (creator/admin only)."""
    title: Optional[str] = Field(None, min_length=1)
    location: Optional[str] = Field(None, min_length=1)
    event_datetime: Optional[datetime] = None
    description: Optional[str] = None


class EventResponse(BaseModel):
    """Schema for event response."""
    id: UUID
    title: str
    location: str
    event_datetime: datetime
    description: Optional[str]
    owner_user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Schema for paginated event list."""
    events: List[EventResponse]
    total: int
    page: int
    page_size: int
