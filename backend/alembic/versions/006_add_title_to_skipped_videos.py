"""Add title column to skipped_videos

Revision ID: 006
Revises: 005
Create Date: 2026-03-28
"""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skipped_videos", sa.Column("title", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("skipped_videos", "title")
