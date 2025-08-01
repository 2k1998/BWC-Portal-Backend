from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Basic endpoints
@app.get("/")
def read_root():
    return {"message": "Welcome to BWC Portal API!", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Add database setup
try:
    from database import Base, engine
    Base.metadata.create_all(bind=engine)
    print("Database setup complete!")
except Exception as e:
    print(f"Database error: {e}")

# Add routers one by one
try:
    from routers.auth import router as auth_router
    app.include_router(auth_router)
    print("Auth router added")
except Exception as e:
    print(f"Auth router error: {e}")

try:
    from routers.companies import router as companies_router
    app.include_router(companies_router)
    print("Companies router added")
except Exception as e:
    print(f"Companies router error: {e}")

try:
    from routers.tasks import router as tasks_router
    app.include_router(tasks_router)
    print("Tasks router added")
except Exception as e:
    print(f"Tasks router error: {e}")

# Add other routers with error handling
router_modules = [
    "groups", "calendar", "events", "cars", "rentals", 
    "reports", "notifications", "contacts", "daily_calls"
]

for module_name in router_modules:
    try:
        module = __import__(f"routers.{module_name}", fromlist=["router"])
        app.include_router(module.router)
        print(f"{module_name} router added")
    except Exception as e:
        print(f"{module_name} router error: {e}")

print("=== BWC Portal API Started Successfully ===")
