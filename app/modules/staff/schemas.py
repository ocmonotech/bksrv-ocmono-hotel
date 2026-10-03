from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.staff.models import StaffRoleType, TipPoolStatus


class StaffShiftCreate(BaseModel):
    outlet_id: int
    user_id: int
    role_type: StaffRoleType = StaffRoleType.WAITER
    shift_date: date
    start_at: datetime
    end_at: datetime
    notes: str | None = Field(default=None, max_length=255)
    tip_eligible: bool = True


class StaffShiftUpdate(BaseModel):
    role_type: StaffRoleType | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=255)
    tip_eligible: bool | None = None
    is_active: bool | None = None


class StaffShiftRead(BaseModel):
    id: int
    outlet_id: int
    brand_id: int | None
    user_id: int
    user_name: str | None = None
    role_type: StaffRoleType
    shift_date: date
    start_at: datetime
    end_at: datetime
    notes: str | None
    tip_eligible: bool
    is_active: bool

    model_config = {"from_attributes": True}


class TipPoolLineCreate(BaseModel):
    user_id: int
    amount: float = Field(ge=0)
    role_type: StaffRoleType | None = None
    staff_shift_id: int | None = None
    share_percent: float | None = None


class TipPoolDistributeRequest(BaseModel):
    method: str = Field(default="equal", pattern="^(equal|custom)$")
    declared_amount: float | None = Field(default=None, ge=0)
    notes: str | None = None
    lines: list[TipPoolLineCreate] | None = None


class TipPoolLineRead(BaseModel):
    id: int
    tip_pool_id: int
    user_id: int
    user_name: str | None = None
    role_type: StaffRoleType | None
    share_percent: float | None
    amount: float
    staff_shift_id: int | None

    model_config = {"from_attributes": True}


class TipPoolRead(BaseModel):
    id: int
    outlet_id: int
    brand_id: int | None
    shift_date: date
    status: TipPoolStatus
    expected_amount: float
    declared_amount: float | None
    pool_amount: float
    variance: float | None
    notes: str | None
    settled_at: datetime | None
    settled_by: int | None
    lines: list[TipPoolLineRead] = []

    model_config = {"from_attributes": True}


class StaffMemberRead(BaseModel):
    id: int
    full_name: str
    role_name: str | None = None


class StaffDaySummary(BaseModel):
    outlet_id: int
    shift_date: date
    shift_count: int
    tip_eligible_count: int
    tip_pool: TipPoolRead | None
    expected_tips: float
