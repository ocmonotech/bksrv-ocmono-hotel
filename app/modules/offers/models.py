from __future__ import annotations

from typing import Optional

import enum

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class OfferType(str, enum.Enum):
    BUY_ONE_GET_ONE = "buy_one_get_one"
    PERCENTAGE_DISCOUNT = "percentage_discount"
    FIXED_DISCOUNT = "fixed_discount"
    COMBO = "combo"
    MINIMUM_BILL = "minimum_bill"
    BIRTHDAY = "birthday"
    LOYALTY = "loyalty"
    HAPPY_HOUR = "happy_hour"


class OfferStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Offer(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "offers"

    offer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    offer_type: Mapped[OfferType] = mapped_column(Enum(OfferType), nullable=False)
    status: Mapped[OfferStatus] = mapped_column(Enum(OfferStatus), default=OfferStatus.ACTIVE)
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    minimum_bill_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    applicable_outlets_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applicable_days_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    applicable_targets: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
