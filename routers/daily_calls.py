# routers/daily_calls.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from typing import List

import models, schemas
from database import get_db
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/daily-calls", tags=["daily_calls"])

# Fixed: Added /me endpoint to match frontend expectations
@router.get("/me", response_model=List[schemas.DailyCallOut])
def get_my_daily_calls(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Retrieves all daily call entries for the currently authenticated user.
    """
    check_roles(current_user, ["Pillar", "Manager", "Head", "admin"])
    
    # Use joinedload to efficiently fetch related contact details in one query
    daily_calls = db.query(models.DailyCall).options(
        joinedload(models.DailyCall.contact)
    ).filter(models.DailyCall.user_id == current_user.id).all()
    
    return daily_calls

# Keep the original root endpoint as well for backward compatibility
@router.get("/", response_model=List[schemas.DailyCallOut])
def get_my_daily_calls_root(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Retrieves all daily call entries for the currently authenticated user (root endpoint).
    """
    return get_my_daily_calls(db, current_user)

@router.post("/", response_model=schemas.DailyCallOut)
def add_contact_to_daily_list(
    payload: schemas.DailyCallCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Adds a contact to the user's daily call list.
    """
    check_roles(current_user, ["Pillar", "Manager", "Head", "admin"])
    
    # 1. Check if the contact exists and belongs to the user
    contact = db.query(models.Contact).filter(
        models.Contact.id == payload.contact_id,
        models.Contact.owner_id == current_user.id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found or you do not have permission to add it.")

    # 2. Check if the contact is already on the daily list
    existing_call = db.query(models.DailyCall).filter(
        models.DailyCall.user_id == current_user.id,
        models.DailyCall.contact_id == payload.contact_id
    ).first()
    if existing_call:
        raise HTTPException(status_code=400, detail="Contact is already on your daily call list.")

    # 3. Create the new entry
    new_daily_call = models.DailyCall(
        user_id=current_user.id,
        contact_id=payload.contact_id
    )
    db.add(new_daily_call)
    db.commit()
    db.refresh(new_daily_call)
    
    # Manually load the contact details to match the response model
    db.refresh(new_daily_call, attribute_names=['contact'])

    return new_daily_call

@router.put("/{daily_call_id}", response_model=schemas.DailyCallOut)
def update_daily_call(
    daily_call_id: int,
    payload: schemas.DailyCallUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Updates the frequency or next call time for a daily call entry.
    """
    daily_call = db.query(models.DailyCall).filter(
        models.DailyCall.id == daily_call_id,
        models.DailyCall.user_id == current_user.id
    ).first()

    if not daily_call:
        raise HTTPException(status_code=404, detail="Daily call entry not found.")

    # Fixed: Use model_dump() instead of dict() for Pydantic v2 compatibility
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(daily_call, key, value)
    
    db.commit()
    db.refresh(daily_call)
    db.refresh(daily_call, attribute_names=['contact'])
    return daily_call

@router.delete("/{daily_call_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_daily_list(
    daily_call_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Removes a contact from the user's daily call list.
    """
    daily_call = db.query(models.DailyCall).filter(
        models.DailyCall.id == daily_call_id,
        models.DailyCall.user_id == current_user.id
    ).first()

    if not daily_call:
        raise HTTPException(status_code=404, detail="Daily call entry not found.")

    db.delete(daily_call)
    db.commit()
    return