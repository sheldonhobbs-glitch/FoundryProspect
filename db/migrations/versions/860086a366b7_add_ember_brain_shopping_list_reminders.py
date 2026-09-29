"""add ember brain, shopping list, reminders

Revision ID: 860086a366b7
Revises: 5bdf1b69cc98
Create Date: 2026-09-29 19:42:16.823341

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '860086a366b7'
down_revision: Union[str, None] = '5bdf1b69cc98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ember_conversations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('member', sa.String(length=50), nullable=True),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('closed', sa.Boolean(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ember_traces',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=True),
    sa.Column('member', sa.String(length=50), nullable=True),
    sa.Column('provider', sa.String(length=50), nullable=True),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('rounds', sa.Integer(), nullable=False),
    sa.Column('tools_requested', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tools_executed', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tools_gated', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tools_failed', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('outcome', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_read_tokens', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ember_traces_created_at'), 'ember_traces', ['created_at'], unique=False)
    op.create_index(op.f('ix_ember_traces_request_id'), 'ember_traces', ['request_id'], unique=False)
    op.create_table('reminders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(length=500), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('due_time', sa.Time(), nullable=True),
    sa.Column('for_member', sa.String(length=50), nullable=True),
    sa.Column('created_by', sa.String(length=50), nullable=True),
    sa.Column('done', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('shopping_list_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('quantity', sa.String(length=100), nullable=True),
    sa.Column('checked', sa.Boolean(), nullable=False),
    sa.Column('added_by', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ember_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['ember_conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ember_messages_conversation_id'), 'ember_messages', ['conversation_id'], unique=False)
    op.create_table('ember_pending_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=True),
    sa.Column('tool_name', sa.String(length=100), nullable=False),
    sa.Column('tool_input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('requested_by', sa.String(length=50), nullable=True),
    sa.Column('resolved_by', sa.String(length=50), nullable=True),
    sa.Column('result_summary', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['ember_conversations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('ember_pending_actions')
    op.drop_index(op.f('ix_ember_messages_conversation_id'), table_name='ember_messages')
    op.drop_table('ember_messages')
    op.drop_table('shopping_list_items')
    op.drop_table('reminders')
    op.drop_index(op.f('ix_ember_traces_request_id'), table_name='ember_traces')
    op.drop_index(op.f('ix_ember_traces_created_at'), table_name='ember_traces')
    op.drop_table('ember_traces')
    op.drop_table('ember_conversations')
