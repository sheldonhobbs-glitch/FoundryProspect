"""Ember Brain persistence: conversations, pending confirmations, traces."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class EmberConversation(Base):
    """One composer session. History is provider-native and append-only:
    replayed verbatim to the model, never edited (editing earlier turns
    invalidates the model's reasoning blocks). Long or idle conversations are
    closed and a fresh one started instead of trimming history."""

    __tablename__ = "ember_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    member: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider: Mapped[str] = mapped_column(String(50))
    closed: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmberMessage(Base):
    __tablename__ = "ember_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ember_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[list | str] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


PENDING_STATUSES = ("pending", "executed", "cancelled", "expired", "failed")


class EmberPendingAction(Base):
    """A consequential tool call the model requested, held until a person
    explicitly approves it. Approval executes exactly the stored, validated
    input — the model is not consulted again."""

    __tablename__ = "ember_pending_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("ember_conversations.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(100))
    tool_input: Mapped[dict] = mapped_column(JSONB)
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    requested_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmberTrace(Base):
    """One row per Ember request, for debugging and cost tracking. Holds tool
    names and outcomes only — never the text of the conversation."""

    __tablename__ = "ember_traces"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="message")
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    member: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rounds: Mapped[int] = mapped_column(default=0)
    tools_requested: Mapped[list] = mapped_column(JSONB, default=list)
    tools_executed: Mapped[list] = mapped_column(JSONB, default=list)
    tools_gated: Mapped[list] = mapped_column(JSONB, default=list)
    tools_failed: Mapped[list] = mapped_column(JSONB, default=list)
    outcome: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cache_read_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
