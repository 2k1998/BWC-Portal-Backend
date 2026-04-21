from sqlalchemy import Column, String, UUID, Date, DateTime, Text, ForeignKey, Numeric
from datetime import datetime, timezone
import uuid

from app.core.database import BaseModel


class Project(BaseModel):
    """Project model - core project management system."""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    project_type = Column(Text, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)
    priority = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    budget_amount = Column(Numeric, nullable=True)
    project_manager_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    location_address = Column(Text, nullable=True)
    location_postcode = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    expected_completion_date = Column(Date, nullable=False)
    status = Column(Text, nullable=False, default="Planning")
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
