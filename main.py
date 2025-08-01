from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
import os

# --- CREATE APP FIRST ---
app = FastAPI(docs_url=None, redoc_url=None, title="BWC Portal API")

# --- ADD CORS IMMEDIATELY (BEFORE ANYTHING ELSE) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("CORS middleware added with wildcard origins!")

# --- ADD BASIC HEALTH CHECK ---
@app.get("/")
def read_root():
    return {"message": "Welcome to BWC Portal API!", "cors": "enabled"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "API is running", "cors": "enabled"}

print("Basic endpoints created!")

# --- DATABASE SETUP ---
try:
    from database import Base, engine
    from models import User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, Notification, Contact, DailyCall, TaskHistory

    print("Database imports successful!")
    # Create database tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

except Exception as e:
    print(f"Database setup error: {e}")
    print("Continuing without database setup...")

# --- STATIC FILES ---
try:
    os.makedirs("uploads", exist_ok=True)
    app.mount("/static", StaticFiles(directory="uploads"), name="static")
    print("Static files setup successful!")
except Exception as e:
    print(f"Static files error: {e}")

# --- DOCS ENDPOINT ---
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )

# --- ADD ROUTERS ---
try:
    from routers import auth, tasks, groups, calendar, companies, events, cars, rentals, reports, notifications, contacts, daily_calls

    app.include_router(auth.router)
    print("Auth router added!")

    app.include_router(tasks.router)
    print("Tasks router added!")

    app.include_router(groups.router)
    print("Groups router added!")

    app.include_router(calendar.router)
    print("Calendar router added!")

    app.include_router(companies.router)
    print("Companies router added!")

    app.include_router(events.router)
    print("Events router added!")

    app.include_router(cars.router)
    print("Cars router added!")

    app.include_router(rentals.router)
    print("Rentals router added!")

    app.include_router(reports.router)
    print("Reports router added!")

    app.include_router(notifications.router)
    print("Notifications router added!")

    app.include_router(contacts.router)
    print("Contacts router added!")

    app.include_router(daily_calls.router)
    print("Daily calls router added!")

    print("All routers added successfully!")

except Exception as e:
    print(f"Router setup error: {e}")
    print("Some routers may not be available")

print("=== APPLICATION STARTUP COMPLETE ===")
print("FastAPI app is ready to serve requests with CORS enabled!")
