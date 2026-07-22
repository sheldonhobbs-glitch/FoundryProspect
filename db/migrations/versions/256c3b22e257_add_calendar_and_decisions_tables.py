"""add calendar and decisions tables

Revision ID: 256c3b22e257
Revises: 5e470bb28a37
Create Date: 2026-07-22 03:55:49.201908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


revision: str = '256c3b22e257'
down_revision: Union[str, None] = '5e470bb28a37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False: op.create_table() would otherwise unconditionally try to
# CREATE TYPE for this column's Enum, even though we create it ourselves
# below with checkfirst=True — it doesn't check, it just tries, and blows up
# with "already exists". create_type only gates the *automatic* table-create/
# drop event hooks; it has no effect on our own explicit create()/drop() calls.
# (Plain sa.Enum silently ignores create_type — it has to be the Postgres-
# dialect ENUM for this flag to actually do anything.)
decision_status_enum = ENUM('open', 'decided', name='decision_status', create_type=False)


def upgrade() -> None:
    decision_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table('calendar_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('google_event_id', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.String(length=2000), nullable=True),
    sa.Column('location', sa.String(length=300), nullable=True),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('all_day', sa.Boolean(), nullable=False),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('google_event_id')
    )
    op.create_table('decisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item', sa.String(length=300), nullable=False),
    sa.Column('notes', sa.String(length=2000), nullable=True),
    sa.Column('status', decision_status_enum, nullable=False),
    sa.Column('decision', sa.String(length=2000), nullable=True),
    sa.Column('decided_at', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('google_calendar_credentials',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('refresh_token', sa.String(length=500), nullable=False),
    sa.Column('google_account_email', sa.String(length=255), nullable=True),
    sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('google_calendar_credentials')
    op.drop_table('decisions')
    op.drop_table('calendar_events')

    decision_status_enum.drop(op.get_bind(), checkfirst=True)
