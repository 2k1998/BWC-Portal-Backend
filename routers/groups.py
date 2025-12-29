from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Group, User, Task  # Ensure User and Task are imported
from schemas import GroupCreate, GroupOut, UserResponse, GroupTaskCreate, TaskResponse, TaskCreate, GroupHeadUpdate
from .auth import get_current_user
from .utils import check_roles, is_admin_or_owner, is_admin_or_group_member

router = APIRouter(prefix="/groups", tags=["groups"])

@router.get("/", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        # Defensive fix for permissions
        if hasattr(current_user, 'permissions'):
            if current_user.permissions is None:
                current_user.permissions = {}
            elif isinstance(current_user.permissions, list):
                current_user.permissions = {}
        
        if current_user.role == "admin":
            groups = db.query(Group).options(joinedload(Group.head), joinedload(Group.members)).all()
        else:
            # Load the groups with head and members relationships
            groups = db.query(Group).options(joinedload(Group.head), joinedload(Group.members)).filter(
                Group.members.any(User.id == current_user.id)
            ).all()
        
        # Fix permissions for all users in the groups
        for group in groups:
            if group.head and hasattr(group.head, 'permissions'):
                if group.head.permissions is None:
                    group.head.permissions = {}
                elif isinstance(group.head.permissions, list):
                    group.head.permissions = {}
            
            for member in group.members:
                if hasattr(member, 'permissions'):
                    if member.permissions is None:
                        member.permissions = {}
                    elif isinstance(member.permissions, list):
                        member.permissions = {}
        
        return groups
    except Exception as e:
        print(f"Error in list_groups: {e}")
        # Return empty list on error to prevent 500
        return []

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

    # Verify head exists if provided
    if group.head_id:
        head = db.query(User).filter(User.id == group.head_id).first()
        if not head:
            raise HTTPException(status_code=404, detail="Head user not found")

    new_group = Group(name=group.name, head_id=group.head_id)
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
    group = db.query(Group).options(joinedload(Group.head), joinedload(Group.members)).filter(Group.id == group_id).first()
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

    # Allow group members and admins to create group tasks
    is_member = current_user in group.members
    is_admin = current_user.role == "admin"
    
    if not (is_admin or is_member):
        raise HTTPException(status_code=403, detail="Not authorized to create tasks for this group")

    new_task = Task(
        title=task.title,
        description=task.description,
        start_date=task.start_date,
        deadline_all_day=task.deadline_all_day,
        deadline=task.deadline,
        urgency=task.urgency,
        important=task.important,
        owner_id=current_user.id,
        created_by_id=current_user.id,
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

    return db.query(Task).filter(
        Task.group_id == group_id,
        Task.deleted_at.is_(None),
    ).all()

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

@router.put("/{group_id}/head", response_model=GroupOut)
def update_group_head(group_id: int, head_update: GroupHeadUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Assign or remove a team head (admin only)"""
    check_roles(current_user, ["admin"])
    
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Verify head exists if provided
    if head_update.head_id:
        head = db.query(User).filter(User.id == head_update.head_id).first()
        if not head:
            raise HTTPException(status_code=404, detail="Head user not found")
        
        # Ensure the head is a member of the group
        if head not in group.members:
            raise HTTPException(status_code=400, detail="Head must be a member of the group")
    
    group.head_id = head_update.head_id
    db.commit()
    db.refresh(group)
    
    return group

@router.get("/{group_id}/head", response_model=UserResponse)
def get_group_head(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get the team head of a group"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if not is_admin_or_group_member(current_user, group.members):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this group's head.")
    
    if not group.head:
        raise HTTPException(status_code=404, detail="No head assigned to this group")
    
    return group.head
