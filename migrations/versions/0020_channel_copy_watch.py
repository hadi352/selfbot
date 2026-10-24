"""کپی کانال: ستون‌های watch («از این به بعد») و children (کارِ سازمان‌دهنده‌ی چندکاناله)

Revision ID: 0020_channel_copy_watch
Revises: 0019_channel_copy_targets
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020_channel_copy_watch"
down_revision: Union[str, None] = "0019_channel_copy_targets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channel_copy_jobs",
        sa.Column("watch", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "channel_copy_jobs",
        sa.Column("children", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("channel_copy_jobs", "children")
    op.drop_column("channel_copy_jobs", "watch")
