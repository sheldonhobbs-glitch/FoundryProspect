from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import IDENTITIES, get_identity, require_auth
from api.schemas import DecisionCreate, DecisionRead, DecisionUpdate, DecisionVoteCreate
from db.models import Decision, DecisionOption, DecisionStatus, DecisionVote
from db.session import get_db
from domain.clock import household_today

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
    decision = Decision(item=payload.item, notes=payload.notes)
    decision.options = [DecisionOption(text=text) for text in payload.options]
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


@router.post("/{decision_id}/vote", response_model=DecisionRead)
def vote_decision(
    decision_id: int, payload: DecisionVoteCreate, db: Session = Depends(get_db),
    identity: str | None = Depends(get_identity),
) -> Decision:
    if identity not in IDENTITIES:
        raise HTTPException(status_code=400, detail="Pick who you are (Sheldon/Partner) before voting.")
    decision = _get_or_404(db, decision_id)
    option = db.get(DecisionOption, payload.option_id)
    if option is None or option.decision_id != decision.id:
        raise HTTPException(status_code=404, detail="Option not found on this decision")

    existing_vote = db.query(DecisionVote).filter_by(decision_id=decision.id, voter=identity).first()
    if existing_vote:
        existing_vote.option_id = option.id
    else:
        db.add(DecisionVote(decision_id=decision.id, option_id=option.id, voter=identity))
    db.commit()
    db.refresh(decision)

    votes_by_voter = {v.voter: v.option_id for v in decision.votes}
    if set(votes_by_voter) >= set(IDENTITIES) and len(set(votes_by_voter.values())) == 1:
        winning_option = db.get(DecisionOption, next(iter(votes_by_voter.values())))
        decision.status = DecisionStatus.decided
        decision.decision = winning_option.text
        decision.decided_at = household_today()
    else:
        decision.status = DecisionStatus.open
        decision.decision = None
        decision.decided_at = None
    db.commit()
    db.refresh(decision)
    return decision


@router.post("/{decision_id}/reopen", response_model=DecisionRead)
def reopen_decision(decision_id: int, db: Session = Depends(get_db)) -> Decision:
    decision = _get_or_404(db, decision_id)
    decision.status = DecisionStatus.open
    decision.decision = None
    decision.decided_at = None
    db.query(DecisionVote).filter_by(decision_id=decision.id).delete()
    db.commit()
    db.refresh(decision)
    return decision
