"""
014_phase14_chat_profiles

Phase 14 — Messaging, Chat & Approvals

Adds:
- user_profiles
- chat_threads
- chat_messages
- approval_requests

This migration follows the provided schema freeze (PRD #17) and PRD #13.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "014_phase14_chat_profiles"
down_revision = "013_phase13_payments"
branch_labels = None
depends_on = None


REQUEST_TYPE_VALUES = ("General", "Expenses", "Task", "Project", "Purchase")
APPROVAL_STATUS_VALUES = ("pending", "approved", "denied")


def upgrade() -> None:
    # ----------------------
    # user_profiles
    # ----------------------
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("profile_photo_url", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
    )

    # ----------------------
    # chat_threads
    # ----------------------
    op.create_table(
        "chat_threads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_one_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_two_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_one_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_two_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("user_one_id", "user_two_id", name="uq_chat_threads_user_pair"),
        # Schema comment requirement: enforce user_one_id < user_two_id to prevent duplicates.
        sa.CheckConstraint("user_one_id < user_two_id", name="ck_chat_threads_user_order"),
    )

    # ----------------------
    # chat_messages
    # ----------------------
    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sender_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("message_text", sa.Text(), nullable=True),
        # Optional file attachment (PRD says files(id), repo maps it to documents(id))
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sender_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["documents.id"],
            ondelete="RESTRICT",
        ),
    )

    # ----------------------
    # approval_requests
    # ----------------------
    request_type_check = "request_type IN ({values})".format(
        values=", ".join([f"'{v}'" for v in REQUEST_TYPE_VALUES])
    )
    status_check = "status IN ({values})".format(
        values=", ".join([f"'{v}'" for v in APPROVAL_STATUS_VALUES])
    )

    op.create_table(
        "approval_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "requester_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "receiver_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "request_type",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["requester_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["receiver_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(request_type_check, name="ck_approval_request_type_valid"),
        sa.CheckConstraint(status_check, name="ck_approval_request_status_valid"),
    )


def downgrade() -> None:
    # Reverse order: dependents first.
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
    op.drop_table("approval_requests")
    op.drop_table("user_profiles")

