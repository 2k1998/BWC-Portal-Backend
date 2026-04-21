from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from enum import Enum

class NotificationType(str, Enum):
    ASSIGNMENT = "ASSIGNMENT"
    STATUS_CHANGE = "STATUS_CHANGE"
    COMMENT = "COMMENT"
    # Future/Reserved
    # MENTION = "MENTION" 
    # DEADLINE = "DEADLINE"

class ReadStatus(str, Enum):
    Unread = "Unread"
    Read = "Read"

class NotificationResponse(BaseModel):
    id: UUID
    recipient_user_id: UUID
    actor_user_id: Optional[UUID]
    entity_type: str
    entity_id: UUID
    title: str
    message: str
    link: str
    read_status: ReadStatus
    notification_type: NotificationType
    created_at: datetime
    
    class Config:
        from_attributes = True

class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    total: int
    page: int
    page_size: int

class UnreadCountResponse(BaseModel):
    unread_count: int
