from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.event import Event
from app.schemas.event import (
    EventCreate, EventUpdate, EventResponse, EventListResponse
)
from app.utils.activity_logger import log_activity

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new event.
    All users can create events.
    """
    event = Event(
        title=event_data.title,
        location=event_data.location,
        event_datetime=event_data.event_datetime,
        event_start_at=event_data.event_datetime,
        description=event_data.description,
        owner_user_id=current_user.id # Strict owner derivation
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    
    # Activity Log
    log_activity(
        db=db,
        entity_type="Event",
        entity_id=str(event.id),
        action_type="CREATE",
        performed_by_user_id=str(current_user.id),
        old_value=None,
        new_value={
            "title": event.title,
            "event_datetime": event.event_datetime.isoformat(),
            "location": event.location,
            "owner_user_id": str(event.owner_user_id)
        }
    )
    
    return event


@router.get("", response_model=EventListResponse)
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    active: Optional[bool] = Query(None, description="Filter active events (event_datetime >= now)"),
    completed: Optional[bool] = Query(None, description="Filter completed events (event_datetime < now)"),
    from_date: Optional[datetime] = Query(None, description="Filter events from this datetime"),
    to_date: Optional[datetime] = Query(None, description="Filter events to this datetime"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all events.
    All users can see all events (public visibility).
    """
    query = db.query(Event).filter(Event.deleted_at.is_(None))
    
    now = datetime.now(timezone.utc)
    
    if active is True:
        query = query.filter(Event.event_start_at >= now)
    
    if completed is True:
        query = query.filter(Event.event_start_at < now)
    
    if from_date:
        query = query.filter(Event.event_start_at >= from_date)
    
    if to_date:
        query = query.filter(Event.event_start_at <= to_date)
    
    total = query.count()
    events = query.order_by(Event.event_start_at).offset((page - 1) * page_size).limit(page_size).all()
    
    return EventListResponse(
        events=events,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get event details.
    All users can view all events.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.deleted_at.is_(None)).first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    return event


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: str,
    event_data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update event (creator or admin only).
    """
    event = db.query(Event).filter(Event.id == event_id, Event.deleted_at.is_(None)).first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    if str(event.owner_user_id) != str(current_user.id) and current_user.user_type != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only event creator or admin can update event"
        )
    
    # Capture old state
    old_state = {
        "title": event.title,
        "location": event.location,
        "event_datetime": event.event_datetime.isoformat(),
        "description": event.description
    }

    if event_data.title is not None:
        event.title = event_data.title
    if event_data.location is not None:
        event.location = event_data.location
    if event_data.event_datetime is not None:
        event.event_datetime = event_data.event_datetime
        event.event_start_at = event_data.event_datetime
    if event_data.description is not None:
        event.description = event_data.description
    
    db.commit()
    db.refresh(event)
    
    # Capture new state
    new_state = {
        "title": event.title,
        "location": event.location,
        "event_datetime": event.event_datetime.isoformat(),
        "description": event.description
    }
    
    # Calculate diff
    diff_old = {}
    diff_new = {}
    has_changes = False
    
    for key, val in old_state.items():
        if val != new_state.get(key):
            diff_old[key] = val
            diff_new[key] = new_state.get(key)
            has_changes = True
            
    if has_changes:
        log_activity(
            db=db,
            entity_type="Event",
            entity_id=str(event.id),
            action_type="METADATA_UPDATE",
            performed_by_user_id=str(current_user.id),
            old_value=diff_old,
            new_value=diff_new
        )
    
    return event


@router.delete("/{event_id}", status_code=status.HTTP_200_OK)
def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete event (creator or admin only).
    Hard delete.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.deleted_at.is_(None)).first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    if str(event.owner_user_id) != str(current_user.id) and current_user.user_type != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only event creator or admin can delete event"
        )
    
    # Capture full snapshot before delete
    snapshot = {
        "id": str(event.id),
        "title": event.title,
        "location": event.location,
        "event_datetime": event.event_datetime.isoformat(),
        "description": event.description,
        "owner_user_id": str(event.owner_user_id)
    }

    event.deleted_at = datetime.now(timezone.utc)
    db.commit()
    
    # Activity Log
    log_activity(
        db=db,
        entity_type="Event",
        entity_id=str(event_id), # ID might be gone from DB but we have it as str
        action_type="DELETE",
        performed_by_user_id=str(current_user.id),
        old_value=snapshot,
        new_value=None
    )
    
    return {"message": f"Event '{event.title}' soft-deleted successfully"}
