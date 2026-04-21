from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )

    thread_id = Column(
        UUID(as_uuid=True),
        sa.ForeignKey("chat_threads.id", ondelete="RESTRICT"),
        nullable=False,
    )

    sender_user_id = Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    message_text = Column(Text, nullable=True)

    # Optional file attachment. PRD says `files(id)`, this repo maps it to `documents(id)`.
    file_id = Column(
        UUID(as_uuid=True),
        sa.ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=True,
    )

    is_read = Column(
        Boolean,
        server_default=sa.text("FALSE"),
        nullable=False,
    )
    message_type = Column(
        String,
        server_default=sa.text("'text'"),
        nullable=False,
    )
    approval_status = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
    )

