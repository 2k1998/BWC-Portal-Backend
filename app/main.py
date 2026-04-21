from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.admin_users import router as admin_users_router
from app.api.companies import router as companies_router
from app.api.admin_departments import router as admin_departments_router
from app.api.teams import router as teams_router
from app.api.tasks import router as tasks_router
from app.api.projects import router as projects_router
from app.api.events import router as events_router
from app.api.documents import router as documents_router
from app.api.activity_logs import router as activity_logs_router
from app.api.notifications import router as notifications_router
from app.api.contacts import router as contacts_router
from app.api.daily_calls import router as daily_calls_router
from app.api.payments import router as payments_router
from app.api.cars import router as cars_router
from app.api.profile import router as profile_router
from app.api.presence import router as presence_router
from app.api.chat import router as chat_router
from app.api.approvals import router as approvals_router
from app.api.analytics import router as analytics_router
from app.api.users import router as users_router
from app.routers.departments import router as departments_router
from app.services.daily_call_reminder_service import (
    start_daily_call_reminder_loop,
    stop_daily_call_reminder_loop,
)
from app.services.retention_jobs import start_retention_scheduler, stop_retention_scheduler
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_daily_call_reminder_loop()
    start_retention_scheduler()
    try:
        yield
    finally:
        stop_retention_scheduler()
        stop_daily_call_reminder_loop()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for BWC Task Manager",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(companies_router)
app.include_router(admin_departments_router)
app.include_router(teams_router)
app.include_router(tasks_router)
app.include_router(projects_router)
app.include_router(events_router)
app.include_router(documents_router)
app.include_router(activity_logs_router)
app.include_router(notifications_router)
app.include_router(contacts_router)
app.include_router(daily_calls_router)
app.include_router(payments_router)
app.include_router(cars_router)
app.include_router(profile_router)
app.include_router(presence_router)
app.include_router(chat_router)
app.include_router(approvals_router)
app.include_router(analytics_router)
app.include_router(users_router)
app.include_router(departments_router)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "BWC Task Manager API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

