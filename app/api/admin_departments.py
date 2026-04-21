from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse, DepartmentListResponse

router = APIRouter(prefix="/admin/departments", tags=["Admin - Departments"])


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new department (admin only).
    Department name must be unique.
    """
    # Check if department name already exists
    existing = db.query(Department).filter(
        func.lower(Department.name) == func.lower(department_data.name)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with name '{department_data.name}' already exists"
        )
    
    # Create department
    department = Department(name=department_data.name)
    
    db.add(department)
    db.commit()
    db.refresh(department)
    
    return department


@router.get("", response_model=DepartmentListResponse)
def list_departments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all departments (admin only).
    """
    # Get total count
    total = db.query(Department).count()
    
    # Apply pagination
    departments = db.query(Department).order_by(Department.name).offset((page - 1) * page_size).limit(page_size).all()
    
    return DepartmentListResponse(
        departments=departments,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department(
    department_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get department details by ID (admin only).
    """
    department = db.query(Department).filter(Department.id == department_id).first()
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    return department


@router.put("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: str,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update department name (admin only).
    """
    department = db.query(Department).filter(Department.id == department_id).first()
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Check if new name conflicts with existing department
    if department_data.name != department.name:
        existing = db.query(Department).filter(
            func.lower(Department.name) == func.lower(department_data.name),
            Department.id != department_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with name '{department_data.name}' already exists"
            )
    
    # Update name
    department.name = department_data.name
    
    db.commit()
    db.refresh(department)
    
    return department
