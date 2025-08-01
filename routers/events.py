# routers/events.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

import models, schemas
from database import get_db
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/events", tags=["events"])

@router.post("/", response_model=schemas.EventOut, status_code=status.HTTP_201_CREATED)
def create_event(event: schemas.EventCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Creates a new event. Admin only.
    """
    check_roles(current_user, ["admin"])
    new_event = models.Event(**event.dict(), created_by_id=current_user.id)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@router.get("/upcoming", response_model=Optional[schemas.EventOut])
def get_upcoming_event(db: Session = Depends(get_db)):
    """
    Gets the single next upcoming event. Returns null if no future events exist.
    """
    upcoming_event = db.query(models.Event).filter(models.Event.event_date >= datetime.now(timezone.utc)).order_by(models.Event.event_date.asc()).first()
    return upcoming_event

@router.get("/", response_model=List[schemas.EventOut])
def list_all_events(db: Session = Depends(get_db)):
    """
    Returns a list of all events, ordered by date.
    """
    return db.query(models.Event).order_by(models.Event.event_date.desc()).all()