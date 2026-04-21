"""
015_phase15_cars

Phase 15 - Cars / Fleet Management module
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "015_phase15_cars"
down_revision = "014_phase14_chat_profiles"
branch_labels = None
depends_on = None


CAR_STATUS_VALUES = ("available", "rented", "sold")
CAR_INCOME_TYPE_VALUES = ("rental", "sale")


def upgrade() -> None:
    car_status_check = "status IN ({values})".format(
        values=", ".join([f"'{v}'" for v in CAR_STATUS_VALUES])
    )
    car_income_type_check = "income_type IN ({values})".format(
        values=", ".join([f"'{v}'" for v in CAR_INCOME_TYPE_VALUES])
    )

    op.create_table(
        "cars",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("make", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("license_plate", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'available'")),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("license_plate", name="uq_cars_license_plate"),
        sa.CheckConstraint(car_status_check, name="check_car_status"),
    )
    op.create_index("ix_cars_status", "cars", ["status"])

    op.create_table(
        "car_maintenance",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "car_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cars.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("last_service_date", sa.Date(), nullable=True),
        sa.Column("next_service_date", sa.Date(), nullable=True),
        sa.Column("last_kteo_date", sa.Date(), nullable=True),
        sa.Column("next_kteo_date", sa.Date(), nullable=True),
        sa.Column("last_tyre_change_date", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_car_maintenance_car_id", "car_maintenance", ["car_id"], unique=True)

    op.create_table(
        "car_incomes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "car_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cars.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("customer_name", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("income_type", sa.Text(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(car_income_type_check, name="check_car_income_type"),
    )
    op.create_index("ix_car_incomes_car_id", "car_incomes", ["car_id"])
    op.create_index("ix_car_incomes_transaction_date", "car_incomes", ["transaction_date"])

    op.create_table(
        "car_expenses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "car_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cars.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("expense_type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_car_expenses_car_id", "car_expenses", ["car_id"])
    op.create_index("ix_car_expenses_transaction_date", "car_expenses", ["transaction_date"])


def downgrade() -> None:
    op.drop_index("ix_car_expenses_transaction_date", table_name="car_expenses")
    op.drop_index("ix_car_expenses_car_id", table_name="car_expenses")
    op.drop_table("car_expenses")

    op.drop_index("ix_car_incomes_transaction_date", table_name="car_incomes")
    op.drop_index("ix_car_incomes_car_id", table_name="car_incomes")
    op.drop_table("car_incomes")

    op.drop_index("ix_car_maintenance_car_id", table_name="car_maintenance")
    op.drop_table("car_maintenance")

    op.drop_index("ix_cars_status", table_name="cars")
    op.drop_table("cars")
