from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest

router = APIRouter(prefix="/profile", tags=["Profile"])


def _profile_to_response(user: User, profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        user_type=user.user_type,
        is_active=user.is_active,
        manager_id=user.manager_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        bio=profile.bio,
        birthday=profile.birthday,
        profile_photo_url=profile.profile_photo_url,
        language=profile.language,
        profile_updated_at=profile.updated_at,
    )


def _get_or_init_profile(db: Session, user: User) -> tuple[UserProfile, bool]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if profile:
        return profile, False

    profile = UserProfile(user_id=user.id)
    db.add(profile)
    return profile, True


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile, created = _get_or_init_profile(db=db, user=current_user)
    if created:
        db.commit()
        db.refresh(profile)
    return _profile_to_response(user=current_user, profile=profile)


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    profile_update: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile, _ = _get_or_init_profile(db=db, user=current_user)

    # Only editable fields are allowed by request schema.
    data = profile_update.model_dump(exclude_unset=True)
    if "bio" in data:
        profile.bio = data["bio"]
    if "birthday" in data:
        profile.birthday = data["birthday"]
    if "profile_photo_url" in data:
        profile.profile_photo_url = data["profile_photo_url"]
    if "language" in data:
        language = data["language"]
        if language not in {"en", "el"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="language must be 'en' or 'el'",
            )
        profile.language = language

    # PRD: updated_at must reflect the latest update time.
    profile.updated_at = datetime.now(timezone.utc)

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return _profile_to_response(user=current_user, profile=profile)

