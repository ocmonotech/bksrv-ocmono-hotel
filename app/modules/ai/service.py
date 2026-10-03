from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.core.config import settings
from app.modules.ai.models import (
    AiAutomationRule,
    AiPrompt,
    AiProvider,
    AiProviderStatus,
    AiUsageLog,
    AiUsageStatus,
)
from app.modules.ai.schemas import (
    AiAutomationRuleCreate,
    AiAutomationRuleRead,
    AiAutomationRuleUpdate,
    AiPromptCreate,
    AiPromptRead,
    AiPromptUpdate,
    AiProviderCreate,
    AiProviderRead,
    AiProviderTestResponse,
    AiProviderUpdate,
    AiUsageLogCreate,
    AiUsageLogRead,
    AiUsageReport,
    DraftWhatsAppReplyRequest,
    GenerateCampaignCopyRequest,
    MockAiResponse,
    MockGenerateRequest,
    ScoreLeadRequest,
)
from app.modules.brands.models import Brand
from app.modules.outlets.models import Outlet

logger = logging.getLogger(__name__)


@dataclass
class StubGenerateResult:
    content: str
    provider_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    confidence_score: float


async def _mock_generate(
    *,
    provider: AiProvider | None,
    module_name: str,
    prompt: str,
    context: dict | None = None,
) -> StubGenerateResult:
    context = context or {}
    provider_name = provider.provider_name.value if provider else "openai"
    model = provider.default_model if provider else settings.ai_default_model
    preview = prompt[:120].replace("\n", " ")

    api_key = settings.openai_api_key
    if api_key and not api_key.startswith("stub"):
        base_url = settings.openai_api_base_url.rstrip("/")
        if provider and provider.api_base_url and "mock.ai.local" not in provider.api_base_url:
            base_url = provider.api_base_url.rstrip("/")
        # Cloud OpenAI model names fail on Ollama/Groq — prefer configured default
        if any(token in base_url for token in ("ollama", "groq.com")) and (
            not model
            or model.startswith(("gpt-", "claude-", "gemini-"))
            or model in {"claude-3-5-sonnet"}
        ):
            model = settings.ai_default_model
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": float(provider.temperature) if provider else 0.7,
                        "max_tokens": min(provider.max_tokens if provider else 512, 1024),
                    },
                )
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                usage = payload.get("usage", {})
                prompt_tokens = int(usage.get("prompt_tokens", max(len(prompt.split()), 10)))
                completion_tokens = int(
                    usage.get("completion_tokens", max(len(content.split()), 20))
                )
                total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens))
                return StubGenerateResult(
                    content=content,
                    provider_name=provider_name,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost=round(total_tokens * 0.002, 4),
                    confidence_score=0.9,
                )
        except Exception as exc:
            logger.warning("OpenAI-compatible API call failed, using mock fallback: %s", exc)

    content = (
        f"[Mock {provider_name}/{model} response for {module_name}] "
        f"Input: {preview}... "
        f"Context: {', '.join(context.keys()) or 'none'}."
    )
    prompt_tokens = max(len(prompt.split()), 10)
    completion_tokens = max(len(content.split()), 20)
    total_tokens = prompt_tokens + completion_tokens

    return StubGenerateResult(
        content=content,
        provider_name=provider_name,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=round(total_tokens * 0.002, 4),
        confidence_score=0.86,
    )


def list_providers(
    db: Session,
    tenant_id: int,
    brand_id: int | None = None,
) -> list[AiProviderRead]:
    query = db.query(AiProvider).filter(
        AiProvider.tenant_id == tenant_id,
        AiProvider.is_active.is_(True),
    )
    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(AiProvider.brand_id.is_(None), AiProvider.brand_id == brand_id))

    providers = query.order_by(AiProvider.is_default.desc(), AiProvider.provider_name).all()
    return [AiProviderRead.model_validate(provider) for provider in providers]


def create_provider(
    db: Session,
    tenant_id: int,
    data: AiProviderCreate,
    default_brand_id: int | None = None,
) -> AiProviderRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    if data.is_default:
        _clear_default_provider(db, tenant_id, brand_id)

    provider = AiProvider(
        tenant_id=tenant_id,
        brand_id=brand_id,
        provider_name=data.provider_name,
        api_base_url=data.api_base_url,
        encrypted_api_key=_encrypt_api_key_placeholder(data.api_key),
        api_key_last4=_api_key_last4(data.api_key),
        default_model=data.default_model,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
        monthly_budget=data.monthly_budget,
        usage_alert_percent=data.usage_alert_percent,
        status=data.status,
        is_default=data.is_default,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return AiProviderRead.model_validate(provider)


def update_provider(
    db: Session,
    tenant_id: int,
    provider_id: int,
    data: AiProviderUpdate,
    user_id: int | None = None,
) -> AiProviderRead:
    provider = _get_provider(db, tenant_id, provider_id)
    old_data = _ai_provider_audit_snapshot(provider)
    updates = data.model_dump(exclude_unset=True)

    if "api_key" in updates:
        api_key = updates.pop("api_key")
        if api_key is not None:
            provider.encrypted_api_key = _encrypt_api_key_placeholder(api_key)
            provider.api_key_last4 = _api_key_last4(api_key)

    for field, value in updates.items():
        setattr(provider, field, value)

    from app.modules.audit.models import AuditAction
    from app.modules.audit.service import log_audit

    log_audit(
        db,
        tenant_id=tenant_id,
        brand_id=provider.brand_id,
        user_id=user_id,
        action=AuditAction.AI_PROVIDER_UPDATED.value,
        module_name="ai",
        record_type="ai_provider",
        record_id=provider.id,
        old_data=old_data,
        new_data=_ai_provider_audit_snapshot(provider),
    )

    db.commit()
    db.refresh(provider)
    return AiProviderRead.model_validate(provider)


async def test_provider_mock(db: Session, tenant_id: int, provider_id: int) -> AiProviderTestResponse:
    provider = _get_provider(db, tenant_id, provider_id)
    result = await _mock_generate(
        provider=provider,
        module_name="provider_test",
        prompt="Provider connectivity test",
    )

    provider.status = AiProviderStatus.CONNECTED
    db.commit()

    return AiProviderTestResponse(
        success=True,
        provider_id=provider.id,
        message=f"Mock test succeeded using {result.provider_name}/{result.model}",
    )


def set_default_provider(db: Session, tenant_id: int, provider_id: int) -> AiProviderRead:
    provider = _get_provider(db, tenant_id, provider_id)
    _clear_default_provider(db, tenant_id, provider.brand_id, exclude_id=provider.id)
    provider.is_default = True
    provider.status = AiProviderStatus.CONNECTED
    db.commit()
    db.refresh(provider)
    return AiProviderRead.model_validate(provider)


def list_prompts(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    category: str | None = None,
    brand_id: int | None = None,
) -> tuple[list[AiPromptRead], int]:
    query = db.query(AiPrompt).filter(AiPrompt.tenant_id == tenant_id, AiPrompt.is_active.is_(True))

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(AiPrompt.brand_id.is_(None), AiPrompt.brand_id == brand_id))

    if category is not None:
        query = query.filter(AiPrompt.category == category)

    query = query.order_by(AiPrompt.prompt_name)
    prompts, total = paginate_query(query, page, page_size)
    return [_prompt_to_read(prompt) for prompt in prompts], total


def create_prompt(
    db: Session,
    tenant_id: int,
    data: AiPromptCreate,
    default_brand_id: int | None = None,
) -> AiPromptRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    prompt = AiPrompt(
        tenant_id=tenant_id,
        brand_id=brand_id,
        prompt_name=data.prompt_name,
        category=data.category,
        system_instruction=data.system_instruction,
        user_prompt_template=data.user_prompt_template,
        variables_json=json.dumps(data.variables),
        output_format=data.output_format,
        tone=data.tone,
        language=data.language,
        status=data.status,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return _prompt_to_read(prompt)


def update_prompt(
    db: Session,
    tenant_id: int,
    prompt_id: int,
    data: AiPromptUpdate,
) -> AiPromptRead:
    prompt = _get_prompt(db, tenant_id, prompt_id)
    updates = data.model_dump(exclude_unset=True)

    if "variables" in updates:
        prompt.variables_json = json.dumps(updates.pop("variables"))

    for field, value in updates.items():
        setattr(prompt, field, value)

    db.commit()
    db.refresh(prompt)
    return _prompt_to_read(prompt)


async def mock_generate(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: MockGenerateRequest,
    default_brand_id: int | None = None,
) -> MockAiResponse:
    provider = _resolve_provider(db, tenant_id, data.provider_id, default_brand_id)
    prompt = data.prompt

    if data.prompt_id is not None:
        prompt_template = _get_prompt(db, tenant_id, data.prompt_id)
        prompt = prompt_template.user_prompt_template

    result = await _mock_generate(
        provider=provider,
        module_name=data.module_name,
        prompt=prompt,
        context=data.context,
    )
    usage_log = _create_usage_log(
        db,
        tenant_id=tenant_id,
        brand_id=provider.brand_id if provider else default_brand_id,
        outlet_id=data.outlet_id,
        provider_id=provider.id if provider else None,
        user_id=user_id,
        module_name=data.module_name,
        request_type="mock_generate",
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost=result.estimated_cost,
    )
    return _to_mock_response(result, usage_log.id)


async def draft_whatsapp_reply(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: DraftWhatsAppReplyRequest,
    default_brand_id: int | None = None,
) -> MockAiResponse:
    provider = _resolve_provider(db, tenant_id, data.provider_id, default_brand_id)
    prompt = (
        f"Draft a {data.tone} WhatsApp reply to: {data.customer_message}. "
        f"Keep it concise and helpful."
    )
    result = await _mock_generate(
        provider=provider,
        module_name="communications",
        prompt=prompt,
        context=data.context,
    )
    result.content = (
        f"Hi! Thanks for your message. {result.content} "
        "We'd love to help you with your request. — Team (mock draft)"
    )
    usage_log = _create_usage_log(
        db,
        tenant_id=tenant_id,
        brand_id=provider.brand_id if provider else default_brand_id,
        outlet_id=data.outlet_id,
        provider_id=provider.id if provider else None,
        user_id=user_id,
        module_name="communications",
        request_type="draft_whatsapp_reply",
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost=result.estimated_cost,
    )
    return _to_mock_response(result, usage_log.id)


async def score_lead(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: ScoreLeadRequest,
    default_brand_id: int | None = None,
) -> MockAiResponse:
    provider = _resolve_provider(db, tenant_id, data.provider_id, default_brand_id)
    prompt = (
        f"Score lead {data.lead_name} from source {data.source or 'unknown'}. "
        f"Last message: {data.last_message or 'none'}."
    )
    result = await _mock_generate(
        provider=provider,
        module_name="leads",
        prompt=prompt,
        context=data.context,
    )

    mock_score = min(100, 35 + len(data.lead_name) + (len(data.last_message or "") // 10))
    result.content = json.dumps(
        {
            "lead_score": mock_score,
            "reasoning": result.content,
            "priority": "high" if mock_score >= 70 else "medium" if mock_score >= 45 else "low",
        }
    )
    result.confidence_score = 0.78

    usage_log = _create_usage_log(
        db,
        tenant_id=tenant_id,
        brand_id=provider.brand_id if provider else default_brand_id,
        outlet_id=None,
        provider_id=provider.id if provider else None,
        user_id=user_id,
        module_name="leads",
        request_type="score_lead",
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost=result.estimated_cost,
    )
    return _to_mock_response(result, usage_log.id)


async def generate_campaign_copy(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: GenerateCampaignCopyRequest,
    default_brand_id: int | None = None,
) -> MockAiResponse:
    provider = _resolve_provider(db, tenant_id, data.provider_id, default_brand_id)
    prompt = (
        f"Generate {data.tone} {data.channel} campaign copy for '{data.campaign_name}'. "
        f"Goal: {data.goal or 'engagement'}. Audience: {data.audience or 'customers'}."
    )
    result = await _mock_generate(
        provider=provider,
        module_name="campaigns",
        prompt=prompt,
        context={"channel": data.channel, "goal": data.goal},
    )
    result.content = (
        f"🎉 {data.campaign_name}\n\n"
        f"{result.content}\n\n"
        f"Visit us today! Reply STOP to opt out. (mock campaign copy)"
    )

    usage_log = _create_usage_log(
        db,
        tenant_id=tenant_id,
        brand_id=provider.brand_id if provider else default_brand_id,
        outlet_id=None,
        provider_id=provider.id if provider else None,
        user_id=user_id,
        module_name="campaigns",
        request_type="generate_campaign_copy",
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost=result.estimated_cost,
    )
    return _to_mock_response(result, usage_log.id)


def create_usage_log(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: AiUsageLogCreate,
    default_brand_id: int | None = None,
) -> AiUsageLogRead:
    brand_id = default_brand_id
    provider = None
    if data.provider_id is not None:
        provider = _get_provider(db, tenant_id, data.provider_id)
        brand_id = provider.brand_id or brand_id

    if data.outlet_id is not None:
        _get_outlet(db, tenant_id, data.outlet_id)

    total_tokens = data.total_tokens or (data.prompt_tokens + data.completion_tokens)
    log = _create_usage_log(
        db,
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        provider_id=data.provider_id,
        user_id=user_id,
        module_name=data.module_name,
        request_type=data.request_type,
        model=data.model,
        prompt_tokens=data.prompt_tokens,
        completion_tokens=data.completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=data.estimated_cost,
        status=data.status,
    )
    return AiUsageLogRead.model_validate(log)


def get_usage_report(
    db: Session,
    tenant_id: int,
    brand_id: int | None = None,
) -> AiUsageReport:
    query = db.query(AiUsageLog).filter(AiUsageLog.tenant_id == tenant_id)
    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(AiUsageLog.brand_id.is_(None), AiUsageLog.brand_id == brand_id))

    logs = query.all()
    total_requests = len(logs)
    total_tokens = sum(log.total_tokens for log in logs)
    total_cost = sum(float(log.estimated_cost or 0) for log in logs)

    by_module: dict[str, dict[str, float | int]] = {}
    by_provider: dict[str, dict[str, float | int]] = {}

    for log in logs:
        module_bucket = by_module.setdefault(
            log.module_name,
            {"requests": 0, "tokens": 0, "estimated_cost": 0.0},
        )
        module_bucket["requests"] = int(module_bucket["requests"]) + 1
        module_bucket["tokens"] = int(module_bucket["tokens"]) + log.total_tokens
        module_bucket["estimated_cost"] = float(module_bucket["estimated_cost"]) + float(
            log.estimated_cost or 0
        )

        provider_key = str(log.provider_id or "unknown")
        provider_bucket = by_provider.setdefault(
            provider_key,
            {"requests": 0, "tokens": 0, "estimated_cost": 0.0},
        )
        provider_bucket["requests"] = int(provider_bucket["requests"]) + 1
        provider_bucket["tokens"] = int(provider_bucket["tokens"]) + log.total_tokens
        provider_bucket["estimated_cost"] = float(provider_bucket["estimated_cost"]) + float(
            log.estimated_cost or 0
        )

    default_provider = (
        db.query(AiProvider)
        .filter(
            AiProvider.tenant_id == tenant_id,
            AiProvider.is_default.is_(True),
            AiProvider.is_active.is_(True),
        )
        .first()
    )
    monthly_budget = float(default_provider.monthly_budget) if default_provider else None
    budget_used_percent = None
    if monthly_budget and monthly_budget > 0:
        budget_used_percent = round(total_cost / monthly_budget * 100, 2)

    return AiUsageReport(
        total_requests=total_requests,
        total_tokens=total_tokens,
        total_estimated_cost=round(total_cost, 4),
        monthly_budget=monthly_budget,
        budget_used_percent=budget_used_percent,
        by_module=by_module,
        by_provider=by_provider,
    )


def list_automation_rules(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    module_name: str | None = None,
    brand_id: int | None = None,
) -> tuple[list[AiAutomationRuleRead], int]:
    query = db.query(AiAutomationRule).filter(AiAutomationRule.tenant_id == tenant_id)

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(AiAutomationRule.brand_id.is_(None), AiAutomationRule.brand_id == brand_id))

    if module_name is not None:
        query = query.filter(AiAutomationRule.module_name == module_name)

    query = query.order_by(AiAutomationRule.rule_name)
    rules, total = paginate_query(query, page, page_size)
    return [AiAutomationRuleRead.model_validate(rule) for rule in rules], total


def create_automation_rule(
    db: Session,
    tenant_id: int,
    data: AiAutomationRuleCreate,
    default_brand_id: int | None = None,
) -> AiAutomationRuleRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    if data.provider_id is not None:
        _get_provider(db, tenant_id, data.provider_id)
    if data.prompt_id is not None:
        _get_prompt(db, tenant_id, data.prompt_id)

    rule = AiAutomationRule(
        tenant_id=tenant_id,
        brand_id=brand_id,
        rule_name=data.rule_name,
        module_name=data.module_name,
        trigger_name=data.trigger_name,
        provider_id=data.provider_id,
        prompt_id=data.prompt_id,
        human_approval_required=data.human_approval_required,
        max_cost_per_run=data.max_cost_per_run,
        is_active=data.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return AiAutomationRuleRead.model_validate(rule)


def update_automation_rule(
    db: Session,
    tenant_id: int,
    rule_id: int,
    data: AiAutomationRuleUpdate,
) -> AiAutomationRuleRead:
    rule = _get_automation_rule(db, tenant_id, rule_id)
    updates = data.model_dump(exclude_unset=True)

    if updates.get("provider_id") is not None:
        _get_provider(db, tenant_id, updates["provider_id"])
    if updates.get("prompt_id") is not None:
        _get_prompt(db, tenant_id, updates["prompt_id"])

    for field, value in updates.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return AiAutomationRuleRead.model_validate(rule)


def list_usage_logs(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
) -> tuple[list[AiUsageLogRead], int]:
    query = (
        db.query(AiUsageLog)
        .filter(AiUsageLog.tenant_id == tenant_id)
        .order_by(AiUsageLog.created_at.desc(), AiUsageLog.id.desc())
    )
    logs, total = paginate_query(query, page, page_size)
    return [AiUsageLogRead.model_validate(log) for log in logs], total


def _create_usage_log(
    db: Session,
    *,
    tenant_id: int,
    brand_id: int | None,
    outlet_id: int | None,
    provider_id: int | None,
    user_id: int,
    module_name: str,
    request_type: str,
    model: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    estimated_cost: float,
    status: AiUsageStatus = AiUsageStatus.SUCCESS,
) -> AiUsageLog:
    log = AiUsageLog(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=outlet_id,
        provider_id=provider_id,
        module_name=module_name,
        request_type=request_type,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        status=status,
        created_by=user_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _to_mock_response(result: StubGenerateResult, usage_log_id: int) -> MockAiResponse:
    return MockAiResponse(
        content=result.content,
        provider_name=result.provider_name,
        model=result.model,
        confidence_score=result.confidence_score,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost=result.estimated_cost,
        usage_log_id=usage_log_id,
    )


def _resolve_provider(
    db: Session,
    tenant_id: int,
    provider_id: int | None,
    default_brand_id: int | None,
) -> AiProvider | None:
    if provider_id is not None:
        return _get_provider(db, tenant_id, provider_id)

    query = db.query(AiProvider).filter(
        AiProvider.tenant_id == tenant_id,
        AiProvider.is_default.is_(True),
        AiProvider.is_active.is_(True),
    )
    if default_brand_id is not None:
        provider = query.filter(AiProvider.brand_id == default_brand_id).first()
        if provider is not None:
            return provider

    return query.filter(AiProvider.brand_id.is_(None)).first()


def _prompt_to_read(prompt: AiPrompt) -> AiPromptRead:
    payload = AiPromptRead.model_validate(prompt)
    payload.variables = _parse_json_list(prompt.variables_json)
    return payload


def _clear_default_provider(
    db: Session,
    tenant_id: int,
    brand_id: int | None,
    exclude_id: int | None = None,
) -> None:
    query = db.query(AiProvider).filter(
        AiProvider.tenant_id == tenant_id,
        AiProvider.is_default.is_(True),
    )
    if brand_id is not None:
        query = query.filter(or_(AiProvider.brand_id.is_(None), AiProvider.brand_id == brand_id))
    if exclude_id is not None:
        query = query.filter(AiProvider.id != exclude_id)
    for provider in query.all():
        provider.is_default = False


from app.utils.encryption import encrypt_secret


def _encrypt_api_key_placeholder(api_key: str | None) -> str | None:
    return encrypt_secret(api_key)


def _api_key_last4(api_key: str | None) -> str | None:
    if not api_key or len(api_key) < 4:
        return None
    return api_key[-4:]


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return []


def _ai_provider_audit_snapshot(provider: AiProvider) -> dict:
    return {
        "provider_name": provider.provider_name.value,
        "status": provider.status.value,
        "default_model": provider.default_model,
        "max_tokens": provider.max_tokens,
        "temperature": float(provider.temperature),
        "monthly_budget": float(provider.monthly_budget),
        "usage_alert_percent": provider.usage_alert_percent,
        "is_default": provider.is_default,
        "api_key_last4": provider.api_key_last4,
    }


def _get_provider(db: Session, tenant_id: int, provider_id: int) -> AiProvider:
    provider = (
        db.query(AiProvider)
        .filter(AiProvider.id == provider_id, AiProvider.tenant_id == tenant_id)
        .first()
    )
    if provider is None:
        raise NotFoundError("AI provider not found")
    return provider


def _get_prompt(db: Session, tenant_id: int, prompt_id: int) -> AiPrompt:
    prompt = (
        db.query(AiPrompt)
        .filter(AiPrompt.id == prompt_id, AiPrompt.tenant_id == tenant_id)
        .first()
    )
    if prompt is None:
        raise NotFoundError("AI prompt not found")
    return prompt


def _get_automation_rule(db: Session, tenant_id: int, rule_id: int) -> AiAutomationRule:
    rule = (
        db.query(AiAutomationRule)
        .filter(AiAutomationRule.id == rule_id, AiAutomationRule.tenant_id == tenant_id)
        .first()
    )
    if rule is None:
        raise NotFoundError("AI automation rule not found")
    return rule


def _validate_brand(db: Session, tenant_id: int, brand_id: int | None) -> None:
    if brand_id is None:
        return
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.tenant_id == tenant_id).first()
    if brand is None:
        raise NotFoundError("Brand not found")


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet
