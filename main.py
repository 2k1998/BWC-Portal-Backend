from fastapi import FastAPI, Response, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from routers import (
    auth, tasks, groups, calendar, companies, events, cars, rentals, reports,
    notifications, contacts, daily_calls, projects, sales, payments, car_finance, documents, task_management, chat, approvals, websocket
)
from routers.auth import get_current_user
import models
import os, re
import logging
import time
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

app = FastAPI(docs_url=None, redoc_url=None, title="BWC Portal API")

# Global exception handler to ensure CORS headers are always present
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
    # Add CORS headers even to error responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# Database initialization and migration
@app.on_event("startup")
async def startup_event():
    """Run database migrations and setup on startup"""
    try:
        logger.info("Starting database initialization...")
        
        # Import and run the migrations
        from add_user_columns_migration import migrate_users_add_columns
        from add_created_by_migration import migrate_tasks_add_created_by
        from add_projects_created_by_migration import migrate_projects_add_created_by
        from add_group_head_migration import run_migration as migrate_group_head
        from fix_permissions_migration import migrate_permissions
        
        logger.info("Running user columns migration...")
        migrate_users_add_columns()
        
        logger.info("Running created_by migration...")
        migrate_tasks_add_created_by()
        
        logger.info("Running projects created_by migration...")
        migrate_projects_add_created_by()
        
        logger.info("Running groups head_id migration...")
        try:
            migrate_group_head()
        except Exception as e:
            logger.warning(f"Group head_id migration skipped/failed: {e}")
        
        logger.info("Running permissions migration...")
        try:
            migrate_permissions()
        except Exception as e:
            logger.warning(f"Permissions migration failed: {e}")
        
        # Import and run the table creation
        from database import Base, engine
        from models import (
            User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, 
            Notification, Contact, DailyCall, TaskHistory, Project,
            Sale, EmployeeCommissionRule, MonthlyCommissionSummary, Payment,
            CarIncome, CarExpense, TaskAssignment, TaskConversation, TaskMessage, 
            TaskNotification, ChatConversation, ChatMessage, ApprovalRequest, 
            ApprovalNotification, Document
        )
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialization completed successfully")
        
        # Run seed data if needed
        try:
            from seed import seed_database
            seed_database()
            logger.info("Database seeding completed")
        except Exception as seed_error:
            logger.warning(f"Database seeding failed (this may be normal if data already exists): {seed_error}")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Don't raise the exception to prevent the app from crashing
        # The error will be logged and the app will continue

# -----------------------------
# CORS (Render-friendly)
# -----------------------------
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip()
EXTRA_ORIGINS = [o.strip() for o in os.getenv("CORS_EXTRA_ORIGINS", "").split(",") if o.strip()]

# Always keep localhost for dev
allow_origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "https://bwc-portal-frontend.onrender.com",  # Add explicit frontend domain
    "https://bwc-portal-frontend-w1qr.onrender.com",  # Add your actual frontend domain
]

if FRONTEND_URL:
    allow_origins.append(FRONTEND_URL)

allow_origins.extend(EXTRA_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],                         # Allow all origins for now to fix the issue
    allow_credentials=False,                     # Disable credentials when allowing all origins
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],                         # includes Authorization, Content-Type, etc.
)

# Add request logging and CORS middleware
@app.middleware("http")
async def log_requests_and_cors(request: Request, call_next):
    start_time = time.time()
    
    # Log request details
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Origin: {request.headers.get('origin', 'No Origin')}")
    
    response = await call_next(request)
    
    # Add CORS headers to all responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Max-Age"] = "86400"
    
    # Log response details
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} in {process_time:.4f}s")
    
    return response

# -----------------------------
# CORS preflight handler (moved after routers to avoid conflicts)
# -----------------------------

# -----------------------------
# Static files (serve uploaded files)
# -----------------------------
app.mount("/static", StaticFiles(directory="uploads"), name="static")

# -----------------------------
# Swagger UI (since docs_url=None)
# -----------------------------
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="BWC Portal API Docs")

# -----------------------------
# Routers
# -----------------------------
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(groups.router)
app.include_router(calendar.router)
app.include_router(companies.router)
app.include_router(events.router)
app.include_router(cars.router)
app.include_router(rentals.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(contacts.router)
app.include_router(daily_calls.router)
app.include_router(projects.router)
app.include_router(sales.router)
app.include_router(payments.router)
app.include_router(car_finance.router)
app.include_router(documents.router)
app.include_router(task_management.router)
app.include_router(chat.router)
app.include_router(approvals.router)
app.include_router(websocket.router)

# -----------------------------
# CORS preflight handlers (after routers to avoid conflicts)
# -----------------------------

# Specific CORS handler for tasks endpoint
@app.options("/tasks/")
def tasks_cors_preflight():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        }
    )

@app.options("/tasks")
def tasks_cors_preflight_no_slash():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        }
    )

@app.options("/projects")
def projects_cors_preflight():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        }
    )

@app.options("/projects/")
def projects_cors_preflight_with_slash():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        }
    )

@app.get("/")
async def read_root():
    return {"message": "Welcome to BWC Portal API!"}

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/cors-test")
async def cors_test():
    """Test endpoint for CORS debugging"""
    return {"cors": "working", "message": "If you can see this, CORS is working!"}

@app.post("/cors-test")
async def cors_test_post():
    """Test POST endpoint for CORS debugging"""
    return {"cors": "working", "method": "POST", "message": "POST requests are working!"}

@app.get("/tasks-test")
async def tasks_test():
    """Test tasks endpoint for CORS debugging"""
    return {"tasks": "working", "message": "Tasks endpoint is accessible!"}

@app.post("/tasks-test")
async def tasks_test_post():
    """Test tasks POST endpoint for CORS debugging"""
    return {"tasks": "working", "method": "POST", "message": "Tasks POST is working!"}

@app.get("/tasks-simple")
async def tasks_simple():
    """Simple tasks endpoint for CORS testing"""
    return {"message": "Simple tasks endpoint working!"}

@app.get("/projects-test")
async def projects_test():
    """Test projects endpoint for CORS debugging"""
    return {"projects": "working", "message": "Projects endpoint is accessible!"}

@app.post("/projects-test")
async def projects_test_post():
    """Test projects POST endpoint for CORS debugging"""
    return {"projects": "working", "method": "POST", "message": "Projects POST is working!"}

@app.get("/test-auth")
async def test_auth(current_user: models.User = Depends(get_current_user)):
    """Test endpoint for authentication"""
    return {"auth": "working", "user": current_user.email}

@app.post("/admin/seed-database")
async def manual_seed_database(current_user: models.User = Depends(get_current_user)):
    """Manual endpoint to seed the database - Admin only"""
    from .routers.utils import check_roles
    check_roles(current_user, ["admin"])
    
    try:
        from seed import seed_database
        seed_database()
        return {"status": "success", "message": "Database seeded successfully"}
    except Exception as e:
        logger.error(f"Manual seeding failed: {e}")
        raise HTTPException(status_code=500, detail=f"Seeding failed: {str(e)}")

@app.get("/debug/companies")
async def debug_companies():
    """Debug endpoint to check if companies exist"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        companies = db.query(models.Company).all()
        return {
            "count": len(companies),
            "companies": [{"id": c.id, "name": c.name} for c in companies]
        }
    finally:
        db.close()


