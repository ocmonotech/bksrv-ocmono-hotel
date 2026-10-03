from __future__ import annotations

from typing import Optional

import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class CustomerSource(str, enum.Enum):
    WALK_IN = "walk_in"
    POS = "pos"
    ONLINE = "online"
    CAMPAIGN = "campaign"
    REFERRAL = "referral"
    OTHER = "other"


class CustomerStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class FeedbackSentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class FeedbackSource(str, enum.Enum):
    POS = "pos"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"
    WEB = "web"


class Customer(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "customers"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    birthday: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    anniversary: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source: Mapped[CustomerSource] = mapped_column(Enum(CustomerSource), default=CustomerSource.WALK_IN)
    consent_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    consent_sms: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    consent_email: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    total_visits: Mapped[int] = mapped_column(Integer, default=0)
    total_spend: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)
    last_visit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    favourite_outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True)
    status: Mapped[CustomerStatus] = mapped_column(Enum(CustomerStatus), default=CustomerStatus.ACTIVE)

    tag_maps: Mapped[list["CustomerTagMap"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    visits: Mapped[list["CustomerVisit"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class CustomerVisit(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "customer_visits"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    bill_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pos_bills.id"), nullable=True)
    visit_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    customer: Mapped["Customer"] = relationship(back_populates="visits")


class CustomerTag(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "customer_tags"

    name: Mapped[str] = mapped_column(String(64), nullable=False)

    tag_maps: Mapped[list["CustomerTagMap"]] = relationship(
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class CustomerTagMap(Base, BaseMixin):
    __tablename__ = "customer_tag_maps"

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("customer_tags.id"), index=True, nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="tag_maps")
    tag: Mapped["CustomerTag"] = relationship(back_populates="tag_maps")


class Feedback(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "customer_feedback"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment: Mapped[FeedbackSentiment] = mapped_column(Enum(FeedbackSentiment))
    source: Mapped[FeedbackSource] = mapped_column(Enum(FeedbackSource), default=FeedbackSource.POS)

    customer: Mapped["Customer"] = relationship(back_populates="feedback_entries")
