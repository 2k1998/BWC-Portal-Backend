"""
017_phase17_index_hardening

Add missing indexes for FK/filter performance hardening.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "017_phase17_index_hardening"
down_revision = "016_phase17_retention_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_tasks_company_id", "tasks", ["company_id"], unique=False)
    op.create_index("ix_tasks_deadline", "tasks", ["deadline"], unique=False)

    op.create_index("ix_contacts_company_id", "contacts", ["company_id"], unique=False)

    op.create_index("ix_daily_calls_contact_id", "daily_calls", ["contact_id"], unique=False)

    op.create_index("ix_notifications_actor_user_id", "notifications", ["actor_user_id"], unique=False)

    op.create_index("ix_teams_head_user_id", "teams", ["head_user_id"], unique=False)
    op.create_index("ix_teams_created_by_user_id", "teams", ["created_by_user_id"], unique=False)

    op.create_index("ix_team_members_team_id", "team_members", ["team_id"], unique=False)
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_team_members_user_id", table_name="team_members")
    op.drop_index("ix_team_members_team_id", table_name="team_members")

    op.drop_index("ix_teams_created_by_user_id", table_name="teams")
    op.drop_index("ix_teams_head_user_id", table_name="teams")

    op.drop_index("ix_notifications_actor_user_id", table_name="notifications")

    op.drop_index("ix_daily_calls_contact_id", table_name="daily_calls")

    op.drop_index("ix_contacts_company_id", table_name="contacts")

    op.drop_index("ix_tasks_deadline", table_name="tasks")
    op.drop_index("ix_tasks_company_id", table_name="tasks")
