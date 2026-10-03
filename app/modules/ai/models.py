from __future__ import annotations

from typing import Optional

import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class AiProviderName(str, enum.Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    PERPLEXITY = "perplexity"
    DEEPSEEK = "deepseek"
    CUSTOM = "custom"


class AiProviderStatus(str, enum.Enum):
    CONNECTED = "connected"
    NOT_CONNECTED = "not_connected"
    ERROR = "error"
    DISABLED = "disabled"


class AiPromptStatus(str, enum.Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    INACTIVE = "inactive"


class AiUsageStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


class AiInsightStatus(str, enum.Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class AiProvider(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ai_providers"

    provider_name: Mapped[AiProviderName] = mapped_column(Enum(AiProviderName), nullable=False)
    api_base_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_key_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    default_model: Mapped[str] = mapped_column(String(128), default="gpt-4o-mini")
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), default=0.7)
    monthly_budget: Mapped[float] = mapped_column(Numeric(12, 2), default=25000)
    usage_alert_percent: Mapped[int] = mapped_column(Integer, default=80)
    status: Mapped[AiProviderStatus] = mapped_column(
        Enum(AiProviderStatus), default=AiProviderStatus.NOT_CONNECTED
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class AiPrompt(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ai_prompts"

    prompt_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general")
    system_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[str] = mapped_column(Text, default="[]")
    output_format: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(64), default="English")
    status: Mapped[AiPromptStatus] = mapped_column(Enum(AiPromptStatus), default=AiPromptStatus.DRAFT)


class AiUsageLog(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ai_usage_logs"

    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_providers.id"), nullable=True)
    module_name: Mapped[str] = mapped_column(String(64), index=True)
    request_type: Mapped[str] = mapped_column(String(64), default="completion")
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    status: Mapped[AiUsageStatus] = mapped_column(Enum(AiUsageStatus), default=AiUsageStatus.SUCCESS)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class AiInsight(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ai_insights"

    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    insight_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    status: Mapped[AiInsightStatus] = mapped_column(Enum(AiInsightStatus), default=AiInsightStatus.NEW)


class AiAutomationRule(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ai_automation_rules"

    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    module_name: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_providers.id"), nullable=True)
    prompt_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_prompts.id"), nullable=True)
    human_approval_required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    max_cost_per_run: Mapped[float] = mapped_column(Numeric(10, 4), default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
