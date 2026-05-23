"""Add streaming_resolved_at to tracks

Lets the streaming-link resolver script skip tracks it has already attempted,
regardless of whether yt-dlp actually found URLs. Mirrors the classifier's
``classified_at`` pattern.

Revision ID: 013
Revises: 012
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("streaming_resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill: tracks that already have at least one URL were obviously
    # attempted by the first script run — mark them so we don't re-process.
    # Tracks where both URLs are NULL stay NULL (will be retried once more,
    # which is fine — a one-time retry on failures is mostly harmless).
    op.execute(
        """
        UPDATE tracks
        SET streaming_resolved_at = updated_at
        WHERE youtube_video_id IS NOT NULL OR soundcloud_url IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("tracks", "streaming_resolved_at")
