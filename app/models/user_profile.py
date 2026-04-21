from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, Date, Text, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )

    bio = Column(Text, nullable=True)
    birthday = Column(Date, nullable=True)
    profile_photo_url = Column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="en")

    updated_at = Column(
        DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
    )

