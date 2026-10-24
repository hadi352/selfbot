"""کپی کانال: ستونِ from_date (تاریخِ شروعِ خواسته‌شده) رویِ channel_copy_jobs

«از 1403/05/01» → تاریخِ شروعِ کار فقط برایِ نمایشِ دوباره ذخیره می‌شه؛
خودِ شروعِ کپی مثلِ قبل از رویِ last_id انجام می‌شه.

Revision ID: 0018_channel_copy_from_date
Revises: 0017_channel_copy
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018_channel_copy_from_date"
down_revision: Union[str, None] = "0017_channel_copy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DateTime بدونِ timezone چون مقدارش «به وقتِ کاربر»ه (فقط برایِ نمایش)
    op.add_column(
        "channel_copy_jobs",
        sa.Column("from_date", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_copy_jobs", "from_date")
