"""Initial Phase 1 migration - Auth, Users & Permissions

Revision ID: 001_initial_phase1
Revises: 
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '001_initial_phase1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('user_type', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('force_password_change', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('manager_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_manager_id', 'users', ['manager_id'])
    
    # Create pages table
    op.create_table(
        'pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('label'),
        sa.UniqueConstraint('key')
    )
    op.create_index('ix_pages_key', 'pages', ['key'])
    
    # Create auth_refresh_tokens table
    op.create_table(
        'auth_refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('token')
    )
    op.create_index('ix_auth_refresh_tokens_user_id', 'auth_refresh_tokens', ['user_id'])
    op.create_index('ix_auth_refresh_tokens_token', 'auth_refresh_tokens', ['token'])
    
    # Create user_page_permissions table
    op.create_table(
        'user_page_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('access', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['page_id'], ['pages.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('user_id', 'page_id', name='uq_user_page')
    )
    op.create_index('ix_user_page_permissions_user_id', 'user_page_permissions', ['user_id'])
    op.create_index('ix_user_page_permissions_page_id', 'user_page_permissions', ['page_id'])
    
    # Create user_audit_logs table
    op.create_table(
        'user_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('admin_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('before_json', postgresql.JSON(), nullable=True),
        sa.Column('after_json', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], ondelete='RESTRICT')
    )
    op.create_index('ix_user_audit_logs_admin_user_id', 'user_audit_logs', ['admin_user_id'])
    op.create_index('ix_user_audit_logs_target_user_id', 'user_audit_logs', ['target_user_id'])


def downgrade() -> None:
    op.drop_table('user_audit_logs')
    op.drop_table('user_page_permissions')
    op.drop_table('auth_refresh_tokens')
    op.drop_table('pages')
    op.drop_table('users')
