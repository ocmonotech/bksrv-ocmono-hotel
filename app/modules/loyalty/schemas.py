from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.loyalty.models import LoyaltySource, LoyaltyTxnType


class LoyaltyConfigRead(BaseModel):
    enabled: bool = True
    points_per_100: float = 5
    stay_points_per_night: int = 50
    stay_points_per_100: float = 2
    min_redeem_points: int = 100
    point_value: float = 1
    earn_on_room_charge: bool = False


class LoyaltyConfigUpdate(BaseModel):
    enabled: bool | None = None
    points_per_100: float | None = Field(default=None, ge=0, le=1000)
    stay_points_per_night: int | None = Field(default=None, ge=0, le=10000)
    stay_points_per_100: float | None = Field(default=None, ge=0, le=1000)
    min_redeem_points: int | None = Field(default=None, ge=1, le=100000)
    point_value: float | None = Field(default=None, gt=0, le=100)
    earn_on_room_charge: bool | None = None


class LoyaltyTierSeedRequest(BaseModel):
    reset: bool = False


class LoyaltyTierRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None = None
    name: str
    code: str
    min_points: int
    earn_multiplier: float
    color: str
    perks: str | None = None
    sort_order: int
    is_active: bool = True


class LoyaltyTierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=32)
    min_points: int = Field(ge=0)
    earn_multiplier: float = Field(default=1, ge=0.1, le=10)
    color: str = Field(default="slate", max_length=32)
    perks: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=0, ge=0)


class LoyaltyTierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    min_points: int | None = Field(default=None, ge=0)
    earn_multiplier: float | None = Field(default=None, ge=0.1, le=10)
    color: str | None = Field(default=None, max_length=32)
    perks: str | None = Field(default=None, max_length=255)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class LoyaltyLedgerRead(ORMSchema, TimestampSchema):
    id: int
    customer_id: int
    customer_name: str | None = None
    customer_mobile: str | None = None
    outlet_id: int | None = None
    txn_type: LoyaltyTxnType
    source: LoyaltySource
    points: int
    balance_after: int
    amount_basis: float
    reference_type: str
    reference_id: str
    description: str
    created_by: int | None = None
    created_at: datetime | None = None


class LoyaltyAdjustRequest(BaseModel):
    customer_id: int
    points: int = Field(..., description="Positive to grant, negative to deduct")
    description: str = Field(min_length=1, max_length=255)
    outlet_id: int | None = None


class LoyaltyRedeemPreview(BaseModel):
    customer_id: int
    points_balance: int
    min_redeem_points: int
    point_value: float
    max_redeem_points: int
    max_redeem_value: float
    can_redeem: bool


class LoyaltyMemberRead(BaseModel):
    customer_id: int
    full_name: str
    mobile: str
    email: str | None = None
    loyalty_points: int
    total_spend: float
    total_visits: int
    tier_code: str | None = None
    tier_name: str | None = None
    tier_color: str | None = None
    earn_multiplier: float = 1
    last_visit_at: datetime | None = None


class LoyaltySummaryRead(BaseModel):
    members: int
    total_points: int
    earned_30d: int
    redeemed_30d: int
    config: LoyaltyConfigRead
    tiers: list[LoyaltyTierRead] = Field(default_factory=list)
    top_members: list[LoyaltyMemberRead] = Field(default_factory=list)
    recent_ledger: list[LoyaltyLedgerRead] = Field(default_factory=list)
