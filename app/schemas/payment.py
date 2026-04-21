from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator
from uuid import UUID


ALLOWED_PAYMENT_TYPES = ["salary", "commission", "bonus", "rent", "bill", "purchase", "service"]
PaymentType = Literal[
    "salary",
    "commission",
    "bonus",
    "rent",
    "bill",
    "purchase",
    "service",
]


class PaymentCreate(BaseModel):
    """Schema for creating a payment (admin or permitted creator)."""

    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    amount: Decimal = Field(..., gt=0)
    currency: str = Field("EUR", min_length=1)
    payment_type: PaymentType
    payment_category: Optional[str] = None
    payment_date: date
    is_income: bool = False
    employee_user_id: Optional[UUID] = None
    company_id: UUID

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v: str) -> str:
        # Keep validation lightweight; PRD doesn't specify strict currency rules.
        if not v or not v.strip():
            raise ValueError("currency must be a non-empty string")
        return v.strip()


class PaymentUpdate(BaseModel):
    """Schema for updating a payment (creator or Admin only in the API)."""

    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=1)
    payment_type: Optional[PaymentType] = None
    payment_category: Optional[str] = None
    payment_date: Optional[date] = None
    is_income: Optional[bool] = None
    employee_user_id: Optional[UUID] = None
    company_id: Optional[UUID] = None

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not v.strip():
            raise ValueError("currency must be a non-empty string")
        return v.strip()


class PaymentResponse(BaseModel):
    """Schema for returning a payment."""

    id: UUID
    title: str
    description: Optional[str]
    amount: Decimal
    currency: str
    payment_type: str
    payment_category: Optional[str]
    payment_date: date
    is_income: bool
    employee_user_id: Optional[UUID]
    company_id: UUID
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    """Schema for paginated payment list."""

    payments: List[PaymentResponse]
    total: int
    page: int
    page_size: int


class PaymentSummaryResponse(BaseModel):
    """Aggregated totals for the current payment filters."""

    total_income: Decimal
    total_expenses: Decimal
    net_balance: Decimal

