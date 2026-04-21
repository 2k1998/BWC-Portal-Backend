from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Column, Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class CarExpense(Base):
    __tablename__ = "car_expenses"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="RESTRICT"),
        nullable=False,
    )
    expense_type = Column(Text, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    transaction_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))
