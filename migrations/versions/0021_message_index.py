"""ایندکسِ پیام‌ها برای جستجوی معنایی: جدول message_index

Revision ID: 0021_message_index
Revises: 0020_channel_copy_watch
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0021_message_index"
down_revision: Union[str, None] = "0020_channel_copy_watch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_index",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("chat_title", sa.Text(), nullable=True),
        sa.Column("chat_username", sa.String(length=64), nullable=True),
        sa.Column("chat_kind", sa.String(length=8), nullable=False, server_default="user"),
        sa.Column("sender_id", sa.BigInteger(), nullable=True),
        sa.Column("sender_name", sa.Text(), nullable=True),
        sa.Column("is_out", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("norm_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("embed_model", sa.String(length=96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id", "message_id", name="uq_message_index_chat_msg"),
    )
    op.create_index("ix_message_index_chat_date", "message_index", ["chat_id", "date"])
    op.create_index("ix_message_index_date", "message_index", ["date"])


def downgrade() -> None:
    op.drop_index("ix_message_index_date", table_name="message_index")
    op.drop_index("ix_message_index_chat_date", table_name="message_index")
    op.drop_table("message_index")
