from fastapi import APIRouter, Depends, HTTPException, Response, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_
from database import get_db
from models import (
    Task,
    User,
    Group,
    Notification,
    TaskHistory,
    TaskAssignment,
    TaskAssignmentStatus,
)  # <-- Import TaskHistory
from schemas import TaskCreate, TaskResponse, TaskUpdate, TaskStatusUpdate, TaskStatusEnum
from .auth import get_current_user
from .utils import check_roles
from .dependencies import get_task_for_update
from datetime import datetime, timedelta  # <-- timedelta added
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("/test")
def test_tasks_cors():
    """Test endpoint for CORS debugging on tasks router"""
    return {"message": "Tasks router CORS is working!"}

@router.post("/", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Allow all authenticated users to create tasks
    
    # Use provided owner_id or default to current user
    task_owner_id = task.owner_id if task.owner_id is not None else current_user.id

    # Check if the specified owner exists
    owner = db.query(User).filter(User.id == task_owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail=f"User with id {task_owner_id} not found.")

    group_record = None
    if task.group_id is not None:
        group_record = (
            db.query(Group)
            .options(joinedload(Group.members))
            .filter(Group.id == task.group_id)
            .first()
        )
        if not group_record:
            raise HTTPException(status_code=404, detail=f"Group with id {task.group_id} not found.")

    # Create a dictionary from the task schema, excluding fields we've already handled
    task_data = task.dict(exclude={"owner_id", "assignee_ids"})
    
    # Create task with both owner and creator information
    # Handle case where created_by_id column might not exist yet
    try:
        new_task = Task(**task_data, owner_id=task_owner_id, created_by_id=current_user.id)
    except TypeError as e:
        if "created_by_id" in str(e):
            # Fallback: create task without created_by_id if column doesn't exist
            logger.warning("created_by_id column not found, creating task without it")
            new_task = Task(**task_data, owner_id=task_owner_id)
        else:
            raise

    completed_raw = task_data.get("completed", None)
    completed_flag = bool(completed_raw) if completed_raw is not None else False
    new_task.completed = completed_flag
    try:
        if hasattr(Task, "completed_at"):
            new_task.completed_at = datetime.utcnow() if completed_flag else None
    except Exception:
        pass

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    notifications_to_add: list[Notification] = []
    assignments_to_add: list[TaskAssignment] = []

    if new_task.owner_id != current_user.id:
        notifications_to_add.append(
            Notification(
                user_id=new_task.owner_id,
                message=f"{current_user.full_name} has assigned you a new task: '{new_task.title}'",
                link="/tasks",
            )
        )

    assignee_ids: list[int] = []
    if task.assignee_ids:
        try:
            assignee_ids = [int(uid) for uid in task.assignee_ids if uid is not None]
        except (TypeError, ValueError):
            logger.warning("Invalid assignee_ids provided during task creation: %s", task.assignee_ids)
            assignee_ids = []

    if task_owner_id and task_owner_id not in assignee_ids:
        assignee_ids.insert(0, task_owner_id)

    if group_record and group_record.members:
        for member in group_record.members:
            if member and member.id is not None:
                assignee_ids.append(member.id)

    seen_ids: set[int] = set()
    ordered_assignees: list[int] = []
    for uid in assignee_ids:
        if uid not in seen_ids:
            seen_ids.add(uid)
            ordered_assignees.append(uid)

    additional_assignee_ids = [uid for uid in ordered_assignees if uid != task_owner_id]

    for assigned_to_id in additional_assignee_ids:
        assigned_user = db.query(User).filter(User.id == assigned_to_id).first()
        if not assigned_user:
            logger.warning("Skipping assignment for unknown user id %s", assigned_to_id)
            continue

        assignments_to_add.append(
            TaskAssignment(
                task_id=new_task.id,
                assigned_by_id=current_user.id,
                assigned_to_id=assigned_to_id,
                assignment_status=TaskAssignmentStatus.pending_acceptance,
            )
        )

        notifications_to_add.append(
            Notification(
                user_id=assigned_to_id,
                message=f"{current_user.full_name} has assigned you a new task: '{new_task.title}'",
                link="/tasks",
            )
        )

    for assignment in assignments_to_add:
        db.add(assignment)

    for notification in notifications_to_add:
        db.add(notification)

    if assignments_to_add or notifications_to_add:
        db.commit()

    return new_task

@router.get("/", response_model=list[TaskResponse])
def list_my_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    importance: str | None = Query(
        None, description="One of: urgent, important, urgent_important, none"
    ),
    user_name: str | None = Query(None, description="Filter by user name (icontains)"),
    user_id: int | None = Query(None, description="Filter by exact user id"),
    company_id: int | None = Query(None, description="Filter by exact company id"),
):
    try:
        if not hasattr(current_user, "permissions") or current_user.permissions is None:
            current_user.permissions = {}
        elif isinstance(current_user.permissions, list):
            current_user.permissions = {}

        q = db.query(Task).filter(Task.deleted_at.is_(None))

        if (current_user.role or "").lower() != "admin":
            user_group_ids = [g.id for g in current_user.groups]
            groups_headed = db.query(Group).filter(Group.head_id == current_user.id).all()
            headed_group_ids = [g.id for g in groups_headed]
            all_group_ids = list(set(user_group_ids + headed_group_ids))

            q = q.filter(
                or_(
                    Task.owner_id == current_user.id,
                    Task.group_id.in_(all_group_ids) if all_group_ids else False,
                )
            )

        if company_id:
            q = q.filter(Task.company_id == company_id)

        if user_id:
            q = q.filter(Task.owner_id == user_id)

        if user_name:
            q = (
                q.join(User, User.id == Task.owner_id, isouter=True)
                .filter(
                    or_(
                        User.username.ilike(f"%{user_name}%"),
                        User.first_name.ilike(f"%{user_name}%"),
                        User.last_name.ilike(f"%{user_name}%"),
                    )
                )
            )

        if importance:
            key = importance.lower()
            if key == "urgent":
                q = q.filter(and_(Task.urgency.is_(True), Task.important.is_(False)))
            elif key == "important":
                q = q.filter(and_(Task.important.is_(True), Task.urgency.is_(False)))
            elif key == "urgent_important":
                q = q.filter(and_(Task.urgency.is_(True), Task.important.is_(True)))
            elif key == "none":
                q = q.filter(and_(Task.urgency.is_(False), Task.important.is_(False)))

        q = q.order_by(Task.deadline.is_(None), Task.deadline.asc().nulls_last())

        tasks = q.options(
            joinedload(Task.owner),
            joinedload(Task.created_by),
            joinedload(Task.status_updater),
            joinedload(Task.company),
        ).all()

        logger.info(
            f"User {current_user.id} ({current_user.email}) retrieved {len(tasks)} tasks with filters"
        )
        return tasks

    except Exception as e:
        logger.error(
            f"Error in list_my_tasks for user {current_user.id}: {str(e)}",
            exc_info=True,
        )
        return []


@router.get("/completed-tasks/list", response_model=list[TaskResponse])
def list_completed_tasks(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Task)
    q = q.filter(Task.deleted_at.is_(None))

    if hasattr(Task, "completed_at"):
        q = q.filter(Task.completed_at.isnot(None))
        if days and days > 0:
            cutoff = datetime.utcnow() - timedelta(days=days)
            q = q.filter(Task.completed_at >= cutoff)
    else:
        q = q.filter(Task.completed.is_(True))

    if (current_user.role or "").lower() != "admin":
        q = q.filter(Task.owner_id == current_user.id)

    q = q.order_by(
        Task.completed_at.desc() if hasattr(Task, "completed_at") else Task.id.desc()
    )

    return q.options(
        joinedload(Task.owner),
        joinedload(Task.company),
    ).all()


@router.get("/deleted-tasks/list", response_model=list[TaskResponse])
def list_deleted_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cutoff = datetime.utcnow() - timedelta(days=90)

    if (current_user.role or "").lower() == "admin":
        db.query(Task).filter(
            Task.deleted_at.isnot(None),
            Task.deleted_at < cutoff,
        ).delete(synchronize_session=False)
        db.commit()

    q = db.query(Task).filter(
        Task.deleted_at.isnot(None),
        Task.deleted_at >= cutoff,
    )

    if (current_user.role or "").lower() != "admin":
        user_group_ids = [g.id for g in current_user.groups]
        groups_headed = db.query(Group).filter(Group.head_id == current_user.id).all()
        headed_group_ids = [g.id for g in groups_headed]
        all_group_ids = list(set(user_group_ids + headed_group_ids))

        q = q.filter(
            or_(
                Task.owner_id == current_user.id,
                Task.group_id.in_(all_group_ids) if all_group_ids else False,
            )
        )

    return q.order_by(Task.deleted_at.desc()).options(
        joinedload(Task.owner),
        joinedload(Task.company),
    ).all()


@router.delete("/deleted-tasks/{task_id}", status_code=204)
def permanently_delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.isnot(None)).first()
    if not task:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    is_admin = current_user.role == "admin"
    is_owner = task.owner_id == current_user.id
    is_group_head = False
    if task.group_id:
        group = db.query(Group).filter(Group.id == task.group_id).first()
        if group and group.head_id == current_user.id:
            is_group_head = True

    if not (is_admin or is_owner or is_group_head):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this task.")

    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{task_id}", response_model=TaskResponse)
def read_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    include_deleted: bool = Query(False, description="Include deleted tasks"),
):
    """
    Retrieves a single task with its full history, including the names of users who made changes.
    """
    # Use joinedload to efficiently fetch the task, its history, and the user for each history entry
    task_query = db.query(Task).options(
        joinedload(Task.history).joinedload(TaskHistory.changed_by)
    ).filter(Task.id == task_id)
    if not include_deleted:
        task_query = task_query.filter(Task.deleted_at.is_(None))
    task = task_query.first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Authorization logic
    is_owner = task.owner_id == current_user.id
    is_admin = current_user.role == "admin"
    is_member = False
    if task.group_id:
        group = db.query(Group).filter(Group.id == task.group_id).first()
        if group and current_user in group.members:
            is_member = True

    if not (is_admin or is_owner or is_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this task.")
    
    return task

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_update: TaskUpdate,
    task: Task = Depends(get_task_for_update),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    update_data = task_update.dict(exclude_unset=True)
    comment = update_data.pop('comment', None)
    completed_update = update_data.pop('completed', None)

    # Store the original status before any changes
    original_status = task.status

    # Apply updates for fields other than status
    for field, value in update_data.items():
        if field != 'status':
            setattr(task, field, value)

    # Handle status change and create TaskHistory entry
    new_status = update_data.get('status')
    if new_status and new_status != original_status:
        history_entry = TaskHistory(
            task_id=task.id,
            changed_by_id=current_user.id,
            status_from=original_status,
            status_to=new_status,
            comment=comment
        )
        db.add(history_entry)
        task.status = new_status

        # Notify admins about the status change, except the one who made the change
        admins = db.query(User).filter(User.role == 'admin').all()
        for admin in admins:
            if admin.id != current_user.id:
                notification = Notification(
                    user_id=admin.id,
                    message=f"Task '{task.title}' status changed to '{new_status.value}' by {current_user.full_name}.",
                    link=f"/tasks/{task.id}"
                )
                db.add(notification)
    elif comment:
        history_entry = TaskHistory(
            task_id=task.id,
            changed_by_id=current_user.id,
            comment=comment
        )
        db.add(history_entry)

    if completed_update is not None:
        was_completed = bool(task.completed)
        now_completed = bool(completed_update)
        task.completed = now_completed
        try:
            if hasattr(Task, "completed_at"):
                if now_completed and not was_completed:
                    task.completed_at = datetime.utcnow()
                elif not now_completed and was_completed:
                    task.completed_at = None
        except Exception:
            pass

    db.commit()
    db.refresh(task)
    return task

@router.put("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    task_id: int, 
    status_update: TaskStatusUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Allow users to update the status of tasks assigned to them or their groups.
    Admins can update any task status.
    """
    # Get the task with owner and group information
    task = db.query(Task).options(joinedload(Task.owner), joinedload(Task.group)).filter(
        Task.id == task_id,
        Task.deleted_at.is_(None),
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check permissions: Admin, task owner, or group member can update status
    can_update = (
        current_user.role == "admin" or
        task.owner_id == current_user.id or
        (task.group_id and task.group in current_user.groups)
    )
    
    if not can_update:
        raise HTTPException(
            status_code=403, 
            detail="You don't have permission to update this task's status"
        )
    
    # Validate loose_end status requires comments
    if status_update.status == TaskStatusEnum.LOOSE_END and not status_update.status_comments:
        raise HTTPException(
            status_code=400, 
            detail="Comments are required when setting status to 'loose_end'"
        )
    
    # Update the task status
    task.status = status_update.status
    task.status_comments = status_update.status_comments
    task.status_updated_at = datetime.utcnow()
    task.status_updated_by = current_user.id

    # Mark completed flag
    task.completed = (status_update.status == TaskStatusEnum.COMPLETED)

    # Maintain completed_at **safely** (only if the column exists)
    try:
        if hasattr(Task, "completed_at"):
            if status_update.status == TaskStatusEnum.COMPLETED:
                task.completed_at = datetime.utcnow()
            else:
                task.completed_at = None
    except Exception as _e:
        # Don't break status updates if the column isn't present
        pass
    
    db.commit()
    db.refresh(task)
    return task

@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # This endpoint remains the same
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    is_admin = current_user.role == "admin"
    is_owner = task.owner_id == current_user.id
    is_group_head = False
    if task.group_id:
        group = db.query(Group).filter(Group.id == task.group_id).first()
        if group and group.head_id == current_user.id:
            is_group_head = True

    if not (is_admin or is_owner or is_group_head):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this task.")

    if task.deleted_at is None:
        task.deleted_at = datetime.utcnow()
        task.deleted_by_id = current_user.id
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{task_id}/status-history")
def get_task_status_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    include_deleted: bool = Query(False, description="Include deleted tasks"),
):
    """
    Get the status change history for a task
    """
    # Check if user can view this task
    task_query = db.query(Task).filter(Task.id == task_id)
    if not include_deleted:
        task_query = task_query.filter(Task.deleted_at.is_(None))
    task = task_query.first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Permission check (same as status update)
    can_view = (
        current_user.role == "admin" or 
        task.owner_id == current_user.id or 
        (task.group_id and task.group in current_user.groups)
    )
    
    if not can_view:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # You could create a TaskStatusHistory model to track all changes
    # For now, return the current status info
    return {
        "task_id": task_id,
        "current_status": task.status,
        "status_comments": task.status_comments,
        "status_updated_at": task.status_updated_at,
        "status_updated_by": task.status_updated_by,
        "updater_name": task.status_updater.full_name if task.status_updater else None
    }
