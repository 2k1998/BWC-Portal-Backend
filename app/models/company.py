import sqlalchemy as sa
from sqlalchemy import Column, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import BaseModel


class Company(BaseModel):
    """Company model - single source of truth for BWC group companies."""
    __tablename__ = "companies"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name = Column(Text, unique=True, nullable=False, index=True)
    vat_number = Column(Text, nullable=True)
    occupation = Column(Text, nullable=True)
    creation_date = Column(Date, nullable=True)  # Company's actual creation date (immutable)
    description = Column(Text, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # created_at and updated_at inherited from BaseModel
