"""add maintenance recurrence interval

Revision ID: 5e470bb28a37
Revises: 6bf8c5b7ecf3
Create Date: 2026-07-22 03:50:14.075599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5e470bb28a37'
down_revision: Union[str, None] = '6bf8c5b7ecf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

recurrence_unit_enum = sa.Enum(
    'days', 'weeks', 'months', 'years', name='maintenance_recurrence_unit'
)


def upgrade() -> None:
    recurrence_unit_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('maintenance_items', sa.Column('recurrence_value', sa.Integer(), nullable=True))
    op.add_column(
        'maintenance_items',
        sa.Column('recurrence_unit', recurrence_unit_enum, nullable=True),
    )


def downgrade() -> None:
    op.drop_column('maintenance_items', 'recurrence_unit')
    op.drop_column('maintenance_items', 'recurrence_value')
    recurrence_unit_enum.drop(op.get_bind(), checkfirst=True)
