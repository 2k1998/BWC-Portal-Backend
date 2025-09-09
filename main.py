from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from routers import (
    auth, tasks, groups, calendar, companies, events, cars, rentals, reports,
    notifications, contacts, daily_calls, projects, sales, payments, car_finance, documents, task_management, chat, approvals, websocket
)
import os, re

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

app = FastAPI(docs_url=None, redoc_url=None, title="BWC Portal API")

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
]

if FRONTEND_URL:
    allow_origins.append(FRONTEND_URL)

allow_origins.extend(EXTRA_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,                 # explicit list (works with credentials if you need later)
    allow_origin_regex=r"^https://.*onrender\.com$",  # also allow Render preview/static site URLs
    allow_credentials=False,                     # you use Bearer tokens, so keep this False (simplifies CORS)
    allow_methods=["*"],
    allow_headers=["*"],                         # includes Authorization, Content-Type, etc.
)

# -----------------------------
# CORS preflight handler
# -----------------------------
@app.options("/{rest_of_path:path}")
def cors_preflight(rest_of_path: str):
    return Response(status_code=204)

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


@app.get("/")
async def read_root():
    return {"message": "Welcome to BWC Portal API!"}
