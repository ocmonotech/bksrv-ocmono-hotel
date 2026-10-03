from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.offers.models import OfferStatus, OfferType


class OfferCreate(BaseModel):
    offer_name: str = Field(max_length=255)
    offer_type: OfferType
    brand_id: int | None = None
    outlet_id: int | None = None
    status: OfferStatus = OfferStatus.ACTIVE
    discount_value: float = Field(default=0, ge=0)
    minimum_bill_amount: float | None = Field(default=None, ge=0)
    applicable_outlets: list[int] = Field(default_factory=list)
    applicable_days: list[str] = Field(default_factory=list)
    start_time: str | None = Field(default=None, max_length=8)
    end_time: str | None = Field(default=None, max_length=8)
    applicable_targets: str | None = None
    description: str | None = None


class OfferUpdate(BaseModel):
    offer_name: str | None = Field(default=None, max_length=255)
    offer_type: OfferType | None = None
    status: OfferStatus | None = None
    discount_value: float | None = Field(default=None, ge=0)
    minimum_bill_amount: float | None = Field(default=None, ge=0)
    applicable_outlets: list[int] | None = None
    applicable_days: list[str] | None = None
    start_time: str | None = Field(default=None, max_length=8)
    end_time: str | None = Field(default=None, max_length=8)
    applicable_targets: str | None = None
    description: str | None = None


class OfferRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int | None
    offer_name: str
    offer_type: OfferType
    status: OfferStatus
    discount_value: float
    minimum_bill_amount: float | None
    applicable_outlets: list[int] = Field(default_factory=list)
    applicable_days: list[str] = Field(default_factory=list)
    start_time: str | None
    end_time: str | None
    applicable_targets: str | None
    description: str | None
    is_active: bool


class OfferDeleteResponse(MessageResponse):
    offer_id: int
