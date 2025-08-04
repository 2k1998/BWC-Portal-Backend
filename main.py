from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os

# JWT Configuration
SECRET_KEY = "bwc-portal-super-secret-key-2025"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 240

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Models
class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    first_name: Optional[str] = None
    surname: Optional[str] = None
    role: str = "Agent"  # Default role should be "Agent", not "user"
    is_active: bool = True
    full_name: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    surname: Optional[str] = None

# Test users database (in memory) - FIXED ADMIN ROLE
USERS_DB = {
    "admin@bwc.com": {
        "id": 1,
        "email": "admin@bwc.com",
        "password": "admin123",
        "first_name": "Administrator",
        "surname": "User",
        "role": "admin",  # This is correct
        "is_active": True
    },
    "test@bwc.com": {
        "id": 2,
        "email": "test@bwc.com", 
        "password": "test123",
        "first_name": "Test",
        "surname": "User",
        "role": "Agent",  # Regular users should be "Agent"
        "is_active": True
    }
}

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Find user by email
    user = None
    for email, user_data in USERS_DB.items():
        if email == user_id:
            user = user_data
            break
    
    if user is None:
        raise credentials_exception
    return user

# Basic endpoints
@app.get("/")
def read_root():
    return {"message": "Welcome to BWC Portal API!", "status": "running", "cors": "enabled"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "All systems operational"}

# Authentication endpoints
@app.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = USERS_DB.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"], "id": user["id"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate):
    if user.email in USERS_DB:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Add new user to database
    new_user_id = len(USERS_DB) + 1
    USERS_DB[user.email] = {
        "id": new_user_id,
        "email": user.email,
        "password": user.password,
        "first_name": user.first_name,
        "surname": user.surname,
        "role": "Agent",  # New users are Agents
        "is_active": True
    }
    
    user_data = USERS_DB[user.email]
    return UserResponse(
        id=user_data["id"],
        email=user_data["email"],
        first_name=user_data["first_name"],
        surname=user_data["surname"],
        role=user_data["role"],
        is_active=user_data["is_active"],
        full_name=f"{user_data.get('first_name', '')} {user_data.get('surname', '')}".strip() or user_data["email"]
    )

@app.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        first_name=current_user.get("first_name"),
        surname=current_user.get("surname"),
        role=current_user["role"],
        is_active=current_user["is_active"],
        full_name=f"{current_user.get('first_name', '')} {current_user.get('surname', '')}".strip() or current_user["email"]
    )

# Companies endpoint
@app.get("/companies/")
def get_companies(current_user: dict = Depends(get_current_user)):
    return [
        {"id": 1, "name": "BWC Company", "vat_number": "123456789"},
        {"id": 2, "name": "Test Corporation", "vat_number": "987654321"},
        {"id": 3, "name": "Demo Ltd", "vat_number": "555666777"}
    ]

# Tasks endpoint
@app.get("/tasks/")
def get_tasks(current_user: dict = Depends(get_current_user)):
    return [
        {
            "id": 1,
            "title": "Welcome to BWC Portal",
            "description": "This is your first task in the system",
            "priority": "high",
            "status": "new",
            "owner_id": current_user["id"],
            "deadline": "2025-08-10T10:00:00Z"
        },
        {
            "id": 2,
            "title": "Review System Features",
            "description": "Explore all the features available in the portal",
            "priority": "normal",
            "status": "pending",
            "owner_id": current_user["id"],
            "deadline": "2025-08-15T15:30:00Z"
        }
    ]

# Notifications endpoint
@app.get("/notifications/me")
def get_my_notifications(current_user: dict = Depends(get_current_user)):
    return [
        {
            "id": 1,
            "message": f"Welcome to BWC Portal, {current_user.get('first_name', 'User')}!",
            "is_read": False,
            "created_at": "2025-08-01T10:00:00Z"
        }
    ]

# Daily calls endpoint
@app.get("/daily-calls/me")
def get_my_daily_calls(current_user: dict = Depends(get_current_user)):
    return [
        {
            "id": 1,
            "contact_name": "John Doe",
            "phone_number": "+1234567890",
            "notes": "Follow up on proposal",
            "scheduled_for": "2025-08-01T14:00:00Z"
        }
    ]

# Calendar events endpoint
@app.get("/calendar/events")
def get_calendar_events(current_user: dict = Depends(get_current_user)):
    return [
        {
            "title": "Team Meeting",
            "start": "2025-08-01T09:00:00Z",
            "end": "2025-08-01T10:00:00Z",
            "type": "meeting",
            "allDay": False
        },
        {
            "title": "Project Deadline",
            "start": "2025-08-15",
            "end": "2025-08-15",
            "type": "deadline",
            "allDay": True
        }
    ]

# Events endpoint
@app.get("/events/upcoming")
def get_upcoming_event(current_user: dict = Depends(get_current_user)):
    return {
        "id": 1,
        "title": "BWC Portal Launch Event",
        "description": "Celebrating the successful deployment of our portal",
        "location": "Main Office",
        "event_date": "2025-08-05T18:00:00Z"
    }

print("=== BWC Portal API Started Successfully ===")
print("🔑 Test Login Credentials:")
print("   👤 ADMINISTRATOR:")
print("      Email: admin@bwc.com")
print("      Password: admin123")
print("      Role: admin")
print("")
print("   👤 Regular Agent:")  
print("      Email: test@bwc.com")
print("      Password: test123")
print("      Role: Agent")
print("==================================================")
print("✅ Available Endpoints:")
print("   - Authentication (login/register)")
print("   - User Profile (/users/me)")
print("   - Companies (/companies/)")
print("   - Tasks (/tasks/)")
print("   - Notifications (/notifications/me)")
print("   - Daily Calls (/daily-calls/me)")
print("   - Calendar Events (/calendar/events)")
print("   - Upcoming Events (/events/upcoming)")
print("==================================================")
