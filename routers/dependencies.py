from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, Task, Group
from .auth import get_current_user

def get_task_for_update(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Task:
    """
    Fetches a task by its ID and verifies if the current user has permission to update it.
    
    Permissions are granted if the user is:
    1. The owner of the task (ONLY OWNERS CAN EDIT TASKS)
    2. An admin (can edit any task)
    
    Raises HTTPException if the task is not found or the user is not authorized.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Only task owners and admins can edit tasks
    is_owner = task.owner_id == current_user.id
    is_admin = current_user.role == "admin"

    # If the user is not the owner or admin, deny access
    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the task owner can edit this task."
        )
    
    return task