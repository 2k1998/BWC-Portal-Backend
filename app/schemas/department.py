from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class DepartmentCreate(BaseModel):
    """Schema for creating a new department (admin only)."""
    name: str = Field(..., min_length=1, max_length=255)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sales"
            }
        }


class DepartmentUpdate(BaseModel):
    """Schema for updating a department (admin only)."""
    name: str = Field(..., min_length=1, max_length=255)


class DepartmentResponse(BaseModel):
    """Schema for department response."""
    id: UUID
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DepartmentListResponse(BaseModel):
    """Schema for paginated department list."""
    departments: list[DepartmentResponse]
    total: int
    page: int
    page_size: int
