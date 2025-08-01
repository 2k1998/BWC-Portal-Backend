from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # Import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from routers import auth, tasks, groups, calendar, companies, events, cars, rentals, reports, notifications, contacts, daily_calls
import os

# --- THE FIX: Configure static file serving ---
# Create a directory for uploads if it doesn't exist
os.makedirs("uploads", exist_ok=True)

app = FastAPI(docs_url=None, redoc_url=None, title="BWC Portal API")

# Mount the 'uploads' directory to be served at the '/static' path
# This line tells FastAPI how to serve the profile pictures.
app.mount("/static", StaticFiles(directory="uploads"), name="static")
# --- END FIX ---

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )

# CORS configuration (no changes here)
origins = [
    "http://localhost",
    "http://localhost:8080", 
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "https://*.ngrok-free.app",  # <-- ADD THIS LINE
    "https://*.ngrok.io",        # <-- AND THIS (older ngrok domains)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all your routers (no changes here)
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
app.include_router(contacts.router)  # <-- ADD THIS LINE
app.include_router(daily_calls.router) # <-- ADD THIS LINE

@app.get("/")
def read_root():
    return {"message": "Welcome to BWC Portal API!"}
