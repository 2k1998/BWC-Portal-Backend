from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from routers import (
    auth, tasks, groups, calendar, companies, events, cars, rentals, reports,
    notifications, contacts, daily_calls, projects, sales, payments, car_finance, documents, task_management
)
import os, logging

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

app = FastAPI(docs_url=None, redoc_url=None, title="BWC Portal API")

# -----------------------------
# CORS (Render-friendly & lenient)
# -----------------------------
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip()
CORS_EXTRA_ORIGINS = os.getenv("CORS_EXTRA_ORIGINS", "").strip()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
]

if FRONTEND_URL:
    origins.append(FRONTEND_URL)

if CORS_EXTRA_ORIGINS:
    origins.extend([o.strip() for o in CORS_EXTRA_ORIGINS.split(",") if o.strip()])

# If you are NOT using cookies for auth, disable credentials and allow '*'
# This simplifies CORS a lot. You are using Bearer tokens, so this is fine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if FRONTEND_URL else ["*"],  # exact list in prod; '*' fallback if not set
    allow_origin_regex=r"^https://.*onrender\.com$",   # also allow Render preview domains
    allow_credentials=False,                            # IMPORTANT: false so we can use '*' when needed
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.getLogger("uvicorn").info(f"CORS allow_origins: {origins}")

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


@app.get("/")
async def read_root():
    return {"message": "Welcome to BWC Portal API!"}
