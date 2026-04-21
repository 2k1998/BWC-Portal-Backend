from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import List, Optional
from app.models.notification import Notification
from app.models.user import User
from app.models.task import Task
from app.models.project import Project
from app.utils.visibility import can_user_view_task, can_user_view_project

from app.schemas.notification import NotificationType

def create_notification(
    db: Session,
    recipient_ids: List[UUID],
    actor_id: Optional[UUID],
    entity_type: str,
    entity_id: str,
    title: str,
    message: str,
    link: str,
    notification_type: str
) -> None:
    """
    Create notifications for multiple recipients with deduplication and visibility checks.
    
    STRICT RULES:
    1. No commit (only db.add/db.add_all). Caller controls transaction.
    2. Visibility check enforced.
    3. Deduplication:
       - Unique recipients only.
       - Never notify actor (if actor_id is provided).
    4. Schema Enforcement:
       - notification_type must be valid (ASSIGNMENT, STATUS_CHANGE)
    """
    # 0. Strict Schema Validation
    # We use the Pydantic Enum to validate the string input.
    # If it fails, we raise ValueError immediately.
    try:
        # This will raise ValueError if string is not in Enum
        valid_type = NotificationType(notification_type)
    except ValueError:
        raise ValueError(f"Invalid notification_type: {notification_type}. Allowed: {[t.value for t in NotificationType]}")
    
    # 1. Deduplication: Unique set of strings first (easier to compare than UUID objects sometimes)
    unique_recipient_ids = set(str(rid) for rid in recipient_ids)
    
    # 2. Deduplication: Remove Actor
    if actor_id and str(actor_id) in unique_recipient_ids:
        unique_recipient_ids.remove(str(actor_id))
    
    if not unique_recipient_ids:
        return

    # Pre-fetch entity for visibility checks (only for entity types that require it).
    entity = None
    if entity_type == "Task":
        entity = db.query(Task).get(entity_id)
        if not entity:
            return
    elif entity_type == "Project":
        entity = db.query(Project).get(entity_id)
        if not entity:
            return

    final_notifications = []
    
    for recipient_id_str in unique_recipient_ids:
        # We need the User object for visibility checks (permissions often depend on user attributes)
        # Optimziation: We might fetch all users in one go if list is long, but loop is fine for small count.
        recipient_user = db.query(User).get(recipient_id_str)
        if not recipient_user:
            continue
            
        can_view = False
        if entity_type == "Task":
            can_view = can_user_view_task(entity, recipient_user, db)
        elif entity_type == "Project":
            can_view = can_user_view_project(entity, recipient_user)
        elif entity_type in {"Company", "ApprovalRequest"}:
            # For approvals: backend recipients are already authoritative.
            # For company: recipients are selected upstream and companies are global.
            can_view = True
        # Event/Document intentionally skipped for earlier phases.
        
        if can_view:
            duplicate_cutoff = datetime.now(timezone.utc) - timedelta(seconds=1)
            existing_duplicate = (
                db.query(Notification.id)
                .filter(
                    and_(
                        Notification.recipient_user_id == recipient_id_str,
                        Notification.entity_type == entity_type,
                        Notification.entity_id == entity_id,
                        Notification.notification_type == notification_type,
                        Notification.title == title,
                        Notification.message == message,
                        Notification.created_at >= duplicate_cutoff,
                    )
                )
                .first()
            )
            if existing_duplicate:
                continue

            notif = Notification(
                recipient_user_id=recipient_id_str,
                actor_user_id=actor_id,
                entity_type=entity_type,
                entity_id=entity_id,
                title=title,
                message=message,
                link=link,
                notification_type=notification_type,
                read_status="Unread"
            )
            final_notifications.append(notif)
            
    if final_notifications:
        db.add_all(final_notifications)
        # No db.commit()!
