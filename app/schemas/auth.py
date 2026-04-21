from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Schema for login request."""
    username_or_email: str = Field(..., description="Username or email address")
    password: str = Field(..., min_length=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "username_or_email": "admin",
                "password": "password123"
            }
        }


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Schema for password change request."""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
