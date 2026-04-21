"""Phase 10.1: Notification Constraints

Revision ID: 010_phase10_1_constraints
Revises: 009_phase10_notifications
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '010_phase10_1_constraints'
down_revision = '162c54803443'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # 1. Pre-validation: Check for invalid notification_types
    result = conn.execute(text("SELECT DISTINCT notification_type FROM notifications"))
    existing_types = {row[0] for row in result}
    allowed_types = {'ASSIGNMENT', 'STATUS_CHANGE'}
    invalid_types = existing_types - allowed_types
    
    if invalid_types:
        raise ValueError(
            f"Migration Aborted: Found invalid notification_types: {invalid_types}. "
            "Manual cleanup required before applying strict constraints."
        )

    # 2. Pre-validation: Check for invalid read_status
    result = conn.execute(text("SELECT DISTINCT read_status FROM notifications"))
    existing_statuses = {row[0] for row in result}
    allowed_statuses = {'Unread', 'Read'}
    invalid_statuses = existing_statuses - allowed_statuses
    
    if invalid_statuses:
         raise ValueError(
            f"Migration Aborted: Found invalid read_status: {invalid_statuses}. "
            "Manual cleanup required before applying strict constraints."
        )

    # 3. Apply CHECK Constraints
    # Note: We use raw SQL for CHECK constraints in some DBs, but Alembic supports op.create_check_constraint
    # or we can rely on result of Table args if we used auto-generate, but here we prefer explicit DDL.
    
    op.create_check_constraint(
        "ck_notification_type_valid",
        "notifications",
        "notification_type IN ('ASSIGNMENT', 'STATUS_CHANGE')"
    )
    
    op.create_check_constraint(
        "ck_notification_read_status_valid",
        "notifications",
        "read_status IN ('Unread', 'Read')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_notification_type_valid", "notifications", type_="check")
    op.drop_constraint("ck_notification_read_status_valid", "notifications", type_="check")
