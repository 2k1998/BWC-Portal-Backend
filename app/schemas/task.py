from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


# Allowed values
ALLOWED_STATUSES = ["New", "Received", "On Process", "Pending", "Completed", "Loose End"]
ALLOWED_URGENCY_LABELS = [
    "Urgent & Important",
    "Urgent",
    "Important",
    "Not Urgent & Not Important",
    "Orange"  # System-assigned only
]
USER_SELECTABLE_URGENCY_LABELS = [
    "Urgent & Important",
    "Urgent",
    "Important",
    "Not Urgent & Not Important"
]


class TaskCreate(BaseModel):
    """Schema for creating a new task."""
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    company_id: UUID
    department: str = Field(..., min_length=1)
    priority: str = Field(..., min_length=1)
    urgency_label: Optional[str] = None  # Optional, can be auto-set to Orange
    start_date: date
    deadline: date
    assigned_user_id: Optional[UUID] = None
    assigned_team_id: Optional[UUID] = None
    
    @field_validator('urgency_label')
    @classmethod
    def validate_urgency_label(cls, v):
        """Validate urgency label is user-selectable."""
        if v is not None and v not in USER_SELECTABLE_URGENCY_LABELS:
            raise ValueError(f"urgency_label must be one of: {', '.join(USER_SELECTABLE_URGENCY_LABELS)}")
        return v
    
    @model_validator(mode='after')
    def validate_assignment(self):
        """Validate exactly one of assigned_user_id or assigned_team_id is set."""
        user_assigned = self.assigned_user_id is not None
        team_assigned = self.assigned_team_id is not None
        
        if not user_assigned and not team_assigned:
            raise ValueError("Either assigned_user_id or assigned_team_id must be provided")
        
        if user_assigned and team_assigned:
            raise ValueError("Cannot assign to both user and team. Please assign to one or the other.")
        
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Review Q4 financials",
                "description": "Complete review of Q4 financial statements",
                "company_id": "123e4567-e89b-12d3-a456-426614174000",
                "department": "Finance",
                "priority": "High",
                "urgency_label": "Urgent & Important",
                "start_date": "2026-02-10",
                "deadline": "2026-02-15",
                "assigned_user_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class TaskUpdate(BaseModel):
    """Schema for updating a task (owner only for metadata)."""
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    company_id: Optional[UUID] = None
    department: Optional[str] = Field(None, min_length=1)
    priority: Optional[str] = Field(None, min_length=1)
    urgency_label: Optional[str] = None
    start_date: Optional[date] = None
    deadline: Optional[date] = None
    assigned_user_id: Optional[UUID] = None
    assigned_team_id: Optional[UUID] = None
    
    @field_validator('urgency_label')
    @classmethod
    def validate_urgency_label(cls, v):
        """Validate urgency label is user-selectable."""
        if v is not None and v not in USER_SELECTABLE_URGENCY_LABELS:
            raise ValueError(f"urgency_label must be one of: {', '.join(USER_SELECTABLE_URGENCY_LABELS)}")
        return v


class TaskStatusUpdate(BaseModel):
    """Schema for updating task status (assigned user/team head only)."""
    status: str
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate status is allowed."""
        if v not in ALLOWED_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(ALLOWED_STATUSES)}")
        return v


class TaskTransfer(BaseModel):
    """Schema for transferring a task."""
    new_assigned_user_id: UUID
    transfer_ownership: bool = False  # If True, also change owner


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: UUID
    title: str
    description: Optional[str]
    company_id: UUID
    department: str
    priority: str
    urgency_label: str
    start_date: date
    deadline: date
    owner_user_id: UUID
    assigned_user_id: Optional[UUID]
    assigned_team_id: Optional[UUID]
    status: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Schema for paginated task list."""
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskDocumentAttachmentItem(BaseModel):
    """One row returned by GET /tasks/{id}/documents (junction + document + uploader display name)."""

    id: UUID
    document_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    uploaded_by: str
    created_at: datetime
