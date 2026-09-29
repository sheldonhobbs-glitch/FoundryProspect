"""Shopping list and reminders."""

from datetime import date, time

from pydantic import BaseModel, Field

from brain.tools.catalog.common import MemberChoice, clock_time, iso_day, join_names, short_day
from brain.tools.registry import Risk, Tool, ToolContext, ToolOutcome, ToolRegistry
from domain import reminders, shopping
from domain.household import member_name


class NoArgs(BaseModel):
    pass


def get_shopping_list(ctx: ToolContext, a: NoArgs) -> ToolOutcome:
    return ToolOutcome({"items": [
        {"name": i.name, **({"quantity": i.quantity} if i.quantity else {})} for i in shopping.list_items(ctx.db)
    ]})


class ShoppingAdd(BaseModel):
    name: str
    quantity: str | None = Field(None, description="Optional, e.g. \"2L\" or \"a dozen\".")


class AddShoppingArgs(BaseModel):
    items: list[ShoppingAdd] = Field(min_length=1)


def add_to_shopping_list(ctx: ToolContext, a: AddShoppingArgs) -> ToolOutcome:
    added = shopping.add_items(ctx.db, [(i.name, i.quantity) for i in a.items], ctx.member)
    names = [i.name for i in added]
    return ToolOutcome({"on_list": names}, f"Added {join_names(names)} to the shopping list.")


class CheckOffArgs(BaseModel):
    names: list[str] = Field(min_length=1, description="Items that have been bought.")


def check_off_shopping_items(ctx: ToolContext, a: CheckOffArgs) -> ToolOutcome:
    checked, missing = shopping.check_off(ctx.db, a.names, ctx.now)
    names = [i.name for i in checked]
    summary = f"Ticked off {join_names(names)}." if names else None
    return ToolOutcome({"ticked_off": names, "not_on_list": missing}, summary)


class ListRemindersArgs(BaseModel):
    include_done: bool = False


def list_reminders(ctx: ToolContext, a: ListRemindersArgs) -> ToolOutcome:
    return ToolOutcome({"reminders": [
        {"id": r.id, "text": r.text, "for": member_name(r.for_member) if r.for_member else "everyone",
         "due": iso_day(r.due_date) if r.due_date else None,
         **({"time": r.due_time.strftime("%H:%M")} if r.due_time else {}), "done": r.done}
        for r in reminders.list_reminders(ctx.db, a.include_done)
    ]})


class CreateReminderArgs(BaseModel):
    text: str = Field(description="What to remember, phrased as a task, e.g. \"Book the car service\".")
    due_date: date | None = Field(None, description="When it's due. Omit if no particular day.")
    due_time: time | None = Field(None, description="Local time HH:MM, only if a specific time was given.")
    for_member: MemberChoice = Field("household", description="Who it's for; household means everyone.")


def create_reminder(ctx: ToolContext, a: CreateReminderArgs) -> ToolOutcome:
    who = None if a.for_member == "household" else a.for_member
    r = reminders.create_reminder(ctx.db, text=a.text, due_date=a.due_date, due_time=a.due_time,
                                  for_member=who, created_by=ctx.member)
    when = ""
    if a.due_date:
        when = f" for {short_day(a.due_date)}" + (f" at {clock_time(a.due_time)}" if a.due_time else "")
    for_whom = f" for {member_name(who)}" if who and who != ctx.member else ""
    return ToolOutcome({"id": r.id}, f"Reminder set{for_whom}: “{a.text}”{when}.")


class ReminderIdArgs(BaseModel):
    reminder_id: int


def complete_reminder(ctx: ToolContext, a: ReminderIdArgs) -> ToolOutcome:
    r = reminders.complete_reminder(ctx.db, reminders.get_reminder(ctx.db, a.reminder_id), ctx.now)
    return ToolOutcome({"done": True}, f"Ticked off “{r.text}”.")


def register(registry: ToolRegistry) -> None:
    registry.register(Tool("get_shopping_list", "Show what's on the shopping list.",
                           NoArgs, Risk.READ, get_shopping_list))
    registry.register(Tool(
        "add_to_shopping_list",
        "Add one or more items to the shared shopping list (e.g. \"add milk, bananas and bread\"). "
        "Items already on the list aren't duplicated.",
        AddShoppingArgs, Risk.LOW, add_to_shopping_list,
    ))
    registry.register(Tool("check_off_shopping_items", "Tick items off the shopping list once bought.",
                           CheckOffArgs, Risk.LOW, check_off_shopping_items))
    registry.register(Tool(
        "list_reminders",
        "List open reminders and to-dos. Also use it to find a reminder's id before ticking it off.",
        ListRemindersArgs, Risk.READ, list_reminders,
    ))
    registry.register(Tool(
        "create_reminder",
        "Create a reminder, e.g. \"remind me to book the car service next month\" or \"remind Sheldon about the "
        "pool guy tomorrow\". Use for tasks to remember; use calendar events for things happening at a set time "
        "and place.",
        CreateReminderArgs, Risk.LOW, create_reminder,
    ))
    registry.register(Tool("complete_reminder", "Tick off a reminder once it's done.",
                           ReminderIdArgs, Risk.LOW, complete_reminder))
