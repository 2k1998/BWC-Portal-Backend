"""013_phase13_payments

Create payments table for operational financial tracking.

Schema is defined to match PRD #11 and the provided schema freeze constraints.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "013_phase13_payments"
down_revision = "013_phase12_fileid_backfill"
branch_labels = None
depends_on = None


PAYMENT_TYPE_VALUES = ("salary", "commission", "bonus", "rent", "bill", "purchase", "service")


def upgrade() -> None:
    payment_type_check = "payment_type IN ({values})".format(
        values=", ".join([f"'{v}'" for v in PAYMENT_TYPE_VALUES])
    )

    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default=sa.text("'EUR'")),
        sa.Column("payment_type", sa.Text(), nullable=False),
        sa.Column("payment_category", sa.Text(), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("is_income", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "employee_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(payment_type_check, name="check_payment_type"),
    )


def downgrade() -> None:
    op.drop_table("payments")

