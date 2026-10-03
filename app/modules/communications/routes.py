from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.communications import service
from app.modules.communications.models import ConversationStatus, MessageChannel
from app.modules.communications.schemas import (
    ConversationRead,
    EmailSendRequest,
    MessageRead,
    MessageTemplateCreate,
    MessageTemplateRead,
    MessageTemplateUpdate,
    MockSendResponse,
    ProviderCreate,
    ProviderRead,
    ProviderTestResponse,
    ProviderUpdate,
    SmsSendRequest,
    WebhookAckResponse,
    WebhookInboundPayload,
    WhatsAppSendRequest,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/conversations", response_model=PaginatedSuccessResponse[ConversationRead])
def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: MessageChannel | None = Query(None),
    outlet_id: int | None = Query(None),
    status: ConversationStatus | None = Query(None),
    assigned_to: int | None = Query(None),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_READ)),
) -> PaginatedSuccessResponse[ConversationRead]:
    items, total = service.list_conversations(
        db,
        current_user.tenant_id,
        page,
        page_size,
        channel=channel,
        outlet_id=outlet_id,
        status=status,
        assigned_to=assigned_to,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_READ)),
) -> list[MessageRead]:
    return service.get_conversation_messages(db, current_user.tenant_id, conversation_id)


@router.post("/whatsapp/send", response_model=MockSendResponse, status_code=status.HTTP_201_CREATED)
async def send_mock_whatsapp(
    body: WhatsAppSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_WRITE)),
) -> MockSendResponse:
    return await service.send_mock_whatsapp(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/sms/send", response_model=MockSendResponse, status_code=status.HTTP_201_CREATED)
async def send_mock_sms(
    body: SmsSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_WRITE)),
) -> MockSendResponse:
    return await service.send_mock_sms(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/email/send", response_model=MockSendResponse, status_code=status.HTTP_201_CREATED)
async def send_mock_email(
    body: EmailSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_WRITE)),
) -> MockSendResponse:
    return await service.send_mock_email(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/whatsapp/webhook", response_model=WebhookAckResponse)
def whatsapp_webhook(
    body: WebhookInboundPayload,
    db: Session = Depends(get_db),
) -> WebhookAckResponse:
    return service.handle_whatsapp_webhook(db, body)


@router.post("/sms/webhook", response_model=WebhookAckResponse)
def sms_webhook(
    body: WebhookInboundPayload,
    db: Session = Depends(get_db),
) -> WebhookAckResponse:
    return service.handle_sms_webhook(db, body)


@router.post("/email/webhook", response_model=WebhookAckResponse)
def email_webhook(
    body: WebhookInboundPayload,
    db: Session = Depends(get_db),
) -> WebhookAckResponse:
    return service.handle_email_webhook(db, body)


@router.get("/templates", response_model=PaginatedSuccessResponse[MessageTemplateRead])
def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: MessageChannel | None = Query(None),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_READ)),
) -> PaginatedSuccessResponse[MessageTemplateRead]:
    items, total = service.list_templates(
        db,
        current_user.tenant_id,
        page,
        page_size,
        channel=channel,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/templates", response_model=MessageTemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    body: MessageTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_WRITE)),
) -> MessageTemplateRead:
    return service.create_template(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/templates/{template_id}", response_model=MessageTemplateRead)
def update_template(
    template_id: int,
    body: MessageTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_WRITE)),
) -> MessageTemplateRead:
    return service.update_template(db, current_user.tenant_id, template_id, body)


@router.get("/providers", response_model=PaginatedSuccessResponse[ProviderRead])
def list_providers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: MessageChannel | None = Query(None),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_READ)),
) -> PaginatedSuccessResponse[ProviderRead]:
    items, total = service.list_providers(
        db,
        current_user.tenant_id,
        page,
        page_size,
        channel=channel,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/providers", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
def create_provider(
    body: ProviderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_WRITE)),
) -> ProviderRead:
    return service.create_provider(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/providers/{provider_id}", response_model=ProviderRead)
def update_provider(
    provider_id: int,
    body: ProviderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_WRITE)),
) -> ProviderRead:
    return service.update_provider(
        db,
        current_user.tenant_id,
        provider_id,
        body,
        current_user.id,
    )


@router.post("/providers/{provider_id}/test", response_model=ProviderTestResponse)
async def test_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMMS_WRITE)),
) -> ProviderTestResponse:
    return await service.test_provider_connection(db, current_user.tenant_id, provider_id)
