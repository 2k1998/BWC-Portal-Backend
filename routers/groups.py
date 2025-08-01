from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from database import get_db
from models import Group, User, Task  # Ensure User and Task are imported
from schemas import GroupCreate, GroupOut, UserResponse, GroupTaskCreate, TaskResponse, TaskCreate
from .auth import get_current_user
from .utils import check_roles, is_admin_or_owner, is_admin_or_group_member

router = APIRouter(prefix="/groups", tags=["groups"])

@router.get("/", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "admin":
        return db.query(Group).all()
    else:
        return current_user.groups

@router.post("/{group_id}/add-user/{user_id}")
def add_user_to_group(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    check_roles(current_user, ["admin"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user in group.members:
        raise HTTPException(status_code=400, detail="User already in group")

    group.members.append(user)
    db.commit()
    return {"message": f"User {user.email} added to group {group.name}"}

@router.post("/", response_model=GroupOut)
def create_group(group: GroupCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_roles(current_user, ["admin"])

    existing = db.query(Group).filter(Group.name == group.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group already exists")

    new_group = Group(name=group.name)
    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    new_group.members.append(current_user)
    db.commit()
    db.refresh(new_group)

    return new_group

@router.get("/{group_id}/members", response_model=list[UserResponse])
def get_group_members(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if not is_admin_or_group_member(current_user, group.members):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view members of this group.")

    return group.members

@router.get("/{group_id}", response_model=GroupOut)
def get_group_by_id(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if not is_admin_or_group_member(current_user, group.members):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this group's details (only admin or member)."
        )
    return group

@router.post("/{group_id}/assign-task", response_model=TaskResponse)
def create_group_task(group_id: int, task: GroupTaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    check_roles(current_user, ["admin"])

    new_task = Task(
        title=task.title,
        description=task.description,
        # --- NEW: Add start_date and deadline_all_day ---
        start_date=task.start_date,
        deadline_all_day=task.deadline_all_day,
        # --- END NEW ---
        deadline=task.deadline,
        urgency=task.urgency,
        important=task.important,
        owner_id=current_user.id,
        group_id=group_id
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@router.get("/{group_id}/tasks", response_model=list[TaskResponse])
def get_group_tasks(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if not is_admin_or_group_member(current_user, group.members):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view tasks of this group.")

    return db.query(Task).filter(Task.group_id == group_id).all()

@router.delete("/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_roles(current_user, ["admin"])

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    return Response(status_code=204)

@router.delete("/{group_id}/remove-user/{user_id}")
def remove_user_from_group(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(Group).filter(Group.id == group_id).first()
    user_to_remove = db.query(User).filter(User.id == user_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if not user_to_remove:
        raise HTTPException(status_code=404, detail="User not found")

    if not current_user.role == "admin" and current_user not in group.members:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to remove members from this group.")

    if user_to_remove not in group.members:
        raise HTTPException(status_code=400, detail="User is not a member of this group")

    if not current_user.role == "admin":
        if user_to_remove.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot remove yourself from the group via this endpoint. Please contact an admin.")
        if user_to_remove.role == "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an admin can remove another admin.")

    group.members.remove(user_to_remove)
    db.commit()
    return {"message": f"User {user_to_remove.email} removed from group {group.name}"}