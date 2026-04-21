from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class ActivityLogResponse(BaseModel):
    """
    Schema for activity log response.
    """
    id: UUID
    entity_type: str
    entity_id: UUID
    action_type: str
    performed_by_user_id: UUID
    perform_by_user_name: Optional[str] = None # Computed field
    old_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True

class ActivityLogListResponse(BaseModel):
    """
    Schema for paginated activity log list.
    """
    logs: list[ActivityLogResponse]
    total: int
    page: int
    page_size: int
