from sqlalchemy import Column, String, UUID, ForeignKey, UniqueConstraint, Index
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class TeamMember(Base):
    """Team member junction table - associates users with teams."""
    __tablename__ = "team_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='RESTRICT'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    role = Column(String, nullable=False)  # 'head' or 'member'
    
    # Unique constraint: user can only be in a team once
    __table_args__ = (
        UniqueConstraint('team_id', 'user_id', name='uq_team_user'),
        Index('ix_team_members_team_id', 'team_id'),
        Index('ix_team_members_user_id', 'user_id'),
    )
