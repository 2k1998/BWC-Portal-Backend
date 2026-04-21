from sqlalchemy import Column, String, UUID, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import BaseModel


class Team(BaseModel):
    """Team model - groups of users for task assignment."""
    __tablename__ = "teams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False, index=True)
    head_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    
    # created_at and updated_at inherited from BaseModel
    __table_args__ = (
        Index("ix_teams_head_user_id", "head_user_id"),
        Index("ix_teams_created_by_user_id", "created_by_user_id"),
    )
