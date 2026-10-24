"""کپی کانال (`.کپی‌کانال`) — جدولِ channel_copy_jobs

Revision ID: 0017_channel_copy
Revises: 0016_task_items
Create Date: 2026-10-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017_channel_copy"
down_revision: Union[str, None] = "0016_task_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_copy_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("source_title", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_ref", sa.Text(), nullable=False, server_default=""),
        sa.Column("dest_id", sa.BigInteger(), nullable=False),
        sa.Column("dest_title", sa.Text(), nullable=False, server_default=""),
        sa.Column("dest_ref", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_id", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("copied", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_hint", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="paused"),
        sa.Column("drop_author", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_channel_copy_jobs_status", "channel_copy_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_channel_copy_jobs_status", table_name="channel_copy_jobs")
    op.drop_table("channel_copy_jobs")
