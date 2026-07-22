from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import DecisionCreate, DecisionRead, DecisionResolve, DecisionUpdate
from db.models import Decision, DecisionStatus
from db.session import get_db

router = APIRouter(prefix="/decisions", tags=["decisions"], dependencies=[Depends(require_auth)])


def _get_or_404(db: Session, decision_id: int) -> Decision:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision


@router.get("", response_model=list[DecisionRead])
def list_decisions(db: Session = Depends(get_db)) -> list[Decision]:
    return list(db.scalars(select(Decision).order_by(Decision.created_at.desc())))


@router.post("", response_model=DecisionRead, status_code=201)
def create_decision(payload: DecisionCreate, db: Session = Depends(get_db)) -> Decision:
    decision = Decision(**payload.model_dump())
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


@router.get("/{decision_id}", response_model=DecisionRead)
def get_decision(decision_id: int, db: Session = Depends(get_db)) -> Decision:
    return _get_or_404(db, decision_id)


@router.patch("/{decision_id}", response_model=DecisionRead)
def update_decision(decision_id: int, payload: DecisionUpdate, db: Session = Depends(get_db)) -> Decision:
    decision = _get_or_404(db, decision_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(decision, field, value)
    db.commit()
    db.refresh(decision)
    return decision


@router.delete("/{decision_id}", status_code=204)
def delete_decision(decision_id: int, db: Session = Depends(get_db)) -> None:
    decision = _get_or_404(db, decision_id)
    db.delete(decision)
    db.commit()


@router.post("/{decision_id}/resolve", response_model=DecisionRead)
def resolve_decision(decision_id: int, payload: DecisionResolve, db: Session = Depends(get_db)) -> Decision:
    decision = _get_or_404(db, decision_id)
    decision.status = DecisionStatus.decided
    decision.decision = payload.decision
    decision.decided_at = date.today()
    db.commit()
    db.refresh(decision)
    return decision


@router.post("/{decision_id}/reopen", response_model=DecisionRead)
def reopen_decision(decision_id: int, db: Session = Depends(get_db)) -> Decision:
    decision = _get_or_404(db, decision_id)
    decision.status = DecisionStatus.open
    decision.decision = None
    decision.decided_at = None
    db.commit()
    db.refresh(decision)
    return decision
