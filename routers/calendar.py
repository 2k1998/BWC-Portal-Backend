# routers/calendar.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import User, Task, Event # Import Event model
from schemas import CalendarEvent
from .auth import get_current_user
from datetime import date, datetime
from typing import List, Optional

router = APIRouter(prefix="/calendar", tags=["calendar"])

@router.get("/events", response_model=List[CalendarEvent])
def get_calendar_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    events = []

    # 1. Fetch Birthdays
    all_users = db.query(User).all()
    for user in all_users:
        if user.birthday:
            birth_date_this_year = date(date.today().year, user.birthday.month, user.birthday.day)
            events.append(
                CalendarEvent(
                    title=f"🎂 {user.first_name or user.email}'s Birthday",
                    start=birth_date_this_year,
                    end=birth_date_this_year,
                    type="birthday",
                    allDay=True
                )
            )

    # 2. Fetch Task Deadlines
    tasks_query = db.query(Task)
    if current_user.role == "admin":
        tasks_to_include = tasks_query.all()
    else:
        user_group_ids = [group.id for group in current_user.groups]
        tasks_to_include = db.query(Task).filter(
            (Task.owner_id == current_user.id) | (Task.group_id.in_(user_group_ids))
        ).all()

    for task in tasks_to_include:
        if task.deadline:
            events.append(
                CalendarEvent(
                    title=f"✔️ Task: {task.title}",
                    start=task.deadline,
                    end=task.deadline,
                    type="task",
                    allDay=task.deadline_all_day
                )
            )
            
    # 3. Fetch Seminars/Events
    all_events = db.query(Event).all()
    for event in all_events:
        events.append(
            CalendarEvent(
                title=f"🗓️ Event: {event.title}",
                # --- THE FIX: Use the correct attribute 'event_date' ---
                start=event.event_date,
                end=event.event_date,
                type="seminar",
                allDay=False 
            )
        )

    return events
