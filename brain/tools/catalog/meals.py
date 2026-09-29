from datetime import date

from pydantic import BaseModel, Field

from brain.tools.catalog.common import iso_day, join_names, short_day
from brain.tools.registry import Risk, Tool, ToolContext, ToolOutcome, ToolRegistry
from domain import meals


class MealPlanArgs(BaseModel):
    start_date: date | None = Field(None, description="Defaults to yesterday.")
    end_date: date | None = Field(None, description="Defaults to six days from today.")


def get_meal_plan(ctx: ToolContext, a: MealPlanArgs) -> ToolOutcome:
    entries = meals.list_plan(ctx.db, a.start_date, a.end_date)
    return ToolOutcome({"dinners": [{"day": iso_day(e.plan_date), "meal": e.meal_text} for e in entries]})


class SetMealArgs(BaseModel):
    day: date
    meal: str = Field(description="What's for dinner, e.g. \"Chicken stir-fry\".")


def set_meal(ctx: ToolContext, a: SetMealArgs) -> ToolOutcome:
    meals.set_meal(ctx.db, a.day, a.meal)
    return ToolOutcome({"set": True}, f"Dinner on {short_day(a.day)}: {a.meal}.")


class NoArgs(BaseModel):
    pass


def get_pantry(ctx: ToolContext, a: NoArgs) -> ToolOutcome:
    return ToolOutcome({"items": [{"name": i.name, "low": i.low_stock} for i in meals.list_pantry(ctx.db)]})


class PantryAdd(BaseModel):
    name: str
    low_stock: bool = False


class UpdatePantryArgs(BaseModel):
    add: list[PantryAdd] = Field(default_factory=list, description="Items now in the house (or running low).")
    remove: list[str] = Field(default_factory=list, description="Items that are used up / gone.")


def update_pantry(ctx: ToolContext, a: UpdatePantryArgs) -> ToolOutcome:
    for item in a.add:
        meals.add_pantry_item(ctx.db, item.name, item.low_stock)
    removed, missing = [], []
    for name in a.remove:
        item = meals.find_pantry_item(ctx.db, name)
        if item is None:
            missing.append(name)
        else:
            meals.remove_pantry_item(ctx.db, name)
            removed.append(item.name)
    parts = []
    if a.add:
        parts.append(f"added {join_names([i.name for i in a.add])}")
    if removed:
        parts.append(f"removed {join_names(removed)}")
    summary = ("Pantry: " + "; ".join(parts) + ".") if parts else None
    return ToolOutcome({"added": [i.name for i in a.add], "removed": removed, "not_in_pantry": missing}, summary)


def register(registry: ToolRegistry) -> None:
    registry.register(Tool(
        "get_meal_plan",
        "Get planned dinners by day. Call this for \"what's for dinner\" or questions about the week's meals.",
        MealPlanArgs, Risk.READ, get_meal_plan,
    ))
    registry.register(Tool(
        "set_meal",
        "Set (or replace) the planned dinner for a day. When asked to plan several days, call it once per day.",
        SetMealArgs, Risk.LOW, set_meal,
    ))
    registry.register(Tool(
        "get_pantry",
        "List what food is in the house, flagging items running low. Call this before suggesting meals from "
        "what's on hand, or when working out what needs buying.",
        NoArgs, Risk.READ, get_pantry,
    ))
    registry.register(Tool(
        "update_pantry",
        "Record food that's now in the house, running low, or used up (e.g. \"we're out of eggs\" -> remove eggs).",
        UpdatePantryArgs, Risk.LOW, update_pantry,
    ))
