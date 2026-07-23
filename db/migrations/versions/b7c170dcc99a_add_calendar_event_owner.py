"""add calendar event owner

Revision ID: b7c170dcc99a
Revises: 256c3b22e257
Create Date: 2026-07-23 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c170dcc99a'
down_revision: Union[str, None] = '256c3b22e257'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'calendar_events',
        sa.Column('owner', sa.String(length=20), nullable=False, server_default='shared'),
    )


def downgrade() -> None:
    op.drop_column('calendar_events', 'owner')
