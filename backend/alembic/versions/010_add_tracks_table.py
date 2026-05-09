"""Add tracks table

Revision ID: 010
Revises: 009
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "artist_id",
            sa.Uuid(),
            sa.ForeignKey("artists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("isrc", sa.Text(), nullable=True),
        sa.Column("deezer_id", sa.Text(), nullable=True),
        sa.Column("deezer_album_id", sa.Text(), nullable=True),
        sa.Column("raw_artists", JSONB(), nullable=True),
        sa.Column("raw_genres", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("preview_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("deezer_id", name="tracks_deezer_id_key"),
        sa.CheckConstraint(
            "status IN ('pending','classifying','active','excluded','invalid')",
            name="tracks_status_check",
        ),
    )
    op.create_index("tracks_artist_id_idx", "tracks", ["artist_id"])
    op.create_index(
        "tracks_isrc_idx",
        "tracks",
        ["isrc"],
        postgresql_where=sa.text("isrc IS NOT NULL"),
    )
    op.create_index(
        "tracks_deezer_album_id_idx",
        "tracks",
        ["deezer_album_id"],
        postgresql_where=sa.text("deezer_album_id IS NOT NULL"),
    )
    op.create_index(
        "tracks_status_idx",
        "tracks",
        ["status"],
        postgresql_where=sa.text("status IN ('pending','classifying')"),
    )


def downgrade() -> None:
    op.drop_table("tracks")
