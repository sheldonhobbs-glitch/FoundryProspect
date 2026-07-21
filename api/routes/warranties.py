from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import WarrantyCreate, WarrantyRead, WarrantyUpdate
from db.models import Warranty
from db.session import get_db

router = APIRouter(
    prefix="/warranties", tags=["warranties"], dependencies=[Depends(require_auth)]
)


def _get_or_404(db: Session, warranty_id: int) -> Warranty:
    warranty = db.get(Warranty, warranty_id)
    if warranty is None:
        raise HTTPException(status_code=404, detail="Warranty not found")
    return warranty


@router.get("", response_model=list[WarrantyRead])
def list_warranties(db: Session = Depends(get_db)) -> list[Warranty]:
    return list(db.scalars(select(Warranty).order_by(Warranty.expiry_date)))


@router.post("", response_model=WarrantyRead, status_code=201)
def create_warranty(payload: WarrantyCreate, db: Session = Depends(get_db)) -> Warranty:
    warranty = Warranty(**payload.model_dump())
    db.add(warranty)
    db.commit()
    db.refresh(warranty)
    return warranty


@router.get("/{warranty_id}", response_model=WarrantyRead)
def get_warranty(warranty_id: int, db: Session = Depends(get_db)) -> Warranty:
    return _get_or_404(db, warranty_id)


@router.patch("/{warranty_id}", response_model=WarrantyRead)
def update_warranty(warranty_id: int, payload: WarrantyUpdate, db: Session = Depends(get_db)) -> Warranty:
    warranty = _get_or_404(db, warranty_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(warranty, field, value)
    db.commit()
    db.refresh(warranty)
    return warranty


@router.delete("/{warranty_id}", status_code=204)
def delete_warranty(warranty_id: int, db: Session = Depends(get_db)) -> None:
    warranty = _get_or_404(db, warranty_id)
    db.delete(warranty)
    db.commit()
