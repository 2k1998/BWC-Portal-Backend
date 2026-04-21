from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


CAR_INCOME_TYPE_VALUES = ("rental", "sale")


class CarIncome(Base):
    __tablename__ = "car_incomes"

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
    customer_name = Column(Text, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    income_type = Column(Text, nullable=False)
    transaction_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            f"income_type IN ({', '.join([repr(v) for v in CAR_INCOME_TYPE_VALUES])})",
            name="check_car_income_type",
        ),
    )
