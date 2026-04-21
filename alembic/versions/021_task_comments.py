"""task comments and COMMENT notification type

Revision ID: 021_task_comments
Revises: 020_seed_phase3_departments_set
Create Date: 2026-04-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "021_task_comments"
down_revision = "020_seed_phase3_departments_set"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_comments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_task_comments_task_id", "task_comments", ["task_id"], unique=False)

    op.drop_constraint("ck_notification_type_valid", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_type_valid",
        "notifications",
        "notification_type IN ('ASSIGNMENT', 'STATUS_CHANGE', 'COMMENT')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_notification_type_valid", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_type_valid",
        "notifications",
        "notification_type IN ('ASSIGNMENT', 'STATUS_CHANGE')",
    )
    op.drop_index("ix_task_comments_task_id", table_name="task_comments")
    op.drop_table("task_comments")
