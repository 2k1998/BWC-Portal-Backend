from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.company import Company
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse,
    ProjectStatusUpdate
)
from app.utils.activity_logger import log_activity
from app.utils.notification_service import create_notification

router = APIRouter(prefix="/projects", tags=["Projects"])


from app.utils.visibility import can_user_view_project


def build_visibility_filter(current_user: User):
    """Build SQLAlchemy filter for project visibility."""
    if current_user.user_type == "Admin":
        return True
    
    filters = [
        Project.owner_user_id == current_user.id,
        Project.project_manager_user_id == current_user.id,
    ]
    
    return or_(*filters)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new project.
    Validates company and project manager exist.
    """
    company = db.query(Company).filter(Company.id == project_data.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    project_manager = db.query(User).filter(User.id == project_data.project_manager_user_id).first()
    if not project_manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project manager not found"
        )
    
    try:
        project = Project(
            name=project_data.name,
            project_type=project_data.project_type,
            company_id=project_data.company_id,
            priority=project_data.priority,
            description=project_data.description,
            budget_amount=project_data.budget_amount,
            project_manager_user_id=project_data.project_manager_user_id,
            location_address=project_data.location_address,
            location_postcode=project_data.location_postcode,
            start_date=project_data.start_date,
            expected_completion_date=project_data.expected_completion_date,
            status="Planning",
            owner_user_id=current_user.id # Strict owner derivation
        )
        
        db.add(project)
        db.flush() # Generate ID, do not commit yet
        db.refresh(project)
        
        # Activity Log
        log_activity(
            db=db,
            entity_type="Project",
            entity_id=str(project.id),
            action_type="CREATE",
            performed_by_user_id=str(current_user.id),
            old_value=None,
            new_value={
                "name": project.name,
                "status": project.status,
                "owner_user_id": str(project.owner_user_id),
            }
        )
        
        # Notification: ASSIGNMENT (Notify Manager)
        if project.project_manager_user_id:
            create_notification(
                db=db,
                recipient_ids=[project.project_manager_user_id],
                actor_id=current_user.id,
                entity_type="Project",
                entity_id=str(project.id),
                title="Project Assignment",
                message=f"You have been assigned as Manager for project: {project.name}",
                link=f"/projects/{project.id}",
                notification_type="ASSIGNMENT"
            )
        
        db.commit()
        return project

    except Exception as e:
        db.rollback()
        raise e


@router.get("", response_model=ProjectListResponse)
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    project_type_filter: Optional[str] = Query(None, description="Filter by project_type"),
    company_filter: Optional[str] = Query(None, description="Filter by company_id"),
    manager_filter: Optional[str] = Query(None, description="Filter by project_manager_user_id"),
    name_search: Optional[str] = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List projects with visibility filtering.
    Users see only projects they own or manage.
    """
    visibility_filter = build_visibility_filter(current_user)
    query = db.query(Project).filter(visibility_filter)
    
    if status_filter:
        query = query.filter(Project.status == status_filter)
    
    if project_type_filter:
        query = query.filter(Project.project_type == project_type_filter)
    
    if company_filter:
        query = query.filter(Project.company_id == company_filter)
    
    if manager_filter:
        query = query.filter(Project.project_manager_user_id == manager_filter)
    
    if name_search:
        query = query.filter(Project.name.ilike(f"%{name_search}%"))
    
    total = query.count()
    projects = query.order_by(Project.start_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return ProjectListResponse(
        projects=projects,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get project details.
    User must have visibility access to the project.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if not can_user_view_project(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project"
        )
    
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update project metadata (owner only).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if str(project.owner_user_id) != str(current_user.id) and current_user.user_type != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner or admin can update project metadata"
        )
    
    # Capture old state
    old_state = {
        "name": project.name,
        "project_type": project.project_type,
        "company_id": str(project.company_id),
        "priority": project.priority,
        "description": project.description,
        "budget_amount": str(project.budget_amount) if project.budget_amount else None,
        "project_manager_user_id": str(project.project_manager_user_id) if project.project_manager_user_id else None,
        "location_address": project.location_address,
        "location_postcode": project.location_postcode,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "expected_completion_date": project.expected_completion_date.isoformat() if project.expected_completion_date else None
    }

    try:
        if project_data.name is not None:
            project.name = project_data.name
        if project_data.project_type is not None:
            project.project_type = project_data.project_type
        if project_data.company_id is not None:
            company = db.query(Company).filter(Company.id == project_data.company_id).first()
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Company not found"
                )
            project.company_id = project_data.company_id
        if project_data.priority is not None:
            project.priority = project_data.priority
        if project_data.description is not None:
            project.description = project_data.description
        if project_data.budget_amount is not None:
            project.budget_amount = project_data.budget_amount
        if project_data.project_manager_user_id is not None:
            project_manager = db.query(User).filter(User.id == project_data.project_manager_user_id).first()
            if not project_manager:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project manager not found"
                )
            project.project_manager_user_id = project_data.project_manager_user_id
        if project_data.location_address is not None:
            project.location_address = project_data.location_address
        if project_data.location_postcode is not None:
            project.location_postcode = project_data.location_postcode
        if project_data.start_date is not None:
            project.start_date = project_data.start_date
        if project_data.expected_completion_date is not None:
            project.expected_completion_date = project_data.expected_completion_date
        
        db.flush()
        db.refresh(project)
        
        # Capture new state
        new_state = {
            "name": project.name,
            "project_type": project.project_type,
            "company_id": str(project.company_id),
            "priority": project.priority,
            "description": project.description,
            "budget_amount": str(project.budget_amount) if project.budget_amount else None,
            "project_manager_user_id": str(project.project_manager_user_id) if project.project_manager_user_id else None,
            "location_address": project.location_address,
            "location_postcode": project.location_postcode,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "expected_completion_date": project.expected_completion_date.isoformat() if project.expected_completion_date else None
        }
        
        # Calculate diff
        diff_old = {}
        diff_new = {}
        has_changes = False
        
        for key, val in old_state.items():
            if val != new_state.get(key):
                diff_old[key] = val
                diff_new[key] = new_state.get(key)
                has_changes = True
                
        if has_changes:
            log_activity(
                db=db,
                entity_type="Project",
                entity_id=str(project.id),
                action_type="METADATA_UPDATE",
                performed_by_user_id=str(current_user.id),
                old_value=diff_old,
                new_value=diff_new
            )

        # Notification check: If manager changed
        if old_state["project_manager_user_id"] != new_state["project_manager_user_id"] and project.project_manager_user_id:
             create_notification(
                db=db,
                recipient_ids=[project.project_manager_user_id],
                actor_id=current_user.id,
                entity_type="Project",
                entity_id=str(project.id),
                title="Project Assignment",
                message=f"You have been assigned as Manager for project: {project.name}",
                link=f"/projects/{project.id}",
                notification_type="ASSIGNMENT"
            )
        
        db.commit()
        return project

    except Exception as e:
        db.rollback()
        raise e


@router.put("/{project_id}/status", response_model=ProjectResponse)
def update_project_status(
    project_id: str,
    status_data: ProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update project status (owner, manager, or admin).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    can_update = False
    
    if str(project.owner_user_id) == str(current_user.id):
        can_update = True
    
    if str(project.project_manager_user_id) == str(current_user.id):
        can_update = True
    
    if current_user.user_type == "Admin":
        can_update = True
    
    if not can_update:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner, manager, or admin can update project status"
        )
    
    try:
        old_status = project.status
        project.status = status_data.status
        db.flush()
        db.refresh(project)
        
        # Activity Log
        log_activity(
            db=db,
            entity_type="Project",
            entity_id=str(project.id),
            action_type="STATUS_CHANGE",
            performed_by_user_id=str(current_user.id),
            old_value={"status": old_status},
            new_value={"status": project.status}
        )
        
        # Notification: STATUS_CHANGE
        # Recipients: Owner + Manager
        recipients = [project.owner_user_id]
        if project.project_manager_user_id:
            recipients.append(project.project_manager_user_id)
            
        create_notification(
            db=db,
            recipient_ids=recipients,
            actor_id=current_user.id,
            entity_type="Project",
            entity_id=str(project.id),
            title="Project Status Updated",
            message=f"Project '{project.name}' updated to {project.status}",
            link=f"/projects/{project.id}",
            notification_type="STATUS_CHANGE"
        )
        
        db.commit()
        return project

    except Exception as e:
        db.rollback()
        raise e
