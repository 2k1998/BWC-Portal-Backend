from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
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

# Basic models for auth
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: int
    email: str
    full_name: str

# Basic endpoints
@app.get("/")
def read_root():
    return {"message": "Welcome to BWC Portal API!", "status": "running", "cors": "enabled"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "All systems operational"}

# Simple auth endpoint for testing
@app.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Test credentials for demo
    if form_data.username == "admin@bwc.com" and form_data.password == "admin123":
        return {
            "access_token": "test-token-12345",
            "token_type": "bearer"
        }
    raise HTTPException(
        status_code=401,
        detail="Incorrect email or password"
    )

# Test user endpoint
@app.get("/users/me", response_model=User)
def read_users_me():
    return {
        "id": 1,
        "email": "admin@bwc.com", 
        "full_name": "Administrator"
    }

# Test companies endpoint
@app.get("/companies/")
def get_companies():
    return [
        {"id": 1, "name": "Test Company", "vat_number": "123456789"}
    ]

print("=== BWC Portal API Started Successfully ===")
print("🔑 Test Login Credentials:")
print("   Email: admin@bwc.com")
print("   Password: admin123")
print("==================================================")
