# Backend/services/recurrence.py
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  # add python-dateutil to requirements if needed

from sqlalchemy.orm import Session
from models import Task

def _next_deadline(now: datetime, current: datetime | None, recurrence: str | None) -> datetime | None:
    if not current or not recurrence:
        return None
    if recurrence == "daily":
        return current + timedelta(days=1)
    if recurrence == "weekly":
        return current + timedelta(weeks=1)
    if recurrence == "monthly":
        return current + relativedelta(months=1)
    if recurrence == "yearly":
        return current + relativedelta(years=1)
    return None

def generate_next_instances(db: Session) -> int:
    """
    For each recurring task that is due (deadline <= today),
    ensure there is a next instance in the future by duplicating with bumped dates.
    Returns number of tasks generated.
    """
    now = datetime.utcnow()
    count = 0

    # fetch candidates
    tasks = (
        db.query(Task)
        .filter(Task.is_recurring == True, Task.deadline != None)
        .all()
    )

    for t in tasks:
        nxt = _next_deadline(now, t.deadline, t.recurrence)
        if not nxt:
            continue
        if nxt <= now:
            # If deadline is way in the past, repeatedly bump until it's in the future
            while nxt and nxt <= now:
                nxt = _next_deadline(now, nxt, t.recurrence)

        if not nxt:
            continue

        # Create a new task instance only if there isn't already a future one with same title & company
        exists = (
            db.query(Task)
            .filter(
                Task.title == t.title,
                Task.company_id == t.company_id,
                Task.is_recurring == True,
                Task.deadline != None,
                Task.deadline >= nxt - timedelta(days=1),  # loose match
            )
            .first()
        )
        if exists:
            continue

        new_task = Task(
            title=t.title,
            description=t.description,
            start_date=t.start_date,
            deadline_all_day=t.deadline_all_day,
            deadline=nxt,
            urgency=t.urgency,
            important=t.important,
            status=t.status,
            status_comments=None,
            company_id=t.company_id,
            owner_id=t.owner_id,
            is_recurring=True,
            recurrence=t.recurrence,
        )
        db.add(new_task)
        count += 1

    if count:
        db.commit()
    return count
