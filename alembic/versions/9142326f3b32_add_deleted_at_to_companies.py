"""add deleted_at to companies

Revision ID: 9142326f3b32
Revises: 010_phase10_1_constraints
Create Date: 2026-03-10 16:00:05.449360

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9142326f3b32'
down_revision = '010_phase10_1_constraints'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'deleted_at')
