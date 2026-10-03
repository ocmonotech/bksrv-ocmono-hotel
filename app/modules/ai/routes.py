from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.ai import service
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
from app.modules.users.models import User

router = APIRouter()


@router.get("/providers", response_model=list[AiProviderRead])
def list_providers(
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_READ)),
) -> list[AiProviderRead]:
    return service.list_providers(db, current_user.tenant_id, brand_id=brand_id)


@router.post("/providers", response_model=AiProviderRead, status_code=status.HTTP_201_CREATED)
def create_provider(
    body: AiProviderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiProviderRead:
    return service.create_provider(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/providers/{provider_id}", response_model=AiProviderRead)
def update_provider(
    provider_id: int,
    body: AiProviderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiProviderRead:
    return service.update_provider(
        db,
        current_user.tenant_id,
        provider_id,
        body,
        current_user.id,
    )


@router.post("/providers/{provider_id}/test", response_model=AiProviderTestResponse)
async def test_provider_mock(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiProviderTestResponse:
    return await service.test_provider_mock(db, current_user.tenant_id, provider_id)


@router.post("/providers/{provider_id}/set-default", response_model=AiProviderRead)
def set_default_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiProviderRead:
    return service.set_default_provider(db, current_user.tenant_id, provider_id)


@router.get("/prompts", response_model=PaginatedSuccessResponse[AiPromptRead])
def list_prompts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_READ)),
) -> PaginatedSuccessResponse[AiPromptRead]:
    items, total = service.list_prompts(
        db,
        current_user.tenant_id,
        page,
        page_size,
        category=category,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/prompts", response_model=AiPromptRead, status_code=status.HTTP_201_CREATED)
def create_prompt(
    body: AiPromptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiPromptRead:
    return service.create_prompt(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/prompts/{prompt_id}", response_model=AiPromptRead)
def update_prompt(
    prompt_id: int,
    body: AiPromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiPromptRead:
    return service.update_prompt(db, current_user.tenant_id, prompt_id, body)


@router.post("/mock-generate", response_model=MockAiResponse)
async def mock_generate(
    body: MockGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> MockAiResponse:
    return await service.mock_generate(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/draft-whatsapp-reply", response_model=MockAiResponse)
async def draft_whatsapp_reply(
    body: DraftWhatsAppReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> MockAiResponse:
    return await service.draft_whatsapp_reply(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/score-lead", response_model=MockAiResponse)
async def score_lead(
    body: ScoreLeadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> MockAiResponse:
    return await service.score_lead(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/generate-campaign-copy", response_model=MockAiResponse)
async def generate_campaign_copy(
    body: GenerateCampaignCopyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> MockAiResponse:
    return await service.generate_campaign_copy(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/usage-logs", response_model=AiUsageLogRead, status_code=status.HTTP_201_CREATED)
def create_usage_log(
    body: AiUsageLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiUsageLogRead:
    return service.create_usage_log(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/usage-logs", response_model=PaginatedSuccessResponse[AiUsageLogRead])
def list_usage_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_READ)),
) -> PaginatedSuccessResponse[AiUsageLogRead]:
    items, total = service.list_usage_logs(db, current_user.tenant_id, page, page_size)
    return success_paginated(items, total, page, page_size)


@router.get("/usage-report", response_model=AiUsageReport)
def get_usage_report(
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_READ)),
) -> AiUsageReport:
    return service.get_usage_report(db, current_user.tenant_id, brand_id=brand_id)


@router.get("/automation-rules", response_model=PaginatedSuccessResponse[AiAutomationRuleRead])
def list_automation_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module_name: str | None = Query(None),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_READ)),
) -> PaginatedSuccessResponse[AiAutomationRuleRead]:
    items, total = service.list_automation_rules(
        db,
        current_user.tenant_id,
        page,
        page_size,
        module_name=module_name,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/automation-rules", response_model=AiAutomationRuleRead, status_code=status.HTTP_201_CREATED)
def create_automation_rule(
    body: AiAutomationRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiAutomationRuleRead:
    return service.create_automation_rule(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/automation-rules/{rule_id}", response_model=AiAutomationRuleRead)
def update_automation_rule(
    rule_id: int,
    body: AiAutomationRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AI_WRITE)),
) -> AiAutomationRuleRead:
    return service.update_automation_rule(db, current_user.tenant_id, rule_id, body)
