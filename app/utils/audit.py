from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.models.audit import UserAuditLog

SENSITIVE_KEYS = {
    "password",
    "hashed_password",
    "token",
    "refresh_token",
    "access_token",
    "secret",
    "api_key",
    "authorization",
}


def _redact_sensitive(data: Any) -> Any:
    if isinstance(data, dict):
        redacted: Dict[str, Any] = {}
        for key, value in data.items():
            normalized_key = str(key).lower()
            if normalized_key in SENSITIVE_KEYS or any(s in normalized_key for s in ("password", "token", "secret", "api_key")):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_sensitive(value)
        return redacted

    if isinstance(data, list):
        return [_redact_sensitive(item) for item in data]

    if isinstance(data, tuple):
        return tuple(_redact_sensitive(item) for item in data)

    return data


def create_audit_log(
    db: Session,
    admin_user_id: str,
    target_user_id: str,
    action: str,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None
) -> UserAuditLog:
    """
    Create an audit log entry for user management actions.
    
    Args:
        db: Database session
        admin_user_id: UUID of the admin performing the action
        target_user_id: UUID of the user being modified
        action: Description of the action (e.g., "create_user", "update_user")
        before_state: State before the action (optional)
        after_state: State after the action (optional)
    
    Returns:
        Created audit log entry
    """
    safe_before_state = _redact_sensitive(before_state) if before_state is not None else None
    safe_after_state = _redact_sensitive(after_state) if after_state is not None else None

    audit_log = UserAuditLog(
        admin_user_id=admin_user_id,
        target_user_id=target_user_id,
        action=action,
        before_json=safe_before_state,
        after_json=safe_after_state
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    
    return audit_log
