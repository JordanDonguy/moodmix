"""add skip_category_filter to seed_channels

Revision ID: 534ed531b629
Revises: 006
Create Date: 2026-04-02 10:06:38.084848

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '534ed531b629'
down_revision: Union[str, Sequence[str], None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('seed_channels', sa.Column('skip_category_filter', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('seed_channels', 'skip_category_filter')
