"""کپی کانال: جدولِ channel_copy_targets (اسم‌های ذخیره‌شده برای کانال‌ها)

چون کانالِ خصوصی یوزرنیم نداره و آیدیِ عددی‌اش هم دستِ کاربر نیست، با
`.کپی‌کانال ذخیره <اسم> <آدرس یا ریپلای>` یک اسمِ دلخواه به یک کانال وصل می‌شه
و بعداً همون اسم توی «شروع» به‌جای آدرس قابلِ استفاده‌ست.

Revision ID: 0019_channel_copy_targets
Revises: 0018_channel_copy_from_date
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019_channel_copy_targets"
down_revision: Union[str, None] = "0018_channel_copy_from_date"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_copy_targets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_channel_copy_targets_name", "channel_copy_targets", ["name"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_channel_copy_targets_name", table_name="channel_copy_targets")
    op.drop_table("channel_copy_targets")
