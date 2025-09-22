import os
from fastapi import APIRouter, Depends, HTTPException, status, Form, Query, Response, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from database import get_db
from models import User, PasswordResetToken, Notification  # <-- Import Notification
from schemas import UserCreate, UserResponse, Token, UserUpdate, UserRoleUpdate, UserStatusUpdate, PasswordResetRequest, PasswordReset
from typing import Optional, List
from .utils import check_roles
import uuid
import shutil
from pathlib import Path
from utils.email_sender import send_email

# Optional cloudinary import for profile picture uploads
try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

# Load secret key and token expiration from environment variables (or use defaults)
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-for-development")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 240))

# Base URL for frontend (used for email links)
# Set FRONTEND_BASE_URL in your environment, e.g. https://portal.example.com
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

router = APIRouter()

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=120))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "id": user.id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=user.email,
        hashed_password=hashed_password,
        first_name=user.first_name,
        surname=user.surname,
        birthday=getattr(user, "birthday", None)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # --- NEW: Notify all admins of the new user ---
    admins = db.query(User).filter(User.role == 'admin').all()
    for admin in admins:
        admin_notification = Notification(
            user_id=admin.id,
            message=f"A new user has registered: {new_user.email}",
            link="/admin-panel"
        )
        db.add(admin_notification)
    db.commit()
    # --- END NEW ---

    return new_user

@router.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    # Defensive normalization so the endpoint never 500s due to permissions shape
    try:
        perms = getattr(current_user, "permissions", None)
        if perms is None:
            current_user.permissions = {}
        elif isinstance(perms, list):
            # Older schema stored a list; normalize to object for the frontend
            current_user.permissions = {}
        elif isinstance(perms, str):
            # Some DBs may have stored JSON as text; best effort parse
            import json
            try:
                parsed = json.loads(perms)
                current_user.permissions = parsed if isinstance(parsed, dict) else {}
            except Exception:
                current_user.permissions = {}
    except Exception:
        # On any unexpected error, fall back to empty permissions
        current_user.permissions = {}
    return current_user

@router.put("/users/me", response_model=UserResponse)
def update_user_me(user_update: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/users/me/upload-picture", response_model=UserResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate file type
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )
    
    # Validate file size (5MB max)
    max_size = 5 * 1024 * 1024  # 5MB
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 5MB"
        )
    
    # Reset file pointer
    await file.seek(0)

    # Check if Cloudinary is available and configured
    if not CLOUDINARY_AVAILABLE:
        raise HTTPException(status_code=500, detail="Cloudinary is not available. Please install cloudinary package.")
    
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not (cloud_name and api_key and api_secret):
        raise HTTPException(status_code=500, detail="Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET.")

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret
    )

    try:
        # Upload directly to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file.file,
            folder="bwc/avatars",
            resource_type="image",
            public_id=f"user_{current_user.id}_{uuid.uuid4()}",
            overwrite=True
        )

        secure_url = upload_result.get("secure_url")
        if not secure_url:
            raise Exception("Cloudinary upload failed: no secure_url returned")

        # Update user profile with absolute URL
        current_user.profile_picture_url = secure_url

        # Commit the database transaction
        db.commit()
        db.refresh(current_user)

        # Verify the update was successful
        if current_user.profile_picture_url != secure_url:
            raise Exception("Database update failed - profile_picture_url not updated")

        return current_user
        
    except Exception as e:
        # Rollback database changes
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload profile picture: {str(e)}"
        )

@router.get("/users/all", response_model=List[UserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: Optional[str] = Query(None, description="Search users by email or full name")
):
    check_roles(current_user, ["admin"])
    query = db.query(User)
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.filter(
            (User.email.ilike(search_pattern)) |
            (User.first_name.ilike(search_pattern)) |
            (User.surname.ilike(search_pattern))
        )
    return query.all()

@router.get("/users/basic", response_model=List[UserResponse])
def list_users_basic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get basic user info for chat/collaboration - accessible to all authenticated users"""
    try:
        # Defensive fix for permissions
        if hasattr(current_user, 'permissions'):
            if current_user.permissions is None:
                current_user.permissions = {}
            elif isinstance(current_user.permissions, list):
                current_user.permissions = {}
        
        # Return only active users with basic info
        users = db.query(User).filter(User.is_active == True).all()
        
        # Fix permissions for all users in the response
        for user in users:
            if hasattr(user, 'permissions'):
                if user.permissions is None:
                    user.permissions = {}
                elif isinstance(user.permissions, list):
                    user.permissions = {}
        
        return users
    except Exception as e:
        print(f"Error in list_users_basic: {e}")
        # Return empty list on error to prevent 500
        return []

@router.get("/users/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_roles(current_user, ["admin"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(user_id: int, role_update: UserRoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_roles(current_user, ["admin"])
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot change their own role.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role_update.role
    db.commit()
    db.refresh(user)
    return user

@router.put("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(user_id: int, status_update: UserStatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_roles(current_user, ["admin"])
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot deactivate their own account.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = status_update.is_active
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_roles(current_user, ["admin"])
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot delete their own account.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return Response(status_code=204)

# Permission Management Endpoints
@router.get("/users/{user_id}/permissions")
def get_user_permissions(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get user permissions - accessible to admins and the user themselves"""
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this user's permissions")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user.id,
        "permissions": user.permissions or {}
    }

@router.put("/users/{user_id}/permissions")
def update_user_permissions(
    user_id: int, 
    permissions_data: dict, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Update user permissions - only admins can do this"""
    check_roles(current_user, ["admin"])
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate permissions data
    valid_permissions = {
        'dashboard', 'tasks', 'profile', 'projects', 'companies', 'contacts', 
        'groups', 'events', 'documents', 'users', 'reports', 'admin_panel', 
        'payments', 'commissions', 'car_finance', 'daily_calls'
    }
    
    permissions = permissions_data.get('permissions', {})
    if not isinstance(permissions, dict):
        raise HTTPException(status_code=400, detail="Permissions must be a dictionary")
    
    # Validate that all permission keys are valid
    for key in permissions.keys():
        if key not in valid_permissions:
            raise HTTPException(status_code=400, detail=f"Invalid permission key: {key}")
    
    # Update permissions
    user.permissions = permissions
    db.commit()
    db.refresh(user)
    
    return {
        "message": "Permissions updated successfully",
        "user_id": user.id,
        "permissions": user.permissions
    }

@router.post("/auth/request-password-reset", response_model=dict)
def request_password_reset(request: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        return {"message": "If an account with that email exists, a password reset link has been sent."}
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
    db_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
        is_used=False
    )
    db.add(db_token)
    db.commit()
    # Build reset link using configurable frontend base URL
    base_url = FRONTEND_BASE_URL.rstrip("/")
    reset_link = f"{base_url}/reset-password?token={token}"
    send_email(
        to_email=user.email,
        subject="Password Reset Request",
        body=f"Click here to reset your password: {reset_link}"
    )
    return {"message": "If an account with that email exists, a password reset link has been sent."}

@router.post("/auth/reset-password", response_model=dict)
def reset_password(request: PasswordReset, db: Session = Depends(get_db)):
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == request.token,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).first()
    if not reset_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token.")
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = get_password_hash(request.new_password)
    reset_token.is_used = True
    db.commit()
    db.refresh(user)
    return {"message": "Password has been successfully reset."}

# UserResponse is already imported from schemas.py above