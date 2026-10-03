from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.brands.models import Brand
from app.modules.campaigns.models import Campaign
from app.modules.communications.models import (
    CommunicationProvider,
    Conversation,
    ConversationStatus,
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    MessageTemplate,
    MessageType,
    ProviderName,
    ProviderStatus,
    TemplateStatus,
)
from app.modules.communications.providers.registry import get_provider_adapter
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
from app.modules.customers.models import Customer
from app.modules.leads.models import Lead
from app.modules.outlets.models import Outlet
from app.modules.users.models import User

DEFAULT_SENDERS = {
    MessageChannel.WHATSAPP: "mock-whatsapp-sender",
    MessageChannel.SMS: "MOCKSMS",
    MessageChannel.EMAIL: "noreply@mock.local",
}

_CHANNEL_SETTING_GROUP = {
    MessageChannel.WHATSAPP: "whatsapp",
    MessageChannel.SMS: "sms",
    MessageChannel.EMAIL: "email",
}


def is_channel_enabled(
    db: Session,
    tenant_id: int,
    channel: MessageChannel,
    *,
    brand_id: int | None,
    outlet_id: int | None = None,
) -> bool:
    from app.modules.settings.service import get_communication_settings

    group = _CHANNEL_SETTING_GROUP[channel]
    comm_settings = get_communication_settings(
        db,
        tenant_id,
        brand_id=brand_id,
        outlet_id=outlet_id,
    )
    channel_settings = getattr(comm_settings, group)
    return bool(channel_settings.get("enabled", True))


def list_conversations(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    channel: MessageChannel | None = None,
    outlet_id: int | None = None,
    status: ConversationStatus | None = None,
    assigned_to: int | None = None,
    brand_id: int | None = None,
) -> tuple[list[ConversationRead], int]:
    query = db.query(Conversation).filter(Conversation.tenant_id == tenant_id)

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(Conversation.brand_id.is_(None), Conversation.brand_id == brand_id))

    if channel is not None:
        query = query.filter(Conversation.channel == channel)

    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(Conversation.outlet_id == outlet_id)

    if status is not None:
        query = query.filter(Conversation.status == status)

    if assigned_to is not None:
        _get_user(db, tenant_id, assigned_to)
        query = query.filter(Conversation.assigned_to == assigned_to)

    query = query.order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
    conversations, total = paginate_query(query, page, page_size)
    return [ConversationRead.model_validate(item) for item in conversations], total


def get_conversation_messages(
    db: Session,
    tenant_id: int,
    conversation_id: int,
) -> list[MessageRead]:
    _get_conversation(db, tenant_id, conversation_id)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.tenant_id == tenant_id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    return [MessageRead.model_validate(message) for message in messages]


async def send_mock_whatsapp(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: WhatsAppSendRequest,
    default_brand_id: int | None = None,
) -> MockSendResponse:
    return await _send_mock_message(
        db,
        tenant_id,
        user_id,
        MessageChannel.WHATSAPP,
        data,
        default_brand_id=default_brand_id,
    )


async def send_mock_sms(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: SmsSendRequest,
    default_brand_id: int | None = None,
) -> MockSendResponse:
    return await _send_mock_message(
        db,
        tenant_id,
        user_id,
        MessageChannel.SMS,
        data,
        default_brand_id=default_brand_id,
    )


async def send_mock_email(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: EmailSendRequest,
    default_brand_id: int | None = None,
) -> MockSendResponse:
    message_text = f"Subject: {data.subject}\n\n{data.message_text}"
    return await _send_mock_message(
        db,
        tenant_id,
        user_id,
        MessageChannel.EMAIL,
        data,
        default_brand_id=default_brand_id,
        message_text=message_text,
    )


async def _send_mock_message(
    db: Session,
    tenant_id: int,
    user_id: int,
    channel: MessageChannel,
    data: WhatsAppSendRequest | SmsSendRequest | EmailSendRequest,
    default_brand_id: int | None = None,
    message_text: str | None = None,
) -> MockSendResponse:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    if data.outlet_id is not None:
        _get_outlet(db, tenant_id, data.outlet_id)
    if data.customer_id is not None:
        _get_customer(db, tenant_id, data.customer_id)
    if data.lead_id is not None:
        _get_lead(db, tenant_id, data.lead_id)

    body = message_text or data.message_text
    if data.template_id is not None:
        template = _get_template(db, tenant_id, data.template_id)
        body = template.body

    adapter, config, sender, is_mock = _resolve_send_context(
        db,
        tenant_id,
        channel,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        requested_sender=data.sender,
    )

    subject = getattr(data, "subject", None)
    result = await adapter.send(
        sender=sender,
        receiver=data.receiver,
        message_text=body,
        subject=subject,
        config=config,
    )

    conversation = _resolve_conversation(
        db,
        tenant_id=tenant_id,
        brand_id=brand_id,
        channel=channel,
        data=data,
    )

    message = Message(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id or conversation.outlet_id,
        conversation_id=conversation.id,
        channel=channel,
        direction=MessageDirection.OUTBOUND,
        sender=sender,
        receiver=data.receiver,
        message_text=body,
        message_type=data.message_type,
        provider_message_id=result.provider_message_id,
        status=result.status if result.success else MessageStatus.FAILED,
        error_message=result.error_message,
        sent_by=user_id,
    )
    db.add(message)

    conversation.last_message = body[:500]
    conversation.last_message_at = datetime.utcnow()
    conversation.status = ConversationStatus.OPEN
    if data.customer_id is not None:
        conversation.customer_id = data.customer_id
    if data.lead_id is not None:
        conversation.lead_id = data.lead_id

    db.commit()
    db.refresh(message)

    return MockSendResponse(
        success=result.success,
        message=MessageRead.model_validate(message),
        provider_message_id=result.provider_message_id,
        mock=is_mock,
    )


def list_templates(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    channel: MessageChannel | None = None,
    brand_id: int | None = None,
) -> tuple[list[MessageTemplateRead], int]:
    query = db.query(MessageTemplate).filter(
        MessageTemplate.tenant_id == tenant_id,
        MessageTemplate.is_active.is_(True),
    )

    if channel is not None:
        query = query.filter(MessageTemplate.channel == channel)

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(MessageTemplate.brand_id.is_(None), MessageTemplate.brand_id == brand_id))

    query = query.order_by(MessageTemplate.template_name)
    templates, total = paginate_query(query, page, page_size)
    return [_template_to_read(template) for template in templates], total


def create_template(
    db: Session,
    tenant_id: int,
    data: MessageTemplateCreate,
    default_brand_id: int | None = None,
) -> MessageTemplateRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    template = MessageTemplate(
        tenant_id=tenant_id,
        brand_id=brand_id,
        channel=data.channel,
        template_name=data.template_name,
        category=data.category,
        language=data.language,
        body=data.body,
        variables_json=json.dumps(data.variables),
        provider_template_id=data.provider_template_id,
        status=data.status,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_to_read(template)


def update_template(
    db: Session,
    tenant_id: int,
    template_id: int,
    data: MessageTemplateUpdate,
) -> MessageTemplateRead:
    template = _get_template(db, tenant_id, template_id)
    updates = data.model_dump(exclude_unset=True)

    if "variables" in updates:
        template.variables_json = json.dumps(updates.pop("variables"))

    for field, value in updates.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)
    return _template_to_read(template)


def list_providers(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    channel: MessageChannel | None = None,
    brand_id: int | None = None,
) -> tuple[list[ProviderRead], int]:
    query = db.query(CommunicationProvider).filter(
        CommunicationProvider.tenant_id == tenant_id,
        CommunicationProvider.is_active.is_(True),
    )

    if channel is not None:
        query = query.filter(CommunicationProvider.channel == channel)

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(
            or_(CommunicationProvider.brand_id.is_(None), CommunicationProvider.brand_id == brand_id)
        )

    query = query.order_by(CommunicationProvider.channel, CommunicationProvider.provider_name)
    providers, total = paginate_query(query, page, page_size)
    return [_provider_to_read(provider) for provider in providers], total


def create_provider(
    db: Session,
    tenant_id: int,
    data: ProviderCreate,
    default_brand_id: int | None = None,
) -> ProviderRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    if data.is_default:
        _clear_default_provider(db, tenant_id, data.channel, brand_id)

    provider = CommunicationProvider(
        tenant_id=tenant_id,
        brand_id=brand_id,
        channel=data.channel,
        provider_name=data.provider_name,
        status=data.status,
        config_json=json.dumps(data.config),
        encrypted_api_key=_encrypt_api_key_placeholder(data.api_key),
        api_key_last4=_api_key_last4(data.api_key),
        is_default=data.is_default,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return _provider_to_read(provider)


def update_provider(
    db: Session,
    tenant_id: int,
    provider_id: int,
    data: ProviderUpdate,
    user_id: int | None = None,
) -> ProviderRead:
    provider = _get_provider(db, tenant_id, provider_id)
    old_data = _comms_provider_audit_snapshot(provider)
    updates = data.model_dump(exclude_unset=True)

    if updates.get("is_default"):
        _clear_default_provider(db, tenant_id, provider.channel, provider.brand_id, exclude_id=provider.id)

    if "config" in updates:
        provider.config_json = json.dumps(updates.pop("config"))

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
        action=AuditAction.COMMS_PROVIDER_UPDATED.value,
        module_name="communications",
        record_type="communication_provider",
        record_id=provider.id,
        old_data=old_data,
        new_data=_comms_provider_audit_snapshot(provider),
    )

    db.commit()
    db.refresh(provider)
    return _provider_to_read(provider)


async def test_provider_connection(
    db: Session,
    tenant_id: int,
    provider_id: int,
) -> ProviderTestResponse:
    import httpx

    from app.core.config import settings as app_settings

    provider = _get_provider(db, tenant_id, provider_id)
    if provider.provider_name == ProviderName.MOCK:
        return ProviderTestResponse(success=True, message="Mock provider is ready", mock=True)

    channel_settings = _load_channel_settings(
        db,
        tenant_id,
        provider.channel,
        brand_id=provider.brand_id,
        outlet_id=None,
    )
    config = _build_provider_config(provider, channel_settings, provider.channel)
    token_or_key = config.get("api_token") or config.get("api_key") or ""
    base_url = config.get("api_base_url") or ""

    if _is_stub_value(token_or_key) or _is_stub_value(base_url):
        return ProviderTestResponse(
            success=False,
            message="Provider credentials are not configured",
            mock=False,
        )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            if provider.channel == MessageChannel.WHATSAPP:
                phone_number_id = config.get("phone_number_id") or channel_settings.get("sender_id")
                if not phone_number_id:
                    return ProviderTestResponse(
                        success=False,
                        message="WhatsApp phone number ID is required",
                        mock=False,
                    )
                url = f"{base_url.rstrip('/')}/{phone_number_id}"
                response = await client.get(
                    url,
                    params={"fields": "display_phone_number"},
                    headers={"Authorization": f"Bearer {token_or_key}"},
                )
            elif provider.channel == MessageChannel.SMS:
                sms_provider = (config.get("provider") or app_settings.sms_provider).lower()
                if sms_provider == "msg91":
                    response = await client.get(
                        "https://control.msg91.com/api/v5/account/details",
                        headers={"authkey": token_or_key},
                    )
                elif ":" in token_or_key:
                    account_sid, auth_token = token_or_key.split(":", 1)
                    url = f"{base_url.rstrip('/')}/2010-04-01/Accounts/{account_sid}.json"
                    response = await client.get(url, auth=(account_sid, auth_token))
                else:
                    return ProviderTestResponse(
                        success=False,
                        message="Twilio credentials must be account_sid:auth_token",
                        mock=False,
                    )
            else:
                url = f"{base_url.rstrip('/')}/v3/user/profile"
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token_or_key}"},
                )

            response.raise_for_status()
    except Exception as exc:
        provider.status = ProviderStatus.ERROR
        db.commit()
        return ProviderTestResponse(success=False, message=str(exc), mock=False)

    provider.status = ProviderStatus.ACTIVE
    db.commit()
    return ProviderTestResponse(success=True, message="Provider connection verified", mock=False)


def _resolve_send_context(
    db: Session,
    tenant_id: int,
    channel: MessageChannel,
    *,
    brand_id: int | None,
    outlet_id: int | None,
    requested_sender: str | None,
) -> tuple[object, dict, str, bool]:
    channel_settings = _load_channel_settings(
        db,
        tenant_id,
        channel,
        brand_id=brand_id,
        outlet_id=outlet_id,
    )
    if not channel_settings.get("enabled", True):
        raise ConflictError(f"{channel.value} channel is disabled for this brand/outlet")

    provider_record = _get_default_provider(db, tenant_id, channel, brand_id)
    provider_name = provider_record.provider_name if provider_record else ProviderName.MOCK
    adapter = get_provider_adapter(channel, provider_name)
    config = _build_provider_config(provider_record, channel_settings, channel)
    sender = requested_sender or _resolve_sender(channel, channel_settings, config)
    is_mock = provider_name == ProviderName.MOCK
    return adapter, config, sender, is_mock


def _load_channel_settings(
    db: Session,
    tenant_id: int,
    channel: MessageChannel,
    *,
    brand_id: int | None,
    outlet_id: int | None,
) -> dict:
    from app.modules.settings.service import get_communication_settings

    group = _CHANNEL_SETTING_GROUP[channel]
    comm_settings = get_communication_settings(
        db,
        tenant_id,
        brand_id=brand_id,
        outlet_id=outlet_id,
    )
    return getattr(comm_settings, group)


def _build_provider_config(
    provider_record: CommunicationProvider | None,
    channel_settings: dict,
    channel: MessageChannel,
) -> dict:
    from app.core.config import settings as app_settings
    from app.utils.encryption import decrypt_secret

    config = _parse_json(provider_record.config_json) if provider_record else {}

    if provider_record and provider_record.encrypted_api_key:
        api_key = decrypt_secret(provider_record.encrypted_api_key)
        if channel == MessageChannel.WHATSAPP:
            config["api_token"] = api_key or config.get("api_token")
        else:
            config["api_key"] = api_key or config.get("api_key")

    if channel == MessageChannel.WHATSAPP:
        config.setdefault("api_base_url", app_settings.whatsapp_api_base_url)
        if channel_settings.get("sender_id"):
            config["phone_number_id"] = channel_settings["sender_id"]
        if channel_settings.get("provider") and channel_settings["provider"] != "mock":
            config["provider"] = channel_settings["provider"]
    elif channel == MessageChannel.SMS:
        config.setdefault("api_base_url", app_settings.sms_api_base_url)
        if channel_settings.get("sender_id"):
            config["sender_id"] = channel_settings["sender_id"]
        config["provider"] = channel_settings.get("provider") or app_settings.sms_provider
    elif channel == MessageChannel.EMAIL:
        config.setdefault("api_base_url", app_settings.email_api_base_url)
        if channel_settings.get("from_email"):
            config["from_address"] = channel_settings["from_email"]
        config["provider"] = channel_settings.get("provider") or app_settings.email_provider

    return config


def _resolve_sender(channel: MessageChannel, channel_settings: dict, config: dict) -> str:
    if channel == MessageChannel.WHATSAPP:
        return (
            channel_settings.get("sender_id")
            or config.get("phone_number_id")
            or DEFAULT_SENDERS[channel]
        )
    if channel == MessageChannel.SMS:
        return channel_settings.get("sender_id") or config.get("sender_id") or DEFAULT_SENDERS[channel]
    return channel_settings.get("from_email") or config.get("from_address") or DEFAULT_SENDERS[channel]


def _is_stub_value(value: str) -> bool:
    from app.core.config import settings as app_settings

    return app_settings.enable_stub_external_services and value.startswith("stub")


def handle_whatsapp_webhook(
    db: Session,
    payload: WebhookInboundPayload,
) -> WebhookAckResponse:
    return _handle_inbound_webhook(db, MessageChannel.WHATSAPP, payload)


def handle_sms_webhook(
    db: Session,
    payload: WebhookInboundPayload,
) -> WebhookAckResponse:
    return _handle_inbound_webhook(db, MessageChannel.SMS, payload)


def handle_email_webhook(
    db: Session,
    payload: WebhookInboundPayload,
) -> WebhookAckResponse:
    return _handle_event_webhook(db, MessageChannel.EMAIL, payload)


def _normalize_webhook_payload(payload: WebhookInboundPayload) -> WebhookInboundPayload:
    raw = payload.raw or {}
    tenant_id = payload.tenant_id or raw.get("tenant_id")
    sender = payload.sender or raw.get("from") or raw.get("sender") or raw.get("mobile")
    message_text = (
        payload.message_text
        or raw.get("message_text")
        or raw.get("text")
        or raw.get("body")
        or raw.get("message")
    )
    provider_message_id = payload.provider_message_id or raw.get("provider_message_id") or raw.get("id")
    return WebhookInboundPayload(
        tenant_id=int(tenant_id) if tenant_id is not None else None,
        outlet_id=payload.outlet_id or raw.get("outlet_id"),
        customer_id=payload.customer_id or raw.get("customer_id"),
        lead_id=payload.lead_id or raw.get("lead_id"),
        conversation_id=payload.conversation_id or raw.get("conversation_id"),
        sender=str(sender) if sender is not None else None,
        receiver=payload.receiver or raw.get("receiver") or raw.get("to"),
        message_text=str(message_text) if message_text is not None else None,
        provider_message_id=str(provider_message_id) if provider_message_id is not None else None,
        external_thread_id=payload.external_thread_id or raw.get("external_thread_id"),
        event_type=payload.event_type or raw.get("event_type") or raw.get("event"),
        raw=raw,
    )


def _handle_inbound_webhook(
    db: Session,
    channel: MessageChannel,
    payload: WebhookInboundPayload,
) -> WebhookAckResponse:
    normalized = _normalize_webhook_payload(payload)
    if normalized.tenant_id is None or not normalized.message_text or not normalized.sender:
        return WebhookAckResponse(
            success=True,
            message=f"{channel.value} webhook accepted — missing tenant_id, sender, or message",
            processed=False,
        )

    conversation = _resolve_webhook_conversation(db, channel, normalized)
    message = Message(
        tenant_id=normalized.tenant_id,
        brand_id=conversation.brand_id,
        outlet_id=normalized.outlet_id or conversation.outlet_id,
        conversation_id=conversation.id,
        channel=channel,
        direction=MessageDirection.INBOUND,
        sender=normalized.sender,
        receiver=normalized.receiver or DEFAULT_SENDERS[channel],
        message_text=normalized.message_text,
        message_type=MessageType.TEXT,
        provider_message_id=normalized.provider_message_id,
        status=MessageStatus.RECEIVED,
    )
    db.add(message)

    conversation.last_message = normalized.message_text[:500]
    conversation.last_message_at = datetime.utcnow()
    conversation.unread_count = (conversation.unread_count or 0) + 1
    conversation.status = ConversationStatus.OPEN
    if normalized.external_thread_id:
        conversation.external_thread_id = normalized.external_thread_id

    db.commit()

    return WebhookAckResponse(
        success=True,
        message=f"{channel.value} inbound webhook processed",
        processed=True,
    )


def _handle_event_webhook(
    db: Session,
    channel: MessageChannel,
    payload: WebhookInboundPayload,
) -> WebhookAckResponse:
    if payload.tenant_id and payload.provider_message_id:
        message = (
            db.query(Message)
            .filter(
                Message.tenant_id == payload.tenant_id,
                Message.provider_message_id == payload.provider_message_id,
            )
            .first()
        )
        if message is not None:
            event = (payload.event_type or "").lower()
            if event in {"delivered", "delivery"}:
                message.status = MessageStatus.DELIVERED
            elif event in {"read", "opened"}:
                message.status = MessageStatus.READ
            elif event in {"failed", "bounce"}:
                message.status = MessageStatus.FAILED
                message.error_message = payload.message_text or "Email delivery failed (mock)"
            db.commit()
            return WebhookAckResponse(
                success=True,
                message="Email event webhook processed",
                processed=True,
            )

    return WebhookAckResponse(
        success=True,
        message="Email events webhook accepted — no matching message found",
        processed=False,
    )


def _resolve_conversation(
    db: Session,
    tenant_id: int,
    brand_id: int | None,
    channel: MessageChannel,
    data: WhatsAppSendRequest | SmsSendRequest | EmailSendRequest,
) -> Conversation:
    if data.conversation_id is not None:
        conversation = _get_conversation(db, tenant_id, data.conversation_id)
        if conversation.channel != channel:
            raise NotFoundError("Conversation channel mismatch")
        return conversation

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.tenant_id == tenant_id,
            Conversation.channel == channel,
            Conversation.customer_id == data.customer_id,
            Conversation.lead_id == data.lead_id,
            Conversation.status != ConversationStatus.CLOSED,
        )
        .order_by(Conversation.id.desc())
        .first()
    )
    if conversation is not None:
        return conversation

    conversation = Conversation(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        customer_id=data.customer_id,
        lead_id=data.lead_id,
        channel=channel,
        status=ConversationStatus.OPEN,
        unread_count=0,
    )
    db.add(conversation)
    db.flush()
    return conversation


def _resolve_webhook_conversation(
    db: Session,
    channel: MessageChannel,
    payload: WebhookInboundPayload,
) -> Conversation:
    if payload.conversation_id is not None:
        return _get_conversation(db, payload.tenant_id, payload.conversation_id)

    if payload.external_thread_id:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.tenant_id == payload.tenant_id,
                Conversation.external_thread_id == payload.external_thread_id,
            )
            .first()
        )
        if conversation is not None:
            return conversation

    conversation = Conversation(
        tenant_id=payload.tenant_id,
        outlet_id=payload.outlet_id,
        customer_id=payload.customer_id,
        lead_id=payload.lead_id,
        channel=channel,
        external_thread_id=payload.external_thread_id,
        status=ConversationStatus.OPEN,
        unread_count=0,
    )
    db.add(conversation)
    db.flush()
    return conversation


def _get_default_provider(
    db: Session,
    tenant_id: int,
    channel: MessageChannel,
    brand_id: int | None,
) -> CommunicationProvider | None:
    query = db.query(CommunicationProvider).filter(
        CommunicationProvider.tenant_id == tenant_id,
        CommunicationProvider.channel == channel,
        CommunicationProvider.is_default.is_(True),
        CommunicationProvider.status == ProviderStatus.ACTIVE,
        CommunicationProvider.is_active.is_(True),
    )
    if brand_id is not None:
        provider = query.filter(CommunicationProvider.brand_id == brand_id).first()
        if provider is not None:
            return provider
    return query.filter(CommunicationProvider.brand_id.is_(None)).first()


def _clear_default_provider(
    db: Session,
    tenant_id: int,
    channel: MessageChannel,
    brand_id: int | None,
    exclude_id: int | None = None,
) -> None:
    query = db.query(CommunicationProvider).filter(
        CommunicationProvider.tenant_id == tenant_id,
        CommunicationProvider.channel == channel,
        CommunicationProvider.is_default.is_(True),
    )
    if brand_id is not None:
        query = query.filter(
            or_(CommunicationProvider.brand_id.is_(None), CommunicationProvider.brand_id == brand_id)
        )
    if exclude_id is not None:
        query = query.filter(CommunicationProvider.id != exclude_id)
    for provider in query.all():
        provider.is_default = False


def _template_to_read(template: MessageTemplate) -> MessageTemplateRead:
    payload = MessageTemplateRead.model_validate(template)
    payload.variables = _parse_json_list(template.variables_json)
    return payload


def _comms_provider_audit_snapshot(provider: CommunicationProvider) -> dict:
    return {
        "channel": provider.channel.value,
        "provider_name": provider.provider_name.value,
        "status": provider.status.value,
        "is_default": provider.is_default,
        "api_key_last4": provider.api_key_last4,
        "config": _parse_json(provider.config_json),
    }


def _provider_to_read(provider: CommunicationProvider) -> ProviderRead:
    payload = ProviderRead.model_validate(provider)
    payload.config = _parse_json(provider.config_json)
    return payload


from app.utils.encryption import encrypt_secret


def _encrypt_api_key_placeholder(api_key: str | None) -> str | None:
    return encrypt_secret(api_key)


def _api_key_last4(api_key: str | None) -> str | None:
    if not api_key or len(api_key) < 4:
        return None
    return api_key[-4:]


def _parse_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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


def _get_conversation(db: Session, tenant_id: int, conversation_id: int) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        .first()
    )
    if conversation is None:
        raise NotFoundError("Conversation not found")
    return conversation


def _get_template(db: Session, tenant_id: int, template_id: int) -> MessageTemplate:
    template = (
        db.query(MessageTemplate)
        .filter(MessageTemplate.id == template_id, MessageTemplate.tenant_id == tenant_id)
        .first()
    )
    if template is None:
        raise NotFoundError("Message template not found")
    return template


def _get_provider(db: Session, tenant_id: int, provider_id: int) -> CommunicationProvider:
    provider = (
        db.query(CommunicationProvider)
        .filter(CommunicationProvider.id == provider_id, CommunicationProvider.tenant_id == tenant_id)
        .first()
    )
    if provider is None:
        raise NotFoundError("Communication provider not found")
    return provider


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


def _get_customer(db: Session, tenant_id: int, customer_id: int) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        .first()
    )
    if customer is None:
        raise NotFoundError("Customer not found")
    return customer


def _get_lead(db: Session, tenant_id: int, lead_id: int) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant_id).first()
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead


def _get_user(db: Session, tenant_id: int, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if user is None:
        raise NotFoundError("User not found")
    return user
