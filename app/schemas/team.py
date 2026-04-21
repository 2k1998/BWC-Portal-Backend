from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# Allowed team member roles
ALLOWED_ROLES = ["head", "member"]


class TeamMemberItem(BaseModel):
    """Schema for team member in requests."""
    user_id: UUID
    role: str = Field(..., description="Must be 'head' or 'member'")


class TeamCreate(BaseModel):
    """Schema for creating a new team (admin only)."""
    name: str = Field(..., min_length=1, max_length=255)
    head_user_id: UUID
    member_ids: List[UUID] = Field(default_factory=list, description="List of user IDs to add as members")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sales Team Alpha",
                "head_user_id": "123e4567-e89b-12d3-a456-426614174000",
                "member_ids": ["123e4567-e89b-12d3-a456-426614174001", "123e4567-e89b-12d3-a456-426614174002"]
            }
        }


class TeamUpdate(BaseModel):
    """Schema for updating a team (admin or head only)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    head_user_id: Optional[UUID] = None


class TeamMemberResponse(BaseModel):
    """Schema for team member response."""
    user_id: UUID
    role: str
    
    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    """Schema for team response."""
    id: UUID
    name: str
    head_user_id: UUID
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    members: List[TeamMemberResponse] = []
    
    class Config:
        from_attributes = True


class TeamListResponse(BaseModel):
    """Schema for paginated team list."""
    teams: list[TeamResponse]
    total: int
    page: int
    page_size: int


class AddMembersRequest(BaseModel):
    """Schema for adding members to a team."""
    user_ids: List[UUID] = Field(..., min_items=1, description="List of user IDs to add as members")
