from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class CampaignChannel(str, enum.Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"


class RecipientStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    REPLIED = "replied"
    FAILED = "failed"
    CONVERTED = "converted"


class AutomationFlowStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


class Campaign(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "campaigns"

    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[CampaignChannel] = mapped_column(Enum(CampaignChannel), nullable=False)
    goal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.DRAFT
    )
    selected_outlets_json: Mapped[str] = mapped_column(Text, default="[]")
    audience_filter_json: Mapped[str] = mapped_column(Text, default="{}")
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("message_templates.id"), nullable=True
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    replied_count: Mapped[int] = mapped_column(Integer, default=0)
    converted_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    actual_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["CampaignEvent"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignEvent.created_at.desc()",
    )


class CampaignRecipient(Base, BaseMixin):
    __tablename__ = "campaign_recipients"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True, nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leads.id"), nullable=True)
    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[RecipientStatus] = mapped_column(
        Enum(RecipientStatus), default=RecipientStatus.PENDING
    )
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="recipients")
    events: Mapped[list["CampaignEvent"]] = relationship(
        back_populates="recipient",
        cascade="all, delete-orphan",
    )


class CampaignEvent(Base, BaseMixin):
    __tablename__ = "campaign_events"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True, nullable=False)
    recipient_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaign_recipients.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_payload_json: Mapped[str] = mapped_column(Text, default="{}")

    campaign: Mapped["Campaign"] = relationship(back_populates="events")
    recipient: Mapped["CampaignRecipient | None"] = relationship(back_populates="events")


class AutomationFlow(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "automation_flows"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(64), default="lead_created")
    channel: Mapped[CampaignChannel] = mapped_column(Enum(CampaignChannel))
    definition_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[AutomationFlowStatus] = mapped_column(
        Enum(AutomationFlowStatus), default=AutomationFlowStatus.DRAFT
    )
