"""Add skipped_videos table and validated field on mixes

Revision ID: 005
Revises: 004
Create Date: 2026-03-27
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skipped_videos",
        sa.Column("youtube_id", sa.String(), primary_key=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column("mixes", sa.Column("validated", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("mixes", "validated")
    op.drop_table("skipped_videos")
