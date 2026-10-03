from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.leads.models import (
    LeadActivityType,
    LeadSource,
    LeadStage,
    LeadStatus,
)


class LeadCreate(BaseModel):
    lead_name: str = Field(min_length=1, max_length=255)
    mobile: str = Field(min_length=5, max_length=32)
    email: str | None = None
    outlet_id: int | None = None
    customer_id: int | None = None
    source: LeadSource = LeadSource.WHATSAPP
    campaign_id: int | None = None
    lead_score: int = Field(default=0, ge=0, le=100)
    stage: LeadStage = LeadStage.NEW
    assigned_to: int | None = None
    last_message: str | None = None
    next_followup_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    brand_id: int | None = None


class LeadStageUpdate(BaseModel):
    stage: LeadStage
    note: str | None = None


class LeadAssign(BaseModel):
    assigned_to: int


class LeadFollowUpUpdate(BaseModel):
    next_followup_at: datetime
    note: str | None = None


class LeadActivityCreate(BaseModel):
    activity_type: LeadActivityType = LeadActivityType.NOTE
    note: str | None = None


class LeadActivityRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    lead_id: int
    activity_type: LeadActivityType
    note: str | None
    created_by: int


class LeadRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int | None
    customer_id: int | None
    lead_name: str
    mobile: str
    email: str | None
    source: LeadSource
    campaign_id: int | None
    lead_score: int
    stage: LeadStage
    assigned_to: int | None
    last_message: str | None
    next_followup_at: datetime | None
    status: LeadStatus
    tags: list[str] = []
    is_active: bool


class LeadDetailRead(LeadRead):
    activities: list[LeadActivityRead] = []


class SegmentCreate(BaseModel):
    segment_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    filter_json: dict = Field(default_factory=dict)
    brand_id: int | None = None


class SegmentUpdate(BaseModel):
    segment_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    filter_json: dict | None = None


class SegmentRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    segment_name: str
    description: str | None
    filter_json: dict
    estimated_count: int
    is_active: bool


class SegmentEstimateResponse(BaseModel):
    segment_id: int
    estimated_count: int
    message: str = "Segment audience estimated"
