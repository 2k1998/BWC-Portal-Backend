from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID


ALLOWED_PROJECT_TYPES = [
    "Renovation",
    "Expansion",
    "New Store",
    "Maintenance",
    "Other"
]

ALLOWED_PROJECT_STATUSES = [
    "Planning",
    "In Progress",
    "Completed",
    "On Hold",
    "Canceled"
]


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""
    name: str = Field(..., min_length=1)
    project_type: str
    company_id: UUID
    priority: str = Field(..., min_length=1)
    description: Optional[str] = None
    budget_amount: Optional[Decimal] = None
    project_manager_user_id: UUID
    location_address: Optional[str] = None
    location_postcode: Optional[str] = None
    start_date: date
    expected_completion_date: date
    
    @field_validator('project_type')
    @classmethod
    def validate_project_type(cls, v):
        """Validate project type is allowed."""
        if v not in ALLOWED_PROJECT_TYPES:
            raise ValueError(f"project_type must be one of: {', '.join(ALLOWED_PROJECT_TYPES)}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Downtown Store Renovation",
                "project_type": "Renovation",
                "company_id": "123e4567-e89b-12d3-a456-426614174000",
                "priority": "High",
                "description": "Complete renovation of downtown location",
                "budget_amount": 150000.00,
                "project_manager_user_id": "123e4567-e89b-12d3-a456-426614174001",
                "location_address": "123 Main St",
                "location_postcode": "12345",
                "start_date": "2026-03-01",
                "expected_completion_date": "2026-06-30"
            }
        }


class ProjectUpdate(BaseModel):
    """Schema for updating a project (owner only for metadata)."""
    name: Optional[str] = Field(None, min_length=1)
    project_type: Optional[str] = None
    company_id: Optional[UUID] = None
    priority: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    budget_amount: Optional[Decimal] = None
    project_manager_user_id: Optional[UUID] = None
    location_address: Optional[str] = None
    location_postcode: Optional[str] = None
    start_date: Optional[date] = None
    expected_completion_date: Optional[date] = None
    
    @field_validator('project_type')
    @classmethod
    def validate_project_type(cls, v):
        """Validate project type is allowed."""
        if v is not None and v not in ALLOWED_PROJECT_TYPES:
            raise ValueError(f"project_type must be one of: {', '.join(ALLOWED_PROJECT_TYPES)}")
        return v


class ProjectStatusUpdate(BaseModel):
    """Schema for updating project status (owner/manager/admin)."""
    status: str
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate status is allowed."""
        if v not in ALLOWED_PROJECT_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(ALLOWED_PROJECT_STATUSES)}")
        return v


class ProjectResponse(BaseModel):
    """Schema for project response."""
    id: UUID
    name: str
    project_type: str
    company_id: UUID
    priority: str
    description: Optional[str]
    budget_amount: Optional[Decimal]
    project_manager_user_id: UUID
    location_address: Optional[str]
    location_postcode: Optional[str]
    start_date: date
    expected_completion_date: date
    status: str
    owner_user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Schema for paginated project list."""
    projects: List[ProjectResponse]
    total: int
    page: int
    page_size: int
