"""Add youtube_video_id to tracks

Revision ID: 012
Revises: 011
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks", sa.Column("youtube_video_id", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("tracks", "youtube_video_id")
