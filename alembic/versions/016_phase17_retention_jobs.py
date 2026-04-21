"""
016_phase17_retention_jobs

Phase 17 - Retention jobs schema alignment:
- tasks.deleted_at
- events.deleted_at
- events.event_start_at (backfilled from event_datetime)
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "016_phase17_retention_jobs"
down_revision = "015_phase15_cars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("events", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("events", sa.Column("event_start_at", sa.DateTime(timezone=True), nullable=True))

    # Backfill from the legacy column used by earlier phases.
    op.execute("UPDATE events SET event_start_at = event_datetime WHERE event_start_at IS NULL")

    op.alter_column("events", "event_start_at", nullable=False)

    op.create_index("ix_tasks_deleted_at", "tasks", ["deleted_at"], unique=False)
    op.create_index("ix_events_deleted_at", "events", ["deleted_at"], unique=False)
    op.create_index("ix_events_event_start_at", "events", ["event_start_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_events_event_start_at", table_name="events")
    op.drop_index("ix_events_deleted_at", table_name="events")
    op.drop_index("ix_tasks_deleted_at", table_name="tasks")

    op.drop_column("events", "event_start_at")
    op.drop_column("events", "deleted_at")
    op.drop_column("tasks", "deleted_at")
