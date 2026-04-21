"""Seed Phase 3 departments set

Revision ID: 020_seed_phase3_departments_set
Revises: 019_task_documents
Create Date: 2026-04-07

"""
from alembic import op
from sqlalchemy import text

revision = "020_seed_phase3_departments_set"
down_revision = "019_task_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        text(
            """
            INSERT INTO departments (id, name, created_at)
            VALUES
                (gen_random_uuid(), 'Ενέργεια', NOW()),
                (gen_random_uuid(), 'Ασφάλειες', NOW()),
                (gen_random_uuid(), 'Ακαδημία Αυτοβελτίωσης', NOW()),
                (gen_random_uuid(), 'Ακίνητα', NOW()),
                (gen_random_uuid(), 'Επενδύσεις', NOW()),
                (gen_random_uuid(), 'Marketing/Κοινωνικά Δίκτυα', NOW()),
                (gen_random_uuid(), 'Τηλεπικοινωνίες', NOW()),
                (gen_random_uuid(), 'Cars', NOW())
            ON CONFLICT (name) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # Intentionally left as no-op to avoid deleting departments that may be referenced by tasks.
    pass
