"""Update genres: remove blues, environment, reggae/dub, downtempo, guitar. Add acoustic & piano.

Revision ID: 004
Revises: 003
Create Date: 2026-03-27
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM genres WHERE slug IN ('blues', 'environment', 'reggae-dub', 'downtempo', 'guitar')")
    op.execute("INSERT INTO genres (name, slug) VALUES ('Acoustic & Piano', 'acoustic-and-piano')")


def downgrade() -> None:
    op.execute("DELETE FROM genres WHERE slug = 'acoustic-and-piano'")
    op.execute("""
        INSERT INTO genres (name, slug) VALUES
            ('Blues', 'blues'),
            ('Environment', 'environment'),
            ('Reggae / Dub', 'reggae-dub'),
            ('Downtempo', 'downtempo'),
            ('Guitar', 'guitar')
    """)
