from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.payment import Payment
from app.models.company import Company
from app.models.user import User
from app.schemas.payment import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentSummaryResponse,
    PaymentUpdate,
    PaymentType,
)
from app.utils.activity_logger import log_activity
from app.utils.permissions import check_user_permission


router = APIRouter(prefix="/payments", tags=["Payments"])


def _payment_snapshot(payment: Payment) -> dict:
    """Create a JSON-serializable snapshot for activity logging."""
    return {
        "id": str(payment.id),
        "title": payment.title,
        "description": payment.description,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "payment_type": payment.payment_type,
        "payment_category": payment.payment_category,
        "payment_date": payment.payment_date.isoformat(),
        "is_income": payment.is_income,
        "employee_user_id": str(payment.employee_user_id) if payment.employee_user_id else None,
        "company_id": str(payment.company_id),
        "created_by_user_id": str(payment.created_by_user_id),
    }


def _require_payments_permission(db: Session, current_user: User) -> str:
    permission = check_user_permission(db=db, user=current_user, page_key="payments")
    if permission == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access Payments")
    return permission


def _build_payment_conditions(
    *,
    date_from: Optional[date],
    date_to: Optional[date],
    company_id: Optional[UUID],
    employee_user_id: Optional[UUID],
    payment_type: Optional[PaymentType],
    payment_category: Optional[str],
    currency: Optional[str],
    is_income: Optional[bool],
):
    conditions = []
    if date_from is not None:
        conditions.append(Payment.payment_date >= date_from)
    if date_to is not None:
        conditions.append(Payment.payment_date <= date_to)
    if company_id is not None:
        conditions.append(Payment.company_id == company_id)
    if employee_user_id is not None:
        conditions.append(Payment.employee_user_id == employee_user_id)
    if payment_type is not None:
        conditions.append(Payment.payment_type == payment_type)
    if payment_category is not None:
        conditions.append(Payment.payment_category == payment_category)
    if currency is not None:
        conditions.append(Payment.currency == currency)
    if is_income is not None:
        conditions.append(Payment.is_income == is_income)
    return conditions


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission = _require_payments_permission(db=db, current_user=current_user)
    if permission != "full":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to create Payments")

    company = db.query(Company).filter(Company.id == payment_data.company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if payment_data.employee_user_id is not None:
        employee = db.query(User).filter(User.id == payment_data.employee_user_id).first()
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee user not found")

    payment = Payment(
        title=payment_data.title,
        description=payment_data.description,
        amount=payment_data.amount,
        currency=payment_data.currency,
        payment_type=payment_data.payment_type,
        payment_category=payment_data.payment_category,
        payment_date=payment_data.payment_date,
        is_income=payment_data.is_income,
        employee_user_id=payment_data.employee_user_id,
        company_id=payment_data.company_id,
        created_by_user_id=current_user.id,
    )

    db.add(payment)
    db.flush()
    db.refresh(payment)

    log_activity(
        db=db,
        entity_type="Payment",
        entity_id=str(payment.id),
        action_type="CREATE",
        performed_by_user_id=str(current_user.id),
        old_value=None,
        new_value=_payment_snapshot(payment),
    )

    db.commit()
    db.refresh(payment)
    return payment


@router.get("", response_model=PaymentListResponse)
def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    date_from: Optional[date] = Query(None, description="Filter payments from this date (ISO date string)"),
    date_to: Optional[date] = Query(None, description="Filter payments to this date (ISO date string)"),
    company_id: Optional[UUID] = Query(None, description="Filter by company_id"),
    employee_user_id: Optional[UUID] = Query(None, description="Filter by employee_user_id"),
    payment_type: Optional[PaymentType] = Query(None, description="Filter by payment_type"),
    payment_category: Optional[str] = Query(None, description="Filter by payment_category"),
    currency: Optional[str] = Query(None, description="Filter by currency"),
    is_income: Optional[bool] = Query(None, description="Filter by is_income"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_payments_permission(db=db, current_user=current_user)

    conditions = _build_payment_conditions(
        date_from=date_from,
        date_to=date_to,
        company_id=company_id,
        employee_user_id=employee_user_id,
        payment_type=payment_type,
        payment_category=payment_category,
        currency=currency,
        is_income=is_income,
    )

    query = db.query(Payment).filter(*conditions)
    total = query.count()
    payments = (
        query.order_by(Payment.payment_date.desc(), Payment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaymentListResponse(payments=payments, total=total, page=page, page_size=page_size)


@router.get("/summary", response_model=PaymentSummaryResponse)
def get_payments_summary(
    date_from: Optional[date] = Query(None, description="Filter payments from this date (ISO date string)"),
    date_to: Optional[date] = Query(None, description="Filter payments to this date (ISO date string)"),
    company_id: Optional[UUID] = Query(None, description="Filter by company_id"),
    employee_user_id: Optional[UUID] = Query(None, description="Filter by employee_user_id"),
    payment_type: Optional[PaymentType] = Query(None, description="Filter by payment_type"),
    payment_category: Optional[str] = Query(None, description="Filter by payment_category"),
    currency: Optional[str] = Query(None, description="Filter by currency"),
    is_income: Optional[bool] = Query(None, description="Filter by is_income"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_payments_permission(db=db, current_user=current_user)

    conditions = _build_payment_conditions(
        date_from=date_from,
        date_to=date_to,
        company_id=company_id,
        employee_user_id=employee_user_id,
        payment_type=payment_type,
        payment_category=payment_category,
        currency=currency,
        is_income=is_income,
    )

    total_income = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(*conditions, Payment.is_income.is_(True))
        .scalar()
    )
    total_expenses = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(*conditions, Payment.is_income.is_(False))
        .scalar()
    )

    # Ensure Decimal types for response consistency
    total_income = Decimal(total_income or 0)
    total_expenses = Decimal(total_expenses or 0)
    net_balance = total_income - total_expenses

    return PaymentSummaryResponse(total_income=total_income, total_expenses=total_expenses, net_balance=net_balance)


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_payments_permission(db=db, current_user=current_user)

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    return payment


@router.put("/{payment_id}", response_model=PaymentResponse)
def update_payment(
    payment_id: UUID,
    payment_data: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission = _require_payments_permission(db=db, current_user=current_user)
    if permission != "full":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to update Payments")

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if current_user.user_type != "Admin" and payment.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can update this Payment")

    old_snapshot = _payment_snapshot(payment)
    fields_set = getattr(payment_data, "model_fields_set", None) or set()

    try:
        if "title" in fields_set:
            if payment_data.title is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title cannot be null")
            payment.title = payment_data.title

        if "description" in fields_set:
            payment.description = payment_data.description

        if "amount" in fields_set:
            if payment_data.amount is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount cannot be null")
            payment.amount = payment_data.amount

        if "currency" in fields_set:
            if payment_data.currency is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="currency cannot be null")
            payment.currency = payment_data.currency

        if "payment_type" in fields_set:
            if payment_data.payment_type is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payment_type cannot be null")
            payment.payment_type = payment_data.payment_type

        if "payment_category" in fields_set:
            payment.payment_category = payment_data.payment_category

        if "payment_date" in fields_set:
            if payment_data.payment_date is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payment_date cannot be null")
            payment.payment_date = payment_data.payment_date

        if "is_income" in fields_set:
            if payment_data.is_income is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="is_income cannot be null")
            payment.is_income = payment_data.is_income

        if "employee_user_id" in fields_set:
            # Nullable FK
            payment.employee_user_id = payment_data.employee_user_id
            if payment_data.employee_user_id is not None:
                employee = db.query(User).filter(User.id == payment_data.employee_user_id).first()
                if not employee:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee user not found")

        if "company_id" in fields_set:
            if payment_data.company_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_id cannot be null")
            company = db.query(Company).filter(Company.id == payment_data.company_id).first()
            if not company:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
            payment.company_id = payment_data.company_id

        db.flush()
        db.refresh(payment)

        new_snapshot = _payment_snapshot(payment)
        log_activity(
            db=db,
            entity_type="Payment",
            entity_id=str(payment.id),
            action_type="UPDATE",
            performed_by_user_id=str(current_user.id),
            old_value=old_snapshot,
            new_value=new_snapshot,
        )

        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


@router.delete("/{payment_id}", status_code=status.HTTP_200_OK)
def delete_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    old_snapshot = _payment_snapshot(payment)

    try:
        db.delete(payment)

        log_activity(
            db=db,
            entity_type="Payment",
            entity_id=str(payment_id),
            action_type="DELETE",
            performed_by_user_id=str(admin.id),
            old_value=old_snapshot,
            new_value=None,
        )

        db.commit()
        return {"message": f"Payment '{payment.title}' deleted successfully"}
    except Exception:
        db.rollback()
        raise

