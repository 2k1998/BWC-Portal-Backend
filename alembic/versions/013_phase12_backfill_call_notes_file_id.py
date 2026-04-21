"""013_phase12_backfill_call_notes_file_id

Backfill `call_notes_files.file_id` from legacy `document_id`.

This repo previously created `call_notes_files.document_id` during early Phase 12 work.
The Phase 12 contract requires `file_id` instead (FK to `documents.id`).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
# IMPORTANT: alembic_version.version_num is varchar(32) in this DB,
# so keep revision IDs short.
revision = "013_phase12_fileid_backfill"
down_revision = "012_enforce_restrict_fks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    table_name = "call_notes_files"
    cols = {c["name"] for c in inspector.get_columns(table_name)}

    if "file_id" not in cols:
        op.add_column(
            table_name,
            sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        )

    # Backfill from legacy document_id if present.
    if "document_id" in cols:
        op.execute(
            sa.text(
                "UPDATE call_notes_files SET file_id = document_id WHERE file_id IS NULL"
            )
        )

    # Enforce NOT NULL if we now have values.
    null_count = conn.execute(sa.text("SELECT COUNT(*) FROM call_notes_files WHERE file_id IS NULL")).scalar()
    if null_count and int(null_count) > 0:
        raise RuntimeError(f"Phase 12 backfill failed: {null_count} rows still have NULL file_id")

    op.alter_column(table_name, "file_id", nullable=False)

    # Ensure foreign key exists for file_id -> documents.id with RESTRICT.
    fks = inspector.get_foreign_keys(table_name)
    has_file_fk = False
    for fk in fks:
        constrained_cols = set(fk.get("constrained_columns") or [])
        referred_cols = set(fk.get("referred_columns") or [])
        if "file_id" in constrained_cols and "id" in referred_cols:
            has_file_fk = True
            break

    if not has_file_fk:
        op.create_foreign_key(
            "fk_call_notes_files_file_id_documents",
            table_name,
            "documents",
            ["file_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """
    Best-effort downgrade: drop the FK and column.
    (Not expected to be used for production; schema freeze relies on forward-only changes.)
    """
    conn = op.get_bind()
    inspector = inspect(conn)

    table_name = "call_notes_files"
    cols = {c["name"] for c in inspector.get_columns(table_name)}
    if "file_id" in cols:
        # Drop FK if it exists.
        try:
            op.drop_constraint("fk_call_notes_files_file_id_documents", table_name, type_="foreignkey")
        except Exception:
            pass

        op.drop_column(table_name, "file_id")

