"""011_phase11_companies

Revision ID: 011_phase11_companies
Revises: 9142326f3b32
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "011_phase11_companies"
down_revision = "9142326f3b32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if "companies" not in inspector.get_table_names():
        op.create_table(
            "companies",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("vat_number", sa.Text(), nullable=True),
            sa.Column("occupation", sa.Text(), nullable=True),
            sa.Column("creation_date", sa.Date(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_unique_constraint("uq_companies_name", "companies", ["name"])
        return

    # Non-destructive schema hardening for existing tables:
    # - keep rows/IDs
    # - only adjust defaults/types and required uniqueness
    op.alter_column(
        "companies",
        "id",
        server_default=sa.text("gen_random_uuid()"),
        existing_type=postgresql.UUID(as_uuid=True),
    )

    op.alter_column(
        "companies",
        "name",
        existing_type=sa.String(),
        type_=sa.Text(),
        existing_nullable=False,
        nullable=False,
    )
    op.alter_column(
        "companies",
        "vat_number",
        existing_type=sa.String(),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True,
    )
    op.alter_column(
        "companies",
        "occupation",
        existing_type=sa.String(),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True,
    )
    op.alter_column(
        "companies",
        "description",
        existing_type=sa.Text(),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "companies",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        existing_nullable=False,
        nullable=False,
    )
    op.alter_column(
        "companies",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "companies",
        "deleted_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        nullable=True,
    )

    # Ensure the frozen constraint: `name TEXT NOT NULL UNIQUE`
    uniques = inspector.get_unique_constraints("companies")
    has_unique_on_name = any("name" in (uc.get("column_names") or []) for uc in uniques)
    if not has_unique_on_name:
        op.create_unique_constraint("uq_companies_name", "companies", ["name"])


def downgrade() -> None:
    # Best-effort downgrade; schema freeze relies on upgrade-only usage.
    conn = op.get_bind()
    inspector = inspect(conn)
    uniques = inspector.get_unique_constraints("companies") if "companies" in inspector.get_table_names() else []
    if any(uc.get("name") == "uq_companies_name" for uc in uniques):
        op.drop_constraint("uq_companies_name", "companies", type_="unique")

