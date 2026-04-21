from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field
from uuid import UUID


class CompanyCreate(BaseModel):
    """Schema for creating a new company (admin only)."""
    name: str = Field(..., min_length=1)
    vat_number: Optional[str] = None
    occupation: Optional[str] = None
    creation_date: Optional[date] = None
    description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "BWC Digital Ltd",
                "vat_number": "123456789",
                "occupation": "Digital Services",
                "creation_date": "2020-01-15",
                "description": "Digital marketing and web development"
            }
        }


class CompanyUpdate(BaseModel):
    """Schema for updating a company (admin only). Creation date is immutable."""
    name: Optional[str] = Field(None, min_length=1)
    vat_number: Optional[str] = None
    occupation: Optional[str] = None
    description: Optional[str] = None
    # creation_date is NOT included - it's immutable per PRD


class CompanyResponse(BaseModel):
    """Schema for company response."""
    id: UUID
    name: str
    vat_number: Optional[str]
    occupation: Optional[str]
    creation_date: Optional[date]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    """Schema for paginated company list."""
    companies: list[CompanyResponse]
    total: int
    page: int
    page_size: int
