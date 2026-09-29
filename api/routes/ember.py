"""The Ember Brain over HTTP: send a message, confirm or cancel a held
action, and read back the current conversation for the composer panel."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import get_settings
from api.deps import get_identity, require_auth
from brain import service
from brain.orchestrator import (
    CONVERSATION_IDLE,
    EmberLimitReached,
    EmberUnavailable,
    Orchestrator,
    cancel_pending_action,
    confirm_pending_action,
)
from brain.prompts import strip_context
from db.models import EmberConversation, EmberMessage, EmberPendingAction
from db.session import get_db
from domain.clock import household_now
from domain.errors import DomainError, NotFound

router = APIRouter(prefix="/ember", tags=["ember"], dependencies=[Depends(require_auth)])

NOT_CONFIGURED = "Ember's assistant isn't set up yet — an Anthropic API key needs to be added."


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ActionOut(BaseModel):
    tool: str
    summary: str


class PendingOut(BaseModel):
    id: int
    summary: str
    expires_at: datetime


class ReplyOut(BaseModel):
    request_id: str
    conversation_id: int
    reply: str
    actions: list[ActionOut]
    pending: list[PendingOut]


class ThreadMessage(BaseModel):
    role: str
    text: str


class ConversationOut(BaseModel):
    available: bool
    messages: list[ThreadMessage]
    pending: list[PendingOut]


@router.post("/message", response_model=ReplyOut)
def send_message(payload: MessageIn, db: Session = Depends(get_db),
                 identity: str | None = Depends(get_identity)) -> ReplyOut:
    provider = service.get_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED)
    orchestrator = Orchestrator(db, provider, service.get_registry(), identity,
                                daily_limit=get_settings().ember_daily_request_limit)
    try:
        reply = orchestrator.handle_message(payload.text)
    except EmberLimitReached as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except EmberUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReplyOut(
        request_id=reply.request_id, conversation_id=reply.conversation_id, reply=reply.text,
        actions=[ActionOut(tool=a.tool, summary=a.summary) for a in reply.actions],
        pending=[PendingOut(id=p.id, summary=p.summary, expires_at=p.expires_at) for p in reply.pending],
    )


@router.post("/actions/{action_id}/confirm")
def confirm_action(action_id: int, db: Session = Depends(get_db),
                   identity: str | None = Depends(get_identity)) -> dict:
    try:
        result = confirm_pending_action(db, service.get_registry(), action_id, identity,
                                        provider=service.get_provider())
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"result": result}


@router.post("/actions/{action_id}/cancel")
def cancel_action(action_id: int, db: Session = Depends(get_db),
                  identity: str | None = Depends(get_identity)) -> dict:
    try:
        cancel_pending_action(db, action_id, identity, provider=service.get_provider())
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/conversation", response_model=ConversationOut)
def current_conversation(db: Session = Depends(get_db),
                         identity: str | None = Depends(get_identity)) -> ConversationOut:
    provider = service.get_provider()
    if provider is None:
        return ConversationOut(available=False, messages=[], pending=[])

    now = household_now()
    member_filter = (EmberConversation.member == identity) if identity else EmberConversation.member.is_(None)
    convo = db.scalars(
        select(EmberConversation)
        .where(member_filter, EmberConversation.provider == provider.name, EmberConversation.closed.is_(False),
               EmberConversation.last_active_at >= now - CONVERSATION_IDLE)
        .order_by(EmberConversation.id.desc())
    ).first()
    if convo is None:
        return ConversationOut(available=True, messages=[], pending=[])

    thread = []
    for row in db.scalars(select(EmberMessage).where(EmberMessage.conversation_id == convo.id)
                          .order_by(EmberMessage.id)):
        if row.role not in ("user", "assistant"):
            continue
        text = provider.message_text(row.content)
        if row.role == "user":
            text = strip_context(text)
        if text:
            thread.append(ThreadMessage(role=row.role, text=text))

    pending = db.scalars(
        select(EmberPendingAction)
        .where(EmberPendingAction.conversation_id == convo.id, EmberPendingAction.status == "pending",
               EmberPendingAction.expires_at > now)
        .order_by(EmberPendingAction.id)
    )
    return ConversationOut(
        available=True, messages=thread,
        pending=[PendingOut(id=p.id, summary=p.summary, expires_at=p.expires_at) for p in pending],
    )
