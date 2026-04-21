from typing import Optional


TASK_STATUS_MAP = {
    "new": "New",
    "received": "Received",
    "on_process": "On Process",
    "pending": "Pending",
    "completed": "Completed",
    "loose_end": "Loose End",
}


PAYMENT_TYPE_MAP = {
    "commission_payment": "commission",
    "base_salary": "salary",
    "bonus": "bonus",
    "office_rent": "rent",
    "utility_bill": "bill",
    "equipment_purchase": "purchase",
}


def map_task_status(old_status: Optional[str]) -> str:
    if not old_status:
        return "New"
    return TASK_STATUS_MAP.get(old_status, "New")


def map_urgency_label(urgent: Optional[bool], important: Optional[bool]) -> str:
    if urgent and important:
        return "Red"
    if urgent and not important:
        return "Orange"
    if (not urgent) and important:
        return "Yellow"
    return "Not Urgent & Not Important"


def map_priority(urgent: Optional[bool], important: Optional[bool]) -> str:
    if urgent and important:
        return "High"
    if urgent or important:
        return "Medium"
    return "Low"


def map_user_type(role: Optional[str]) -> str:
    if not role:
        return "Agent"
    role_norm = role.strip().lower()
    if role_norm == "admin":
        return "Admin"
    if role_norm == "manager":
        return "Manager"
    if role_norm == "head":
        return "Head"
    if role_norm == "pillar":
        return "Pillar"
    return "Agent"


def map_payment_type(value: Optional[str]) -> str:
    if not value:
        return "service"
    return PAYMENT_TYPE_MAP.get(value, "service")

