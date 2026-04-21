from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class PresenceUserResponse(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    user_type: str
    is_online: bool
    last_seen_at: Optional[datetime] = None


class PresenceListResponse(BaseModel):
    users: List[PresenceUserResponse]

