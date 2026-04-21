import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timezone

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.task import Task
from app.models.team_member import TeamMember
from app.models.department import Department
from app.models.company import Company
from app.models.document import Document
from app.models.task_document import TaskDocument
from app.models.task_comment import TaskComment
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse,
    TaskStatusUpdate, TaskTransfer, ALLOWED_STATUSES, TaskDocumentAttachmentItem,
)
from app.schemas.task_comment import TaskCommentCreate, TaskCommentResponse
from app.utils.activity_logger import log_activity
from app.utils.notification_service import create_notification

MAX_TASK_ATTACHMENT_SIZE = 100 * 1024 * 1024


def _ensure_upload_dir() -> Path:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir

# Strict Status Transitions (PRD Phase 8)
VALID_TRANSITIONS = {
    "New": ["Received"],
    "Received": ["On Process", "Pending"],
    "On Process": ["Pending", "Completed", "Loose End"],
    "Pending": ["On Process", "Completed", "Loose End"],
    "Loose End": ["On Process", "Pending"],
    "Completed": []  # Terminal state
}

router = APIRouter(prefix="/tasks", tags=["Tasks"])


from app.utils.visibility import can_user_view_task, get_subordinate_ids


def _task_snapshot(task: Task) -> Dict[str, Any]:
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "company_id": str(task.company_id),
        "department": task.department,
        "urgency_label": task.urgency_label,
        "start_date": task.start_date.isoformat() if task.start_date else None,
        "deadline_date": task.deadline.isoformat() if task.deadline else None,
        "owner_user_id": str(task.owner_user_id),
        "assigned_user_id": str(task.assigned_user_id) if task.assigned_user_id else None,
        "assigned_team_id": str(task.assigned_team_id) if task.assigned_team_id else None,
        "status": task.status,
        "deleted_at": task.deleted_at.isoformat() if task.deleted_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def build_visibility_filter(current_user: User, db: Session):
    """Build SQLAlchemy filter for task visibility."""
    if current_user.user_type == "Admin":
        return True
    
    subordinate_ids = get_subordinate_ids(current_user, db)
    user_teams = db.query(TeamMember.team_id).filter(TeamMember.user_id == current_user.id).all()
    team_ids = [str(t[0]) for t in user_teams]
    
    filters = [
        Task.owner_user_id == current_user.id,
        Task.assigned_user_id == current_user.id,
    ]
    
    if team_ids:
        filters.append(Task.assigned_team_id.in_(team_ids))
    
    if subordinate_ids:
        filters.append(Task.assigned_user_id.in_(subordinate_ids))
    
    return and_(Task.deleted_at.is_(None), or_(*filters))


def _can_access_task_comments(task: Task, current_user: User) -> bool:
    return (
        current_user.user_type == "Admin"
        or str(task.owner_user_id) == str(current_user.id)
        or (task.assigned_user_id is not None and str(task.assigned_user_id) == str(current_user.id))
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new task.
    Validates assignment rules, department, company, and auto-sets urgency if needed.
    """
    company = db.query(Company).filter(Company.id == task_data.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    dept = db.query(Department).filter(Department.name == task_data.department).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department '{task_data.department}' does not exist"
        )
    
    if task_data.assigned_user_id:
        assigned_user = db.query(User).filter(User.id == task_data.assigned_user_id).first()
        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned user not found"
            )
    
    if task_data.assigned_team_id:
        from app.models.team import Team
        assigned_team = db.query(Team).filter(Team.id == task_data.assigned_team_id).first()
        if not assigned_team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned team not found"
            )
    
    urgency_label = task_data.urgency_label
    if urgency_label is None and task_data.start_date == task_data.deadline:
        urgency_label = "Orange"
    elif urgency_label is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="urgency_label is required when start_date != deadline"
        )
    
    try:
        task = Task(
            title=task_data.title,
            description=task_data.description,
            company_id=task_data.company_id,
            department=task_data.department,
            priority=task_data.priority,
            urgency_label=urgency_label,
            start_date=task_data.start_date,
            deadline=task_data.deadline,
            owner_user_id=current_user.id, # Strict owner derivation
            assigned_user_id=task_data.assigned_user_id,
            assigned_team_id=task_data.assigned_team_id,
            status="New"
        )
        
        db.add(task)
        db.flush() # Generate ID, do not commit yet
        db.refresh(task)
        
        # Activity Log
        log_activity(
            db=db,
            entity_type="Task",
            entity_id=str(task.id),
            action_type="CREATE",
            performed_by_user_id=str(current_user.id),
            old_value=None,
            new_value={
                "title": task.title,
                "status": task.status,
                "owner_user_id": str(task.owner_user_id),
                "assigned_user_id": str(task.assigned_user_id) if task.assigned_user_id else None,
            }
        )
        
        # Notification: ASSIGNMENT
        if task.assigned_user_id:
            create_notification(
                db=db,
                recipient_ids=[task.assigned_user_id],
                actor_id=current_user.id,
                entity_type="Task",
                entity_id=str(task.id),
                title="New Task Assignment",
                message=f"You have been assigned to task: {task.title}",
                link=f"/tasks/{task.id}",
                notification_type="ASSIGNMENT"
            )
        
        db.commit()
        return task

    except Exception as e:
        db.rollback()
        raise e


@router.get("", response_model=TaskListResponse)
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    urgency_filter: Optional[str] = Query(None, description="Filter by urgency_label"),
    company_filter: Optional[str] = Query(None, description="Filter by company_id"),
    assigned_user_filter: Optional[str] = Query(None, description="Filter by assigned_user_id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List tasks with visibility filtering.
    Users see only tasks they can access based on visibility rules.
    """
    visibility_filter = build_visibility_filter(current_user, db)
    query = db.query(Task).filter(visibility_filter)
    
    if status_filter:
        query = query.filter(Task.status == status_filter)
    
    if urgency_filter:
        query = query.filter(Task.urgency_label == urgency_filter)
    
    if company_filter:
        query = query.filter(Task.company_id == company_filter)
    
    if assigned_user_filter:
        query = query.filter(Task.assigned_user_id == assigned_user_filter)
    
    total = query.count()
    tasks = query.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return TaskListResponse(
        tasks=tasks,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/{task_id}/documents", response_model=TaskDocumentAttachmentItem, status_code=status.HTTP_201_CREATED)
async def upload_task_document(
    task_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach an uploaded file to a task (creates a Document row and a task_documents link)."""
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if not can_user_view_task(task, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this task")

    file_content = await file.read()
    file_size = len(file_content)
    if file_size > MAX_TASK_ATTACHMENT_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {MAX_TASK_ATTACHMENT_SIZE / (1024 * 1024)}MB",
        )

    upload_dir = _ensure_upload_dir()
    storage_filename = str(uuid.uuid4())
    storage_path = upload_dir / storage_filename
    with open(storage_path, "wb") as f:
        f.write(file_content)

    document = Document(
        filename=storage_filename,
        original_filename=file.filename or "upload",
        file_size_bytes=file_size,
        mime_type=file.content_type or "application/octet-stream",
        storage_path=str(storage_path),
        uploaded_by_user_id=current_user.id,
    )
    db.add(document)
    db.flush()
    db.refresh(document)

    td = TaskDocument(
        task_id=task.id,
        document_id=document.id,
        uploaded_by_user_id=current_user.id,
    )
    db.add(td)
    db.flush()
    db.refresh(td)

    log_activity(
        db=db,
        entity_type="Task",
        entity_id=str(task.id),
        action_type="document_attached",
        performed_by_user_id=str(current_user.id),
        old_value=None,
        new_value={
            "document_id": str(document.id),
            "task_document_id": str(td.id),
            "original_filename": document.original_filename,
        },
    )
    db.commit()

    return TaskDocumentAttachmentItem(
        id=td.id,
        document_id=document.id,
        filename=document.original_filename,
        mime_type=document.mime_type,
        size_bytes=document.file_size_bytes,
        uploaded_by=f"{current_user.first_name} {current_user.last_name}".strip(),
        created_at=td.created_at,
    )


@router.get("/{task_id}/documents", response_model=List[TaskDocumentAttachmentItem])
def list_task_documents(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents attached to a task."""
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if not can_user_view_task(task, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this task")

    rows = (
        db.query(TaskDocument, Document, User)
        .filter(TaskDocument.task_id == task_id)
        .join(Document, TaskDocument.document_id == Document.id)
        .join(User, TaskDocument.uploaded_by_user_id == User.id)
        .order_by(TaskDocument.created_at.desc())
        .all()
    )

    return [
        TaskDocumentAttachmentItem(
            id=td.id,
            document_id=doc.id,
            filename=doc.original_filename,
            mime_type=doc.mime_type,
            size_bytes=doc.file_size_bytes,
            uploaded_by=f"{user.first_name} {user.last_name}".strip(),
            created_at=td.created_at,
        )
        for td, doc, user in rows
    ]


@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=status.HTTP_201_CREATED)
def create_task_comment(
    task_id: str,
    comment_data: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not _can_access_task_comments(task, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this task")

    if task.status == "New":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comments are not allowed while task is in New status",
        )

    try:
        comment = TaskComment(
            task_id=task.id,
            user_id=current_user.id,
            body=comment_data.body,
        )
        db.add(comment)
        db.flush()
        db.refresh(comment)

        recipient_ids = [task.owner_user_id]
        if task.assigned_user_id:
            recipient_ids.append(task.assigned_user_id)
        recipient_ids = list(set(recipient_ids))

        commenter_full_name = f"{current_user.first_name} {current_user.last_name}".strip()
        create_notification(
            db=db,
            recipient_ids=recipient_ids,
            actor_id=current_user.id,
            entity_type="Task",
            entity_id=str(task.id),
            title="Task comment",
            message=f"{commenter_full_name} commented on task: {task.title}",
            link=f"/tasks/{task.id}",
            notification_type="COMMENT",
        )

        db.commit()
        return TaskCommentResponse(
            id=comment.id,
            task_id=comment.task_id,
            user_id=comment.user_id,
            user_full_name=commenter_full_name,
            body=comment.body,
            created_at=comment.created_at,
        )
    except Exception as e:
        db.rollback()
        raise e


@router.get("/{task_id}/comments", response_model=List[TaskCommentResponse])
def list_task_comments(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not _can_access_task_comments(task, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this task")

    rows = (
        db.query(TaskComment, User)
        .join(User, TaskComment.user_id == User.id)
        .filter(TaskComment.task_id == task.id)
        .order_by(TaskComment.created_at.asc())
        .all()
    )

    return [
        TaskCommentResponse(
            id=comment.id,
            task_id=comment.task_id,
            user_id=comment.user_id,
            user_full_name=f"{user.first_name} {user.last_name}".strip(),
            body=comment.body,
            created_at=comment.created_at,
        )
        for comment, user in rows
    ]


@router.delete("/{task_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach_task_document(
    task_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a task–document link (does not delete the Document row)."""
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if not can_user_view_task(task, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this task")

    td = (
        db.query(TaskDocument)
        .filter(TaskDocument.task_id == task_id, TaskDocument.document_id == document_id)
        .first()
    )
    if not td:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    can_remove = (
        current_user.user_type == "Admin"
        or str(task.owner_user_id) == str(current_user.id)
        or str(td.uploaded_by_user_id) == str(current_user.id)
    )
    if not can_remove:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to remove this attachment",
        )

    doc = db.query(Document).filter(Document.id == document_id).first()
    old_value = {
        "document_id": str(document_id),
        "task_document_id": str(td.id),
        "original_filename": doc.original_filename if doc else None,
    }

    db.delete(td)
    log_activity(
        db=db,
        entity_type="Task",
        entity_id=str(task.id),
        action_type="document_removed",
        performed_by_user_id=str(current_user.id),
        old_value=old_value,
        new_value=None,
    )
    db.commit()
    return None


@router.get("/deleted", response_model=TaskListResponse)
def list_deleted_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List soft-deleted tasks (admin only)."""
    if current_user.user_type != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view deleted tasks",
        )

    query = db.query(Task).filter(Task.deleted_at.isnot(None))
    total = query.count()
    tasks = query.order_by(Task.deleted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return TaskListResponse(
        tasks=tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get task details.
    User must have visibility access to the task.
    """
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    if not can_user_view_task(task, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task"
        )
    
    return task


@router.post("/{task_id}/view", status_code=status.HTTP_200_OK)
def view_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark task as viewed.
    If status is "New" and user is assigned, auto-update to "Received".
    """
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    if not can_user_view_task(task, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task"
        )
    
    if task.status == "New":
        is_assigned = False
        
        if task.assigned_user_id and str(task.assigned_user_id) == str(current_user.id):
            is_assigned = True
        
        if task.assigned_team_id:
            is_member = db.query(TeamMember).filter(
                TeamMember.team_id == task.assigned_team_id,
                TeamMember.user_id == current_user.id
            ).first()
            if is_member:
                is_assigned = True
        
        if is_assigned:
            try:
                # Verify transition logic (redundant but safe)
                if "Received" not in VALID_TRANSITIONS["New"]:
                     raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid status transition from New to Received"
                    )
                
                old_status = task.status
                task.status = "Received"
                db.flush() # Ensure update is pending
                
                # Activity Log
                log_activity(
                    db=db,
                    entity_type="Task",
                    entity_id=str(task.id),
                    action_type="STATUS_CHANGE",
                    performed_by_user_id=str(current_user.id),
                    old_value={"status": old_status},
                    new_value={"status": "Received"}
                )
                
                # Notification: STATUS_CHANGE
                # Recipients: Owner. Assignee is the actor.
                create_notification(
                    db=db,
                    recipient_ids=[task.owner_user_id],
                    actor_id=current_user.id,
                    entity_type="Task",
                    entity_id=str(task.id),
                    title="Task Received",
                    message=f"Task '{task.title}' marked as Received by {current_user.first_name}",
                    link=f"/tasks/{task.id}",
                    notification_type="STATUS_CHANGE"
                )
                
                db.commit()
                return {"message": "Task marked as viewed and status updated to Received"}
            except Exception as e:
                db.rollback()
                raise e
    
    return {"message": "Task viewed"}


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update task metadata (owner or admin only)."""
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    if str(task.owner_user_id) != str(current_user.id) and current_user.user_type != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only task owner or admin can update task"
        )
    
    if task.status.lower() == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed tasks cannot be edited."
        )
    
    old_state = _task_snapshot(task)
    old_assigned_user_id = str(task.assigned_user_id) if task.assigned_user_id else None
    old_deadline = task.deadline.isoformat() if task.deadline else None
    
    try:
        if task_data.title is not None:
            task.title = task_data.title
        if task_data.description is not None:
            task.description = task_data.description
        if task_data.company_id is not None:
            company = db.query(Company).filter(Company.id == task_data.company_id).first()
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Company not found"
                )
            task.company_id = task_data.company_id
        if task_data.department is not None:
            dept = db.query(Department).filter(Department.name == task_data.department).first()
            if not dept:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Department '{task_data.department}' does not exist"
                )
            task.department = task_data.department
        if task_data.urgency_label is not None:
            task.urgency_label = task_data.urgency_label
        if task_data.start_date is not None:
            task.start_date = task_data.start_date
        if task_data.deadline is not None:
            task.deadline = task_data.deadline
        
        if task_data.assigned_user_id is not None or task_data.assigned_team_id is not None:
            if task_data.assigned_user_id and task_data.assigned_team_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot assign to both user and team"
                )
            
            if task_data.assigned_user_id:
                assigned_user = db.query(User).filter(User.id == task_data.assigned_user_id).first()
                if not assigned_user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Assigned user not found"
                    )
                task.assigned_user_id = task_data.assigned_user_id
                task.assigned_team_id = None
            
            if task_data.assigned_team_id:
                from app.models.team import Team
                assigned_team = db.query(Team).filter(Team.id == task_data.assigned_team_id).first()
                if not assigned_team:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Assigned team not found"
                    )
                task.assigned_team_id = task_data.assigned_team_id
                task.assigned_user_id = None

        effective_start_date = task_data.start_date if task_data.start_date is not None else task.start_date
        effective_deadline = task_data.deadline if task_data.deadline is not None else task.deadline
        if effective_deadline < effective_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="deadline_date must be greater than or equal to start_date"
            )
        
        db.flush()
        db.refresh(task)
        
        new_state = _task_snapshot(task)
        
        allowed_edit_fields = {
            "title",
            "description",
            "company_id",
            "department",
            "urgency_label",
            "start_date",
            "deadline_date",
            "assigned_user_id",
            "assigned_team_id",
        }
        updated_fields = {}
        has_changes = False
        
        for key, val in old_state.items():
            if key in allowed_edit_fields and val != new_state.get(key):
                updated_fields[key] = new_state.get(key)
                has_changes = True
                
        if has_changes:
            log_activity(
                db=db,
                entity_type="Task",
                entity_id=str(task.id),
                action_type="update",
                performed_by_user_id=str(current_user.id),
                old_value=old_state,
                new_value=updated_fields
            )

            new_assigned_user_id = str(task.assigned_user_id) if task.assigned_user_id else None
            new_deadline = task.deadline.isoformat() if task.deadline else None

            if old_assigned_user_id != new_assigned_user_id and task.assigned_user_id:
                create_notification(
                    db=db,
                    recipient_ids=[task.assigned_user_id],
                    actor_id=current_user.id,
                    entity_type="Task",
                    entity_id=str(task.id),
                    title="You have been assigned a task",
                    message=f"{task.title}",
                    link=f"/tasks/{task.id}",
                    notification_type="ASSIGNMENT"
                )

            if old_deadline != new_deadline and task.assigned_user_id:
                create_notification(
                    db=db,
                    recipient_ids=[task.assigned_user_id],
                    actor_id=current_user.id,
                    entity_type="Task",
                    entity_id=str(task.id),
                    title="Task deadline updated",
                    message=f"{task.title} deadline has been changed.",
                    link=f"/tasks/{task.id}",
                    notification_type="STATUS_CHANGE"
                )
        
        db.commit()
        return task

    except Exception as e:
        db.rollback()
        raise e


@router.put("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    task_id: str,
    status_data: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update task status (assigned user or team head only).
    """
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    can_update = False
    
    if task.assigned_user_id and str(task.assigned_user_id) == str(current_user.id):
        can_update = True
    
    if task.assigned_team_id:
        from app.models.team import Team
        team = db.query(Team).filter(Team.id == task.assigned_team_id).first()
        if team and str(team.head_user_id) == str(current_user.id):
            can_update = True
    
    if current_user.user_type == "Admin":
        can_update = True
    
    if not can_update:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only assigned user or team head can update task status"
        )
    
    try:
        # Strict Status Transition Logic (Phase 8)
        if status_data.status not in ALLOWED_STATUSES:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {ALLOWED_STATUSES}"
            )

        allowed_next_statuses = VALID_TRANSITIONS.get(task.status, [])
        if status_data.status not in allowed_next_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transition from {task.status} to {status_data.status}. Allowed: {allowed_next_statuses}"
            )
        
        old_status = task.status
        task.status = status_data.status
        db.flush()
        db.refresh(task)
        
        # Activity Log
        log_activity(
            db=db,
            entity_type="Task",
            entity_id=str(task.id),
            action_type="STATUS_CHANGE",
            performed_by_user_id=str(current_user.id),
            old_value={"status": old_status},
            new_value={"status": task.status}
        )
        
        # Notification: STATUS_CHANGE
        # Recipients: Owner + Assignee (if exists)
        recipients = [task.owner_user_id]
        if task.assigned_user_id:
            recipients.append(task.assigned_user_id)
            
        create_notification(
            db=db,
            recipient_ids=recipients,
            actor_id=current_user.id,
            entity_type="Task",
            entity_id=str(task.id),
            title="Task Status Updated",
            message=f"Task '{task.title}' updated to {task.status}",
            link=f"/tasks/{task.id}",
            notification_type="STATUS_CHANGE"
        )
        
        db.commit()
        return task

    except Exception as e:
        db.rollback()
        raise e


@router.post("/{task_id}/transfer", response_model=TaskResponse)
def transfer_task(
    task_id: str,
    transfer_data: TaskTransfer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Transfer task to another user.
    Only "Not Urgent & Not Important" tasks can be transferred.
    Can only transfer to subordinates.
    """
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    if str(task.owner_user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only task owner can transfer task"
        )
    
    if task.urgency_label != "Not Urgent & Not Important":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only 'Not Urgent & Not Important' tasks can be transferred"
        )
    
    new_user = db.query(User).filter(User.id == transfer_data.new_assigned_user_id).first()
    if not new_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New assigned user not found"
        )
    
    # Strict Transfer Logic (Phase 8)
    
    # 1. New assignee must be a subordinate (already checked below, but ensuring logic flow)
    subordinate_ids = get_subordinate_ids(current_user, db)
    if str(transfer_data.new_assigned_user_id) not in subordinate_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only transfer tasks to subordinates"
        )
        
    # 2. Cannot transfer to self (implicit since self is not in subordinate_ids usually, but explicit check is good)
    if str(transfer_data.new_assigned_user_id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot transfer task to yourself"
        )
        
    # 3. Urgency check (Yellow tasks only)
    # PRD: urgency_label == "Not Urgent & Not Important"
    if task.urgency_label != "Not Urgent & Not Important":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only 'Not Urgent & Not Important' tasks can be transferred"
        )
    
    try:
        # Capture old assignee
        old_assignee_id = str(task.assigned_user_id) if task.assigned_user_id else None
        old_owner_id = str(task.owner_user_id)

        task.assigned_user_id = transfer_data.new_assigned_user_id
        task.assigned_team_id = None
        
        # Ownership transfer (only if requested, otherwise ownership preserved)
        if transfer_data.transfer_ownership:
            task.owner_user_id = transfer_data.new_assigned_user_id
        
        db.flush()
        db.refresh(task)
        
        # Activity Log
        new_assignee_id = str(task.assigned_user_id)
        new_owner_id = str(task.owner_user_id)
        
        log_payload_old = {"assigned_user_id": old_assignee_id}
        log_payload_new = {"assigned_user_id": new_assignee_id}
        
        if old_owner_id != new_owner_id:
            log_payload_old["owner_user_id"] = old_owner_id
            log_payload_new["owner_user_id"] = new_owner_id
            
        log_activity(
            db=db,
            entity_type="Task",
            entity_id=str(task.id),
            action_type="TRANSFER",
            performed_by_user_id=str(current_user.id),
            old_value=log_payload_old,
            new_value=log_payload_new
        )
        
        # Notification: ASSIGNMENT (Transfer is an assignment)
        create_notification(
            db=db,
            recipient_ids=[task.assigned_user_id],
            actor_id=current_user.id,
            entity_type="Task",
            entity_id=str(task.id),
            title="Task Transferred to You",
            message=f"You have been transferred task: {task.title}",
            link=f"/tasks/{task.id}",
            notification_type="ASSIGNMENT"
        )
        
        db.commit()
        return task

    except Exception as e:
        db.rollback()
        raise e


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Soft-delete task (owner or admin only).
    """
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    if str(task.owner_user_id) != str(current_user.id) and current_user.user_type != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only task owner or admin can delete task"
        )

    old_snapshot = _task_snapshot(task)
    deleted_by_owner = str(task.owner_user_id) == str(current_user.id)
    task_assignee = task.assigned_user_id
    task_owner = task.owner_user_id

    try:
        task.deleted_at = datetime.now(timezone.utc)
        db.flush()

        log_activity(
            db=db,
            entity_type="Task",
            entity_id=str(task.id),
            action_type="delete",
            performed_by_user_id=str(current_user.id),
            old_value=old_snapshot,
            new_value=None,
        )

        if deleted_by_owner and task_assignee:
            create_notification(
                db=db,
                recipient_ids=[task_assignee],
                actor_id=current_user.id,
                entity_type="Task",
                entity_id=str(task.id),
                title="Task deleted",
                message=f"A task assigned to you has been deleted: {task.title}",
                link=f"/tasks/{task.id}",
                notification_type="STATUS_CHANGE",
            )
        elif current_user.user_type == "Admin":
            create_notification(
                db=db,
                recipient_ids=[task_owner],
                actor_id=current_user.id,
                entity_type="Task",
                entity_id=str(task.id),
                title="Task deleted",
                message=f"A task assigned to you has been deleted: {task.title}",
                link=f"/tasks/{task.id}",
                notification_type="STATUS_CHANGE",
            )

        db.commit()
        return {"message": f"Task '{task.title}' soft-deleted successfully"}
    except Exception as e:
        db.rollback()
        raise e


