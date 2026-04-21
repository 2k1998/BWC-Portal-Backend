from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaskCommentCreate(BaseModel):
    body: str = Field(..., min_length=1)


class TaskCommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    user_id: UUID
    user_full_name: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True
