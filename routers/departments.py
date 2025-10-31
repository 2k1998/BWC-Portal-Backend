# routes/departments.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models_department import Department
from models import User
from .auth import get_current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    role = (getattr(current_user, "role", None) or "").lower()
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins only"
        )
    return current_user

router = APIRouter(prefix="/departments", tags=["departments"])

# PUBLIC: dropdown data source
@router.get("", response_model=list[dict])
def list_departments(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Department).where(Department.is_active == True).order_by(Department.name.asc())
    ).scalars().all()
    return [{"id": d.id, "name": d.name} for d in rows]

# ADMIN: add a department
@router.post("", status_code=status.HTTP_201_CREATED)
def create_department(payload: dict, db: Session = Depends(get_db), user = Depends(require_admin)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Name is required")
    exists = db.execute(select(Department).where(Department.name.ilike(name))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Department already exists")
    d = Department(name=name, created_by=getattr(user, "id", None))
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"id": d.id, "name": d.name, "is_active": d.is_active}

# ADMIN: optional archive (soft delete)
@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_department(dept_id: int, db: Session = Depends(get_db), user = Depends(require_admin)):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(404, "Not found")
    d.is_active = False
    db.add(d)
    db.commit()
