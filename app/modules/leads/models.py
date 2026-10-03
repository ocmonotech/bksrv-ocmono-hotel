from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class LeadSource(str, enum.Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    WEBSITE = "website"
    QR = "qr"
    GOOGLE = "google"
    WALK_IN = "walk_in"
    REFERRAL = "referral"


class LeadStage(str, enum.Enum):
    NEW = "new"
    INTERESTED = "interested"
    FOLLOW_UP = "follow_up"
    TABLE_BOOKED = "table_booked"
    VISITED = "visited"
    CONVERTED = "converted"
    LOST = "lost"


class LeadStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class LeadActivityType(str, enum.Enum):
    NOTE = "note"
    CALL = "call"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    STAGE_CHANGE = "stage_change"
    ASSIGNMENT = "assignment"
    FOLLOW_UP = "follow_up"


class Lead(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "leads"

    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    lead_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[LeadSource] = mapped_column(Enum(LeadSource), default=LeadSource.WHATSAPP)
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[LeadStage] = mapped_column(Enum(LeadStage), default=LeadStage.NEW)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    last_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.OPEN)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")

    activities: Mapped[list["LeadActivity"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadActivity.created_at.desc()",
    )


class LeadActivity(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "lead_activities"

    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True, nullable=False)
    activity_type: Mapped[LeadActivityType] = mapped_column(Enum(LeadActivityType))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="activities")


class Segment(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "lead_segments"

    segment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    filter_json: Mapped[str] = mapped_column(Text, default="{}")
    estimated_count: Mapped[int] = mapped_column(Integer, default=0)
