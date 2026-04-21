from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, Column, Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import BaseModel


PAYMENT_TYPE_VALUES = ("salary", "commission", "bonus", "rent", "bill", "purchase", "service")


class Payment(BaseModel):
    """Payment model for operational financial tracking."""

    __tablename__ = "payments"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(Text, nullable=False, server_default=sa.text("'EUR'"))
    payment_type = Column(Text, nullable=False)
    payment_category = Column(Text, nullable=True)
    payment_date = Column(Date, nullable=False)
    is_income = Column(Boolean, nullable=False, server_default=sa.text("false"))

    employee_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            f"payment_type IN ({', '.join([repr(v) for v in PAYMENT_TYPE_VALUES])})",
            name="check_payment_type",
        ),
    )

