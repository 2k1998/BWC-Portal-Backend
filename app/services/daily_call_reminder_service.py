import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, Set

from sqlalchemy import and_
from sqlalchemy.orm import Session
import uuid as uuid_lib

from app.core.database import SessionLocal
from app.models.daily_call import DailyCall
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationType


logger = logging.getLogger(__name__)


_thread: threading.Thread | None = None
_stop_event = threading.Event()


REMINDER_30_TITLE = "Daily Call Reminder (30 minutes)"
REMINDER_5_TITLE = "Daily Call Reminder (5 minutes)"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _in_send_window(due_time: datetime, now: datetime, window_seconds: int = 120) -> bool:
    """
    Returns True if `now` is within the reminder window right after `due_time`.
    This tolerates small scheduler/API delays without spamming due to notification deduping.
    """
    return due_time <= now <= (due_time + timedelta(seconds=window_seconds))


def _existing_notification_entity_ids(
    db: Session,
    *,
    entity_ids: Iterable[str],
    title: str,
) -> Set[str]:
    entity_ids_set = {str(eid) for eid in entity_ids}
    entity_uuids = set()
    for eid in entity_ids_set:
        try:
            entity_uuids.add(uuid_lib.UUID(eid))
        except (ValueError, TypeError):
            continue

    if not entity_uuids:
        return set()

    existing = (
        db.query(Notification.entity_id)
        .filter(
            Notification.entity_type == "DailyCall",
            Notification.notification_type == NotificationType.STATUS_CHANGE.value,
            Notification.title == title,
            Notification.entity_id.in_(entity_uuids),
        )
        .all()
    )
    return {str(row[0]) for row in existing}


def ensure_daily_call_reminders_for_daily_call(db: Session, daily_call: DailyCall, now: datetime) -> None:
    """
    Creates reminder notifications if:
    - the daily_call is due for a 30m/5m reminder right now (within tolerance), AND
    - there is no existing notification for that daily_call + offset.
    """
    next_call_at = daily_call.next_call_at
    if not next_call_at:
        return

    # 30 minutes before: due at next_call_at - 30m
    due_30 = next_call_at - timedelta(minutes=30)
    send_30 = _in_send_window(due_30, now)

    # 5 minutes before: due at next_call_at - 5m
    due_5 = next_call_at - timedelta(minutes=5)
    send_5 = _in_send_window(due_5, now)

    if not (send_30 or send_5):
        return

    entity_id_str = str(daily_call.id)
    recipient_user_id = daily_call.user_id

    new_notifications: list[Notification] = []

    if send_30:
        existing_ids = _existing_notification_entity_ids(
            db, entity_ids=[entity_id_str], title=REMINDER_30_TITLE
        )
        if entity_id_str not in existing_ids:
            new_notifications.append(
                Notification(
                    recipient_user_id=recipient_user_id,
                    actor_user_id=None,
                    entity_type="DailyCall",
                    entity_id=daily_call.id,
                    title=REMINDER_30_TITLE,
                    message="Your scheduled call is in 30 minutes.",
                    link=f"/daily-calls/{daily_call.id}",
                    notification_type=NotificationType.STATUS_CHANGE.value,
                    read_status="Unread",
                )
            )

    if send_5:
        existing_ids = _existing_notification_entity_ids(
            db, entity_ids=[entity_id_str], title=REMINDER_5_TITLE
        )
        if entity_id_str not in existing_ids:
            new_notifications.append(
                Notification(
                    recipient_user_id=recipient_user_id,
                    actor_user_id=None,
                    entity_type="DailyCall",
                    entity_id=daily_call.id,
                    title=REMINDER_5_TITLE,
                    message="Your scheduled call is in 5 minutes.",
                    link=f"/daily-calls/{daily_call.id}",
                    notification_type=NotificationType.STATUS_CHANGE.value,
                    read_status="Unread",
                )
            )

    if new_notifications:
        db.add_all(new_notifications)


def run_daily_call_reminder_check_once() -> None:
    """
    Poll due DailyCalls and create reminder notifications.
    Called by the background thread every minute.
    """
    db = SessionLocal()
    try:
        now = _now_utc()

        # Window to fetch candidates, then we do precise due-time checks.
        candidate_window = timedelta(minutes=2)

        user_ids = [row[0] for row in db.query(User.id).all()]

        def _candidates_for_offset(minutes: int, *, user_id) -> list[DailyCall]:
            target_next_call_at = now + timedelta(minutes=minutes)
            start = target_next_call_at - candidate_window
            end = target_next_call_at + candidate_window
            return (
                db.query(DailyCall)
                .filter(
                    and_(
                        DailyCall.user_id == user_id,
                        DailyCall.next_call_at >= start,
                        DailyCall.next_call_at <= end,
                    )
                )
                .all()
            )

        for user_id in user_ids:
            for daily_call in _candidates_for_offset(30, user_id=user_id):
                ensure_daily_call_reminders_for_daily_call(db, daily_call, now)

            for daily_call in _candidates_for_offset(5, user_id=user_id):
                ensure_daily_call_reminders_for_daily_call(db, daily_call, now)

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed daily call reminder poll")
    finally:
        db.close()


def start_daily_call_reminder_loop(poll_interval_seconds: int = 60) -> None:
    """
    Starts a lightweight polling loop on FastAPI startup.
    """
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()

    def _loop() -> None:
        while not _stop_event.is_set():
            run_daily_call_reminder_check_once()
            # Sleep at the end so the first run happens immediately on startup.
            time.sleep(poll_interval_seconds)

    _thread = threading.Thread(target=_loop, name="daily-call-reminder-poller", daemon=True)
    _thread.start()


def stop_daily_call_reminder_loop() -> None:
    global _thread
    _stop_event.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=2)

