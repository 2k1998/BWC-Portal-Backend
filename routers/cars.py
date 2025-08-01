# routers/cars.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import get_db
from .auth import get_current_user
from .utils import check_roles  # Import the role checker

router = APIRouter(prefix="/cars", tags=["cars"])

@router.post("/{company_id}", response_model=schemas.CarOut, status_code=status.HTTP_201_CREATED)
def create_car_for_company(
    company_id: int,
    car: schemas.CarCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user) # Ensures user is logged in
):
    """
    Creates a new car and associates it with a specific company.
    Accessible by any authenticated user.
    """
    # Check if the company exists
    db_company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not db_company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check for unique license plate and VIN
    if db.query(models.Car).filter(models.Car.license_plate == car.license_plate).first():
        raise HTTPException(status_code=400, detail="A car with this license plate already exists.")
    if db.query(models.Car).filter(models.Car.vin == car.vin).first():
        raise HTTPException(status_code=400, detail="A car with this VIN already exists.")

    new_car = models.Car(**car.dict(), company_id=company_id)
    db.add(new_car)
    db.commit()
    db.refresh(new_car)
    return new_car

@router.get("/company/{company_id}", response_model=List[schemas.CarOut])
def get_cars_for_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user) # Ensures user is logged in
):
    """
    Returns a list of all cars for a specific company.
    """
    cars = db.query(models.Car).filter(models.Car.company_id == company_id).all()
    return cars

# --- NEW: Endpoint to update a car's details ---
@router.put("/{car_id}", response_model=schemas.CarOut)
def update_car(
    car_id: int,
    car_update: schemas.CarUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    check_roles(current_user, ["admin"])  # Admin only

    car = db.query(models.Car).filter(models.Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    
    update_data = car_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(car, field, value)
    
    db.commit()
    db.refresh(car)
    return car

# --- NEW: Endpoint to delete a car ---
@router.delete("/{car_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_car(
    car_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    check_roles(current_user, ["admin"])  # Admin only

    car = db.query(models.Car).filter(models.Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    
    # Safety check: prevent deleting a car if it has active rental records
    if db.query(models.Rental).filter(models.Rental.car_id == car_id).count() > 0:
        raise HTTPException(status_code=400, detail="Cannot delete car with active rental records. Please resolve rentals first.")

    db.delete(car)
    db.commit()
