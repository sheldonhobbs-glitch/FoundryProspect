from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    MealPlanEntryCreate,
    MealPlanEntryRead,
    MealSuggestion,
    PantryItemCreate,
    PantryItemRead,
    PantryItemUpdate,
)
from db.models import MealPlanEntry, PantryItem
from db.session import get_db
from domain import meals

router = APIRouter(prefix="/meals", tags=["meals"], dependencies=[Depends(require_auth)])

# Small static recipe list matched against pantry contents — a rule-based
# stand-in for real suggestion logic, not an AI feature.
RECIPE_SUGGESTIONS = [
    {"title": "Fried rice with egg & carrot", "icon": "🍳", "needs": ["egg", "carrot", "rice"]},
    {"title": "Chicken stir-fry", "icon": "🥘", "needs": ["chicken", "soy sauce", "onion"]},
    {"title": "Omelette", "icon": "🍳", "needs": ["egg", "butter"]},
    {"title": "Veggie stir-fry", "icon": "🥗", "needs": ["carrot", "onion", "soy sauce"]},
    {"title": "Pasta with garlic and butter", "icon": "🍝", "needs": ["pasta", "garlic", "butter"]},
    {"title": "Cheese omelette with toast", "icon": "🍞", "needs": ["egg", "cheese", "bread"]},
]


def _get_pantry_item_or_404(db: Session, item_id: int) -> PantryItem:
    item = db.get(PantryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Pantry item not found")
    return item


@router.get("/pantry", response_model=list[PantryItemRead])
def list_pantry(db: Session = Depends(get_db)) -> list[PantryItem]:
    return list(db.scalars(select(PantryItem).order_by(PantryItem.name)))


@router.post("/pantry", response_model=PantryItemRead, status_code=201)
def create_pantry_item(payload: PantryItemCreate, db: Session = Depends(get_db)) -> PantryItem:
    item = PantryItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/pantry/{item_id}", response_model=PantryItemRead)
def update_pantry_item(item_id: int, payload: PantryItemUpdate, db: Session = Depends(get_db)) -> PantryItem:
    item = _get_pantry_item_or_404(db, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/pantry/{item_id}", status_code=204)
def delete_pantry_item(item_id: int, db: Session = Depends(get_db)) -> None:
    item = _get_pantry_item_or_404(db, item_id)
    db.delete(item)
    db.commit()


@router.get("/plan", response_model=list[MealPlanEntryRead])
def list_plan(db: Session = Depends(get_db)) -> list[MealPlanEntry]:
    return meals.list_plan(db)


@router.post("/plan", response_model=MealPlanEntryRead, status_code=201)
def set_plan_entry(payload: MealPlanEntryCreate, db: Session = Depends(get_db)) -> MealPlanEntry:
    """Upsert: setting a meal for a date that already has one replaces it."""
    entry = meals.set_meal(db, payload.plan_date, payload.meal_text)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/plan/{entry_id}", status_code=204)
def delete_plan_entry(entry_id: int, db: Session = Depends(get_db)) -> None:
    entry = db.get(MealPlanEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Plan entry not found")
    db.delete(entry)
    db.commit()


@router.get("/suggestions", response_model=list[MealSuggestion])
def get_suggestions(db: Session = Depends(get_db)) -> list[MealSuggestion]:
    pantry_names = {item.name.strip().lower() for item in db.scalars(select(PantryItem))}

    scored = []
    for recipe in RECIPE_SUGGESTIONS:
        missing = [need for need in recipe["needs"] if need not in pantry_names]
        scored.append((len(missing), recipe, missing))

    scored.sort(key=lambda t: t[0])
    return [
        MealSuggestion(title=r["title"], icon=r["icon"], missing=missing)
        for _, r, missing in scored
        if len(missing) <= 1
    ][:3]
