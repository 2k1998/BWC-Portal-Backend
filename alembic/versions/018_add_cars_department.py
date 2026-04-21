"""Add Cars department row

Revision ID: 018_add_cars_department
Revises: 017_phase17_index_hardening
Create Date: 2026-04-06

"""
from alembic import op
from sqlalchemy import text

revision = "018_add_cars_department"
down_revision = "017_phase17_index_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        text(
            """
            INSERT INTO departments (id, name, created_at)
            SELECT gen_random_uuid(), 'Cars', NOW()
            WHERE NOT EXISTS (SELECT 1 FROM departments WHERE name = 'Cars')
            """
        )
    )


def downgrade() -> None:
    op.execute(text("DELETE FROM departments WHERE name = 'Cars'"))
