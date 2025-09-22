from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from database import get_db
from models import Task, User, Group, Notification, TaskHistory  # <-- Import TaskHistory
from schemas import TaskCreate, TaskResponse, TaskUpdate, TaskStatusUpdate, TaskStatusEnum
from .auth import get_current_user
from .utils import check_roles
from .dependencies import get_task_for_update
from datetime import datetime
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

    # Create a dictionary from the task schema, excluding the owner_id we've already handled
    task_data = task.dict(exclude={"owner_id"})
    
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
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    # Notify the new owner if they are not the creator
    if new_task.owner_id != current_user.id:
        notification = Notification(
            user_id=new_task.owner_id,
            message=f"{current_user.full_name} has assigned you a new task: '{new_task.title}'",
            link="/tasks"
        )
        db.add(notification)
        db.commit()

    return new_task

@router.get("/", response_model=list[TaskResponse])
def list_my_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        # Defensive fix for permissions
        if hasattr(current_user, 'permissions'):
            if current_user.permissions is None:
                current_user.permissions = {}
            elif isinstance(current_user.permissions, list):
                current_user.permissions = {}
        
        if current_user.role == "admin":
            return db.query(Task).all()
        else:
            # Get personal tasks and tasks from all groups the user is in
            user_group_ids = [group.id for group in current_user.groups]
            
            # Get groups where user is the head
            groups_headed = db.query(Group).filter(Group.head_id == current_user.id).all()
            headed_group_ids = [group.id for group in groups_headed]
            
            # Combine all group IDs (member + head)
            all_group_ids = list(set(user_group_ids + headed_group_ids))
            
            return db.query(Task).filter(
                (Task.owner_id == current_user.id) |
                (Task.group_id.in_(all_group_ids))
            ).all()
    except Exception as e:
        logger.error(f"Error in list_my_tasks: {e}")
        # Return empty list on error to prevent 500
        return []

@router.get("/{task_id}", response_model=TaskResponse)
def read_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Retrieves a single task with its full history, including the names of users who made changes.
    """
    # Use joinedload to efficiently fetch the task, its history, and the user for each history entry
    task = db.query(Task).options(
        joinedload(Task.history).joinedload(TaskHistory.changed_by)
    ).filter(Task.id == task_id).first()

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
    task = db.query(Task).options(joinedload(Task.owner), joinedload(Task.group)).filter(Task.id == task_id).first()
    
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

    # FIX: Change COMPLETE to COMPLETED
    task.completed = (status_update.status == TaskStatusEnum.COMPLETED)  # <-- FIXED!
    
    db.commit()
    db.refresh(task)
    return task

@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # This endpoint remains the same
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not (current_user.role == "admin" or task.owner_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this task.")

    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{task_id}/status-history")
def get_task_status_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the status change history for a task
    """
    # Check if user can view this task
    task = db.query(Task).filter(Task.id == task_id).first()
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