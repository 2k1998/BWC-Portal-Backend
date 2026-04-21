from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, date
from uuid import UUID


ALLOWED_APPROVAL_TYPES = ["General", "Expenses", "Task", "Project", "Purchase"]
ALLOWED_APPROVAL_STATUSES = ["pending", "approved", "denied"]


class ApprovalCreateRequest(BaseModel):
    receiver_user_id: UUID
    request_type: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: Optional[str] = None

    @field_validator("request_type")
    @classmethod
    def validate_request_type(cls, v: str) -> str:
        if v not in ALLOWED_APPROVAL_TYPES:
            raise ValueError(f"request_type must be one of: {', '.join(ALLOWED_APPROVAL_TYPES)}")
        return v


class ApprovalResponse(BaseModel):
    id: UUID
    requester_user_id: UUID
    receiver_user_id: UUID
    request_type: str
    title: str
    description: Optional[str] = None
    status: str
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApprovalListResponse(BaseModel):
    sent_approvals: list[ApprovalResponse]
    received_approvals: list[ApprovalResponse]


class ApprovalDetailResponse(BaseModel):
    approval: ApprovalResponse

