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
    1. The owner of the task.
    2. An admin.
    3. A member of the group the task is assigned to.

    Raises HTTPException if the task is not found or the user is not authorized.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # --- THIS IS THE CORRECTED LOGIC ---
    is_owner = task.owner_id == current_user.id
    is_admin = current_user.role == "admin"
    
    # Check if the user is a member of the task's group, if it has one
    is_group_member = False
    if task.group_id:
        if any(group.id == task.group_id for group in current_user.groups):
            is_group_member = True

    # If the user does not meet any of the criteria, deny access
    if not (is_owner or is_admin or is_group_member):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this task."
        )
    
    return task
    # --- END OF CORRECTION ---