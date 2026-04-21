import sys
import os
import time
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from starlette.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# Setup Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.models.notification import Notification
from app.models.contact import Contact
from app.models.daily_call import DailyCall
from app.models.call_notes_file import CallNotesFile
from app.models.document import Document
from app.services.daily_call_reminder_service import REMINDER_30_TITLE, REMINDER_5_TITLE
from app.main import app


engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()
client = TestClient(app)


def _hash_password(password: str) -> str:
    from app.core.security import hash_password

    return hash_password(password)


def setup_users():
    """
    Creates 2 users (owner + outsider) with known credentials.
    We avoid relying on page permissions; contacts/daily-calls are private by ownership.
    """
    owner_email = "phase12_owner@test.com"
    outsider_email = "phase12_outsider@test.com"

    owner = db.query(User).filter(User.email == owner_email).first()
    if not owner:
        owner = User(
            email=owner_email,
            username="phase12_owner",
            hashed_password=_hash_password("password123"),
            first_name="Phase12",
            last_name="Owner",
            user_type="Admin",
            is_active=True,
            force_password_change=False,
        )
        db.add(owner)
        db.commit()

    outsider = db.query(User).filter(User.email == outsider_email).first()
    if not outsider:
        outsider = User(
            email=outsider_email,
            username="phase12_outsider",
            hashed_password=_hash_password("password123"),
            first_name="Phase12",
            last_name="Outsider",
            user_type="Employee",
            is_active=True,
            force_password_change=False,
        )
        db.add(outsider)
        db.commit()

    db.refresh(owner)
    db.refresh(outsider)
    return owner, outsider


def get_token(email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"username_or_email": email, "password": password})
    if resp.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]


def cleanup_phase12_rows(owner_id, outsider_id):
    """
    Best-effort cleanup to keep script re-runnable.
    This deletes records by user ownership only (no admin override).
    """
    # Notifications
    db.query(Notification).filter(Notification.recipient_user_id.in_([owner_id, outsider_id])).delete(synchronize_session=False)
    db.commit()


def verify_reminder_dedupe(owner_token: str, owner_id, outsider_token: str, outsider_id) -> None:
    print("\n--- Phase 12: Reminder + Dedupe ---")

    # Owner creates a contact
    contact_payload = {
        "first_name": "John",
        "last_name": "Doe",
        "phone": "2101234567",
        "email": "john.doe@example.com",
        "company_name": None,
        "company_id": None,
        "notes": None,
    }
    resp = client.post("/contacts", json=contact_payload, headers={"Authorization": f"Bearer {owner_token}"})
    if resp.status_code != 201:
        raise RuntimeError(f"Create contact failed: {resp.status_code} {resp.text}")
    contact = resp.json()
    contact_id = contact["id"]

    # Outsider cannot read owner contact
    resp = client.get(f"/contacts/{contact_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    if resp.status_code != 403:
        raise RuntimeError(f"Expected 403 reading someone else's contact. Got {resp.status_code}: {resp.text}")
    print("SUCCESS: Contact privacy enforcement (403 for outsider).")

    # Schedule DailyCall such that the 30-min reminder is due "right now".
    now = datetime.now(timezone.utc)
    # due_30 = next_call_at - 30m must be <= now <= due_30+120s
    next_call_at = now + timedelta(minutes=30) - timedelta(seconds=30)  # due_30 ~= now-30s
    next_call_at_iso = next_call_at.replace(microsecond=0).isoformat()

    daily_call_payload = {"contact_id": contact_id, "next_call_at": next_call_at_iso}
    resp = client.post("/daily-calls", json=daily_call_payload, headers={"Authorization": f"Bearer {owner_token}"})
    if resp.status_code != 201:
        raise RuntimeError(f"Schedule daily call failed: {resp.status_code} {resp.text}")
    daily_call = resp.json()
    daily_call_id = daily_call["id"]

    # Give the proactive reminder logic a moment (background thread may also run).
    time.sleep(0.5)

    # Verify 30-min reminder exists exactly once (for this daily_call)
    notif_30 = (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == owner_id,
            Notification.entity_type == "DailyCall",
            Notification.entity_id == daily_call_id,
            Notification.title == REMINDER_30_TITLE,
            Notification.notification_type == "STATUS_CHANGE",
        )
        .all()
    )
    if len(notif_30) != 1:
        raise RuntimeError(f"Expected exactly 1 30-min reminder. Found {len(notif_30)}")
    print("SUCCESS: 30-min reminder created (deduped).")

    # Trigger another proactive ensure by updating call_note (should not create duplicates)
    # Phase 12 requires call_notes_files.file_id. If DB wasn't migrated yet,
    # the call-note creation will fail, and we should stop early.
    call_notes_cols = {c["name"] for c in inspect(engine).get_columns("call_notes_files")}
    if "file_id" not in call_notes_cols:
        raise RuntimeError(
            "DB schema is behind Phase 12: `call_notes_files.file_id` column is missing. "
            f"Found columns: {sorted(call_notes_cols)}. "
            "Apply Alembic migration for Phase 12 (012_phase12_contacts_daily_calls.py), then re-run this script."
        )

    resp = client.put(
        f"/daily-calls/{daily_call_id}",
        json={"call_note": f"Note {uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Update daily call (call_note) failed: {resp.status_code} {resp.text}")

    time.sleep(0.5)

    notif_30_after = (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == owner_id,
            Notification.entity_type == "DailyCall",
            Notification.entity_id == daily_call_id,
            Notification.title == REMINDER_30_TITLE,
            Notification.notification_type == "STATUS_CHANGE",
        )
        .all()
    )
    if len(notif_30_after) != 1:
        raise RuntimeError(f"Dedupe failed: expected 1 30-min reminder after update. Found {len(notif_30_after)}")
    print("SUCCESS: Reminder dedupe holds after call_note update.")

    # Ensure 5-min reminder is NOT created (should be due far in the future for our next_call_at choice)
    notif_5 = (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == owner_id,
            Notification.entity_type == "DailyCall",
            Notification.entity_id == daily_call_id,
            Notification.title == REMINDER_5_TITLE,
            Notification.notification_type == "STATUS_CHANGE",
        )
        .all()
    )
    if len(notif_5) != 0:
        raise RuntimeError(f"Expected 0 5-min reminders for this schedule. Found {len(notif_5)}")
    print("SUCCESS: No premature 5-min reminder created.")


def verify_expired_download_410(owner_token: str, owner_id, outsider_token: str, outsider_id) -> None:
    print("\n--- Phase 12: Expired call-note download (410) ---")

    call_notes_cols = {c["name"] for c in inspect(engine).get_columns("call_notes_files")}
    if "file_id" not in call_notes_cols:
        raise RuntimeError(
            "DB schema is behind Phase 12: `call_notes_files.file_id` column is missing. "
            f"Found columns: {sorted(call_notes_cols)}. "
            "Apply Alembic migration for Phase 12, then re-run this script."
        )

    # Create another contact + daily call for cleaner linking
    contact_payload = {
        "first_name": "Alice",
        "last_name": "Smith",
        "phone": "6901234567",
        "email": None,
        "company_name": None,
        "company_id": None,
        "notes": None,
    }
    resp = client.post("/contacts", json=contact_payload, headers={"Authorization": f"Bearer {owner_token}"})
    if resp.status_code != 201:
        raise RuntimeError(f"Create contact failed: {resp.status_code} {resp.text}")
    contact_id = resp.json()["id"]

    now = datetime.now(timezone.utc)
    next_call_at = now + timedelta(hours=1)  # no reminder relevance for this test
    resp = client.post(
        "/daily-calls",
        json={"contact_id": contact_id, "next_call_at": next_call_at.replace(microsecond=0).isoformat()},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    if resp.status_code != 201:
        raise RuntimeError(f"Schedule daily call failed: {resp.status_code} {resp.text}")
    daily_call_id = resp.json()["id"]

    # Upload a call notes file
    file_content = b"hello call notes"
    upload_resp = client.post(
        f"/daily-calls/{daily_call_id}/notes",
        files={"file": ("call_notes.doc", file_content, "application/msword")},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    if upload_resp.status_code != 201:
        raise RuntimeError(f"Upload call notes failed: {upload_resp.status_code} {upload_resp.text}")

    doc_id = upload_resp.json()["id"]

    # Expire the link directly in DB
    link = db.query(CallNotesFile).filter(CallNotesFile.daily_call_id == daily_call_id, CallNotesFile.file_id == doc_id).first()
    if not link:
        raise RuntimeError("CallNotesFile link not found after upload")

    link.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    # Owner download should return 410 Gone
    dl_resp_owner = client.get(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {owner_token}"})
    if dl_resp_owner.status_code != 410:
        raise RuntimeError(f"Expected 410 Gone for expired call note (owner). Got {dl_resp_owner.status_code}: {dl_resp_owner.text}")
    print("SUCCESS: Expired call-note returns 410 for owner.")

    # Outsider download should return 403 Forbidden (private to owner)
    dl_resp_outsider = client.get(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    if dl_resp_outsider.status_code != 403:
        raise RuntimeError(f"Expected 403 for outsider trying to download owner call note. Got {dl_resp_outsider.status_code}: {dl_resp_outsider.text}")
    print("SUCCESS: Outsider download is blocked with 403.")


if __name__ == "__main__":
    owner, outsider = setup_users()
    cleanup_phase12_rows(owner.id, outsider.id)

    owner_token = get_token(owner.email, "password123")
    outsider_token = get_token(outsider.email, "password123")

    verify_reminder_dedupe(owner_token, owner.id, outsider_token, outsider.id)
    verify_expired_download_410(owner_token, owner.id, outsider_token, outsider.id)

    print("\nPhase 12 verification script: ALL CHECKS PASSED")

