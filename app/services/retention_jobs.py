import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, or_

from app.core.database import SessionLocal
from app.models.call_notes_file import CallNotesFile
from app.models.document import Document
from app.models.event import Event
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User


logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def cleanup_call_notes() -> None:
    db = SessionLocal()
    cleaned_links = 0
    cleaned_docs = 0
    file_delete_errors = 0
    try:
        now = _now_utc()
        expired_links = db.query(CallNotesFile).filter(CallNotesFile.expires_at < now).all()

        for link in expired_links:
            doc = db.query(Document).filter(Document.id == link.file_id).first()
            if doc:
                try:
                    if doc.storage_path and os.path.exists(doc.storage_path):
                        os.remove(doc.storage_path)
                except OSError:
                    file_delete_errors += 1
                    logger.exception("Failed deleting expired call-note file from disk")

                db.delete(doc)
                cleaned_docs += 1

            db.delete(link)
            cleaned_links += 1

        db.commit()
        logger.info(
            "Retention call-notes cleanup finished: links=%s docs=%s file_delete_errors=%s",
            cleaned_links,
            cleaned_docs,
            file_delete_errors,
        )
    except Exception:
        db.rollback()
        logger.exception("Retention call-notes cleanup failed")
    finally:
        db.close()


def cleanup_events() -> None:
    db = SessionLocal()
    hard_deleted = 0
    try:
        now = _now_utc()
        cutoff = now - timedelta(days=3)

        stale_events = (
            db.query(Event)
            .filter(
                and_(
                    Event.deleted_at.is_not(None),
                    or_(
                        Event.deleted_at < cutoff,
                        Event.event_start_at < cutoff,
                    ),
                )
            )
            .all()
        )

        for event in stale_events:
            db.delete(event)
            hard_deleted += 1

        db.commit()
        logger.info("Retention events cleanup finished: deleted=%s", hard_deleted)
    except Exception:
        db.rollback()
        logger.exception("Retention events cleanup failed")
    finally:
        db.close()


def task_retention_report() -> None:
    db = SessionLocal()
    try:
        now = _now_utc()
        cutoff = now - timedelta(days=90)
        stale_tasks = (
            db.query(Task)
            .filter(
                and_(
                    or_(Task.status == "Completed", Task.deleted_at.is_not(None)),
                    Task.updated_at < cutoff,
                )
            )
            .all()
        )

        task_count = len(stale_tasks)
        logger.info("Task retention report generated: stale_tasks=%s cutoff=%s", task_count, cutoff.isoformat())

        if task_count > 0:
            admin_ids = [row[0] for row in db.query(User.id).filter(User.user_type == "Admin").all()]
            summary_entity_id = stale_tasks[0].id
            summary_message = (
                f"{task_count} tasks passed 90-day retention threshold and require admin review."
            )
            for admin_id in admin_ids:
                db.add(
                    Notification(
                        recipient_user_id=admin_id,
                        actor_user_id=None,
                        entity_type="Task",
                        entity_id=summary_entity_id,
                        title="Task retention report",
                        message=summary_message,
                        link="/tasks",
                        notification_type="STATUS_CHANGE",
                        read_status="Unread",
                    )
                )

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task retention report job failed")
    finally:
        db.close()


def start_retention_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(cleanup_call_notes, "interval", hours=1, id="cleanup_call_notes", replace_existing=True)
    _scheduler.add_job(cleanup_events, "interval", hours=1, id="cleanup_events", replace_existing=True)
    _scheduler.add_job(task_retention_report, "cron", hour=2, id="task_retention_report", replace_existing=True)
    _scheduler.start()
    logger.info("Retention scheduler started")


def stop_retention_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Retention scheduler stopped")
