# routers/companies.py
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import get_db
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/companies", tags=["companies"])

@router.post("/", response_model=schemas.CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(
    company: schemas.CompanyCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    check_roles(current_user, ["admin"])
    if company.vat_number:
        if db.query(models.Company).filter(models.Company.vat_number == company.vat_number).first():
            raise HTTPException(status_code=400, detail="A company with this VAT number already exists.")
    if db.query(models.Company).filter(models.Company.name == company.name).first():
        raise HTTPException(status_code=400, detail="A company with this name already exists.")
    
    new_company = models.Company(**company.model_dump())
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    return new_company

@router.get("/", response_model=List[schemas.CompanyOut])
def list_companies(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Company).all()

@router.get("/{company_id}", response_model=schemas.CompanyOut)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.put("/{company_id}", response_model=schemas.CompanyOut)
def update_company(
    company_id: int,
    company_update: schemas.CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    check_roles(current_user, ["admin"])
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check for duplicate name/VAT if they're being updated
    update_data = company_update.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != company.name:
        if db.query(models.Company).filter(models.Company.name == update_data["name"]).first():
            raise HTTPException(status_code=400, detail="A company with this name already exists.")
    
    if "vat_number" in update_data and update_data["vat_number"] != company.vat_number:
        if db.query(models.Company).filter(models.Company.vat_number == update_data["vat_number"]).first():
            raise HTTPException(status_code=400, detail="A company with this VAT number already exists.")
    
    for field, value in update_data.items():
        setattr(company, field, value)
    
    db.commit()
    db.refresh(company)
    return company

@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    check_roles(current_user, ["admin"])
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check if company has associated tasks, cars, or rentals
    task_count = db.query(models.Task).filter(models.Task.company_id == company_id).count()
    car_count = db.query(models.Car).filter(models.Car.company_id == company_id).count()
    rental_count = db.query(models.Rental).filter(models.Rental.company_id == company_id).count()
    
    if task_count > 0 or car_count > 0 or rental_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete company. It has {task_count} tasks, {car_count} cars, and {rental_count} rentals associated with it."
        )
    
    db.delete(company)
    db.commit()

@router.get("/{company_id}/tasks", response_model=List[schemas.TaskResponse])
def get_tasks_for_company(
    company_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """Returns all tasks assigned to a specific company."""
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    tasks = db.query(models.Task).filter(models.Task.company_id == company_id).all()
    return tasks
