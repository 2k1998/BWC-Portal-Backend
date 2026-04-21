from sqlalchemy import Column, String, UUID, Date, DateTime, Text, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import validates, relationship
from datetime import datetime, timezone, date
import uuid

from app.core.database import BaseModel


class Task(BaseModel):
    """Task model - core execution engine with strict assignment and visibility rules."""
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)
    department = Column(Text, nullable=False)  # TEXT field, validated against departments
    priority = Column(Text, nullable=False)
    urgency_label = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    deadline = Column(Date, nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=True)
    assigned_team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id', ondelete='RESTRICT'), nullable=True)
    status = Column(Text, nullable=False, default="New")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    comments = relationship("TaskComment", back_populates="task")
    
    # created_at and updated_at inherited from BaseModel
    
    # Check constraint: exactly one of assigned_user_id OR assigned_team_id must be set
    __table_args__ = (
        CheckConstraint(
            '(assigned_user_id IS NOT NULL AND assigned_team_id IS NULL) OR '
            '(assigned_user_id IS NULL AND assigned_team_id IS NOT NULL)',
            name='check_single_assignment'
        ),
        Index("ix_tasks_company_id", "company_id"),
        Index("ix_tasks_deadline", "deadline"),
    )
