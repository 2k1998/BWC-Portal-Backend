from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field
from uuid import UUID


CarStatus = Literal["available", "rented", "sold"]
CarIncomeType = Literal["rental", "sale"]


class CarCreate(BaseModel):
    make: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    license_plate: str = Field(..., min_length=1)
    year: int
    purchase_date: Optional[date] = None
    purchase_price: Optional[Decimal] = Field(None, gt=0)
    status: CarStatus = "available"
    notes: Optional[str] = None


class CarUpdate(BaseModel):
    make: Optional[str] = Field(None, min_length=1)
    model: Optional[str] = Field(None, min_length=1)
    license_plate: Optional[str] = Field(None, min_length=1)
    year: Optional[int] = None
    purchase_date: Optional[date] = None
    purchase_price: Optional[Decimal] = Field(None, gt=0)
    status: Optional[CarStatus] = None
    notes: Optional[str] = None


class CarResponse(BaseModel):
    id: UUID
    make: str
    model: str
    license_plate: str
    year: int
    purchase_date: Optional[date]
    purchase_price: Optional[Decimal]
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CarMaintenanceUpsert(BaseModel):
    last_service_date: Optional[date] = None
    next_service_date: Optional[date] = None
    last_kteo_date: Optional[date] = None
    next_kteo_date: Optional[date] = None
    last_tyre_change_date: Optional[date] = None


class CarMaintenanceResponse(BaseModel):
    id: UUID
    car_id: UUID
    last_service_date: Optional[date]
    next_service_date: Optional[date]
    last_kteo_date: Optional[date]
    next_kteo_date: Optional[date]
    last_tyre_change_date: Optional[date]
    updated_at: datetime

    class Config:
        from_attributes = True


class CarDetailResponse(CarResponse):
    maintenance: Optional[CarMaintenanceResponse] = None


class CarListResponse(BaseModel):
    cars: List[CarResponse]
    total: int
    page: int
    page_size: int


class CarIncomeCreate(BaseModel):
    customer_name: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    income_type: CarIncomeType
    transaction_date: date
    description: Optional[str] = None


class CarIncomeResponse(BaseModel):
    id: UUID
    car_id: UUID
    customer_name: str
    amount: Decimal
    income_type: str
    transaction_date: date
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CarExpenseCreate(BaseModel):
    expense_type: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    transaction_date: date
    description: Optional[str] = None


class CarExpenseResponse(BaseModel):
    id: UUID
    car_id: UUID
    expense_type: str
    amount: Decimal
    transaction_date: date
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CarFinancialsResponse(BaseModel):
    incomes: List[CarIncomeResponse]
    expenses: List[CarExpenseResponse]
    total_income: Decimal
    total_expenses: Decimal
    profit: Decimal
