from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import secrets
import string
from uuid import UUID

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import hash_password
from app.models.user import User
from app.models.permission import UserPagePermission
from app.models.page import Page
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse, ALLOWED_USER_TYPES
from app.schemas.permission import SetPermissionsRequest, PagePermissionResponse, ALLOWED_ACCESS_LEVELS
from app.utils.audit import create_audit_log

router = APIRouter(prefix="/admin/users", tags=["Admin - User Management"])


def generate_temporary_password(length: int = 12) -> str:
    """Generate a random temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(require_admin),
):
    """
    Get current admin user's information.
    """
    return current_user


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Create a new user (admin only).
    Generates temporary password and forces password change on first login.
    """
    # Validate user_type
    if user_data.user_type not in ALLOWED_USER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user_type. Must be one of: {', '.join(ALLOWED_USER_TYPES)}"
        )
    
    # Check if email already exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Validate manager exists if provided
    if user_data.manager_id:
        manager = db.query(User).filter(User.id == user_data.manager_id).first()
        if not manager:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manager not found"
            )
    
    # Generate temporary password
    temp_password = generate_temporary_password()
    
    # Create user
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        hashed_password=hash_password(temp_password),
        user_type=user_data.user_type,
        manager_id=user_data.manager_id,
        force_password_change=True,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create audit log
    create_audit_log(
        db=db,
        admin_user_id=str(admin.id),
        target_user_id=str(new_user.id),
        action="create_user",
        before_state=None,
        # REDACTED: Do not log generated passwords
        after_state={
            "email": new_user.email,
            "username": new_user.username,
            "user_type": new_user.user_type,
            "manager_id": str(new_user.manager_id) if new_user.manager_id else None
        }
    )
    
    # Return explicit structure with plaintext password (ONCE)
    return {
        "user_id": new_user.id,
        "email": new_user.email,
        "username": new_user.username,
        "first_name": new_user.first_name,
        "last_name": new_user.last_name,
        "user_type": new_user.user_type,
        "is_active": new_user.is_active,
        "manager_id": new_user.manager_id,
        "generated_password": temp_password
    }


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    List all users with pagination and filters (admin only).
    """
    query = db.query(User)
    
    # Apply filters
    if user_type:
        if user_type not in ALLOWED_USER_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user_type. Must be one of: {', '.join(ALLOWED_USER_TYPES)}"
            )
        query = query.filter(User.user_type == user_type)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Get user details by ID (admin only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Update user details (admin only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Capture before state
    before_state = {
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "user_type": user.user_type,
        "is_active": user.is_active,
        "manager_id": str(user.manager_id) if user.manager_id else None
    }
    
    # Validate and update fields
    if user_data.email is not None:
        # Check if email already exists (excluding current user)
        existing = db.query(User).filter(User.email == user_data.email, User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        user.email = user_data.email
    
    if user_data.username is not None:
        # Check if username already exists (excluding current user)
        existing = db.query(User).filter(User.username == user_data.username, User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        user.username = user_data.username
    
    if user_data.first_name is not None:
        user.first_name = user_data.first_name
    
    if user_data.last_name is not None:
        user.last_name = user_data.last_name
    
    if user_data.user_type is not None:
        if user_data.user_type not in ALLOWED_USER_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user_type. Must be one of: {', '.join(ALLOWED_USER_TYPES)}"
            )
        user.user_type = user_data.user_type
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    if user_data.manager_id is not None:
        # Validate manager exists
        manager = db.query(User).filter(User.id == user_data.manager_id).first()
        if not manager:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manager not found"
            )
        # Prevent circular reference (user cannot be their own manager)
        if user_data.manager_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User cannot be their own manager"
            )
        user.manager_id = user_data.manager_id
    
    db.commit()
    db.refresh(user)
    
    # Capture after state
    after_state = {
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "user_type": user.user_type,
        "is_active": user.is_active,
        "manager_id": str(user.manager_id) if user.manager_id else None
    }
    
    # Create audit log
    create_audit_log(
        db=db,
        admin_user_id=str(admin.id),
        target_user_id=str(user.id),
        action="update_user",
        before_state=before_state,
        after_state=after_state
    )
    
    return user



@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Reset user password (admin only).
    Generates new random password and returns it plaintext ONCE.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate new password
    new_password = generate_temporary_password()
    
    # Capture before state
    before_state = {"action": "password_reset_requested"}
    
    # Update password
    user.hashed_password = hash_password(new_password)
    user.force_password_change = True
    db.commit()
    
    # Create audit log
    create_audit_log(
        db=db,
        admin_user_id=str(admin.id),
        target_user_id=str(user.id),
        action="reset_password",
        before_state=before_state,
        # REDACTED: Never log the new password
        after_state={"password_reset": True}
    )
    
    return {"generated_password": new_password}


@router.post("/{user_id}/permissions", response_model=List[PagePermissionResponse])
def set_user_permissions(
    user_id: UUID,
    permissions_data: SetPermissionsRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Set page permissions for a user (admin only).
    Replaces all existing permissions.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate all access levels
    for perm in permissions_data.permissions:
        if perm.access not in ALLOWED_ACCESS_LEVELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid access level '{perm.access}'. Must be one of: {', '.join(ALLOWED_ACCESS_LEVELS)}"
            )
    
    # Validate all pages exist
    page_ids = [perm.page_id for perm in permissions_data.permissions]
    pages = db.query(Page).filter(Page.id.in_(page_ids)).all()
    
    if len(pages) != len(page_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more page IDs are invalid"
        )
    
    # Capture before state
    existing_perms = db.query(UserPagePermission).filter(
        UserPagePermission.user_id == user_id
    ).all()
    before_state = {
        "permissions": [
            {"page_id": str(p.page_id), "access": p.access}
            for p in existing_perms
        ]
    }
    
    # Delete existing permissions
    db.query(UserPagePermission).filter(UserPagePermission.user_id == user_id).delete()
    
    # Create new permissions
    new_permissions = []
    for perm_data in permissions_data.permissions:
        perm = UserPagePermission(
            user_id=user_id,
            page_id=perm_data.page_id,
            access=perm_data.access
        )
        db.add(perm)
        new_permissions.append(perm)
    
    db.commit()
    
    # Refresh all permissions
    for perm in new_permissions:
        db.refresh(perm)
    
    # Capture after state
    after_state = {
        "permissions": [
            {"page_id": str(p.page_id), "access": p.access}
            for p in new_permissions
        ]
    }
    
    # Create audit log
    create_audit_log(
        db=db,
        admin_user_id=str(admin.id),
        target_user_id=str(user_id),
        action="set_permissions",
        before_state=before_state,
        after_state=after_state
    )
    
    return new_permissions


@router.post("/{user_id}/deactivate")
def deactivate_user(  # Legacy POST endpoint kept for backward compatibility
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Deactivate a user (admin only).
    Prevents login but keeps historical references intact.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent deactivating yourself
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    # Capture before state
    before_state = {"is_active": user.is_active}
    
    # Deactivate user
    user.is_active = False
    db.commit()
    
    # Capture after state
    after_state = {"is_active": user.is_active}
    
    # Create audit log
    create_audit_log(
        db=db,
        admin_user_id=str(admin.id),
        target_user_id=str(user.id),
        action="deactivate_user",
        before_state=before_state,
        after_state=after_state
    )
    
    return {"message": "User deactivated successfully"}


@router.patch("/{user_id}/deactivate")
def deactivate_user_patch(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Deactivate a user (admin only).
    PATCH variant per current API spec.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    before_state = {"is_active": user.is_active}
    user.is_active = False
    db.commit()
    after_state = {"is_active": user.is_active}

    create_audit_log(
        db=db,
        admin_user_id=str(admin.id),
        target_user_id=str(user.id),
        action="deactivate_user",
        before_state=before_state,
        after_state=after_state
    )

    return {"message": "User deactivated successfully"}


@router.patch("/{user_id}/activate")
def activate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Activate a user (admin only).
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    before_state = {"is_active": user.is_active}
    user.is_active = True
    db.commit()
    after_state = {"is_active": user.is_active}

    create_audit_log(
        db=db,
        admin_user_id=str(admin.id),
        target_user_id=str(user.id),
        action="activate_user",
        before_state=before_state,
        after_state=after_state
    )

    return {"message": "User activated successfully"}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Permanently delete a user (admin only).
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    try:
        db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to delete user due to related records"
        )

    create_audit_log(
        db=db,
        admin_user_id=str(admin.id),
        target_user_id=str(user_id),
        action="delete_user",
        before_state={"id": str(user_id)},
        after_state=None
    )

    return None
