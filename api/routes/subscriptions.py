from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import SubscriptionCreate, SubscriptionRead, SubscriptionUpdate
from db.models import Subscription
from db.session import get_db
from domain import household_admin

router = APIRouter(
    prefix="/subscriptions", tags=["subscriptions"], dependencies=[Depends(require_auth)]
)

def _get_or_404(db: Session, subscription_id: int) -> Subscription:
    subscription = db.get(Subscription, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@router.get("", response_model=list[SubscriptionRead])
def list_subscriptions(db: Session = Depends(get_db)) -> list[Subscription]:
    return list(db.scalars(select(Subscription).order_by(Subscription.renewal_date)))


@router.post("", response_model=SubscriptionRead, status_code=201)
def create_subscription(payload: SubscriptionCreate, db: Session = Depends(get_db)) -> Subscription:
    subscription = Subscription(**payload.model_dump())
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


@router.get("/{subscription_id}", response_model=SubscriptionRead)
def get_subscription(subscription_id: int, db: Session = Depends(get_db)) -> Subscription:
    return _get_or_404(db, subscription_id)


@router.patch("/{subscription_id}", response_model=SubscriptionRead)
def update_subscription(
    subscription_id: int, payload: SubscriptionUpdate, db: Session = Depends(get_db)
) -> Subscription:
    subscription = _get_or_404(db, subscription_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subscription, field, value)
    db.commit()
    db.refresh(subscription)
    return subscription


@router.delete("/{subscription_id}", status_code=204)
def delete_subscription(subscription_id: int, db: Session = Depends(get_db)) -> None:
    subscription = _get_or_404(db, subscription_id)
    db.delete(subscription)
    db.commit()


@router.post("/{subscription_id}/renew", response_model=SubscriptionRead)
def renew_subscription(subscription_id: int, db: Session = Depends(get_db)) -> Subscription:
    """Rolls renewal_date forward by one billing cycle."""
    subscription = household_admin.renew_subscription(db, _get_or_404(db, subscription_id))
    db.commit()
    db.refresh(subscription)
    return subscription
