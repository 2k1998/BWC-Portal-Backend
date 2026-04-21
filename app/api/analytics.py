from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Date, and_, cast, func, or_
from sqlalchemy.orm import Session, aliased

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.company import Company
from app.models.task import Task
from app.models.team import Team
from app.models.user import User
from app.schemas.analytics import (
    CompletedSeriesResponse,
    AnalyticsSummaryResponse,
    AnalyticsTaskListResponse,
    AnalyticsTaskRow,
    CompletedSeriesRow,
    TasksPerCompanyResponse,
    TasksPerCompanyRow,
    TasksPerUserResponse,
    TasksPerUserRow,
)
from app.schemas.task import ALLOWED_STATUSES, ALLOWED_URGENCY_LABELS
from app.utils.cache import TTLCache
from app.utils.permissions import check_user_permission, get_user_hierarchy


router = APIRouter(prefix="/analytics", tags=["Analytics"])

_cache = TTLCache(ttl_seconds=60)


def _require_analytics_permission(db: Session, current_user: User) -> None:
    permission = check_user_permission(db=db, user=current_user, page_key="analytics")
    if permission == "none":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access Analytics",
        )


def _cache_key(endpoint: str, current_user: User, **params: object) -> tuple:
    normalized = []
    for key in sorted(params.keys()):
        value = params[key]
        if isinstance(value, (datetime, date)):
            normalized_value = value.isoformat()
        else:
            normalized_value = str(value)
        normalized.append((key, normalized_value))
    return (endpoint, str(current_user.id), tuple(normalized))


def _get_scope_user_ids(db: Session, current_user: User) -> Optional[list[UUID]]:
    if current_user.user_type in ("Admin", "Pillar"):
        return None
    if current_user.user_type == "Manager":
        hierarchy = get_user_hierarchy(db, current_user.id)
        ids = [current_user.id] + [u.id for u in hierarchy]
        return ids
    return [current_user.id]


def _build_task_scope_filter(db: Session, current_user: User):
    scope_user_ids = _get_scope_user_ids(db, current_user)
    if scope_user_ids is None:
        return True
    return or_(Task.owner_user_id.in_(scope_user_ids), Task.assigned_user_id.in_(scope_user_ids))


def _active_tasks_filter():
    return Task.status != "Completed"


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_analytics_permission(db=db, current_user=current_user)
    key = _cache_key("summary", current_user)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    today = datetime.now(timezone.utc).date()
    month_start = date(today.year, today.month, 1)
    completed_since = datetime.now(timezone.utc) - timedelta(days=30)

    scope_filter = _build_task_scope_filter(db=db, current_user=current_user)

    active_tasks_count = db.query(func.count(Task.id)).filter(scope_filter, _active_tasks_filter()).scalar() or 0
    overdue_tasks_count = (
        db.query(func.count(Task.id))
        .filter(scope_filter, _active_tasks_filter(), Task.deadline < today)
        .scalar()
        or 0
    )
    # completed_at is not available in current schema; updated_at on completed tasks is used as completion proxy.
    completed_last_30_days = (
        db.query(func.count(Task.id))
        .filter(scope_filter, Task.status == "Completed", Task.updated_at >= completed_since)
        .scalar()
        or 0
    )
    tasks_created_this_month = (
        db.query(func.count(Task.id))
        .filter(scope_filter, Task.created_at >= month_start)
        .scalar()
        or 0
    )

    scope_user_ids = _get_scope_user_ids(db, current_user)
    if scope_user_ids is None:
        total_users = db.query(func.count(User.id)).scalar() or 0
        total_companies = db.query(func.count(Company.id)).scalar() or 0
    else:
        total_users = db.query(func.count(User.id)).filter(User.id.in_(scope_user_ids)).scalar() or 0
        total_companies = (
            db.query(func.count(func.distinct(Task.company_id)))
            .filter(scope_filter)
            .scalar()
            or 0
        )

    result = AnalyticsSummaryResponse(
        active_tasks=active_tasks_count,
        overdue_tasks=overdue_tasks_count,
        completed_last_30_days=completed_last_30_days,
        tasks_created_this_month=tasks_created_this_month,
        total_companies=total_companies,
        total_users=total_users,
    )
    _cache.set(key, result)
    return result


@router.get("/tasks", response_model=AnalyticsTaskListResponse)
def get_analytics_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    company_id: Optional[UUID] = Query(None),
    user_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    urgency_label: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_analytics_permission(db=db, current_user=current_user)
    if status_filter is not None and status_filter not in ALLOWED_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status. Must be one of: {ALLOWED_STATUSES}")
    if urgency_label is not None and urgency_label not in ALLOWED_URGENCY_LABELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid urgency_label. Must be one of: {ALLOWED_URGENCY_LABELS}",
        )

    key = _cache_key(
        "tasks",
        current_user,
        page=page,
        page_size=page_size,
        company_id=company_id,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        urgency_label=urgency_label,
    )
    cached = _cache.get(key)
    if cached is not None:
        return cached

    scope_filter = _build_task_scope_filter(db=db, current_user=current_user)
    owner_user = aliased(User)
    assignee_user = aliased(User)

    query = (
        db.query(
            Task.id.label("task_id"),
            Task.title,
            Company.name.label("company_name"),
            owner_user.first_name.label("owner_first_name"),
            owner_user.last_name.label("owner_last_name"),
            assignee_user.first_name.label("assignee_first_name"),
            assignee_user.last_name.label("assignee_last_name"),
            Team.name.label("team_name"),
            Task.status,
            Task.urgency_label,
            Task.deadline,
        )
        .join(Company, Company.id == Task.company_id)
        .join(owner_user, owner_user.id == Task.owner_user_id)
        .outerjoin(assignee_user, assignee_user.id == Task.assigned_user_id)
        .outerjoin(Team, Team.id == Task.assigned_team_id)
        .filter(scope_filter)
    )

    if company_id is not None:
        query = query.filter(Task.company_id == company_id)
    if user_id is not None:
        query = query.filter(or_(Task.owner_user_id == user_id, Task.assigned_user_id == user_id))
    if date_from is not None:
        query = query.filter(Task.created_at >= date_from)
    if date_to is not None:
        query = query.filter(Task.created_at < (date_to + timedelta(days=1)))
    if status_filter is not None:
        query = query.filter(Task.status == status_filter)
    if urgency_label is not None:
        query = query.filter(Task.urgency_label == urgency_label)

    total = query.count()
    rows = query.order_by(Task.deadline.asc()).offset((page - 1) * page_size).limit(page_size).all()

    tasks = []
    for row in rows:
        owner_name = f"{row.owner_first_name} {row.owner_last_name}".strip()
        assignee_name = None
        if row.assignee_first_name or row.assignee_last_name:
            assignee_name = f"{row.assignee_first_name or ''} {row.assignee_last_name or ''}".strip()
        elif row.team_name:
            assignee_name = f"Team: {row.team_name}"

        tasks.append(
            AnalyticsTaskRow(
                id=row.task_id,
                title=row.title,
                company_name=row.company_name,
                assignee_name=assignee_name,
                owner_name=owner_name,
                status=row.status,
                urgency_label=row.urgency_label,
                deadline=row.deadline,
            )
        )

    result = AnalyticsTaskListResponse(tasks=tasks, total=total, page=page, page_size=page_size)
    _cache.set(key, result)
    return result


@router.get("/tasks-per-company", response_model=TasksPerCompanyResponse)
def get_tasks_per_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_analytics_permission(db=db, current_user=current_user)
    key = _cache_key("tasks-per-company", current_user)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    scope_filter = _build_task_scope_filter(db=db, current_user=current_user)

    rows = (
        db.query(
            Company.id.label("company_id"),
            Company.name.label("company_name"),
            func.count(Task.id).label("task_count"),
        )
        .join(Task, Task.company_id == Company.id)
        .filter(scope_filter, _active_tasks_filter())
        .group_by(Company.id, Company.name)
        .order_by(func.count(Task.id).desc(), Company.name.asc())
        .all()
    )

    result = TasksPerCompanyResponse(
        items=[TasksPerCompanyRow(company_id=row.company_id, company_name=row.company_name, task_count=row.task_count) for row in rows]
    )
    _cache.set(key, result)
    return result


@router.get("/tasks-per-user", response_model=TasksPerUserResponse)
def get_tasks_per_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_analytics_permission(db=db, current_user=current_user)
    key = _cache_key("tasks-per-user", current_user)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    scope_filter = _build_task_scope_filter(db=db, current_user=current_user)

    rows = (
        db.query(
            User.id.label("user_id"),
            User.first_name.label("first_name"),
            User.last_name.label("last_name"),
            func.count(Task.id).label("task_count"),
        )
        .join(Task, Task.assigned_user_id == User.id)
        .filter(scope_filter, _active_tasks_filter(), Task.assigned_user_id.isnot(None))
        .group_by(User.id, User.first_name, User.last_name)
        .order_by(func.count(Task.id).desc(), User.first_name.asc(), User.last_name.asc())
        .all()
    )

    result = TasksPerUserResponse(
        items=[
            TasksPerUserRow(
                user_id=row.user_id,
                user_name=f"{row.first_name} {row.last_name}".strip(),
                task_count=row.task_count,
            )
            for row in rows
        ]
    )
    _cache.set(key, result)
    return result


@router.get("/users")
def get_analytics_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_analytics_permission(db=db, current_user=current_user)
    scope_user_ids = _get_scope_user_ids(db, current_user)

    query = db.query(User).filter(User.is_active.is_(True))
    if scope_user_ids is not None:
        query = query.filter(User.id.in_(scope_user_ids))

    users = query.order_by(User.first_name.asc(), User.last_name.asc(), User.username.asc()).all()
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


@router.get("/completed", response_model=CompletedSeriesResponse)
def get_completed_series(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_analytics_permission(db=db, current_user=current_user)
    key = _cache_key("completed", current_user, date_from=date_from, date_to=date_to)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    scope_filter = _build_task_scope_filter(db=db, current_user=current_user)
    completed_date_expr = cast(Task.updated_at, Date)

    conditions = [scope_filter, Task.status == "Completed"]
    if date_from is not None:
        conditions.append(completed_date_expr >= date_from)
    if date_to is not None:
        conditions.append(completed_date_expr <= date_to)

    rows = (
        db.query(
            completed_date_expr.label("completed_date"),
            func.count(Task.id).label("completed_count"),
        )
        .filter(and_(*conditions))
        .group_by(completed_date_expr)
        .order_by(completed_date_expr.asc())
        .all()
    )

    result = CompletedSeriesResponse(
        items=[CompletedSeriesRow(date=row.completed_date, completed_count=row.completed_count) for row in rows]
    )
    _cache.set(key, result)
    return result

