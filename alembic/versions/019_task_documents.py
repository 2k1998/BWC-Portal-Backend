"""task_documents junction table

Revision ID: 019_task_documents
Revises: 018_add_cars_department
Create Date: 2026-04-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019_task_documents"
down_revision = "018_add_cars_department"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("task_id", "document_id", name="uq_task_documents_task_document"),
    )
    op.create_index("ix_task_documents_task_id", "task_documents", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_documents_task_id", table_name="task_documents")
    op.drop_table("task_documents")
