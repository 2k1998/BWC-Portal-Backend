# routers/utils.py
from fastapi import HTTPException, status
from models import User  # Import User model

def check_roles(current_user: User, allowed_roles: list[str]):
    """
    Checks if the current_user has at least one of the allowed roles.
    Raises HTTPException if not authorized.
    """
    # --- NEW: Debug print for role check ---
    print(f"DEBUG_ROLE: Checking user ID {current_user.id} ({current_user.email}) with role '{current_user.role}' against allowed roles: {allowed_roles}")
    # --- END NEW ---
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action. Insufficient role."
        )

def is_admin_or_owner(current_user: User, owner_id: int):
    """
    Checks if the current_user is an 'admin' or the owner of a resource.
    """
    return current_user.role == "admin" or current_user.id == owner_id

def is_admin_or_group_member(current_user: User, group_members: list[User]):
    """
    Checks if the current_user is an 'admin' or a member of the given group.
    """
    return current_user.role == "admin" or current_user in group_members