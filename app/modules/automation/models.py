from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class AutomationTriggerType(str, enum.Enum):
    NEW_CUSTOMER_ADDED = "new_customer_added"
    CUSTOMER_BIRTHDAY = "customer_birthday"
    NO_VISIT_30_DAYS = "no_visit_30_days"
    NEW_WHATSAPP_MESSAGE = "new_whatsapp_message"
    CAMPAIGN_REPLY_RECEIVED = "campaign_reply_received"
    NEGATIVE_FEEDBACK_RECEIVED = "negative_feedback_received"
    RESERVATION_CREATED = "reservation_created"
    SPA_BOOKING_CREATED = "spa_booking_created"
    SPA_BOOKING_CONFIRMED = "spa_booking_confirmed"
    BANQUET_BOOKING_CREATED = "banquet_booking_created"
    BANQUET_BOOKING_CONFIRMED = "banquet_booking_confirmed"
    GUEST_RESERVATION_CONFIRMED = "guest_reservation_confirmed"
    GUEST_RESERVATION_CHECKED_OUT = "guest_reservation_checked_out"
    EVENT_CONFIRMED = "event_confirmed"
    BILL_GENERATED = "bill_generated"


class AutomationActionType(str, enum.Enum):
    SEND_WHATSAPP_TEMPLATE = "send_whatsapp_template"
    SEND_SMS = "send_sms"
    SEND_EMAIL = "send_email"
    ASSIGN_USER = "assign_user"
    ADD_TAG = "add_tag"
    CHANGE_LEAD_STAGE = "change_lead_stage"
    CREATE_FOLLOWUP_TASK = "create_followup_task"
    NOTIFY_MANAGER = "notify_manager"
    GENERATE_AI_REPLY_DRAFT = "generate_ai_reply_draft"


class AutomationRuleStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class AutomationRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AutomationRule(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "automation_rules"

    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_type: Mapped[AutomationTriggerType] = mapped_column(Enum(AutomationTriggerType))
    conditions_json: Mapped[str] = mapped_column(Text, default="{}")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    timing_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[AutomationRuleStatus] = mapped_column(
        Enum(AutomationRuleStatus), default=AutomationRuleStatus.DRAFT
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    runs: Mapped[list["AutomationRun"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AutomationRun.started_at.desc()",
    )


class AutomationRun(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "automation_runs"

    rule_id: Mapped[int] = mapped_column(ForeignKey("automation_rules.id"), index=True, nullable=False)
    trigger_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[AutomationRunStatus] = mapped_column(
        Enum(AutomationRunStatus), default=AutomationRunStatus.PENDING
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rule: Mapped["AutomationRule"] = relationship(back_populates="runs")
