"""add household admin tables

Revision ID: 6bf8c5b7ecf3
Revises:
Create Date: 2026-07-21 20:09:55.909237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


revision: str = '6bf8c5b7ecf3'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False: op.create_table() would otherwise unconditionally try to
# CREATE TYPE for these columns' Enums, even though we create them ourselves
# below with checkfirst=True — it doesn't check, it just tries, and blows up
# with "already exists". create_type only gates the *automatic* table-create/
# drop event hooks; it has no effect on our own explicit create()/drop() calls.
# (Plain sa.Enum silently ignores create_type — it has to be the Postgres-
# dialect ENUM for this flag to actually do anything.)
bill_recurrence_enum = ENUM(
    'one_time', 'weekly', 'monthly', 'quarterly', 'yearly',
    name='bill_recurrence', create_type=False,
)
subscription_billing_cycle_enum = ENUM(
    'weekly', 'monthly', 'quarterly', 'yearly',
    name='subscription_billing_cycle', create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    bill_recurrence_enum.create(bind, checkfirst=True)
    subscription_billing_cycle_enum.create(bind, checkfirst=True)

    op.create_table('bills',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('recurrence', bill_recurrence_enum, nullable=False),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('paid', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('maintenance_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('task', sa.String(length=200), nullable=False),
    sa.Column('property_or_appliance', sa.String(length=200), nullable=False),
    sa.Column('last_done', sa.Date(), nullable=True),
    sa.Column('next_due', sa.Date(), nullable=True),
    sa.Column('notes', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pending_notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resource_type', sa.String(length=50), nullable=False),
    sa.Column('resource_id', sa.Integer(), nullable=False),
    sa.Column('message', sa.String(length=500), nullable=False),
    sa.Column('sent', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('subscriptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('cost', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('billing_cycle', subscription_billing_cycle_enum, nullable=False),
    sa.Column('renewal_date', sa.Date(), nullable=False),
    sa.Column('cancel_by_date', sa.Date(), nullable=True),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('warranties',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item', sa.String(length=200), nullable=False),
    sa.Column('purchase_date', sa.Date(), nullable=False),
    sa.Column('expiry_date', sa.Date(), nullable=False),
    sa.Column('document_reference', sa.String(length=500), nullable=True),
    sa.Column('notes', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('warranties')
    op.drop_table('subscriptions')
    op.drop_table('pending_notifications')
    op.drop_table('maintenance_items')
    op.drop_table('bills')

    bind = op.get_bind()
    subscription_billing_cycle_enum.drop(bind, checkfirst=True)
    bill_recurrence_enum.drop(bind, checkfirst=True)
