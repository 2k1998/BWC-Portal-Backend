from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationListResponse, NotificationResponse, UnreadCountResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    read_status: Optional[str] = Query(None, description="Filter by read_status (Unread/Read)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List notifications for current user.
    """
    query = db.query(Notification).filter(Notification.recipient_user_id == current_user.id)
    
    if read_status:
        query = query.filter(Notification.read_status == read_status)
    
    total = query.count()
    notifications = query.order_by(desc(Notification.created_at))\
                         .offset((page - 1) * page_size)\
                         .limit(page_size)\
                         .all()
    
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get count of unread notifications.
    Optimized query using index.
    """
    count = db.query(Notification).filter(
        Notification.recipient_user_id == current_user.id,
        Notification.read_status == "Unread"
    ).count()
    
    return UnreadCountResponse(unread_count=count)

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a single notification as Read.
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.recipient_user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.read_status = "Read"
    db.commit()
    db.refresh(notification)
    
    return notification

@router.patch("/read-all", status_code=status.HTTP_200_OK)
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark ALL unread notifications as Read for current user.
    """
    # Bulk update for efficiency
    db.query(Notification).filter(
        Notification.recipient_user_id == current_user.id,
        Notification.read_status == "Unread"
    ).update({Notification.read_status: "Read"}, synchronize_session=False)
    
    db.commit()
    
    return {"message": "All notifications marked as read"}


@router.post("/trigger-test", status_code=status.HTTP_201_CREATED)
def trigger_test_notification(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger a test notification for the current user.
    """
    import uuid
    # Create dummy notification
    notif = Notification(
        recipient_user_id=current_user.id,
        actor_user_id=current_user.id,
        entity_type="System",
        entity_id=uuid.uuid4(),
        title="Test Notification",
        message="This is a test notification to verify the system.",
        link="/notifications",
        notification_type="ASSIGNMENT",
        read_status="Unread"
    )
    
    db.add(notif)
    db.commit()
    return {"message": "Test notification sent"}
