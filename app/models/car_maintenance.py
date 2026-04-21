from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Column, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class CarMaintenance(Base):
    __tablename__ = "car_maintenance"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    last_service_date = Column(Date, nullable=True)
    next_service_date = Column(Date, nullable=True)
    last_kteo_date = Column(Date, nullable=True)
    next_kteo_date = Column(Date, nullable=True)
    last_tyre_change_date = Column(Date, nullable=True)
    updated_at = Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))
