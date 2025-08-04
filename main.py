from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from jose import jwt
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = "test-secret-key"
ALGORITHM = "HS256"

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    surname: str
    role: str
    is_active: bool
    full_name: str

# Test user
TEST_USER = {
    "id": 1,
    "email": "admin@bwc.com",
    "password": "admin123",
    "first_name": "Administrator",
    "surname": "BWC",
    "role": "admin",
    "is_active": True
}

def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=240)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TEST_USER
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/")
def root():
    return {"message": "BWC Portal API - Working!", "version": "1.0", "admin_ready": True}

@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == "admin@bwc.com" and form_data.password == "admin123":
        token = create_access_token(data={"sub": form_data.username})
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/users/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=1,
        email="admin@bwc.com",
        first_name="Administrator",
        surname="BWC",
        role="admin",
        is_active=True,
        full_name="Administrator BWC"
    )

@app.get("/companies/")
def get_companies(current_user: dict = Depends(get_current_user)):
    return [{"id": 1, "name": "BWC Corp", "vat_number": "123456789"}]

@app.get("/tasks/")
def get_tasks(current_user: dict = Depends(get_current_user)):
    return [{"id": 1, "title": "Test Task", "description": "Demo task", "status": "new"}]

@app.get("/notifications/me")
def get_notifications(current_user: dict = Depends(get_current_user)):
    return [{"id": 1, "message": "Welcome Admin!", "is_read": False}]

@app.get("/daily-calls/me")
def get_daily_calls(current_user: dict = Depends(get_current_user)):
    return [{"id": 1, "contact_name": "Test Contact", "phone_number": "123-456-7890"}]

@app.get("/calendar/events")
def get_calendar_events(current_user: dict = Depends(get_current_user)):
    return [{"title": "Test Event", "start": "2025-08-01", "type": "meeting", "allDay": True}]

@app.get("/events/upcoming")
def get_upcoming_event(current_user: dict = Depends(get_current_user)):
    return {"id": 1, "title": "BWC Launch", "location": "Office", "event_date": "2025-08-05"}

print("🚀 ULTRA SIMPLE BWC PORTAL API READY!")
print("🔑 Login: admin@bwc.com / admin123")
print("👑 Role: admin")
