from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import json
from uuid import UUID

from app.models.activity_log import ActivityLog
from app.models.task import Task
from app.models.project import Project
from app.models.event import Event
from app.models.document import Document
from app.models.company import Company

SENSITIVE_FIELDS = {
    "password", "hashed_password", "generated_password",
    "token", "access_token", "refresh_token", "api_key"
}

def _redact_sensitive_data(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively redact sensitive fields from dictionary."""
    if not data:
        return None
    
    redacted = data.copy()
    for key, value in data.items():
        if key in SENSITIVE_FIELDS:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = _redact_sensitive_data(value)
            
    return redacted

def log_activity(
    db: Session,
    entity_type: str,
    entity_id: str,
    action_type: str,
    performed_by_user_id: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None
) -> ActivityLog:
    """
    Create a secure activity log entry.
    Automatically redacts sensitive information.
    """
    
    log = ActivityLog(
        entity_type=entity_type,
        entity_id=UUID(str(entity_id)),
        action_type=action_type,
        performed_by_user_id=UUID(str(performed_by_user_id)),
        old_value=_redact_sensitive_data(old_value),
        new_value=_redact_sensitive_data(new_value)
    )
    
    db.add(log)
    # We generally want to commit as part of the main transaction,
    # but logging often happens alongside it.
    # The caller is responsible for the final commit if they are in a transaction,
    # or we can flush here to ensure the object has an ID.
    db.flush()
    
    return log
