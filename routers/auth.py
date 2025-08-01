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

# Load secret key and token expiration from environment variables (or use defaults)
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-for-development")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 240))

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
        birthday=user.birthday
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
def upload_profile_picture(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = upload_dir / unique_filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    file_url = f"/static/{unique_filename}"
    current_user.profile_picture_url = file_url
    db.commit()
    db.refresh(current_user)
    return current_user

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
    reset_link = f"http://localhost:5173/reset-password?token={token}"
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

from pydantic import BaseModel, EmailStr, computed_field, ConfigDict
from datetime import date

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    first_name: Optional[str] = None
    surname: Optional[str] = None
    birthday: Optional[date] = None
    role: str = "user"
    is_active: bool = True
    
    # --- NEW: Add profile picture URL to the response model ---
    profile_picture_url: Optional[str] = None

    @computed_field
    def full_name(self) -> str:
        if self.first_name and self.surname:
            return f"{self.first_name} {self.surname}"
        return self.first_name or self.surname or "No name set"

    model_config = ConfigDict(from_attributes=True)