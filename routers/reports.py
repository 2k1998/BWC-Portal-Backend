# routers/reports.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from pydantic import BaseModel
from datetime import datetime, timedelta

import models, schemas
from database import get_db
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/reports", tags=["reports"])

# --- Pydantic Models for Report Data Structures ---
class TasksPerCompany(BaseModel):
    company_name: str
    task_count: int

class CarRentalStatus(BaseModel):
    status: str
    count: int

class TasksTimeline(BaseModel):
    date: str
    count: int

class UserTaskStats(BaseModel):
    user_id: int
    user_name: str
    user_email: str
    owned_tasks: int
    created_tasks: int

# --- API Endpoints ---

@router.get("/tasks-per-company", response_model=List[TasksPerCompany])
def get_tasks_per_company(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Returns the number of active tasks for each company."""
    check_roles(current_user, ["admin"])
    
    # Get all companies first
    companies = db.query(models.Company).all()
    
    results = []
    for company in companies:
        # Count active tasks for this company
        task_count = db.query(models.Task).filter(
            models.Task.company_id == company.id,
            models.Task.completed == False
        ).count()
        
        results.append({
            "company_name": company.name,
            "task_count": task_count
        })
    
    return results

@router.get("/rental-car-status", response_model=List[CarRentalStatus])
def get_rental_car_status(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Returns the count of currently rented vs. available cars for 'Best Solution Cars'."""
    check_roles(current_user, ["admin"])

    best_solution_cars = db.query(models.Company).filter(models.Company.name == 'Best Solution Cars').first()
    if not best_solution_cars:
        return [] # Return empty if the company doesn't exist

    total_cars = db.query(models.Car).filter(models.Car.company_id == best_solution_cars.id).count()
    
    # Count cars that are part of an active (not locked) rental
    rented_cars_count = db.query(models.Rental)\
        .filter(models.Rental.company_id == best_solution_cars.id, models.Rental.is_locked == False)\
        .count()
        
    available_cars = total_cars - rented_cars_count
    
    return [
        {"status": "Rented", "count": rented_cars_count},
        {"status": "Available", "count": available_cars}
    ]

@router.get("/tasks-completed-timeline", response_model=List[TasksTimeline])
def get_tasks_completed_timeline(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Returns the number of tasks completed per day for the last 30 days."""
    check_roles(current_user, ["admin"])
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Query tasks completed in the last 30 days using TaskHistory
    try:
        results = db.query(
            func.date(models.TaskHistory.timestamp).label('completion_date'),
            func.count(models.TaskHistory.id).label('count')
        ).join(models.Task, models.TaskHistory.task_id == models.Task.id)\
        .filter(
            models.TaskHistory.status_to == 'completed',
            func.date(models.TaskHistory.timestamp) >= start_date,
            func.date(models.TaskHistory.timestamp) <= end_date
        ).group_by(func.date(models.TaskHistory.timestamp))\
        .order_by(func.date(models.TaskHistory.timestamp))\
        .all()
    except Exception as e:
        # Fallback: If TaskHistory doesn't exist or has issues, use Task table directly
        # This queries tasks that were completed (assuming completion date is when status changed)
        results = db.query(
            func.date(models.Task.deadline).label('completion_date'),
            func.count(models.Task.id).label('count')
        ).filter(
            models.Task.completed == True,
            models.Task.deadline.isnot(None),
            func.date(models.Task.deadline) >= start_date,
            func.date(models.Task.deadline) <= end_date
        ).group_by(func.date(models.Task.deadline))\
        .order_by(func.date(models.Task.deadline))\
        .all()
    
    # Fill in missing dates with 0 count
    timeline_data = []
    current_date = start_date
    results_dict = {str(date): count for date, count in results}
    
    while current_date <= end_date:
        timeline_data.append({
            "date": str(current_date),
            "count": results_dict.get(str(current_date), 0)
        })
        current_date += timedelta(days=1)
    
    return timeline_data

@router.get("/user-task-statistics", response_model=List[UserTaskStats])
def get_user_task_statistics(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Returns statistics about how many tasks each user owns and has created."""
    check_roles(current_user, ["admin"])
    
    # Get all users first
    all_users = db.query(models.User).all()
    
    stats = []
    for user in all_users:
        # Count owned tasks
        owned_count = db.query(models.Task).filter(
            models.Task.owner_id == user.id
        ).count()
        
        # Count created tasks
        created_count = db.query(models.Task).filter(
            models.Task.created_by_id == user.id
        ).count()
        
        stats.append({
            "user_id": user.id,
            "user_name": user.full_name or f"{user.first_name or ''} {user.surname or ''}".strip() or user.email,
            "user_email": user.email,
            "owned_tasks": owned_count,
            "created_tasks": created_count
        })
    
    return stats

@router.get("/debug-tasks")
def debug_tasks(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Debug endpoint to check task data"""
    check_roles(current_user, ["admin"])
    
    # Get basic task counts
    total_tasks = db.query(models.Task).count()
    active_tasks = db.query(models.Task).filter(models.Task.completed == False).count()
    completed_tasks = db.query(models.Task).filter(models.Task.completed == True).count()
    
    # Get sample tasks
    sample_tasks = db.query(models.Task).limit(5).all()
    
    # Get companies
    companies = db.query(models.Company).all()
    
    # Get users
    users = db.query(models.User).all()
    
    return {
        "total_tasks": total_tasks,
        "active_tasks": active_tasks,
        "completed_tasks": completed_tasks,
        "sample_tasks": [
            {
                "id": task.id,
                "title": task.title,
                "company_id": task.company_id,
                "owner_id": task.owner_id,
                "created_by_id": task.created_by_id,
                "completed": task.completed
            } for task in sample_tasks
        ],
        "companies": [{"id": c.id, "name": c.name} for c in companies],
        "users": [{"id": u.id, "name": u.full_name or u.email} for u in users]
    }