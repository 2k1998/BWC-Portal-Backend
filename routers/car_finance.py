# routers/car_finance.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from pydantic import BaseModel
from decimal import Decimal

import models
from database import get_db
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/car-finances", tags=["car-finances"])

# Pydantic Models
class CarIncomeCreate(BaseModel):
    rental_id: Optional[int] = None
    car_id: int
    amount: Decimal
    description: Optional[str] = None
    date: date
    customer_name: str

class CarExpenseCreate(BaseModel):
    car_id: int
    service_type: str
    amount: Decimal
    description: Optional[str] = None
    date: date
    vendor: str
    mileage: Optional[int] = None

class CarFinanceSummary(BaseModel):
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    monthly_income: Decimal
    monthly_expenses: Decimal
    car_statistics: Dict[str, int]

class TransactionRecord(BaseModel):
    id: int
    type: str  # 'income' or 'expense'
    amount: Decimal
    description: Optional[str]
    date: date
    car_id: Optional[int]
    customer_name: Optional[str]
    vendor: Optional[str]
    service_type: Optional[str]

# API Endpoints
@router.get("/summary")
def get_finance_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get financial summary for car fleet with real data"""
    check_roles(current_user, ["admin"])
    
    # Get Best Solution Cars company
    company = db.query(models.Company).filter(
        models.Company.name == "Best Solution Cars"
    ).first()
    
    if not company:
        # Return empty data if company doesn't exist
        return {
            "total_income": 0,
            "total_expenses": 0,
            "net_profit": 0,
            "monthly_income": 0,
            "monthly_expenses": 0,
            "car_statistics": {
                "total_cars": 0,
                "active_cars": 0,
                "in_service_cars": 0,
                "available_cars": 0
            }
        }
    
    # Get all cars for the company
    total_cars = db.query(models.Car).filter(
        models.Car.company_id == company.id
    ).count()
    
    # Get active rentals (not locked means currently rented)
    active_rentals = db.query(models.Rental).filter(
        models.Rental.company_id == company.id,
        models.Rental.is_locked == False
    ).count()
    
    # Calculate available cars
    available_cars = total_cars - active_rentals
    
    # Calculate income from completed rentals
    rental_query = db.query(models.Rental).filter(
        models.Rental.company_id == company.id,
        models.Rental.is_locked == True  # Only completed rentals
    )
    
    if start_date:
        rental_query = rental_query.filter(models.Rental.return_datetime >= start_date)
    if end_date:
        rental_query = rental_query.filter(models.Rental.return_datetime <= end_date)
    
    rentals = rental_query.all()
    
    # Calculate total income from rentals (€50 per day as default rate)
    total_income = sum((r.rental_days * 50) for r in rentals if r.rental_days)
    
    # Get income from CarIncome table if it exists
    income_query = db.query(models.CarIncome).join(
        models.Car
    ).filter(
        models.Car.company_id == company.id
    )
    
    if start_date:
        income_query = income_query.filter(models.CarIncome.transaction_date >= start_date)
    if end_date:
        income_query = income_query.filter(models.CarIncome.transaction_date <= end_date)
    
    car_incomes = income_query.all()
    total_income += sum(float(income.amount) for income in car_incomes)
    
    # Get expenses from CarExpense table
    expense_query = db.query(models.CarExpense).join(
        models.Car
    ).filter(
        models.Car.company_id == company.id
    )
    
    if start_date:
        expense_query = expense_query.filter(models.CarExpense.transaction_date >= start_date)
    if end_date:
        expense_query = expense_query.filter(models.CarExpense.transaction_date <= end_date)
    
    car_expenses = expense_query.all()
    total_expenses = sum(float(expense.amount) for expense in car_expenses)
    
    # Calculate monthly averages
    if start_date and end_date:
        days_diff = (end_date - start_date).days or 1
        months = days_diff / 30.0
    else:
        months = 1.0
    
    monthly_income = total_income / months if months > 0 else total_income
    monthly_expenses = total_expenses / months if months > 0 else total_expenses
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
        "car_statistics": {
            "total_cars": total_cars,
            "active_cars": active_rentals,
            "in_service_cars": 0,  # Could be enhanced with a service tracking system
            "available_cars": available_cars
        }
    }

@router.post("/income")
def add_car_income(
    income: CarIncomeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Add income record for car rental"""
    check_roles(current_user, ["admin"])
    
    # Verify car exists
    car = db.query(models.Car).filter(models.Car.id == income.car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    
    # Create income record
    new_income = models.CarIncome(
        rental_id=income.rental_id,
        car_id=income.car_id,
        amount=income.amount,
        description=income.description,
        transaction_date=income.date,
        customer_name=income.customer_name,
        created_by_id=current_user.id
    )
    
    db.add(new_income)
    db.commit()
    db.refresh(new_income)
    
    return {"message": "Income added successfully", "id": new_income.id}

@router.post("/expense")
def add_car_expense(
    expense: CarExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Add expense record for car service"""
    check_roles(current_user, ["admin"])
    
    # Verify car exists
    car = db.query(models.Car).filter(models.Car.id == expense.car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    
    # Create expense record
    new_expense = models.CarExpense(
        car_id=expense.car_id,
        service_type=expense.service_type,
        amount=expense.amount,
        description=expense.description,
        transaction_date=expense.date,
        vendor=expense.vendor,
        mileage=expense.mileage,
        created_by_id=current_user.id
    )
    
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    
    return {"message": "Expense added successfully", "id": new_expense.id}

@router.get("/transactions")
def get_car_transactions(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    transaction_type: Optional[str] = None,  # 'income' or 'expense'
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all car-related financial transactions"""
    check_roles(current_user, ["admin"])
    
    # Get Best Solution Cars company
    company = db.query(models.Company).filter(
        models.Company.name == "Best Solution Cars"
    ).first()
    
    if not company:
        return []
    
    transactions = []
    
    # Get income records if needed
    if transaction_type != 'expense':
        income_query = db.query(models.CarIncome).join(
            models.Car
        ).filter(
            models.Car.company_id == company.id
        )
        
        if start_date:
            income_query = income_query.filter(models.CarIncome.transaction_date >= start_date)
        if end_date:
            income_query = income_query.filter(models.CarIncome.transaction_date <= end_date)
        
        incomes = income_query.all()
        
        for income in incomes:
            transactions.append({
                "id": income.id,
                "type": "income",
                "amount": float(income.amount),
                "description": income.description,
                "date": income.transaction_date.isoformat() if income.transaction_date else None,
                "car_id": income.car_id,
                "customer_name": income.customer_name,
                "vendor": None,
                "service_type": None
            })
    
    # Get expense records if needed
    if transaction_type != 'income':
        expense_query = db.query(models.CarExpense).join(
            models.Car
        ).filter(
            models.Car.company_id == company.id
        )
        
        if start_date:
            expense_query = expense_query.filter(models.CarExpense.transaction_date >= start_date)
        if end_date:
            expense_query = expense_query.filter(models.CarExpense.transaction_date <= end_date)
        
        expenses = expense_query.all()
        
        for expense in expenses:
            transactions.append({
                "id": expense.id,
                "type": "expense",
                "amount": float(expense.amount),
                "description": expense.description,
                "date": expense.transaction_date.isoformat() if expense.transaction_date else None,
                "car_id": expense.car_id,
                "customer_name": None,
                "vendor": expense.vendor,
                "service_type": expense.service_type
            })
    
    # Sort by date (most recent first)
    transactions.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
    
    return transactions

@router.get("/cars")
def get_fleet_cars(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all cars in the Best Solution Cars fleet"""
    check_roles(current_user, ["admin"])
    
    # Get Best Solution Cars company
    company = db.query(models.Company).filter(
        models.Company.name == "Best Solution Cars"
    ).first()
    
    if not company:
        return []
    
    # Get all cars for the company
    cars = db.query(models.Car).filter(
        models.Car.company_id == company.id
    ).all()
    
    return [
        {
            "id": car.id,
            "manufacturer": car.manufacturer,
            "model": car.model,
            "license_plate": car.license_plate,
            "vin": car.vin
        }
        for car in cars
    ]

@router.get("/rentals")
def get_rental_records(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all rental records for Best Solution Cars"""
    check_roles(current_user, ["admin"])
    
    # Get Best Solution Cars company
    company = db.query(models.Company).filter(
        models.Company.name == "Best Solution Cars"
    ).first()
    
    if not company:
        return []
    
    # Get all rentals for the company with car information
    rentals = db.query(models.Rental).filter(
        models.Rental.company_id == company.id
    ).order_by(models.Rental.return_datetime.desc()).all()
    
    rental_list = []
    for rental in rentals:
        # Get car details if available
        car = db.query(models.Car).filter(models.Car.id == rental.car_id).first()
        
        rental_list.append({
            "id": rental.id,
            "customer_name": rental.customer_name,
            "customer_surname": rental.customer_surname,
            "car_id": rental.car_id,
            "car_details": f"{car.manufacturer} {car.model}" if car else "Unknown",
            "rental_days": rental.rental_days,
            "is_locked": rental.is_locked,
            "created_at": rental.return_datetime.isoformat() if rental.return_datetime else None
        })
    
    return rental_list

@router.delete("/income/{income_id}")
def delete_income(
    income_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete an income record"""
    check_roles(current_user, ["admin"])
    
    income = db.query(models.CarIncome).filter(models.CarIncome.id == income_id).first()
    if not income:
        raise HTTPException(status_code=404, detail="Income record not found")
    
    db.delete(income)
    db.commit()
    
    return {"message": "Income record deleted successfully"}

@router.delete("/expense/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete an expense record"""
    check_roles(current_user, ["admin"])
    
    expense = db.query(models.CarExpense).filter(models.CarExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense record not found")
    
    db.delete(expense)
    db.commit()
    
    return {"message": "Expense record deleted successfully"}