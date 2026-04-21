from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID

from app.models.user import User
from app.models.permission import UserPagePermission


def check_user_permission(db: Session, user: User, page_key: str) -> str:
    """
    Check user's permission level for a specific page.
    
    Permission evaluation order (per PRD #0):
    1. Admin override - admins have full access to everything
    2. Explicit page permission
    3. Default to 'none'
    
    Args:
        db: Database session
        user: User object
        page_key: Page key to check permission for
    
    Returns:
        Permission level: 'none', 'read', or 'full'
    """
    # Admin override - admins bypass all permission checks
    if user.user_type == "Admin":
        return "full"
    
    # Check explicit page permission
    from app.models.page import Page
    
    page = db.query(Page).filter(Page.key == page_key).first()
    if not page:
        return "none"
    
    permission = db.query(UserPagePermission).filter(
        UserPagePermission.user_id == user.id,
        UserPagePermission.page_id == page.id
    ).first()
    
    if permission:
        return permission.access
    
    # Default to no access
    return "none"


def get_user_hierarchy(db: Session, user_id: UUID) -> List[User]:
    """
    Get all subordinates for a user (recursive).
    
    Args:
        db: Database session
        user_id: User ID to get subordinates for
    
    Returns:
        List of all subordinate users
    """
    subordinates = []
    
    # Get direct subordinates
    direct_subordinates = db.query(User).filter(User.manager_id == user_id).all()
    
    for subordinate in direct_subordinates:
        subordinates.append(subordinate)
        # Recursively get subordinates of subordinates
        subordinates.extend(get_user_hierarchy(db, subordinate.id))
    
    return subordinates
