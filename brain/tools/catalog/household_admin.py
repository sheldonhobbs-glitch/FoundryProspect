from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from brain.tools.catalog.common import MAX_LIST_ITEMS, iso_day, money, short_day
from brain.tools.registry import Risk, Tool, ToolContext, ToolOutcome, ToolRegistry
from db.models import Bill, BillingCycle, MaintenanceItem, Recurrence, RecurrenceUnit, Subscription
from domain import household_admin

# --- bills ------------------------------------------------------------------

class ListBillsArgs(BaseModel):
    include_paid: bool = Field(False, description="Also include bills already paid.")
    due_within_days: int | None = Field(None, description="Only bills due within this many days from today "
                                                          "(overdue bills are always included).")


def list_bills(ctx: ToolContext, a: ListBillsArgs) -> ToolOutcome:
    today = ctx.now.date()
    stmt = select(Bill).order_by(Bill.due_date)
    if not a.include_paid:
        stmt = stmt.where(Bill.paid.is_(False))
    if a.due_within_days is not None:
        stmt = stmt.where(Bill.due_date <= today + timedelta(days=a.due_within_days))
    bills = list(ctx.db.scalars(stmt))
    return ToolOutcome({"bills": [
        {"id": b.id, "name": b.name, "amount": str(b.amount), "due": iso_day(b.due_date),
         "overdue": (not b.paid and b.due_date < today), "paid": b.paid,
         "repeats": b.recurrence.value, "category": b.category}
        for b in bills[:MAX_LIST_ITEMS]
    ]})


class BillIdArgs(BaseModel):
    bill_id: int


def mark_bill_paid(ctx: ToolContext, a: BillIdArgs) -> ToolOutcome:
    bill = household_admin.get_bill(ctx.db, a.bill_id)
    was_recurring = bill.recurrence is not Recurrence.one_time
    household_admin.mark_bill_paid(ctx.db, bill)
    summary = f"Marked {bill.name} ({money(bill.amount)}) as paid"
    summary += f" — next one's due {short_day(bill.due_date)}." if was_recurring else "."
    return ToolOutcome({"paid": True, "next_due": iso_day(bill.due_date) if was_recurring else None}, summary)


class CreateBillArgs(BaseModel):
    name: str = Field(description="Who the bill is from, e.g. \"Origin electricity\".")
    amount: Decimal
    due_date: date
    recurrence: Literal[tuple(r.value for r in Recurrence)] = "one_time"
    category: str = "bills"


def create_bill(ctx: ToolContext, a: CreateBillArgs) -> ToolOutcome:
    bill = Bill(name=a.name, amount=a.amount, due_date=a.due_date, recurrence=Recurrence(a.recurrence),
                category=a.category, paid=False)
    ctx.db.add(bill)
    ctx.db.flush()
    return ToolOutcome({"id": bill.id},
                       f"Added the {a.name} bill ({money(a.amount)}, due {short_day(a.due_date)}).")


# --- subscriptions -------------------------------------------------------------

class ListSubscriptionsArgs(BaseModel):
    include_inactive: bool = False
    renewing_within_days: int | None = Field(None, description="Only subscriptions renewing within this many days.")


def list_subscriptions(ctx: ToolContext, a: ListSubscriptionsArgs) -> ToolOutcome:
    stmt = select(Subscription).order_by(Subscription.renewal_date)
    if not a.include_inactive:
        stmt = stmt.where(Subscription.active.is_(True))
    if a.renewing_within_days is not None:
        stmt = stmt.where(Subscription.renewal_date <= ctx.now.date() + timedelta(days=a.renewing_within_days))
    subs = list(ctx.db.scalars(stmt))
    return ToolOutcome({"subscriptions": [
        {"id": s.id, "name": s.name, "cost": str(s.cost), "cycle": s.billing_cycle.value,
         "renews": iso_day(s.renewal_date), "active": s.active, "category": s.category,
         **({"cancel_by": iso_day(s.cancel_by_date)} if s.cancel_by_date else {})}
        for s in subs[:MAX_LIST_ITEMS]
    ]})


class CreateSubscriptionArgs(BaseModel):
    name: str
    cost: Decimal
    billing_cycle: Literal[tuple(c.value for c in BillingCycle)] = "monthly"
    renewal_date: date = Field(description="Next date it charges.")
    category: str = "subscriptions"


def create_subscription(ctx: ToolContext, a: CreateSubscriptionArgs) -> ToolOutcome:
    sub = Subscription(name=a.name, cost=a.cost, billing_cycle=BillingCycle(a.billing_cycle),
                       renewal_date=a.renewal_date, category=a.category, active=True)
    ctx.db.add(sub)
    ctx.db.flush()
    return ToolOutcome({"id": sub.id}, f"Added {a.name} ({money(a.cost)}/{a.billing_cycle}), "
                                       f"next charging {short_day(a.renewal_date)}.")


class SubscriptionIdArgs(BaseModel):
    subscription_id: int


def describe_cancel_subscription(ctx: ToolContext, a: SubscriptionIdArgs) -> str:
    sub = household_admin.get_subscription(ctx.db, a.subscription_id)
    return (f"Mark {sub.name} ({money(sub.cost)}/{sub.billing_cycle.value}) as cancelled? "
            f"This only updates Ember — it won't cancel it with {sub.name}.")


def cancel_subscription(ctx: ToolContext, a: SubscriptionIdArgs) -> ToolOutcome:
    sub = household_admin.get_subscription(ctx.db, a.subscription_id)
    sub.active = False
    ctx.db.flush()
    return ToolOutcome({"cancelled": True}, f"Marked {sub.name} as cancelled.")


# --- maintenance ----------------------------------------------------------------

class ListMaintenanceArgs(BaseModel):
    due_within_days: int | None = Field(None, description="Only tasks due within this many days "
                                                          "(overdue tasks are always included).")


def list_maintenance(ctx: ToolContext, a: ListMaintenanceArgs) -> ToolOutcome:
    today = ctx.now.date()
    stmt = select(MaintenanceItem).order_by(MaintenanceItem.next_due.asc().nulls_last())
    if a.due_within_days is not None:
        stmt = stmt.where(MaintenanceItem.next_due <= today + timedelta(days=a.due_within_days))
    items = list(ctx.db.scalars(stmt))
    return ToolOutcome({"tasks": [
        {"id": m.id, "task": m.task, "where": m.property_or_appliance,
         "next_due": iso_day(m.next_due) if m.next_due else None,
         "overdue": bool(m.next_due and m.next_due < today),
         "last_done": iso_day(m.last_done) if m.last_done else None,
         "repeats": f"every {m.recurrence_value} {m.recurrence_unit.value}"
                    if m.recurrence_value and m.recurrence_unit else None}
        for m in items[:MAX_LIST_ITEMS]
    ]})


class MaintenanceIdArgs(BaseModel):
    task_id: int


def mark_maintenance_done(ctx: ToolContext, a: MaintenanceIdArgs) -> ToolOutcome:
    item = household_admin.get_maintenance_item(ctx.db, a.task_id)
    household_admin.mark_maintenance_done(ctx.db, item)
    summary = f"Marked “{item.task}” done"
    summary += f" — next due {short_day(item.next_due)}." if item.recurrence_value and item.next_due else "."
    return ToolOutcome({"done": True, "next_due": iso_day(item.next_due) if item.next_due else None}, summary)


class CreateMaintenanceArgs(BaseModel):
    task: str = Field(description="What needs doing, e.g. \"Clean the gutters\".")
    where: str = Field("Home", description="Property, room or appliance it's for.")
    next_due: date | None = None
    repeat_every: int | None = Field(None, description="Repeat interval number, e.g. 3 for every 3 months.")
    repeat_unit: Literal[tuple(u.value for u in RecurrenceUnit)] | None = None


def create_maintenance_task(ctx: ToolContext, a: CreateMaintenanceArgs) -> ToolOutcome:
    has_repeat = a.repeat_every is not None and a.repeat_unit is not None
    item = MaintenanceItem(
        task=a.task, property_or_appliance=a.where, next_due=a.next_due,
        recurrence_value=a.repeat_every if has_repeat else None,
        recurrence_unit=RecurrenceUnit(a.repeat_unit) if has_repeat else None,
    )
    ctx.db.add(item)
    ctx.db.flush()
    due = f", due {short_day(a.next_due)}" if a.next_due else ""
    repeat = f", every {a.repeat_every} {a.repeat_unit}" if has_repeat else ""
    return ToolOutcome({"id": item.id}, f"Added “{a.task}”{due}{repeat}.")


def register(registry: ToolRegistry) -> None:
    registry.register(Tool(
        "list_bills",
        "List household bills with amounts and due dates. Call this for questions about what's due or owed, "
        "and to find a bill's id before marking it paid.",
        ListBillsArgs, Risk.READ, list_bills,
    ))
    registry.register(Tool(
        "mark_bill_paid",
        "Record that a bill has been paid (e.g. \"the electricity bill is paid\"). Recurring bills roll on to "
        "their next due date. Get the bill_id from list_bills first.",
        BillIdArgs, Risk.LOW, mark_bill_paid,
    ))
    registry.register(Tool("create_bill", "Add a new bill to track.", CreateBillArgs, Risk.LOW, create_bill))
    registry.register(Tool(
        "list_subscriptions",
        "List subscriptions (streaming, software, memberships) with cost and next renewal. Call this for "
        "questions about what renews or what the household pays for.",
        ListSubscriptionsArgs, Risk.READ, list_subscriptions,
    ))
    registry.register(Tool("create_subscription", "Start tracking a subscription.",
                           CreateSubscriptionArgs, Risk.LOW, create_subscription))
    registry.register(Tool(
        "cancel_subscription",
        "Mark a subscription as cancelled in Ember (it does not contact the provider). Needs the user's "
        "confirmation. Get the id from list_subscriptions.",
        SubscriptionIdArgs, Risk.CONFIRM, cancel_subscription, describe=describe_cancel_subscription,
    ))
    registry.register(Tool(
        "list_maintenance",
        "List home maintenance tasks and when they're due. Call this for \"what needs doing around the house\" "
        "and to find a task's id.",
        ListMaintenanceArgs, Risk.READ, list_maintenance,
    ))
    registry.register(Tool(
        "mark_maintenance_done",
        "Record that a maintenance task was done today; repeating tasks roll on to their next due date.",
        MaintenanceIdArgs, Risk.LOW, mark_maintenance_done,
    ))
    registry.register(Tool("create_maintenance_task", "Add a home maintenance task, optionally repeating.",
                           CreateMaintenanceArgs, Risk.LOW, create_maintenance_task))
