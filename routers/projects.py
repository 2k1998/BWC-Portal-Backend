# routers/projects.py - Create this file in your routers folder
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, or_, and_
from typing import List, Optional
from datetime import datetime

from database import get_db
import models, schemas
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/projects", tags=["projects"])

# Add CORS middleware to this router
@router.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

@router.post("/", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new project"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    # Verify company exists
    company = db.query(models.Company).filter(models.Company.id == project.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Verify project manager exists if provided
    if project.project_manager_id:
        manager = db.query(models.User).filter(models.User.id == project.project_manager_id).first()
        if not manager:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project manager not found"
            )
    
    # Create new project
    db_project = models.Project(
        **project.model_dump(),
        created_by_id=current_user.id
    )
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    # Load relationships for response
    db_project = db.query(models.Project).options(
        joinedload(models.Project.company),
        joinedload(models.Project.project_manager),
        joinedload(models.Project.created_by)
    ).filter(models.Project.id == db_project.id).first()
    
    return db_project

@router.get("/", response_model=List[schemas.ProjectListItem])
async def get_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[models.ProjectStatus] = None,
    project_type_filter: Optional[models.ProjectType] = None,
    company_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(name|status|created_at|expected_completion_date|progress_percentage)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all projects with filtering and sorting"""
    
    query = db.query(models.Project).options(
        joinedload(models.Project.company),
        joinedload(models.Project.project_manager)
    )
    
    # Apply filters
    if status_filter:
        query = query.filter(models.Project.status == status_filter)
    
    if project_type_filter:
        query = query.filter(models.Project.project_type == project_type_filter)
    
    if company_id:
        query = query.filter(models.Project.company_id == company_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                models.Project.name.ilike(search_term),
                models.Project.description.ilike(search_term),
                models.Project.store_location.ilike(search_term)
            )
        )
    
    # Apply sorting
    order_func = desc if sort_order == "desc" else asc
    if sort_by == "name":
        query = query.order_by(order_func(models.Project.name))
    elif sort_by == "status":
        query = query.order_by(order_func(models.Project.status))
    elif sort_by == "expected_completion_date":
        query = query.order_by(order_func(models.Project.expected_completion_date))
    elif sort_by == "progress_percentage":
        query = query.order_by(order_func(models.Project.progress_percentage))
    else:  # created_at
        query = query.order_by(order_func(models.Project.created_at))
    
    projects = query.offset(skip).limit(limit).all()
    
    # Transform to list items with computed fields
    project_list = []
    for project in projects:
        project_list.append({
            "id": project.id,
            "name": project.name,
            "project_type": project.project_type,
            "status": project.status,
            "store_location": project.store_location,
            "company_name": project.company.name if project.company else "Unknown",
            "project_manager_name": project.project_manager.full_name if project.project_manager else None,
            "progress_percentage": project.progress_percentage,
            "expected_completion_date": project.expected_completion_date,
            "created_at": project.created_at
        })
    
    return project_list

@router.get("/{project_id}", response_model=schemas.ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific project by ID"""
    
    project = db.query(models.Project).options(
        joinedload(models.Project.company),
        joinedload(models.Project.project_manager),
        joinedload(models.Project.created_by)
    ).filter(models.Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project

@router.put("/{project_id}", response_model=schemas.ProjectResponse)
async def update_project(
    project_id: int,
    project_update: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update a project"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    # Get existing project
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Verify company exists if being updated
    if project_update.company_id:
        company = db.query(models.Company).filter(models.Company.id == project_update.company_id).first()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
    
    # Verify project manager exists if being updated
    if project_update.project_manager_id:
        manager = db.query(models.User).filter(models.User.id == project_update.project_manager_id).first()
        if not manager:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project manager not found"
            )
    
    # Update fields
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_project, field, value)
    
    db_project.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_project)
    
    # Load relationships for response
    db_project = db.query(models.Project).options(
        joinedload(models.Project.company),
        joinedload(models.Project.project_manager),
        joinedload(models.Project.created_by)
    ).filter(models.Project.id == project_id).first()
    
    return db_project

@router.patch("/{project_id}/status", response_model=schemas.ProjectResponse)
async def update_project_status(
    project_id: int,
    status_update: schemas.ProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update project status and progress"""
    check_roles(current_user, ["admin", "Manager", "Head"])
    
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update status fields
    db_project.status = status_update.status
    if status_update.last_update:
        db_project.last_update = status_update.last_update
    if status_update.progress_percentage is not None:
        db_project.progress_percentage = max(0, min(100, status_update.progress_percentage))
    
    # Auto-set completion date if status is completed
    if status_update.status == models.ProjectStatus.completed and not db_project.actual_completion_date:
        db_project.actual_completion_date = datetime.utcnow().date()
    
    db_project.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_project)
    
    # Load relationships for response
    db_project = db.query(models.Project).options(
        joinedload(models.Project.company),
        joinedload(models.Project.project_manager),
        joinedload(models.Project.created_by)
    ).filter(models.Project.id == project_id).first()
    
    return db_project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a project"""
    check_roles(current_user, ["admin"])
    
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    db.delete(db_project)
    db.commit()
    
    return None

@router.get("/stats/overview")
async def get_project_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get project statistics overview"""
    
    total_projects = db.query(models.Project).count()
    active_projects = db.query(models.Project).filter(
        models.Project.status.in_([models.ProjectStatus.planning, models.ProjectStatus.in_progress])
    ).count()
    completed_projects = db.query(models.Project).filter(
        models.Project.status == models.ProjectStatus.completed
    ).count()
    on_hold_projects = db.query(models.Project).filter(
        models.Project.status == models.ProjectStatus.on_hold
    ).count()
    
    # Projects by type
    projects_by_type = {}
    for project_type in models.ProjectType:
        count = db.query(models.Project).filter(models.Project.project_type == project_type).count()
        projects_by_type[project_type.value] = count
    
    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "on_hold_projects": on_hold_projects,
        "projects_by_type": projects_by_type,
        "completion_rate": round((completed_projects / total_projects * 100) if total_projects > 0 else 0, 1)
    }