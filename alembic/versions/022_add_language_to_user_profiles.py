"""add language column to user_profiles

Revision ID: 022_add_language_to_user_profiles
Revises: 021_task_comments
Create Date: 2026-04-08

"""
from alembic import op
import sqlalchemy as sa

revision = "022_user_profiles_language"
down_revision = "021_task_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "language",
            sa.String(2),
            nullable=False,
            server_default="en",
        ),
    )
    op.create_check_constraint(
        "ck_user_profiles_language_valid",
        "user_profiles",
        "language IN ('en', 'el')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_profiles_language_valid", "user_profiles", type_="check")
    op.drop_column("user_profiles", "language")
