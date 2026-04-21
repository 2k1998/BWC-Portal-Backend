# Import all API routers
from app.api import auth, admin_users, companies, admin_departments

__all__ = [
    "auth",
    "admin_users",
    "companies",
    "admin_departments",
]
