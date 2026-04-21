"""Phase 2: Add companies and departments tables

Revision ID: 002_phase2_companies_departments
Revises: 001_initial_phase1
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_phase2_companies_departments'
down_revision = '001_initial_phase1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create companies table
    op.create_table(
        'companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('vat_number', sa.String(), nullable=True),
        sa.Column('occupation', sa.String(), nullable=True),
        sa.Column('creation_date', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create unique index on company name
    op.create_index('ix_companies_name', 'companies', ['name'], unique=True)
    
    # Create departments table
    op.create_table(
        'departments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create unique index on department name
    op.create_index('ix_departments_name', 'departments', ['name'], unique=True)


def downgrade() -> None:
    # Drop departments table
    op.drop_index('ix_departments_name', table_name='departments')
    op.drop_table('departments')
    
    # Drop companies table
    op.drop_index('ix_companies_name', table_name='companies')
    op.drop_table('companies')
