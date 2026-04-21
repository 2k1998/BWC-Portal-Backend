from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.company import Company
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyListResponse, CompanyResponse, CompanyUpdate
from app.utils.activity_logger import log_activity
from app.utils.notification_service import create_notification
from app.utils.permissions import check_user_permission

router = APIRouter(tags=["Companies"])


def _company_snapshot(company: Company) -> dict:
    return {
        "name": company.name,
        "vat_number": company.vat_number,
        "occupation": company.occupation,
        "creation_date": company.creation_date.isoformat() if company.creation_date else None,
        "description": company.description,
    }


def _require_companies_permission(
    *,
    db: Session,
    current_user: User,
    required: str,
):
    permission = check_user_permission(db=db, user=current_user, page_key="companies")
    if permission != required:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access Companies")


def _require_companies_read(db: Session, current_user: User) -> None:
    permission = check_user_permission(db=db, user=current_user, page_key="companies")
    if permission == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access Companies")


def _table_exists(db: Session, table_name: str) -> bool:
    inspector = inspect(db.get_bind())
    return table_name in inspector.get_table_names()


def _has_payment_or_car_reference(db: Session, *, table_name: str, company_id: UUID) -> bool:
    if not _table_exists(db, table_name):
        return False

    stmt = text(f"SELECT 1 FROM {table_name} WHERE company_id = :company_id LIMIT 1")
    row = db.execute(stmt, {"company_id": company_id}).first()
    return row is not None


@router.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    company_data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission = check_user_permission(db=db, user=current_user, page_key="companies")
    if permission != "full":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to create companies")

    existing = db.query(Company).filter(Company.name == company_data.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Company with name '{company_data.name}' already exists")

    company = Company(
        name=company_data.name,
        vat_number=company_data.vat_number,
        occupation=company_data.occupation,
        creation_date=company_data.creation_date,
        description=company_data.description,
    )

    try:
        db.add(company)
        db.flush()  # ensure company.id exists before logging/notifications
        db.refresh(company)

        log_activity(
            db=db,
            entity_type="Company",
            entity_id=str(company.id),
            action_type="create",
            performed_by_user_id=str(current_user.id),
            old_value=None,
            new_value=_company_snapshot(company),
        )

        recipients = db.query(User).filter(User.user_type.in_(["Admin", "Pillar"])).all()
        recipient_ids = [u.id for u in recipients]
        create_notification(
            db=db,
            recipient_ids=recipient_ids,
            actor_id=None,
            entity_type="Company",
            entity_id=str(company.id),
            title="Company Created",
            message=f"Company '{company.name}' was created by {current_user.first_name} {current_user.last_name}.",
            link=f"/companies/{company.id}",
            notification_type="STATUS_CHANGE",
        )

        db.commit()
        db.refresh(company)
        return company
    except Exception as e:
        db.rollback()
        raise e


@router.get("/companies", response_model=CompanyListResponse)
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    name_search: Optional[str] = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_companies_read(db=db, current_user=current_user)

    query = db.query(Company).filter(Company.deleted_at.is_(None))
    if name_search:
        query = query.filter(Company.name.ilike(f"%{name_search}%"))

    total = query.count()
    companies = (
        query.order_by(Company.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
    )

    return CompanyListResponse(companies=companies, total=total, page=page, page_size=page_size)


@router.get("/companies/{id}", response_model=CompanyResponse)
def get_company(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_companies_read(db=db, current_user=current_user)

    company = db.query(Company).filter(Company.id == id, Company.deleted_at.is_(None)).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return company


@router.put("/companies/{id}", response_model=CompanyResponse)
def update_company(
    id: UUID,
    company_data: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission = check_user_permission(db=db, user=current_user, page_key="companies")
    if permission != "full":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to update companies")

    company = db.query(Company).filter(Company.id == id, Company.deleted_at.is_(None)).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if company_data.name is not None and company_data.name != company.name:
        existing = db.query(Company).filter(Company.name == company_data.name, Company.id != id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Company with name '{company_data.name}' already exists")

    old_snapshot = _company_snapshot(company)

    if company_data.name is not None:
        company.name = company_data.name
    if company_data.vat_number is not None:
        company.vat_number = company_data.vat_number
    if company_data.occupation is not None:
        company.occupation = company_data.occupation
    if company_data.description is not None:
        company.description = company_data.description

    try:
        db.flush()
        db.refresh(company)

        log_activity(
            db=db,
            entity_type="Company",
            entity_id=str(company.id),
            action_type="update",
            performed_by_user_id=str(current_user.id),
            old_value=old_snapshot,
            new_value=_company_snapshot(company),
        )

        recipients = db.query(User).filter(User.user_type.in_(["Admin", "Pillar"])).all()
        recipient_ids = [u.id for u in recipients]
        create_notification(
            db=db,
            recipient_ids=recipient_ids,
            actor_id=None,
            entity_type="Company",
            entity_id=str(company.id),
            title="Company Updated",
            message=f"Company '{company.name}' was updated by {current_user.first_name} {current_user.last_name}.",
            link=f"/companies/{company.id}",
            notification_type="STATUS_CHANGE",
        )

        db.commit()
        db.refresh(company)
        return company
    except Exception as e:
        db.rollback()
        raise e


@router.delete("/companies/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    company = db.query(Company).filter(Company.id == id, Company.deleted_at.is_(None)).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    reference_sources: list[str] = []

    has_tasks = _table_exists(db, "tasks") and db.query(Task.id).filter(Task.company_id == id).first() is not None
    if has_tasks:
        reference_sources.append("tasks")

    has_projects = _table_exists(db, "projects") and db.query(Project.id).filter(Project.company_id == id).first() is not None
    if has_projects:
        reference_sources.append("projects")

    if _has_payment_or_car_reference(db, table_name="payments", company_id=id):
        reference_sources.append("payments")

    if reference_sources:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company cannot be deleted because it is referenced by: {', '.join(reference_sources)}",
        )

    old_snapshot = _company_snapshot(company)

    try:
        db.delete(company)  # hard delete

        log_activity(
            db=db,
            entity_type="Company",
            entity_id=str(id),
            action_type="delete",
            performed_by_user_id=str(current_user.id),
            old_value=old_snapshot,
            new_value=None,
        )

        recipients = db.query(User).filter(User.user_type.in_(["Admin", "Pillar"])).all()
        recipient_ids = [u.id for u in recipients]
        create_notification(
            db=db,
            recipient_ids=recipient_ids,
            actor_id=None,
            entity_type="Company",
            entity_id=str(id),
            title="Company Deleted",
            message=f"Company '{company.name}' was deleted by {current_user.first_name} {current_user.last_name}.",
            link=f"/companies/{id}",
            notification_type="STATUS_CHANGE",
        )

        db.commit()
        return None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company cannot be deleted because it is referenced by other records",
        )
