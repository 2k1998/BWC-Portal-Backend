# Import all models here for Alembic to detect them
from app.models.user import User
from app.models.auth import AuthRefreshToken
from app.models.page import Page
from app.models.permission import UserPagePermission
from app.models.audit import UserAuditLog
from app.models.company import Company
from app.models.department import Department
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.task import Task
from app.models.task_document import TaskDocument
from app.models.task_comment import TaskComment
from app.models.project import Project
from app.models.event import Event
from app.models.document import Document
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.models.contact import Contact
from app.models.daily_call import DailyCall
from app.models.call_notes_file import CallNotesFile
from app.models.payment import Payment
from app.models.car import Car
from app.models.car_maintenance import CarMaintenance
from app.models.car_income import CarIncome
from app.models.car_expense import CarExpense
from app.models.user_profile import UserProfile
from app.models.chat_thread import ChatThread
from app.models.chat_thread_member import ChatThreadMember
from app.models.chat_message import ChatMessage
from app.models.approval_request import ApprovalRequest

__all__ = [
    "User",
    "AuthRefreshToken",
    "Page",
    "UserPagePermission",
    "UserAuditLog",
    "Company",
    "Department",
    "Team",
    "TeamMember",
    "Task",
    "TaskDocument",
    "TaskComment",
    "Project",
    "Event",
    "Document",
    "Notification",
    "ActivityLog",
    "Contact",
    "DailyCall",
    "CallNotesFile",
    "Payment",
    "Car",
    "CarMaintenance",
    "CarIncome",
    "CarExpense",
    "UserProfile",
    "ChatThread",
    "ChatThreadMember",
    "ChatMessage",
    "ApprovalRequest",
]

