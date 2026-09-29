"""The Ember request loop.

One user message -> up to MAX_ROUNDS model turns. Each turn the model may
request tools; the orchestrator validates every call against the tool's
input model and then, by the tool's declared risk:

    READ / LOW -> runs it now (its own DB transaction) and reports back
    CONFIRM    -> stores a PendingAction and tells the model it's awaiting
                  approval; nothing changes until a person confirms

Every request writes one EmberTrace row (tool names and outcomes, no text).
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brain.prompts import SYSTEM_PROMPT, context_line
from brain.provider import AIProvider, ProviderError, ToolCall, ToolResult
from brain.tools import Risk, ToolContext, ToolRegistry
from db.models import EmberConversation, EmberMessage, EmberPendingAction, EmberTrace
from domain.clock import household_now
from domain.errors import DomainError, NotFound

logger = logging.getLogger("ember.brain")

MAX_ROUNDS = 6
CONVERSATION_IDLE = timedelta(minutes=30)
MAX_USER_TURNS = 20
PENDING_TTL = timedelta(minutes=15)

FALLBACK_REPLIES = {
    "limit": "That took more steps than I expected. Could you try asking in a simpler way?",
    "refusal": "Sorry, I can't help with that one.",
    "truncated": "Sorry, I lost my train of thought there. Could you ask again?",
}


class EmberUnavailable(Exception):
    """The Brain can't handle requests right now; str(exc) is user-facing."""


class EmberLimitReached(EmberUnavailable):
    pass


@dataclass
class ActionTaken:
    tool: str
    summary: str


@dataclass
class PendingView:
    id: int
    tool: str
    summary: str
    expires_at: datetime


@dataclass
class EmberReply:
    request_id: str
    conversation_id: int
    text: str
    actions: list[ActionTaken] = field(default_factory=list)
    pending: list[PendingView] = field(default_factory=list)


class Orchestrator:
    def __init__(self, db: Session, provider: AIProvider, registry: ToolRegistry,
                 member: str | None, *, daily_limit: int | None = None, clock=household_now):
        self.db = db
        self.provider = provider
        self.registry = registry
        self.member = member
        self.daily_limit = daily_limit
        self.clock = clock

    # --- public -----------------------------------------------------------

    def handle_message(self, text: str) -> EmberReply:
        started = time.monotonic()
        now = self.clock()
        self._check_daily_limit(now)

        trace = _new_trace("message", self.member, now, provider=self.provider.name)
        actions: list[ActionTaken] = []
        pending: list[PendingView] = []
        conversation = None
        try:
            conversation = self._conversation_for(now)
            trace.conversation_id = conversation.id
            history = self._load_history(conversation)

            user_msg = self.provider.user_text_message(f"{context_line(now, self.member)}\n\n{text.strip()}")
            history.append(user_msg)
            self._persist(conversation, "user", user_msg, now)

            reply_text = self._run_loop(conversation, history, now, trace, actions, pending)
            return EmberReply(trace.request_id, conversation.id, reply_text, actions, pending)
        except ProviderError as exc:
            self.db.rollback()
            trace.outcome, trace.error = "provider_error", str(exc)
            raise EmberUnavailable(str(exc)) from exc
        except Exception as exc:
            self.db.rollback()
            trace.outcome, trace.error = "error", type(exc).__name__
            logger.exception("Ember request failed")
            # History may now end mid tool-call; never replay it.
            if conversation is not None:
                try:
                    self._close(conversation)
                except Exception:
                    self.db.rollback()
            raise
        finally:
            trace.latency_ms = int((time.monotonic() - started) * 1000)
            self._write_trace(trace)

    # --- loop -------------------------------------------------------------

    def _run_loop(self, conversation, history, now, trace, actions, pending) -> str:
        ctx = ToolContext(db=self.db, member=self.member, now=now)
        specs = self.registry.specs()

        for _ in range(MAX_ROUNDS):
            turn = self.provider.run_turn(system=SYSTEM_PROMPT, messages=history, tools=specs)
            trace.rounds += 1
            trace.model = turn.model
            trace.input_tokens += turn.input_tokens
            trace.output_tokens += turn.output_tokens
            trace.cache_read_tokens += turn.cache_read_tokens

            assistant_msg = self.provider.assistant_message(turn)
            history.append(assistant_msg)
            self._persist(conversation, "assistant", assistant_msg, now)

            if turn.stop == "end_turn" or (turn.stop == "tool_use" and not turn.tool_calls):
                return turn.text or self._default_text(actions, pending)

            if turn.stop != "tool_use":
                # refusal / truncated / anything unexpected: never run tools
                # from this turn, and start fresh next time.
                trace.outcome = "refusal" if turn.stop == "refusal" else "truncated"
                self._close(conversation)
                return FALLBACK_REPLIES["refusal" if turn.stop == "refusal" else "truncated"]

            results = [self._execute(call, ctx, conversation, trace, actions, pending) for call in turn.tool_calls]
            results_msg = self.provider.tool_results_message(results)
            history.append(results_msg)
            self._persist(conversation, "tool_results", results_msg, now)

        trace.outcome = "limit"
        self._close(conversation)
        return FALLBACK_REPLIES["limit"]

    def _execute(self, call: ToolCall, ctx: ToolContext, conversation, trace, actions, pending) -> ToolResult:
        trace.tools_requested.append(call.name)
        tool = self.registry.get(call.name)
        if tool is None:
            trace.tools_failed.append(call.name)
            return ToolResult(call.id, f"Unknown tool '{call.name}'.", is_error=True)

        try:
            args = tool.input_model.model_validate(call.input)
        except ValidationError as exc:
            trace.tools_failed.append(call.name)
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'input'}: {e['msg']}" for e in exc.errors()
            )
            return ToolResult(call.id, f"Invalid input — {problems}", is_error=True)

        if tool.risk is Risk.CONFIRM:
            return self._gate(tool, args, call, ctx, conversation, trace, pending)

        try:
            outcome = tool.handler(ctx, args)
            self.db.commit()
        except DomainError as exc:
            self.db.rollback()
            trace.tools_failed.append(call.name)
            return ToolResult(call.id, str(exc), is_error=True)
        except Exception:
            self.db.rollback()
            logger.exception("tool %s failed", call.name)
            trace.tools_failed.append(call.name)
            return ToolResult(call.id, "Something went wrong running that; nothing was changed.", is_error=True)

        trace.tools_executed.append(call.name)
        if tool.risk is Risk.LOW and outcome.summary:
            actions.append(ActionTaken(call.name, outcome.summary))
        return ToolResult(call.id, json.dumps(outcome.data, default=str))

    def _gate(self, tool, args, call, ctx, conversation, trace, pending) -> ToolResult:
        try:
            summary = tool.describe(ctx, args)
        except DomainError as exc:
            self.db.rollback()
            trace.tools_failed.append(call.name)
            return ToolResult(call.id, str(exc), is_error=True)

        action = EmberPendingAction(
            conversation_id=conversation.id, tool_name=tool.name,
            tool_input=args.model_dump(mode="json"), summary=summary, status="pending",
            requested_by=self.member, expires_at=ctx.now + PENDING_TTL,
        )
        self.db.add(action)
        self.db.commit()
        trace.tools_gated.append(call.name)
        pending.append(PendingView(action.id, tool.name, summary, action.expires_at))
        return ToolResult(call.id, json.dumps({
            "status": "awaiting_user_confirmation",
            "summary": summary,
            "note": "Not done yet. The user will see a Confirm button.",
        }))

    # --- persistence ----------------------------------------------------

    def _conversation_for(self, now: datetime) -> EmberConversation:
        member_filter = (EmberConversation.member == self.member) if self.member else EmberConversation.member.is_(None)
        convo = self.db.scalars(
            select(EmberConversation)
            .where(member_filter, EmberConversation.provider == self.provider.name,
                   EmberConversation.closed.is_(False),
                   EmberConversation.last_active_at >= now - CONVERSATION_IDLE)
            .order_by(EmberConversation.id.desc())
        ).first()
        if convo is not None:
            turns = self.db.scalar(
                select(func.count()).select_from(EmberMessage)
                .where(EmberMessage.conversation_id == convo.id, EmberMessage.role == "user")
            )
            if turns < MAX_USER_TURNS:
                return convo
            # Start fresh rather than trimming history: replayed history must stay append-only.
            convo.closed = True
        convo = EmberConversation(member=self.member, provider=self.provider.name, last_active_at=now)
        self.db.add(convo)
        self.db.commit()
        return convo

    def _load_history(self, conversation: EmberConversation) -> list[dict]:
        rows = self.db.scalars(
            select(EmberMessage).where(EmberMessage.conversation_id == conversation.id).order_by(EmberMessage.id)
        )
        return [row.content for row in rows]

    def _persist(self, conversation: EmberConversation, role: str, message: dict, now: datetime) -> None:
        self.db.add(EmberMessage(conversation_id=conversation.id, role=role, content=message))
        conversation.last_active_at = now
        self.db.commit()

    def _close(self, conversation: EmberConversation) -> None:
        conversation.closed = True
        self.db.commit()

    def _write_trace(self, trace: EmberTrace) -> None:
        try:
            self.db.add(trace)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("failed to write Ember trace %s", trace.request_id)

    def _check_daily_limit(self, now: datetime) -> None:
        if not self.daily_limit:
            return
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        used = self.db.scalar(
            select(func.count()).select_from(EmberTrace)
            .where(EmberTrace.kind == "message", EmberTrace.created_at >= day_start)
        )
        if used >= self.daily_limit:
            raise EmberLimitReached("Ember has hit today's request limit. It resets at midnight.")

    @staticmethod
    def _default_text(actions: list[ActionTaken], pending: list[PendingView]) -> str:
        if pending:
            return "Can you confirm that for me?"
        if actions:
            return " ".join(a.summary for a in actions)
        return "Done."


# --- confirmations ------------------------------------------------------

def _load_pending(db: Session, action_id: int, now: datetime) -> EmberPendingAction:
    action = db.get(EmberPendingAction, action_id)
    if action is None:
        raise NotFound("That confirmation doesn't exist.")
    if action.status != "pending":
        raise DomainError(f"That's already been {action.status}.")
    if action.expires_at < now:
        action.status = "expired"
        db.commit()
        raise DomainError("That confirmation has expired. Ask Ember again if you still want it.")
    return action


def _note_on_conversation(db: Session, provider: AIProvider | None, action: EmberPendingAction, note: str) -> None:
    """Lets the model know, on the next turn, what happened to its request."""
    if provider is None or action.conversation_id is None:
        return
    convo = db.get(EmberConversation, action.conversation_id)
    if convo is None or convo.closed or convo.provider != provider.name:
        return
    db.add(EmberMessage(conversation_id=convo.id, role="app_note",
                        content=provider.user_text_message(f"[Ember app: {note}]")))


def confirm_pending_action(db: Session, registry: ToolRegistry, action_id: int, member: str | None,
                           provider: AIProvider | None = None, clock=household_now) -> str:
    """Executes exactly the stored, validated input. Returns what was done."""
    now = clock()
    started = time.monotonic()
    action = _load_pending(db, action_id, now)
    trace = _new_trace("confirm", member, now, conversation_id=action.conversation_id)
    trace.tools_requested.append(action.tool_name)
    try:
        tool = registry.get(action.tool_name)
        if tool is None:
            raise DomainError("That action isn't available any more.")
        args = tool.input_model.model_validate(action.tool_input)
        outcome = tool.handler(ToolContext(db=db, member=member, now=now), args)
    except (DomainError, ValidationError) as exc:
        db.rollback()
        action = db.get(EmberPendingAction, action_id)
        action.status, action.resolved_by, action.resolved_at = "failed", member, now
        action.result_summary = str(exc) if isinstance(exc, DomainError) else "Stored input was invalid."
        db.commit()
        trace.outcome, trace.error = "failed", action.result_summary
        trace.tools_failed.append(action.tool_name)
        _finish_trace(db, trace, started)
        raise DomainError(action.result_summary) from exc

    result = outcome.summary or action.summary
    action.status, action.resolved_by, action.resolved_at, action.result_summary = "executed", member, now, result
    _note_on_conversation(db, provider, action, f"the user confirmed and it's done: {result}")
    db.commit()
    trace.tools_executed.append(action.tool_name)
    _finish_trace(db, trace, started)
    return result


def cancel_pending_action(db: Session, action_id: int, member: str | None,
                          provider: AIProvider | None = None, clock=household_now) -> None:
    now = clock()
    action = _load_pending(db, action_id, now)
    action.status, action.resolved_by, action.resolved_at = "cancelled", member, now
    _note_on_conversation(db, provider, action, f"the user cancelled: {action.summary}")
    db.commit()


def _new_trace(kind: str, member: str | None, now: datetime, **fields) -> EmberTrace:
    # Column defaults only apply on INSERT; counters must be real ints from the start.
    return EmberTrace(
        request_id=str(uuid.uuid4()), kind=kind, member=member, created_at=now, outcome="ok",
        rounds=0, latency_ms=0, input_tokens=0, output_tokens=0, cache_read_tokens=0,
        tools_requested=[], tools_executed=[], tools_gated=[], tools_failed=[], **fields,
    )


def _finish_trace(db: Session, trace: EmberTrace, started: float) -> None:
    trace.latency_ms = int((time.monotonic() - started) * 1000)
    try:
        db.add(trace)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed to write Ember trace %s", trace.request_id)
