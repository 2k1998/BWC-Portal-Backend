# routers/notifications.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Fixed: Added /me endpoint to match frontend expectations
@router.get("/me", response_model=List[schemas.NotificationOut])
def get_my_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Retrieves all notifications for the currently authenticated user, newest first.
    """
    return db.query(models.Notification)\
             .filter(models.Notification.user_id == current_user.id)\
             .order_by(models.Notification.created_at.desc())\
             .all()

# Keep the original root endpoint as well for backward compatibility
@router.get("/", response_model=List[schemas.NotificationOut])
def get_my_notifications_root(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Retrieves all notifications for the currently authenticated user (root endpoint).
    """
    return get_my_notifications(db, current_user)

# Fixed: Added /read endpoint to match frontend expectations
@router.put("/{notification_id}/read", response_model=schemas.NotificationOut)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Marks a single notification as read.
    """
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found or you do not have permission to access it.")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification

# Keep the original endpoint as well
@router.post("/{notification_id}/mark-as-read", response_model=schemas.NotificationOut)
def mark_notification_as_read_post(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Marks a single notification as read (POST method for backward compatibility).
    """
    return mark_notification_as_read(notification_id, db, current_user)

# Fixed: Added correct endpoint URL for mark all as read
@router.put("/mark-all-read", response_model=dict)
def mark_all_notifications_as_read(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Marks all of the user's unread notifications as read.
    """
    updated_count = db.query(models.Notification)\
      .filter(models.Notification.user_id == current_user.id, models.Notification.is_read == False)\
      .update({"is_read": True})
    
    db.commit()
    return {"message": f"Marked {updated_count} notifications as read."}

# Keep original endpoint as well
@router.post("/mark-all-as-read", response_model=dict)
def mark_all_notifications_as_read_post(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Marks all of the user's unread notifications as read (POST method for backward compatibility).
    """
    return mark_all_notifications_as_read(db, current_user)

# Fixed: Added correct endpoint URL for clear all
@router.delete("/clear-all", status_code=status.HTTP_204_NO_CONTENT)
def clear_all_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Deletes all notifications for the currently authenticated user.
    """
    deleted_count = db.query(models.Notification).filter(models.Notification.user_id == current_user.id).delete()
    db.commit()
    return

# Keep original endpoint as well
@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_my_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Deletes all notifications for the currently authenticated user (alternative endpoint).
    """
