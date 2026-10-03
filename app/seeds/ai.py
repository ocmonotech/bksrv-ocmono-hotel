"""AI providers, prompts, usage logs, insights, and automation rules."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.modules.ai.models import (
    AiAutomationRule,
    AiInsight,
    AiInsightStatus,
    AiPrompt,
    AiPromptStatus,
    AiProvider,
    AiProviderName,
    AiProviderStatus,
    AiUsageLog,
    AiUsageStatus,
)
from app.seeds.base import SeedContext
from app.seeds.constants import SUPER_ADMIN_EMAIL


def seed_ai(db: Session, ctx: SeedContext) -> None:
    ctx.ai_providers = _seed_ai_providers(db, ctx)
    prompts = _seed_ai_prompts(db, ctx)
    _seed_ai_usage_logs(db, ctx)
    _seed_ai_insights(db, ctx)
    _seed_ai_automation_rules(db, ctx, prompts)


def _seed_ai_providers(db: Session, ctx: SeedContext) -> dict[str, AiProvider]:
    tenant, brand = ctx.tenant, ctx.brand
    from app.core.config import settings

    default_model = settings.ai_default_model or "llama3.2:1b"
    default_base = settings.openai_api_base_url or "http://ollama:11434/v1"
    if "api.openai.com" in default_base and not settings.openai_api_key.startswith("stub"):
        # Keep OpenAI URL only when a real OpenAI/Groq key is configured via that base
        pass
    elif settings.openai_api_key.startswith("stub") or "ollama" in default_base:
        default_base = (
            default_base
            if "ollama" in default_base or "groq.com" in default_base
            else "http://ollama:11434/v1"
        )

    specs = [
        (AiProviderName.OPENAI, AiProviderStatus.CONNECTED, default_model, True, default_base),
        (AiProviderName.GEMINI, AiProviderStatus.NOT_CONNECTED, "gemini-1.5-flash", False, "https://mock.ai.local"),
        (AiProviderName.CLAUDE, AiProviderStatus.NOT_CONNECTED, "claude-3-5-sonnet", False, "https://mock.ai.local"),
    ]
    providers: dict[str, AiProvider] = {}
    for provider_name, status, model, is_default, base_url in specs:
        provider = (
            db.query(AiProvider)
            .filter(
                AiProvider.tenant_id == tenant.id,
                AiProvider.brand_id == brand.id,
                AiProvider.provider_name == provider_name,
            )
            .first()
        )
        if provider is None:
            provider = AiProvider(
                tenant_id=tenant.id,
                brand_id=brand.id,
                provider_name=provider_name,
                api_base_url=base_url,
                encrypted_api_key="MOCK_ENC:demo-ai-key",
                api_key_last4="demo",
                default_model=model,
                max_tokens=2048,
                temperature=0.7,
                monthly_budget=25000,
                usage_alert_percent=80,
                status=status,
                is_default=is_default,
            )
            db.add(provider)
            db.flush()
        elif is_default:
            provider.api_base_url = base_url
            provider.default_model = model
            provider.status = status
        providers[provider_name.value] = provider
    return providers


def _seed_ai_prompts(db: Session, ctx: SeedContext) -> dict[str, AiPrompt]:
    tenant, brand = ctx.tenant, ctx.brand
    prompt_specs = [
        (
            "Menu Description Generator",
            "menu",
            "You are a restaurant copywriter.",
            "Write a 2-sentence description for {{item_name}} priced at ₹{{price}}.",
            ["item_name", "price"],
        ),
        (
            "Review Response Draft",
            "crm",
            "You are a polite restaurant manager.",
            "Draft a reply to this customer feedback: {{feedback}}",
            ["feedback"],
        ),
        (
            "Daily Sales Summary",
            "analytics",
            "You are a restaurant analyst.",
            "Summarize today's sales: {{sales_data}}",
            ["sales_data"],
        ),
        (
            "Campaign Copy Writer",
            "campaigns",
            "You are a hospitality marketing expert.",
            "Write a short WhatsApp campaign message for the offer: {{offer_name}}. Keep it under 160 characters.",
            ["offer_name"],
        ),
        (
            "Guest Complaint Handler",
            "crm",
            "You are an empathetic hotel guest relations manager.",
            "Draft a professional resolution response for this guest complaint: {{complaint}}",
            ["complaint"],
        ),
    ]
    prompts: dict[str, AiPrompt] = {}
    for name, category, system, user_template, variables in prompt_specs:
        prompt = (
            db.query(AiPrompt)
            .filter(AiPrompt.tenant_id == tenant.id, AiPrompt.prompt_name == name)
            .first()
        )
        if prompt is None:
            prompt = AiPrompt(
                tenant_id=tenant.id,
                brand_id=brand.id,
                prompt_name=name,
                category=category,
                system_instruction=system,
                user_prompt_template=user_template,
                variables_json=json.dumps(variables),
                output_format="text",
                tone="professional",
                language="English",
                status=AiPromptStatus.ACTIVE,
            )
            db.add(prompt)
            db.flush()
        prompts[name] = prompt
    return prompts


def _seed_ai_usage_logs(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    openai = ctx.ai_providers.get("openai")
    if openai is None:
        return

    usage_specs = [
        ("menu", "completion", "gpt-4o-mini", 120, 85, 205, 0.02),
        ("crm", "completion", "gpt-4o-mini", 200, 150, 350, 0.04),
        ("analytics", "completion", "gpt-4o-mini", 350, 220, 570, 0.06),
        ("campaigns", "completion", "gpt-4o-mini", 90, 60, 150, 0.015),
    ]

    for module, req_type, model, prompt_tok, comp_tok, total_tok, cost in usage_specs:
        existing = (
            db.query(AiUsageLog)
            .filter(
                AiUsageLog.tenant_id == tenant.id,
                AiUsageLog.module_name == module,
                AiUsageLog.request_type == req_type,
            )
            .first()
        )
        if existing is not None:
            continue
        db.add(
            AiUsageLog(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                provider_id=openai.id,
                module_name=module,
                request_type=req_type,
                model=model,
                prompt_tokens=prompt_tok,
                completion_tokens=comp_tok,
                total_tokens=total_tok,
                estimated_cost=cost,
                status=AiUsageStatus.SUCCESS,
                created_by=admin.id if admin else None,
            )
        )


def _seed_ai_insights(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]

    insights = [
        (
            "slow_moving_item",
            "Paneer Lababdar sales down 18%",
            "Paneer Lababdar orders dropped this week compared to last week.",
            "Consider a combo offer or staff upsell training.",
            82.5,
        ),
        (
            "peak_hour",
            "Friday 8–10 PM peak detected",
            "Andheri West sees highest table turnover on Friday evenings.",
            "Schedule extra wait staff for Friday dinner service.",
            91.0,
        ),
        (
            "high_revenue_item",
            "Butter Chicken top revenue driver this month",
            "Butter Chicken contributed 22% of total food revenue across all outlets.",
            "Feature Butter Chicken prominently in digital menus and campaigns.",
            88.0,
        ),
        (
            "customer_churn",
            "15 VIP customers not visited in 30+ days",
            "High-value customers who typically visit weekly have not returned this month.",
            "Send a personalised re-engagement WhatsApp offer to this segment.",
            76.5,
        ),
        (
            "inventory_waste",
            "Fresh cream wastage up 12% this week",
            "Purchase vs consumption variance indicates over-ordering of fresh cream.",
            "Reduce fresh cream purchase order by 20% for next week.",
            79.0,
        ),
    ]

    for insight_type, title, description, recommendation, confidence in insights:
        existing = (
            db.query(AiInsight)
            .filter(AiInsight.tenant_id == tenant.id, AiInsight.title == title)
            .first()
        )
        if existing is not None:
            continue
        db.add(
            AiInsight(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                insight_type=insight_type,
                title=title,
                description=description,
                recommendation=recommendation,
                confidence_score=confidence,
                status=AiInsightStatus.NEW,
            )
        )


def _seed_ai_automation_rules(db: Session, ctx: SeedContext, prompts: dict[str, AiPrompt]) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    openai = ctx.ai_providers.get("openai")
    review_prompt = prompts.get("Review Response Draft")
    if openai is None or review_prompt is None:
        return

    existing = (
        db.query(AiAutomationRule)
        .filter(AiAutomationRule.tenant_id == tenant.id, AiAutomationRule.rule_name == "Auto Draft Review Reply")
        .first()
    )
    if existing is not None:
        return

    db.add(
        AiAutomationRule(
            tenant_id=tenant.id,
            brand_id=brand.id,
            rule_name="Auto Draft Review Reply",
            module_name="crm",
            trigger_name="negative_feedback_received",
            provider_id=openai.id,
            prompt_id=review_prompt.id,
            human_approval_required=True,
            max_cost_per_run=0.5,
            is_active=True,
        )
    )
