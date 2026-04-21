"""012_phase12_contacts_daily_calls

Revision ID: 89a4996f0774
Revises: 011_phase11_companies
Create Date: 2026-03-11 14:23:41.703146
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '89a4996f0774'
down_revision = '011_phase11_companies'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # contacts
    op.create_table(
        'contacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('first_name', sa.Text(), nullable=False),
        sa.Column('last_name', sa.Text(), nullable=False),
        sa.Column('phone', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('company_name', sa.Text(), nullable=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_contacts_user_id', 'contacts', ['user_id'])

    # daily_calls
    op.create_table(
        'daily_calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contacts.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('next_call_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_daily_calls_user_id', 'daily_calls', ['user_id'])
    op.create_index('ix_daily_calls_next_call_at', 'daily_calls', ['next_call_at'])

    # call_notes_files
    op.create_table(
        'call_notes_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('daily_call_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daily_calls.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('call_notes_files')
    op.drop_index('ix_daily_calls_next_call_at', table_name='daily_calls')
    op.drop_index('ix_daily_calls_user_id', table_name='daily_calls')
    op.drop_table('daily_calls')
    op.drop_index('ix_contacts_user_id', table_name='contacts')
    op.drop_table('contacts')

