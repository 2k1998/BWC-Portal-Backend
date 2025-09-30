from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import os

from database import get_db
from .auth import get_current_user
from models import User

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from jose import jwt
from datetime import datetime, timezone, timedelta, date

# Reuse auth settings
from .auth import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/google-calendar", tags=["google-calendar"])


def _get_oauth_flow() -> Flow:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="Google OAuth environment not configured")

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": [redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    scopes = [
        "https://www.googleapis.com/auth/calendar.events",
    ]
    flow = Flow.from_client_config(client_config, scopes=scopes)
    flow.redirect_uri = redirect_uri
    return flow


@router.get("/status")
def google_status(current_user: User = Depends(get_current_user)):
    enabled = bool(getattr(current_user, "google_calendar_sync_enabled", False))
    connected = bool(getattr(current_user, "google_credentials", None))
    return {"connected": connected, "sync_enabled": enabled}


@router.get("/auth-url")
def get_auth_url(current_user: User = Depends(get_current_user)):
    flow = _get_oauth_flow()
    # Encode user context in state so callback doesn't require Authorization header
    state_payload = {"uid": current_user.id, "ts": datetime.now(timezone.utc).isoformat()}
    encoded_state = jwt.encode(state_payload, SECRET_KEY, algorithm=ALGORITHM)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=encoded_state,
    )
    return {"auth_url": auth_url, "state": state}


@router.get("/oauth-callback")
def oauth_callback(code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_db)):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    # Decode state to identify user without requiring Authorization header
    try:
        data = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = data.get("uid")
        if not user_id:
            raise ValueError("No uid in state")
        current_user = db.query(User).filter(User.id == user_id).first()
        if not current_user:
            raise ValueError("User not found")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    flow = _get_oauth_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Store credentials in user
    cred_dict = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
        "expiry": credentials.expiry.isoformat() if getattr(credentials, "expiry", None) else None,
    }
    current_user.google_credentials = cred_dict
    current_user.google_calendar_sync_enabled = True
    db.commit()
    db.refresh(current_user)

    frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    # Redirect user back to frontend page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{frontend_base}/calendar-sync?connected=1")


@router.post("/disconnect")
def disconnect(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.google_credentials = None
    current_user.google_calendar_sync_enabled = False
    db.commit()
    db.refresh(current_user)
    return {"message": "Disconnected from Google Calendar"}


def _build_service_from_user(user: User):
    creds_data = getattr(user, "google_credentials", None)
    if not creds_data:
        raise HTTPException(status_code=400, detail="Not connected to Google Calendar")
    credentials = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=creds_data.get("scopes"),
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


@router.post("/sync")
def sync_to_google(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Lazy import to avoid heavy cost if unused
    from .calendar import get_calendar_events  # reuse existing events aggregation
    service = _build_service_from_user(current_user)

    # Fetch aggregated events for this user
    events = get_calendar_events(db=db, current_user=current_user)

    created_count = 0
    skipped_count = 0
    last_error: Optional[str] = None
    for ev in events:
        try:
            if ev.allDay:
                start_payload = {"date": (ev.start if isinstance(ev.start, date) else ev.start.date()).isoformat()}
                end_payload = {"date": (ev.end if isinstance(ev.end, date) else ev.end.date()).isoformat()}
            else:
                # Ensure RFC3339 with timezone; default to UTC if naive
                start_dt = ev.start if isinstance(ev.start, datetime) else datetime.combine(ev.start, datetime.min.time())
                end_dt = ev.end if isinstance(ev.end, datetime) else datetime.combine(ev.end, datetime.min.time())
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                start_payload = {"dateTime": start_dt.isoformat()}
                end_payload = {"dateTime": end_dt.isoformat()}

            body = {
                "summary": ev.title,
                "start": start_payload,
                "end": end_payload,
            }
            service.events().insert(calendarId="primary", body=body).execute()
            created_count += 1
        except Exception as e:
            skipped_count += 1
            try:
                last_error = str(e)
            except Exception:
                last_error = "error"
            continue

    return {"status": "ok", "created": created_count, "skipped": skipped_count, "last_error": last_error}

