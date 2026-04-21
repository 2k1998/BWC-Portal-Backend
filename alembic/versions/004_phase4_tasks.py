"""Phase 4: Add tasks table

Revision ID: 004_phase4_tasks
Revises: 003_phase3_teams
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_phase4_tasks'
down_revision = '003_phase3_teams'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('department', sa.Text(), nullable=False),
        sa.Column('priority', sa.Text(), nullable=False),
        sa.Column('urgency_label', sa.Text(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=False),
        sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_team_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='New'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['assigned_team_id'], ['teams.id'], ondelete='RESTRICT'),
        sa.CheckConstraint(
            '(assigned_user_id IS NOT NULL AND assigned_team_id IS NULL) OR '
            '(assigned_user_id IS NULL AND assigned_team_id IS NOT NULL)',
            name='check_single_assignment'
        ),
    )


def downgrade() -> None:
    # Drop tasks table
    op.drop_table('tasks')
