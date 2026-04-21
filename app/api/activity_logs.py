from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.models.activity_log import ActivityLog
from app.models.task import Task
from app.models.project import Project
from app.models.event import Event
from app.models.document import Document
from app.models.payment import Payment
from app.schemas.activity_log import ActivityLogResponse, ActivityLogListResponse
from app.utils.visibility import can_user_view_task, can_user_view_project
from app.utils.permissions import check_user_permission

router = APIRouter(prefix="/activity-logs", tags=["Activity Logs"])

@router.get("/admin", response_model=ActivityLogListResponse)
def get_admin_activity_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    performed_by_user_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Get global activity logs (Admin only).
    """
    query = db.query(ActivityLog)

    if entity_type:
        query = query.filter(ActivityLog.entity_type == entity_type)
    
    if entity_id:
        query = query.filter(ActivityLog.entity_id == entity_id)

    if performed_by_user_id:
        query = query.filter(ActivityLog.performed_by_user_id == performed_by_user_id)

    total = query.count()
    logs = (
        query.options(joinedload(ActivityLog.performed_by))
        .order_by(desc(ActivityLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Enrich logs with user names if needed, or rely on frontend to fetch user details.
    # For now, we return standard objects. The schema has perform_by_user_name but it might be expensive to join.
    # Let's keep it simple and efficient. The database model has a relationship `performed_by`.
    
    # Transform to schema to populate perform_by_user_name safely
    results = []
    for log in logs:
        # Relationship access might trigger lazy load
        user_name = f"{log.performed_by.first_name} {log.performed_by.last_name}" if log.performed_by else "Unknown"
        
        # Pydantic will handle the rest, but we need to explicitly set the computed field if we added it to schema
        # The schema I created has `perform_by_user_name`.
        log_dict = log.__dict__.copy()
        log_dict["perform_by_user_name"] = user_name
        results.append(log_dict)

    return ActivityLogListResponse(
        logs=results,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("", response_model=ActivityLogListResponse)
def get_entity_activity_logs(
    entity_type: str = Query(..., description="Entity type (Task, Project, Event, Document, Payment)"),
    entity_id: UUID = Query(..., description="Entity ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get activity logs for a specific entity.
    User must have read access to the entity.
    """
    
    # 1. Validate Entity Existence & Permission
    if entity_type == "Task":
        task = db.query(Task).filter(Task.id == entity_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if not can_user_view_task(task, current_user, db):
            raise HTTPException(status_code=403, detail="You do not have access to this task")
            
    elif entity_type == "Project":
        project = db.query(Project).filter(Project.id == entity_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not can_user_view_project(project, current_user):
            raise HTTPException(status_code=403, detail="You do not have access to this project")
            
    elif entity_type == "Event":
        event = db.query(Event).filter(Event.id == entity_id).first()
        if not event:
             raise HTTPException(status_code=404, detail="Event not found")
        # Event visibility logic (PRD #6): Public visibility but maybe restricted?
        # Re-reading PRD #6: "Public visibility". 
        # If it's public, everyone can see it. But let's check if there are restricted events.
        # Simple for now: If it exists, you can see logs.
        pass 
        
    elif entity_type == "Document":
        doc = db.query(Document).filter(Document.id == entity_id).first()
        if not doc:
             raise HTTPException(status_code=404, detail="Document not found")
        # Document visibility (PRD #7): Public.
        pass

    elif entity_type == "Payment":
        payment = db.query(Payment).filter(Payment.id == entity_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        permission = check_user_permission(db=db, user=current_user, page_key="payments")
        if permission == "none":
            raise HTTPException(status_code=403, detail="You do not have access to payments activity logs")
        
    else:
        raise HTTPException(status_code=400, detail="Invalid entity_type")

    # 2. Fetch Logs
    query = db.query(ActivityLog).filter(
        ActivityLog.entity_type == entity_type,
        ActivityLog.entity_id == entity_id
    )

    total = query.count()
    logs = (
        query.options(joinedload(ActivityLog.performed_by))
        .order_by(desc(ActivityLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []
    for log in logs:
        user_name = f"{log.performed_by.first_name} {log.performed_by.last_name}" if log.performed_by else "Unknown"
        log_dict = log.__dict__.copy()
        log_dict["perform_by_user_name"] = user_name
        results.append(log_dict)

    return ActivityLogListResponse(
        logs=results,
        total=total,
        page=page,
        page_size=page_size
    )
