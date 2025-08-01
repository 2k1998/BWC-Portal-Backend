# routers/rentals.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/rentals", tags=["rentals"])

@router.post("/{company_id}", response_model=schemas.RentalOut, status_code=status.HTTP_201_CREATED)
def create_rental(
    company_id: int,
    rental: schemas.RentalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if the car and company exist
    db_company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not db_company:
        raise HTTPException(status_code=404, detail="Company not found")
    db_car = db.query(models.Car).filter(models.Car.id == rental.car_id).first()
    if not db_car:
        raise HTTPException(status_code=404, detail="Car not found")

    new_rental = models.Rental(**rental.dict(), company_id=company_id)
    db.add(new_rental)
    db.commit()
    db.refresh(new_rental)
    return new_rental

@router.get("/company/{company_id}", response_model=List[schemas.RentalOut])
def get_rentals_for_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Rental).filter(models.Rental.company_id == company_id).order_by(models.Rental.return_datetime.desc()).all()

@router.put("/{rental_id}/return", response_model=schemas.RentalOut)
def update_rental_on_return(
    rental_id: int,
    rental_update: schemas.RentalUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_rental = db.query(models.Rental).filter(models.Rental.id == rental_id).first()
    if not db_rental:
        raise HTTPException(status_code=404, detail="Rental record not found")
    if db_rental.is_locked:
        raise HTTPException(status_code=400, detail="This rental record is locked and cannot be edited.")

    # Update the fields and lock the record
    db_rental.end_kilometers = rental_update.end_kilometers
    db_rental.gas_tank_end = rental_update.gas_tank_end
    db_rental.is_locked = True
    
    db.commit()
    db.refresh(db_rental)
    return db_rental
