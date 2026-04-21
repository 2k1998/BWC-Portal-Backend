from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, Date, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import BaseModel


CAR_STATUS_VALUES = ("available", "rented", "sold")


class Car(BaseModel):
    __tablename__ = "cars"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    make = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    license_plate = Column(Text, nullable=False, unique=True)
    year = Column(Integer, nullable=False)
    purchase_date = Column(Date, nullable=True)
    purchase_price = Column(Numeric(12, 2), nullable=True)
    status = Column(Text, nullable=False, server_default=sa.text("'available'"))
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join([repr(v) for v in CAR_STATUS_VALUES])})",
            name="check_car_status",
        ),
    )
