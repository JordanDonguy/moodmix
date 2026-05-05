"""Add user_playback_state for resume-playback

Revision ID: 008
Revises: 007
Create Date: 2026-05-12
"""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_playback_state",
        # One row per user — resume is a single pointer, not a history.
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # ON DELETE SET NULL so a removed mix doesn't cascade-delete the user's
        # resume row; the read path treats null mix_id as "nothing to resume".
        sa.Column("mix_id", sa.Uuid(), sa.ForeignKey("mixes.id", ondelete="SET NULL")),
        sa.Column("seconds_listened", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # `updated_at` index for the read-time TTL filter (rows older than 5 days
    # are not surfaced) — also useful if/when a cleanup job lands.
    op.create_index(
        "idx_user_playback_state_updated_at", "user_playback_state", ["updated_at"]
    )


def downgrade() -> None:
    op.drop_table("user_playback_state")
