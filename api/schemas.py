from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from db.models import BillingCycle, Recurrence, RecurrenceUnit


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
    purchase_date: date
    expiry_date: date
    document_reference: str | None = None
    notes: str | None = None


class WarrantyCreate(WarrantyBase):
    pass


class WarrantyUpdate(BaseModel):
    item: str | None = None
    purchase_date: date | None = None
    expiry_date: date | None = None
    document_reference: str | None = None
    notes: str | None = None


class WarrantyRead(WarrantyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_type: str
    resource_id: int
    message: str
    sent: bool
    created_at: datetime
