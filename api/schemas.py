from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from db.models import BillingCycle, CashflowKind, DecisionStatus, Recurrence, RecurrenceUnit


def _assume_utc_if_naive(v: datetime | None) -> datetime | None:
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class IdentitySet(BaseModel):
    name: str


class BillBase(BaseModel):
    name: str
    amount: Decimal
    due_date: date
    recurrence: Recurrence = Recurrence.one_time
    category: str
    notes: str | None = None


class BillCreate(BillBase):
    paid: bool = False


class BillUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = None
    due_date: date | None = None
    recurrence: Recurrence | None = None
    category: str | None = None
    notes: str | None = None
    paid: bool | None = None


class BillRead(BillBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paid: bool
    created_at: datetime
    updated_at: datetime


class SubscriptionBase(BaseModel):
    name: str
    cost: Decimal
    billing_cycle: BillingCycle
    renewal_date: date
    cancel_by_date: date | None = None
    category: str
    notes: str | None = None


class SubscriptionCreate(SubscriptionBase):
    active: bool = True


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    cost: Decimal | None = None
    billing_cycle: BillingCycle | None = None
    renewal_date: date | None = None
    cancel_by_date: date | None = None
    category: str | None = None
    notes: str | None = None
    active: bool | None = None


class SubscriptionRead(SubscriptionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    active: bool
    created_at: datetime
    updated_at: datetime


class MaintenanceItemBase(BaseModel):
    task: str
    property_or_appliance: str
    last_done: date | None = None
    next_due: date | None = None
    recurrence_value: int | None = None
    recurrence_unit: RecurrenceUnit | None = None
    notes: str | None = None


class MaintenanceItemCreate(MaintenanceItemBase):
    pass


class MaintenanceItemUpdate(BaseModel):
    task: str | None = None
    property_or_appliance: str | None = None
    last_done: date | None = None
    next_due: date | None = None
    recurrence_value: int | None = None
    recurrence_unit: RecurrenceUnit | None = None
    notes: str | None = None


class MaintenanceItemRead(MaintenanceItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class WarrantyBase(BaseModel):
    item: str
    retailer: str | None = None
    purchase_date: date
    expiry_date: date
    document_reference: str | None = None
    receipt_id: int | None = None
    notes: str | None = None


class WarrantyCreate(WarrantyBase):
    pass


class WarrantyUpdate(BaseModel):
    item: str | None = None
    retailer: str | None = None
    purchase_date: date | None = None
    expiry_date: date | None = None
    document_reference: str | None = None
    receipt_id: int | None = None
    notes: str | None = None


class WarrantyRead(WarrantyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ReceiptBase(BaseModel):
    vendor: str
    amount: Decimal
    purchased_at: date
    category: str
    notes: str | None = None


class ReceiptCreate(ReceiptBase):
    pass


class ReceiptUpdate(BaseModel):
    vendor: str | None = None
    amount: Decimal | None = None
    purchased_at: date | None = None
    category: str | None = None
    notes: str | None = None


class ReceiptRead(ReceiptBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class CashflowEntryBase(BaseModel):
    kind: CashflowKind
    amount: Decimal
    entry_date: date
    note: str | None = None


class CashflowEntryCreate(CashflowEntryBase):
    pass


class CashflowEntryRead(CashflowEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_type: str
    resource_id: int
    message: str
    sent: bool
    created_at: datetime


class CalendarEventBase(BaseModel):
    title: str
    description: str | None = None
    location: str | None = None
    start_time: datetime
    end_time: datetime
    all_day: bool = False
    owner: str = "shared"

    _tz_start = field_validator("start_time")(_assume_utc_if_naive)
    _tz_end = field_validator("end_time")(_assume_utc_if_naive)


class CalendarEventCreate(CalendarEventBase):
    pass


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    all_day: bool | None = None
    owner: str | None = None

    _tz_start = field_validator("start_time")(_assume_utc_if_naive)
    _tz_end = field_validator("end_time")(_assume_utc_if_naive)


class CalendarEventRead(CalendarEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    google_event_id: str
    last_synced_at: datetime


class CalendarStatus(BaseModel):
    configured: bool
    connected: bool
    google_account_email: str | None = None
    calendar_id: str


class DecisionOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str


class DecisionVoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    option_id: int
    voter: str


class DecisionBase(BaseModel):
    item: str
    notes: str | None = None


class DecisionCreate(DecisionBase):
    options: list[str]

    @field_validator("options")
    @classmethod
    def _at_least_two_options(cls, v: list[str]) -> list[str]:
        cleaned = [o.strip() for o in v if o.strip()]
        if len(cleaned) < 2:
            raise ValueError("A decision needs at least two options.")
        return cleaned


class DecisionUpdate(BaseModel):
    item: str | None = None
    notes: str | None = None


class DecisionVoteCreate(BaseModel):
    option_id: int


class DecisionRead(DecisionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: DecisionStatus
    decision: str | None = None
    decided_at: date | None = None
    created_at: datetime
    updated_at: datetime
    options: list[DecisionOptionRead] = []
    votes: list[DecisionVoteRead] = []
