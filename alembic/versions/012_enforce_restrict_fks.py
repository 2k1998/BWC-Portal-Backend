"""012_enforce_restrict_fks

Revision ID: 012_enforce_restrict_fks
Revises: 89a4996f0774
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "012_enforce_restrict_fks"
down_revision = "89a4996f0774"
branch_labels = None
depends_on = None


def _drop_fk_if_exists(table_name: str, column_name: str) -> None:
    # Alembic's op.execute signature differs between versions; use connection.execute for safety.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DO $$
            DECLARE fk_name text;
            BEGIN
              SELECT c.conname
              INTO fk_name
              FROM pg_constraint c
              JOIN pg_class t ON t.oid = c.conrelid
              JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
              WHERE c.contype = 'f'
                AND t.relname = :table_name
                AND a.attname = :column_name
              LIMIT 1;

              IF fk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', :table_name, fk_name);
              END IF;
            END $$;
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )


def upgrade() -> None:
    # contacts.company_id -> companies.id ON DELETE RESTRICT
    _drop_fk_if_exists("contacts", "company_id")
    op.create_foreign_key(
        "fk_contacts_company_id_companies",
        "contacts",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # daily_calls.contact_id -> contacts.id ON DELETE RESTRICT
    _drop_fk_if_exists("daily_calls", "contact_id")
    op.create_foreign_key(
        "fk_daily_calls_contact_id_contacts",
        "daily_calls",
        "contacts",
        ["contact_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # call_notes_files.daily_call_id -> daily_calls.id ON DELETE RESTRICT
    _drop_fk_if_exists("call_notes_files", "daily_call_id")
    op.create_foreign_key(
        "fk_call_notes_files_daily_call_id_daily_calls",
        "call_notes_files",
        "daily_calls",
        ["daily_call_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_call_notes_files_daily_call_id_daily_calls", "call_notes_files", type_="foreignkey")
    op.create_foreign_key(
        "fk_call_notes_files_daily_call_id_daily_calls",
        "call_notes_files",
        "daily_calls",
        ["daily_call_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("fk_daily_calls_contact_id_contacts", "daily_calls", type_="foreignkey")
    op.create_foreign_key(
        "fk_daily_calls_contact_id_contacts",
        "daily_calls",
        "contacts",
        ["contact_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("fk_contacts_company_id_companies", "contacts", type_="foreignkey")
    op.create_foreign_key(
        "fk_contacts_company_id_companies",
        "contacts",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )

