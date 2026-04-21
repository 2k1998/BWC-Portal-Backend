from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("")
def search_users(
    query: str = Query("", min_length=0, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = query.strip()

    users_q = db.query(User).filter(User.is_active.is_(True), User.id != current_user.id)
    if q:
        pattern = f"%{q}%"
        users_q = users_q.filter(
            or_(
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.username.ilike(pattern),
                User.email.ilike(pattern),
            )
        )

    users = users_q.order_by(User.first_name.asc(), User.last_name.asc(), User.username.asc()).limit(limit).all()
    return {
        "users": [
            {
                "id": str(user.id),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "email": user.email,
            }
            for user in users
        ]
    }
