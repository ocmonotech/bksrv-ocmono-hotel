from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.ai.models import (
    AiPromptStatus,
    AiProviderName,
    AiProviderStatus,
    AiUsageStatus,
)


class AiProviderCreate(BaseModel):
    provider_name: AiProviderName
    api_base_url: str | None = None
    api_key: str | None = None
    default_model: str = "gpt-4o-mini"
    max_tokens: int = Field(default=2048, ge=1, le=128000)
    temperature: float = Field(default=0.7, ge=0, le=2)
    monthly_budget: float = Field(default=25000, ge=0)
    usage_alert_percent: int = Field(default=80, ge=1, le=100)
    status: AiProviderStatus = AiProviderStatus.NOT_CONNECTED
    is_default: bool = False
    brand_id: int | None = None


class AiProviderUpdate(BaseModel):
    api_base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=128000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    monthly_budget: float | None = Field(default=None, ge=0)
    usage_alert_percent: int | None = Field(default=None, ge=1, le=100)
    status: AiProviderStatus | None = None


class AiProviderRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    provider_name: AiProviderName
    api_base_url: str | None
    api_key_last4: str | None
    default_model: str
    max_tokens: int
    temperature: float
    monthly_budget: float
    usage_alert_percent: int
    status: AiProviderStatus
    is_default: bool
    is_active: bool


class AiProviderTestResponse(BaseModel):
    success: bool
    provider_id: int
    message: str
    mock: bool = True


class AiPromptCreate(BaseModel):
    prompt_name: str = Field(min_length=1, max_length=255)
    category: str = "general"
    system_instruction: str | None = None
    user_prompt_template: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    output_format: str | None = None
    tone: str | None = None
    language: str = "English"
    status: AiPromptStatus = AiPromptStatus.DRAFT
    brand_id: int | None = None


class AiPromptUpdate(BaseModel):
    prompt_name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = None
    system_instruction: str | None = None
    user_prompt_template: str | None = Field(default=None, min_length=1)
    variables: list[str] | None = None
    output_format: str | None = None
    tone: str | None = None
    language: str | None = None
    status: AiPromptStatus | None = None


class AiPromptRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    prompt_name: str
    category: str
    system_instruction: str | None
    user_prompt_template: str
    variables: list[str] = []
    output_format: str | None
    tone: str | None
    language: str
    status: AiPromptStatus
    is_active: bool


class MockGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    module_name: str = "general"
    context: dict = Field(default_factory=dict)
    provider_id: int | None = None
    prompt_id: int | None = None
    outlet_id: int | None = None


class DraftWhatsAppReplyRequest(BaseModel):
    customer_message: str = Field(min_length=1)
    context: dict = Field(default_factory=dict)
    tone: str = "friendly"
    provider_id: int | None = None
    outlet_id: int | None = None


class ScoreLeadRequest(BaseModel):
    lead_name: str
    source: str | None = None
    last_message: str | None = None
    context: dict = Field(default_factory=dict)
    provider_id: int | None = None


class GenerateCampaignCopyRequest(BaseModel):
    campaign_name: str
    channel: str = "whatsapp"
    goal: str | None = None
    audience: str | None = None
    tone: str = "promotional"
    provider_id: int | None = None


class MockAiResponse(BaseModel):
    content: str
    provider_name: str
    model: str
    confidence_score: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    usage_log_id: int | None = None
    mock: bool = True


class AiUsageLogCreate(BaseModel):
    provider_id: int | None = None
    outlet_id: int | None = None
    module_name: str
    request_type: str = "completion"
    model: str | None = None
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    status: AiUsageStatus = AiUsageStatus.SUCCESS


class AiUsageLogRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int | None
    provider_id: int | None
    module_name: str
    request_type: str
    model: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    status: AiUsageStatus
    created_by: int | None


class AiUsageReport(BaseModel):
    total_requests: int
    total_tokens: int
    total_estimated_cost: float
    monthly_budget: float | None
    budget_used_percent: float | None
    by_module: dict[str, dict[str, float | int]]
    by_provider: dict[str, dict[str, float | int]]


class AiAutomationRuleCreate(BaseModel):
    rule_name: str = Field(min_length=1, max_length=255)
    module_name: str
    trigger_name: str
    provider_id: int | None = None
    prompt_id: int | None = None
    human_approval_required: bool = True
    max_cost_per_run: float = Field(default=1.0, ge=0)
    is_active: bool = True
    brand_id: int | None = None


class AiAutomationRuleUpdate(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=255)
    module_name: str | None = None
    trigger_name: str | None = None
    provider_id: int | None = None
    prompt_id: int | None = None
    human_approval_required: bool | None = None
    max_cost_per_run: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class AiAutomationRuleRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    rule_name: str
    module_name: str
    trigger_name: str
    provider_id: int | None
    prompt_id: int | None
    human_approval_required: bool
    max_cost_per_run: float
    is_active: bool
