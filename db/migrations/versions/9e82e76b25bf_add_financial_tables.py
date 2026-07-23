"""add financial tables (receipts, cashflow entries, warranty links)

Revision ID: 9e82e76b25bf
Revises: c51e8dde88de
Create Date: 2026-07-23 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


revision: str = '9e82e76b25bf'
down_revision: Union[str, None] = 'c51e8dde88de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

cashflow_kind_enum = ENUM('income', 'expense', name='cashflow_kind', create_type=False)


def upgrade() -> None:
    op.create_table('receipts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vendor', sa.String(length=200), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('purchased_at', sa.Date(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('notes', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    cashflow_kind_enum.create(op.get_bind(), checkfirst=True)
    op.create_table('cashflow_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', cashflow_kind_enum, nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('warranties', sa.Column('retailer', sa.String(length=200), nullable=True))
    op.add_column('warranties', sa.Column('receipt_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_warranties_receipt_id', 'warranties', 'receipts', ['receipt_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_warranties_receipt_id', 'warranties', type_='foreignkey')
    op.drop_column('warranties', 'receipt_id')
    op.drop_column('warranties', 'retailer')

    op.drop_table('cashflow_entries')
    cashflow_kind_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_table('receipts')
