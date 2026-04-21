from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ContactCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    company_name: Optional[str] = None
    company_id: Optional[UUID] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    company_id: Optional[UUID] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    phone: str
    email: Optional[str]
    company_name: Optional[str]
    company_id: Optional[UUID]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    contacts: List[ContactResponse]
    total: int
    page: int
    page_size: int
