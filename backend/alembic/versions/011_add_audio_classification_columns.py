"""Add audio classification columns to tracks

Revision ID: 011
Revises: 010
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy.dialects.postgresql import JSONB

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Drop the check constraint and partial indexes that reference soon-to-be-
    # dropped columns. Doing this before dropping the columns avoids implicit
    # cascade behavior.
    op.drop_constraint("tracks_status_check", "tracks", type_="check")
    op.drop_index("tracks_status_idx", table_name="tracks")
    op.drop_index("tracks_deezer_album_id_idx", table_name="tracks")

    # Drop columns no longer needed:
    #   - deezer_album_id: was for Deezer genre lookups; but we won't use it
    #   - preview_url: previews expire, re-fetch on demand
    #   - status: replaced by "is mood_vector populated?" check
    #   - raw_genres: was Deezer genres; switching to Discogs or Spotify later
    #   - raw_artists: simplifying to single primary artist per track
    #   - exclusion_reason: excluded tracks will be deleted, not marked
    op.drop_column("tracks", "deezer_album_id")
    op.drop_column("tracks", "preview_url")
    op.drop_column("tracks", "status")
    op.drop_column("tracks", "raw_genres")
    op.drop_column("tracks", "raw_artists")
    op.drop_column("tracks", "exclusion_reason")

    # Add audio classification + playback columns. All nullable: existing
    # rows will be backfilled by the classification job over time.
    op.add_column("tracks", sa.Column("soundcloud_url", sa.Text(), nullable=True))
    op.add_column("tracks", sa.Column("mood_vector", Vector(3), nullable=True))
    op.add_column("tracks", sa.Column("embedding", Vector(1280), nullable=True))
    op.add_column(
        "tracks",
        sa.Column("classification_confidence", sa.Float(), nullable=True),
    )
    op.add_column("tracks", sa.Column("loudness_db", sa.Float(), nullable=True))
    op.add_column("tracks", sa.Column("features", JSONB(), nullable=True))
    op.add_column("tracks", sa.Column("classifier_version", sa.Text(), nullable=True))
    op.add_column(
        "tracks",
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # HNSW indexes for fast nearest-neighbor search on the vector columns.
    # mood_vector uses L2 (3D Euclidean space); embedding uses cosine
    # (high-dim semantic similarity).
    op.execute(
        "CREATE INDEX tracks_mood_vector_idx ON tracks "
        "USING hnsw (mood_vector vector_l2_ops)"
    )
    op.execute(
        "CREATE INDEX tracks_embedding_idx ON tracks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("tracks_embedding_idx", table_name="tracks")
    op.drop_index("tracks_mood_vector_idx", table_name="tracks")

    op.drop_column("tracks", "classified_at")
    op.drop_column("tracks", "classifier_version")
    op.drop_column("tracks", "features")
    op.drop_column("tracks", "loudness_db")
    op.drop_column("tracks", "classification_confidence")
    op.drop_column("tracks", "embedding")
    op.drop_column("tracks", "mood_vector")
    op.drop_column("tracks", "soundcloud_url")

    # Restore dropped columns (data is permanently lost in upgrade).
    op.add_column("tracks", sa.Column("exclusion_reason", sa.Text(), nullable=True))
    op.add_column("tracks", sa.Column("raw_artists", JSONB(), nullable=True))
    op.add_column(
        "tracks",
        sa.Column("raw_genres", sa.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "status",
            sa.Text(),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column("tracks", sa.Column("preview_url", sa.Text(), nullable=True))
    op.add_column("tracks", sa.Column("deezer_album_id", sa.Text(), nullable=True))

    op.create_check_constraint(
        "tracks_status_check",
        "tracks",
        "status IN ('pending','classifying','active','excluded','invalid')",
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
