from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date, datetime
from uuid import UUID


class ProfileUpdateRequest(BaseModel):
    bio: Optional[str] = None
    birthday: Optional[date] = None
    profile_photo_url: Optional[str] = None
    language: Optional[str] = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"en", "el"}:
            raise ValueError("language must be 'en' or 'el'")
        return normalized


class ProfileResponse(BaseModel):
    # User identity (read-only)
    id: UUID
    email: str
    username: str
    first_name: str
    last_name: str
    user_type: str
    is_active: bool
    manager_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    # Profile fields (editable/readable)
    bio: Optional[str] = None
    birthday: Optional[date] = None
    profile_photo_url: Optional[str] = None
    language: str
    profile_updated_at: datetime

    class Config:
        from_attributes = True

