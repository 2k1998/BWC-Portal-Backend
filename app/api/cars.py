from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.car import Car
from app.models.car_expense import CarExpense
from app.models.car_income import CarIncome
from app.models.car_maintenance import CarMaintenance
from app.models.user import User
from app.schemas.car import (
    CarCreate,
    CarDetailResponse,
    CarExpenseCreate,
    CarExpenseResponse,
    CarFinancialsResponse,
    CarIncomeCreate,
    CarIncomeResponse,
    CarListResponse,
    CarMaintenanceResponse,
    CarMaintenanceUpsert,
    CarResponse,
    CarUpdate,
)
from app.utils.activity_logger import log_activity
from app.utils.permissions import check_user_permission

router = APIRouter(prefix="/cars", tags=["Cars"])


def _car_snapshot(car: Car) -> dict:
    return {
        "id": str(car.id),
        "make": car.make,
        "model": car.model,
        "license_plate": car.license_plate,
        "year": car.year,
        "purchase_date": car.purchase_date.isoformat() if car.purchase_date else None,
        "purchase_price": str(car.purchase_price) if car.purchase_price is not None else None,
        "status": car.status,
        "notes": car.notes,
    }


def _require_cars_permission(db: Session, current_user: User) -> str:
    permission = check_user_permission(db=db, user=current_user, page_key="cars")
    if permission == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access Cars")
    return permission


def _require_cars_full(db: Session, current_user: User) -> None:
    permission = _require_cars_permission(db=db, current_user=current_user)
    if permission != "full":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify Cars")


def _get_car_or_404(db: Session, car_id: UUID) -> Car:
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found")
    return car


@router.post("", response_model=CarResponse, status_code=status.HTTP_201_CREATED)
def create_car(
    payload: CarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cars_full(db=db, current_user=current_user)

    existing = db.query(Car).filter(Car.license_plate == payload.license_plate).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="License plate already exists")

    car = Car(
        make=payload.make,
        model=payload.model,
        license_plate=payload.license_plate,
        year=payload.year,
        purchase_date=payload.purchase_date,
        purchase_price=payload.purchase_price,
        status=payload.status,
        notes=payload.notes,
    )
    try:
        db.add(car)
        db.flush()
        db.refresh(car)
        log_activity(
            db=db,
            entity_type="Car",
            entity_id=str(car.id),
            action_type="create",
            performed_by_user_id=str(current_user.id),
            old_value=None,
            new_value=_car_snapshot(car),
        )
        db.commit()
        db.refresh(car)
        return car
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid car data")


@router.get("", response_model=CarListResponse)
def list_cars(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by car status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cars_permission(db=db, current_user=current_user)

    query = db.query(Car)
    if status_filter is not None:
        query = query.filter(Car.status == status_filter)
    total = query.count()
    cars = query.order_by(Car.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return CarListResponse(cars=cars, total=total, page=page, page_size=page_size)


@router.get("/{car_id}", response_model=CarDetailResponse)
def get_car(
    car_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cars_permission(db=db, current_user=current_user)
    car = _get_car_or_404(db, car_id)
    maintenance = db.query(CarMaintenance).filter(CarMaintenance.car_id == car_id).first()

    return CarDetailResponse(
        id=car.id,
        make=car.make,
        model=car.model,
        license_plate=car.license_plate,
        year=car.year,
        purchase_date=car.purchase_date,
        purchase_price=car.purchase_price,
        status=car.status,
        notes=car.notes,
        created_at=car.created_at,
        updated_at=car.updated_at,
        maintenance=CarMaintenanceResponse.model_validate(maintenance) if maintenance else None,
    )


@router.put("/{car_id}", response_model=CarResponse)
def update_car(
    car_id: UUID,
    payload: CarUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cars_full(db=db, current_user=current_user)
    car = _get_car_or_404(db, car_id)
    old_snapshot = _car_snapshot(car)
    fields_set = getattr(payload, "model_fields_set", None) or set()

    if "license_plate" in fields_set and payload.license_plate is not None:
        existing = db.query(Car).filter(Car.license_plate == payload.license_plate, Car.id != car_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="License plate already exists")

    if "make" in fields_set and payload.make is not None:
        car.make = payload.make
    if "model" in fields_set and payload.model is not None:
        car.model = payload.model
    if "license_plate" in fields_set and payload.license_plate is not None:
        car.license_plate = payload.license_plate
    if "year" in fields_set and payload.year is not None:
        car.year = payload.year
    if "purchase_date" in fields_set:
        car.purchase_date = payload.purchase_date
    if "purchase_price" in fields_set:
        car.purchase_price = payload.purchase_price
    if "status" in fields_set and payload.status is not None:
        car.status = payload.status
    if "notes" in fields_set:
        car.notes = payload.notes

    try:
        db.flush()
        db.refresh(car)
        log_activity(
            db=db,
            entity_type="Car",
            entity_id=str(car.id),
            action_type="update",
            performed_by_user_id=str(current_user.id),
            old_value=old_snapshot,
            new_value=_car_snapshot(car),
        )
        db.commit()
        db.refresh(car)
        return car
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid car update")


@router.delete("/{car_id}", status_code=status.HTTP_200_OK)
def delete_car(
    car_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    car = _get_car_or_404(db, car_id)

    has_income = db.query(CarIncome.id).filter(CarIncome.car_id == car_id).first() is not None
    has_expense = db.query(CarExpense.id).filter(CarExpense.car_id == car_id).first() is not None
    if has_income or has_expense:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Car cannot be deleted because it has financial records",
        )

    old_snapshot = _car_snapshot(car)
    maintenance = db.query(CarMaintenance).filter(CarMaintenance.car_id == car_id).first()

    try:
        if maintenance:
            db.delete(maintenance)
        db.delete(car)
        log_activity(
            db=db,
            entity_type="Car",
            entity_id=str(car_id),
            action_type="delete",
            performed_by_user_id=str(admin.id),
            old_value=old_snapshot,
            new_value=None,
        )
        db.commit()
        return {"message": "Car deleted successfully"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Car cannot be deleted")


@router.put("/{car_id}/maintenance", response_model=CarMaintenanceResponse)
def upsert_maintenance(
    car_id: UUID,
    payload: CarMaintenanceUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cars_full(db=db, current_user=current_user)
    _get_car_or_404(db, car_id)

    maintenance = db.query(CarMaintenance).filter(CarMaintenance.car_id == car_id).first()
    old_snapshot = None
    if maintenance:
        old_snapshot = {
            "id": str(maintenance.id),
            "car_id": str(maintenance.car_id),
            "last_service_date": maintenance.last_service_date.isoformat() if maintenance.last_service_date else None,
            "next_service_date": maintenance.next_service_date.isoformat() if maintenance.next_service_date else None,
            "last_kteo_date": maintenance.last_kteo_date.isoformat() if maintenance.last_kteo_date else None,
            "next_kteo_date": maintenance.next_kteo_date.isoformat() if maintenance.next_kteo_date else None,
            "last_tyre_change_date": maintenance.last_tyre_change_date.isoformat() if maintenance.last_tyre_change_date else None,
        }
    else:
        maintenance = CarMaintenance(car_id=car_id)
        db.add(maintenance)

    maintenance.last_service_date = payload.last_service_date
    maintenance.next_service_date = payload.next_service_date
    maintenance.last_kteo_date = payload.last_kteo_date
    maintenance.next_kteo_date = payload.next_kteo_date
    maintenance.last_tyre_change_date = payload.last_tyre_change_date

    db.flush()
    db.refresh(maintenance)

    new_snapshot = {
        "id": str(maintenance.id),
        "car_id": str(maintenance.car_id),
        "last_service_date": maintenance.last_service_date.isoformat() if maintenance.last_service_date else None,
        "next_service_date": maintenance.next_service_date.isoformat() if maintenance.next_service_date else None,
        "last_kteo_date": maintenance.last_kteo_date.isoformat() if maintenance.last_kteo_date else None,
        "next_kteo_date": maintenance.next_kteo_date.isoformat() if maintenance.next_kteo_date else None,
        "last_tyre_change_date": maintenance.last_tyre_change_date.isoformat() if maintenance.last_tyre_change_date else None,
    }
    log_activity(
        db=db,
        entity_type="Car",
        entity_id=str(car_id),
        action_type="maintenance_update",
        performed_by_user_id=str(current_user.id),
        old_value=old_snapshot,
        new_value=new_snapshot,
    )
    db.commit()
    db.refresh(maintenance)
    return maintenance


@router.post("/{car_id}/income", response_model=CarIncomeResponse, status_code=status.HTTP_201_CREATED)
def add_income(
    car_id: UUID,
    payload: CarIncomeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cars_full(db=db, current_user=current_user)
    _get_car_or_404(db, car_id)

    income = CarIncome(
        car_id=car_id,
        customer_name=payload.customer_name,
        amount=payload.amount,
        income_type=payload.income_type,
        transaction_date=payload.transaction_date,
        description=payload.description,
    )
    db.add(income)
    db.commit()
    db.refresh(income)
    return income


@router.post("/{car_id}/expense", response_model=CarExpenseResponse, status_code=status.HTTP_201_CREATED)
def add_expense(
    car_id: UUID,
    payload: CarExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cars_full(db=db, current_user=current_user)
    _get_car_or_404(db, car_id)

    expense = CarExpense(
        car_id=car_id,
        expense_type=payload.expense_type,
        amount=payload.amount,
        transaction_date=payload.transaction_date,
        description=payload.description,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/{car_id}/financials", response_model=CarFinancialsResponse)
def get_financials(
    car_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cars_permission(db=db, current_user=current_user)
    _get_car_or_404(db, car_id)

    incomes = (
        db.query(CarIncome)
        .filter(CarIncome.car_id == car_id)
        .order_by(CarIncome.transaction_date.desc(), CarIncome.created_at.desc())
        .all()
    )
    expenses = (
        db.query(CarExpense)
        .filter(CarExpense.car_id == car_id)
        .order_by(CarExpense.transaction_date.desc(), CarExpense.created_at.desc())
        .all()
    )

    total_income = db.query(func.coalesce(func.sum(CarIncome.amount), 0)).filter(CarIncome.car_id == car_id).scalar()
    total_expenses = db.query(func.coalesce(func.sum(CarExpense.amount), 0)).filter(CarExpense.car_id == car_id).scalar()
    total_income = Decimal(total_income or 0)
    total_expenses = Decimal(total_expenses or 0)

    return CarFinancialsResponse(
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expenses=total_expenses,
        profit=total_income - total_expenses,
    )
