"""Add artists table

Revision ID: 009
Revises: 008
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artists",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("spotify_id", sa.Text(), nullable=True),
        sa.Column("deezer_id", sa.Text(), nullable=True),
        sa.Column("resolution_tier", sa.Text(), nullable=True),
        sa.Column("genres", sa.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("spotify_id", name="artists_spotify_id_key"),
        sa.UniqueConstraint("deezer_id", name="artists_deezer_id_key"),
        sa.CheckConstraint(
            "resolution_tier IN ('confirmed', 'probable', 'ambiguous', 'failed')",
            name="artists_resolution_tier_check",
        ),
    )
    # Case-insensitive dedup: same name with different casing collapses to one row.
    op.execute(
        "CREATE UNIQUE INDEX artists_name_lower_idx ON artists (LOWER(name))"
    )


def downgrade() -> None:
    op.drop_table("artists")
