from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.campaigns.models import CampaignChannel, CampaignStatus, RecipientStatus


class CampaignCreate(BaseModel):
    campaign_name: str = Field(min_length=1, max_length=255)
    channel: CampaignChannel
    goal: str | None = None
    template_id: int | None = None
    selected_outlets: list[int] = Field(default_factory=list)
    audience_filter: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None
    estimated_cost: float = Field(default=0, ge=0)
    brand_id: int | None = None


class CampaignUpdate(BaseModel):
    campaign_name: str | None = Field(default=None, min_length=1, max_length=255)
    goal: str | None = None
    template_id: int | None = None
    selected_outlets: list[int] | None = None
    audience_filter: dict | None = None
    scheduled_at: datetime | None = None
    estimated_cost: float | None = Field(default=None, ge=0)


class CampaignSchedule(BaseModel):
    scheduled_at: datetime


class CampaignRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    campaign_name: str
    channel: CampaignChannel
    goal: str | None
    status: CampaignStatus
    selected_outlets: list[int] = []
    audience_filter: dict = {}
    template_id: int | None
    scheduled_at: datetime | None
    sent_count: int
    delivered_count: int
    read_count: int
    replied_count: int
    converted_count: int
    failed_count: int
    estimated_cost: float
    actual_cost: float
    created_by: int
    is_active: bool


class CampaignDetailRead(CampaignRead):
    recipient_count: int = 0


class CampaignRecipientRead(ORMSchema, TimestampSchema):
    id: int
    campaign_id: int
    customer_id: int | None
    lead_id: int | None
    outlet_id: int | None
    mobile: str | None
    email: str | None
    status: RecipientStatus
    provider_message_id: str | None
    error_message: str | None


class CampaignEventRead(ORMSchema, TimestampSchema):
    id: int
    campaign_id: int
    recipient_id: int | None
    event_type: str
    event_payload: dict = {}


class CampaignReport(BaseModel):
    campaign_id: int
    campaign_name: str
    status: CampaignStatus
    channel: CampaignChannel
    sent_count: int
    delivered_count: int
    read_count: int
    replied_count: int
    converted_count: int
    failed_count: int
    delivery_rate: float
    read_rate: float
    reply_rate: float
    conversion_rate: float
    estimated_cost: float
    actual_cost: float
    recipient_total: int
    recipient_breakdown: dict[str, int]


class MockLaunchResponse(BaseModel):
    success: bool
    campaign_id: int
    status: CampaignStatus
    recipients_processed: int
    message: str
    mock: bool = True
