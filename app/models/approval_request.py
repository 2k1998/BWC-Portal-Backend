from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


REQUEST_TYPE_VALUES = ("General", "Expenses", "Task", "Project", "Purchase")
APPROVAL_STATUS_VALUES = ("pending", "approved", "denied")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )

    requester_user_id = Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    receiver_user_id = Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    request_type = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    status = Column(
        Text,
        server_default=sa.text("'pending'"),
        nullable=False,
    )

    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            f"request_type IN ({', '.join([repr(v) for v in REQUEST_TYPE_VALUES])})",
            name="ck_approval_request_type_valid",
        ),
        CheckConstraint(
            f"status IN ({', '.join([repr(v) for v in APPROVAL_STATUS_VALUES])})",
            name="ck_approval_request_status_valid",
        ),
    )

