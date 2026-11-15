from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlanBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Plan name, e.g. Gym Fit")
    price: float = Field(..., ge=0.01, description="Price in MXN (supports decimals, e.g. 0.05)")
    interval: str = Field(default="monthly", description="Recurrence interval: weekly, biweekly, monthly")
    description: Optional[str] = Field(default=None, description="Detailed description")
    icon: str = Field(default="wallet", description="Icon identifier: gym, yoga, pilates, wallet")
    charge_day: int = Field(default=1, ge=1, le=31, description="Day of month for billing")
    chargeDay: Optional[int] = None
    is_active: bool = Field(default=True, description="Whether plan is active")

    @model_validator(mode="after")
    def sync_charge_day(self):
        if self.chargeDay is None:
            self.chargeDay = self.charge_day
        elif self.charge_day == 1 and self.chargeDay != 1:
            self.charge_day = self.chargeDay
        return self


class PlanCreate(PlanBase):
    id: Optional[str] = Field(default=None, description="Optional custom identifier (e.g. 'demo', 'gym')")


class PlanUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0.01)
    interval: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    charge_day: Optional[int] = Field(default=None, ge=1, le=31)
    chargeDay: Optional[int] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def sync_charge_day(self):
        if self.chargeDay is not None and self.charge_day is None:
            self.charge_day = self.chargeDay
        elif self.charge_day is not None and self.chargeDay is None:
            self.chargeDay = self.charge_day
        return self


class PlanResponse(PlanBase):
    id: str
    created_at: str
    active_subscribers: int = Field(default=0, description="Count of active subscribers on this plan")
    expected: float = Field(default=0.0, description="Expected monthly revenue from this plan")
    collected: float = Field(default=0.0, description="Collected revenue this month for this plan")
    pending: float = Field(default=0.0, description="Pending revenue this month for this plan")
    late_count: int = Field(default=0, description="Number of subscribers in atrasado status")


class SubscriberBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    phone: str
    plan_id: str
    planId: Optional[str] = None
    note: Optional[str] = None
    is_active: bool = True

    @model_validator(mode="after")
    def sync_plan_id(self):
        if self.planId is None:
            self.planId = self.plan_id
        return self


class SubscriberCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    name: str
    phone: str
    plan_id: Optional[str] = None
    planId: Optional[str] = None
    start_date: Optional[str] = None
    next_due_date: Optional[str] = None
    note: Optional[str] = None
    instant_charge: Optional[bool] = False

    @model_validator(mode="after")
    def sync_plan_id(self):
        if not self.plan_id and self.planId:
            self.plan_id = self.planId
        elif not self.planId and self.plan_id:
            self.planId = self.plan_id
        if not self.plan_id:
            raise ValueError("plan_id or planId is required")
        return self


class SubscriberUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = None
    phone: Optional[str] = None
    plan_id: Optional[str] = None
    planId: Optional[str] = None
    next_due_date: Optional[str] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def sync_plan_id(self):
        if self.planId is not None and self.plan_id is None:
            self.plan_id = self.planId
        elif self.plan_id is not None and self.planId is None:
            self.planId = self.plan_id
        return self


class SubscriberResponse(SubscriberBase):
    id: str
    start_date: Optional[str] = None
    next_due_date: str
    last_paid_at: Optional[str] = None
    status: str = Field(..., description="'atrasado', 'por_vencer', or 'al_corriente'")
    created_at: str
    plan_name: Optional[str] = None


class ChargeBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    subscriber_id: str
    subscriberId: Optional[str] = None
    plan_id: str
    planId: Optional[str] = None
    amount: float
    concept: Optional[str] = ""
    method: str = Field(default="codi", description="'codi' or 'efectivo'/'cash'")
    status: str = Field(default="pending", description="'pending'/'pendiente', 'paid'/'pagado', 'expired'/'vencido', 'failed'/'fallido'")

    @model_validator(mode="after")
    def sync_ids(self):
        if self.subscriberId is None:
            self.subscriberId = self.subscriber_id
        if self.planId is None:
            self.planId = self.plan_id
        return self


class ChargeCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    subscriber_id: Optional[str] = None
    subscriberId: Optional[str] = None
    plan_id: Optional[str] = None
    planId: Optional[str] = None
    amount: Optional[float] = Field(default=None, ge=0.01, allow_inf_nan=False)
    concept: Optional[str] = None
    method: Optional[str] = "codi"

    @model_validator(mode="after")
    def sync_ids(self):
        if not self.subscriber_id and self.subscriberId:
            self.subscriber_id = self.subscriberId
        elif not self.subscriberId and self.subscriber_id:
            self.subscriberId = self.subscriber_id
        if not self.subscriber_id:
            raise ValueError("subscriber_id or subscriberId is required")
        if not self.plan_id and self.planId:
            self.plan_id = self.planId
        return self


class ChargeResponse(ChargeBase):
    id: str
    subscriber_name: Optional[str] = None
    plan_name: Optional[str] = None
    codi_qr_id: Optional[str] = None
    qr_payload: Optional[str] = None
    qr_image: Optional[str] = None
    payment_link_id: Optional[str] = None
    payment_link_url: Optional[str] = None
    pey_transaction_id: Optional[str] = None
    num_ref: Optional[str] = None
    created_at: str
    paid_at: Optional[str] = None
    when: Optional[str] = Field(default=None, description="Formatted relative/absolute time string for UI")
    subscriber_next_due_date: Optional[str] = None
    subscriber_status: Optional[str] = None


class DashboardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_subscribers: int
    active_subscribers: int
    overdue_count: int
    due_soon_count: int
    current_count: int
    expected_monthly: float
    collected_month: float
    recent_movements: List[ChargeResponse]
