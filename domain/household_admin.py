"""Bills, subscriptions, and maintenance: the recurring-admin actions."""

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from db.models import Bill, BillingCycle, MaintenanceItem, Recurrence, Subscription
from domain.clock import household_today
from domain.errors import NotFound

_BILL_STEP = {
    Recurrence.weekly: relativedelta(weeks=1),
    Recurrence.monthly: relativedelta(months=1),
    Recurrence.quarterly: relativedelta(months=3),
    Recurrence.yearly: relativedelta(years=1),
}

_CYCLE_STEP = {
    BillingCycle.weekly: relativedelta(weeks=1),
    BillingCycle.monthly: relativedelta(months=1),
    BillingCycle.quarterly: relativedelta(months=3),
    BillingCycle.yearly: relativedelta(years=1),
}


def get_bill(db: Session, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise NotFound(f"No bill with id {bill_id}.")
    return bill


def mark_bill_paid(db: Session, bill: Bill) -> Bill:
    """Recurring bills roll to their next due date and stay unpaid for the
    new cycle; one-off bills are simply marked paid."""
    step = _BILL_STEP.get(bill.recurrence)
    if step is not None:
        bill.due_date = bill.due_date + step
        bill.paid = False
    else:
        bill.paid = True
    db.flush()
    return bill


def get_subscription(db: Session, subscription_id: int) -> Subscription:
    subscription = db.get(Subscription, subscription_id)
    if subscription is None:
        raise NotFound(f"No subscription with id {subscription_id}.")
    return subscription


def renew_subscription(db: Session, subscription: Subscription) -> Subscription:
    subscription.renewal_date = subscription.renewal_date + _CYCLE_STEP[subscription.billing_cycle]
    db.flush()
    return subscription


def get_maintenance_item(db: Session, item_id: int) -> MaintenanceItem:
    item = db.get(MaintenanceItem, item_id)
    if item is None:
        raise NotFound(f"No maintenance item with id {item_id}.")
    return item


def mark_maintenance_done(db: Session, item: MaintenanceItem) -> MaintenanceItem:
    """Sets last_done to today; if a recurrence interval is set, rolls
    next_due forward by it, otherwise next_due is left for manual editing."""
    item.last_done = household_today()
    if item.recurrence_value and item.recurrence_unit:
        item.next_due = item.last_done + relativedelta(
            **{item.recurrence_unit.value: item.recurrence_value}
        )
    db.flush()
    return item
