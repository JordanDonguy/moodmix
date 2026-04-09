"""Initial schema — mixes, genres, mix_genres, seed_channels, pipeline_runs

Revision ID: 001
Revises:
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Genres
    op.create_table(
        "genres",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("slug", sa.String(), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Seed genres
    op.execute("""
        INSERT INTO genres (name, slug) VALUES
            ('Lo-Fi', 'lo-fi'),
            ('Hip-Hop', 'hip-hop'),
            ('Synthwave', 'synthwave'),
            ('Chill Electronic', 'chill-electronic'),
            ('Deep House', 'deep-house'),
            ('Drum & Bass', 'drum-and-bass'),
            ('Neo-Soul / R&B', 'neo-soul-r-and-b'),
            ('Jazz', 'jazz'),
            ('Ambient', 'ambient'),
            ('Acoustic & Piano', 'acoustic-and-piano')
    """)

    # Mixes
    op.create_table(
        "mixes",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("youtube_id", sa.String(), unique=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("channel_name", sa.String()),
        sa.Column("channel_id", sa.String(), index=True),
        sa.Column("description", sa.Text()),
        sa.Column("tags", sa.ARRAY(sa.String())),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("thumbnail_url", sa.String()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("view_count", sa.Integer()),
        sa.Column("mood_vector", Vector(3)),
        sa.Column("valence", sa.Float()),
        sa.Column("energy", sa.Float()),
        sa.Column("instrumentation", sa.Float()),
        sa.Column("has_vocals", sa.Boolean()),
        sa.Column("classification_confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("unavailable_at", sa.DateTime(timezone=True)),
    )

    # pgvector HNSW index
    op.execute("CREATE INDEX idx_mixes_mood_vector ON mixes USING hnsw (mood_vector vector_cosine_ops)")

    # Mix-Genre association
    op.create_table(
        "mix_genres",
        sa.Column("mix_id", sa.Uuid(), sa.ForeignKey("mixes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("genre_id", sa.Uuid(), sa.ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("idx_mix_genres_genre_id", "mix_genres", ["genre_id"])

    # Seed channels
    op.create_table(
        "seed_channels",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", sa.String(), unique=True, nullable=False),
        sa.Column("channel_name", sa.String(), nullable=False),
        sa.Column("uploads_playlist_id", sa.String()),
        sa.Column("active", sa.Boolean(), default=True, nullable=False),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True)),
        sa.Column("total_mixes_found", sa.Integer(), default=0, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Pipeline runs
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pipeline_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="running", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("mixes_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mixes_added", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata", sa.JSON()),
    )
    op.create_index("idx_pipeline_runs_type", "pipeline_runs", ["pipeline_type", sa.text("started_at DESC")])


def downgrade() -> None:
    op.drop_table("pipeline_runs")
    op.drop_table("seed_channels")
    op.drop_table("mix_genres")
    op.drop_table("mixes")
    op.drop_table("genres")
    op.execute("DROP EXTENSION IF EXISTS vector")
