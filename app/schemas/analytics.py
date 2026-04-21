from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field
from uuid import UUID

from app.schemas.task import ALLOWED_STATUSES, ALLOWED_URGENCY_LABELS


class AnalyticsSummaryResponse(BaseModel):
    active_tasks: int
    overdue_tasks: int
    completed_last_30_days: int
    tasks_created_this_month: int
    total_companies: int
    total_users: int


class AnalyticsTaskRow(BaseModel):
    id: UUID
    title: str
    company_name: str
    assignee_name: Optional[str] = None
    owner_name: str
    status: str
    urgency_label: str
    deadline: Optional[date] = None


class AnalyticsTaskListResponse(BaseModel):
    tasks: List[AnalyticsTaskRow]
    total: int
    page: int
    page_size: int


class TasksPerCompanyRow(BaseModel):
    company_id: UUID
    company_name: str
    task_count: int


class TasksPerCompanyResponse(BaseModel):
    items: List[TasksPerCompanyRow]


class TasksPerUserRow(BaseModel):
    user_id: UUID
    user_name: str
    task_count: int


class TasksPerUserResponse(BaseModel):
    items: List[TasksPerUserRow]


class CompletedSeriesRow(BaseModel):
    date: date
    completed_count: int


class CompletedSeriesResponse(BaseModel):
    items: List[CompletedSeriesRow]


class AnalyticsTaskFilters(BaseModel):
    company_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[str] = Field(None, description="Task status filter")
    urgency_label: Optional[str] = Field(None, description="Task urgency filter")

    @staticmethod
    def validate_status_value(value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ALLOWED_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(ALLOWED_STATUSES)}")
        return value

    @staticmethod
    def validate_urgency_value(value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ALLOWED_URGENCY_LABELS:
            raise ValueError(f"urgency_label must be one of: {', '.join(ALLOWED_URGENCY_LABELS)}")
        return value
