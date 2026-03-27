"""Rename valence column to mood (dark/bright axis)

Revision ID: 003
Revises: 002
Create Date: 2026-03-26
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("mixes", "valence", new_column_name="mood")


def downgrade() -> None:
    op.alter_column("mixes", "mood", new_column_name="valence")
