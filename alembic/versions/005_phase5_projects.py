"""Phase 5: Add projects table

Revision ID: 005_phase5_projects
Revises: 004_phase4_tasks
Create Date: 2026-02-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_phase5_projects'
down_revision = '004_phase4_tasks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('project_type', sa.Text(), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('priority', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('budget_amount', sa.Numeric(), nullable=True),
        sa.Column('project_manager_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_address', sa.Text(), nullable=True),
        sa.Column('location_postcode', sa.Text(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('expected_completion_date', sa.Date(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='Planning'),
        sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['project_manager_user_id'], ['users.id'], ondelete='RESTRICT'),
    )


def downgrade() -> None:
    op.drop_table('projects')
