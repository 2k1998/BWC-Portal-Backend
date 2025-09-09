# routers/payments.py - Payment management API
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, or_, and_, func
from typing import List, Optional
from datetime import datetime, date

from database import get_db
import models, schemas
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/", response_model=schemas.PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment: schemas.PaymentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new payment"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    # Verify employee exists if provided
    if payment.employee_id:
        employee = db.query(models.User).filter(models.User.id == payment.employee_id).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
    
    # Verify commission summary exists if provided
    if payment.commission_summary_id:
        summary = db.query(models.MonthlyCommissionSummary).filter(
            models.MonthlyCommissionSummary.id == payment.commission_summary_id
        ).first()
        if not summary:
            raise HTTPException(status_code=404, detail="Commission summary not found")
    
    # Create new payment
    db_payment = models.Payment(
        **payment.model_dump(),
        created_by_id=current_user.id
    )
    
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    
    # Load relationships for response
    db_payment = db.query(models.Payment).options(
        joinedload(models.Payment.employee),
        joinedload(models.Payment.company),
        joinedload(models.Payment.commission_summary),
        joinedload(models.Payment.created_by),
        joinedload(models.Payment.approved_by)
    ).filter(models.Payment.id == db_payment.id).first()
    
    return db_payment

@router.post("/commission/{commission_summary_id}", response_model=schemas.PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_commission_payment(
    commission_summary_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a payment from a commission summary"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    # Get commission summary
    summary = db.query(models.MonthlyCommissionSummary).options(
        joinedload(models.MonthlyCommissionSummary.employee)
    ).filter(models.MonthlyCommissionSummary.id == commission_summary_id).first()
    
    if not summary:
        raise HTTPException(status_code=404, detail="Commission summary not found")
    
    # Check if payment already exists for this summary
    existing_payment = db.query(models.Payment).filter(
        models.Payment.commission_summary_id == commission_summary_id
    ).first()
    
    if existing_payment:
        raise HTTPException(status_code=400, detail="Payment already exists for this commission summary")
    
    # Create commission payment
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    month_name = month_names[summary.month - 1]
    
    payment_title = f"{month_name} {summary.year} Commission - {summary.employee.full_name}"
    
    db_payment = models.Payment(
        title=payment_title,
        description=f"Commission payment for {summary.closed_deals_count} closed deals totaling €{summary.total_sales_amount}",
        amount=summary.total_commission,
        currency="EUR",
        payment_type=models.PaymentType.commission_payment,
        due_date=date.today(),
        employee_id=summary.employee_id,
        commission_summary_id=commission_summary_id,
        category="Commission",
        created_by_id=current_user.id
    )
    
    db.add(db_payment)
    
    # Update commission summary payment status
    summary.payment_status = models.CommissionStatus.pending
    
    db.commit()
    db.refresh(db_payment)
    
    # Load relationships for response
    db_payment = db.query(models.Payment).options(
        joinedload(models.Payment.employee),
        joinedload(models.Payment.company),
        joinedload(models.Payment.commission_summary),
        joinedload(models.Payment.created_by),
        joinedload(models.Payment.approved_by)
    ).filter(models.Payment.id == db_payment.id).first()
    
    return db_payment

@router.get("/", response_model=List[schemas.PaymentListItem])
def get_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    payment_type_filter: Optional[models.PaymentType] = None,
    status_filter: Optional[models.PaymentStatus] = None,
    employee_id: Optional[int] = None,
    company_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(title|amount|due_date|paid_date|created_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all payments with filtering and sorting"""
    
    query = db.query(models.Payment).options(
        joinedload(models.Payment.employee),
        joinedload(models.Payment.company)
    )
    
    # Apply filters
    if payment_type_filter:
        query = query.filter(models.Payment.payment_type == payment_type_filter)
    
    if status_filter:
        query = query.filter(models.Payment.status == status_filter)
    
    if employee_id:
        query = query.filter(models.Payment.employee_id == employee_id)
    
    if company_id:
        query = query.filter(models.Payment.company_id == company_id)
    
    if from_date:
        query = query.filter(models.Payment.due_date >= from_date)
    
    if to_date:
        query = query.filter(models.Payment.due_date <= to_date)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                models.Payment.title.ilike(search_term),
                models.Payment.description.ilike(search_term),
                models.Payment.category.ilike(search_term)
            )
        )
    
    # Apply sorting
    order_func = desc if sort_order == "desc" else asc
    if sort_by == "title":
        query = query.order_by(order_func(models.Payment.title))
    elif sort_by == "amount":
        query = query.order_by(order_func(models.Payment.amount))
    elif sort_by == "due_date":
        query = query.order_by(order_func(models.Payment.due_date))
    elif sort_by == "paid_date":
        query = query.order_by(order_func(models.Payment.paid_date))
    else:  # created_at
        query = query.order_by(order_func(models.Payment.created_at))
    
    payments = query.offset(skip).limit(limit).all()
    
    # Transform to list items
    payment_list = []
    for payment in payments:
        payment_list.append({
            "id": payment.id,
            "title": payment.title,
            "amount": payment.amount,
            "currency": payment.currency,
            "payment_type": payment.payment_type,
            "status": payment.status,
            "due_date": payment.due_date,
            "paid_date": payment.paid_date,
            "employee_name": payment.employee.full_name if payment.employee else None,
            "company_name": payment.company.name if payment.company else None,
            "is_commission": payment.payment_type == models.PaymentType.commission_payment,
            "is_income": payment.is_income,
            "is_expense": payment.is_expense,
            "created_at": payment.created_at
        })
    
    return payment_list

@router.get("/{payment_id}", response_model=schemas.PaymentResponse)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific payment by ID"""
    
    payment = db.query(models.Payment).options(
        joinedload(models.Payment.employee),
        joinedload(models.Payment.company),
        joinedload(models.Payment.commission_summary),
        joinedload(models.Payment.created_by),
        joinedload(models.Payment.approved_by)
    ).filter(models.Payment.id == payment_id).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    return payment

@router.put("/{payment_id}", response_model=schemas.PaymentResponse)
def update_payment(
    payment_id: int,
    payment_update: schemas.PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update a payment"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    db_payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Update fields
    update_data = payment_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_payment, field, value)
    
    db_payment.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_payment)
    
    # Load relationships for response
    db_payment = db.query(models.Payment).options(
        joinedload(models.Payment.employee),
        joinedload(models.Payment.company),
        joinedload(models.Payment.commission_summary),
        joinedload(models.Payment.created_by),
        joinedload(models.Payment.approved_by)
    ).filter(models.Payment.id == payment_id).first()
    
    return db_payment

@router.patch("/{payment_id}/status", response_model=schemas.PaymentResponse)
def update_payment_status(
    payment_id: int,
    status_update: schemas.PaymentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update payment status"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    db_payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Update status
    db_payment.status = status_update.status
    if status_update.paid_date:
        db_payment.paid_date = status_update.paid_date
    if status_update.notes:
        db_payment.notes = status_update.notes
    
    # Auto-set paid date if status is paid
    if status_update.status == models.PaymentStatus.paid and not db_payment.paid_date:
        db_payment.paid_date = datetime.utcnow().date()
    
    # Update commission summary if this is a commission payment
    if db_payment.commission_summary_id and status_update.status == models.PaymentStatus.paid:
        commission_summary = db.query(models.MonthlyCommissionSummary).filter(
            models.MonthlyCommissionSummary.id == db_payment.commission_summary_id
        ).first()
        if commission_summary:
            commission_summary.payment_status = models.CommissionStatus.paid
            commission_summary.payment_date = db_payment.paid_date
    
    db_payment.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_payment)
    
    # Load relationships for response
    db_payment = db.query(models.Payment).options(
        joinedload(models.Payment.employee),
        joinedload(models.Payment.company),
        joinedload(models.Payment.commission_summary),
        joinedload(models.Payment.created_by),
        joinedload(models.Payment.approved_by)
    ).filter(models.Payment.id == payment_id).first()
    
    return db_payment

@router.post("/{payment_id}/approve", response_model=schemas.PaymentResponse)
def approve_payment(
    payment_id: int,
    approval: schemas.PaymentApproval,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Approve or reject a payment"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    db_payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if approval.approve:
        db_payment.status = models.PaymentStatus.approved
        db_payment.approved_by_id = current_user.id
        db_payment.approved_at = datetime.utcnow()
    else:
        db_payment.status = models.PaymentStatus.cancelled
    
    db_payment.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_payment)
    
    # Load relationships for response
    db_payment = db.query(models.Payment).options(
        joinedload(models.Payment.employee),
        joinedload(models.Payment.company),
        joinedload(models.Payment.commission_summary),
        joinedload(models.Payment.created_by),
        joinedload(models.Payment.approved_by)
    ).filter(models.Payment.id == payment_id).first()
    
    return db_payment

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a payment"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    db_payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    db.delete(db_payment)
    db.commit()
    
    return None  # 204 No Content response
