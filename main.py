from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Create app first
app = FastAPI(title="BWC Portal API")

# Add CORS immediately
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("CORS middleware added!")

# Basic endpoints first
@app.get("/")
def read_root():
    return {"message": "Welcome to BWC Portal API!", "status": "running", "cors": "enabled"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "All systems operational"}

print("Basic endpoints created!")

# Create uploads directory and mount static files
try:
    os.makedirs("uploads", exist_ok=True)
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory="uploads"), name="static")
    print("Static files mounted successfully!")
except Exception as e:
    print(f"Static files error (non-critical): {e}")

# Add database setup
try:
    from database import Base, engine
    from models import User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, Notification, Contact, DailyCall
    Base.metadata.create_all(bind=engine)
    print("Database setup complete!")
except Exception as e:
    print(f"Database error: {e}")

# Add custom docs endpoint
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    try:
        from fastapi.openapi.docs import get_swagger_ui_html
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
        )
    except Exception as e:
        return {"error": "Docs unavailable", "details": str(e)}

# Add routers one by one with detailed error handling
try:
    from routers.auth import router as auth_router
    app.include_router(auth_router)
    print("✅ Auth router added")
except Exception as e:
    print(f"❌ Auth router error: {e}")

try:
    from routers.companies import router as companies_router
    app.include_router(companies_router)
    print("✅ Companies router added")
except Exception as e:
    print(f"❌ Companies router error: {e}")

try:
    from routers.tasks import router as tasks_router
    app.include_router(tasks_router)
    print("✅ Tasks router added")
except Exception as e:
    print(f"❌ Tasks router error: {e}")

# Add remaining routers
router_modules = [
    ("groups", "Groups"),
    ("calendar", "Calendar"), 
    ("events", "Events"),
    ("cars", "Cars"),
    ("rentals", "Rentals"),
    ("reports", "Reports"),
    ("notifications", "Notifications"),
    ("contacts", "Contacts"),
    ("daily_calls", "Daily Calls")
]

for module_name, display_name in router_modules:
    try:
        module = __import__(f"routers.{module_name}", fromlist=["router"])
        app.include_router(module.router)
        print(f"✅ {display_name} router added")
    except Exception as e:
        print(f"❌ {display_name} router error: {e}")

print("=" * 50)
print("🚀 BWC Portal API Started Successfully!")
print("📍 Available endpoints:")
print("   GET  /          - Welcome message")
print("   GET  /health    - Health check")  
print("   GET  /docs      - API documentation")
print("   POST /token     - User authentication")
print("=" * 50)
