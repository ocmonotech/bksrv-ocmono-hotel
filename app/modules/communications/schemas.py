from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.communications.models import (
    ConversationStatus,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    MessageType,
    ProviderName,
    ProviderStatus,
    TemplateStatus,
)


class ConversationRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int | None
    customer_id: int | None
    lead_id: int | None
    channel: MessageChannel
    external_thread_id: str | None
    status: ConversationStatus
    assigned_to: int | None
    last_message: str | None
    last_message_at: datetime | None
    unread_count: int
    source_campaign_id: int | None
    is_active: bool


class MessageRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int | None
    conversation_id: int
    channel: MessageChannel
    direction: MessageDirection
    sender: str
    receiver: str
    message_text: str
    message_type: MessageType
    provider_message_id: str | None
    status: MessageStatus
    error_message: str | None
    sent_by: int | None


class WhatsAppSendRequest(BaseModel):
    receiver: str = Field(min_length=5, max_length=32)
    message_text: str = Field(min_length=1)
    sender: str | None = None
    outlet_id: int | None = None
    customer_id: int | None = None
    lead_id: int | None = None
    conversation_id: int | None = None
    template_id: int | None = None
    message_type: MessageType = MessageType.TEXT
    brand_id: int | None = None


class SmsSendRequest(BaseModel):
    receiver: str = Field(min_length=5, max_length=32)
    message_text: str = Field(min_length=1)
    sender: str | None = None
    outlet_id: int | None = None
    customer_id: int | None = None
    lead_id: int | None = None
    conversation_id: int | None = None
    template_id: int | None = None
    message_type: MessageType = MessageType.TEXT
    brand_id: int | None = None


class EmailSendRequest(BaseModel):
    receiver: str = Field(min_length=3, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    message_text: str = Field(min_length=1)
    sender: str | None = None
    outlet_id: int | None = None
    customer_id: int | None = None
    lead_id: int | None = None
    conversation_id: int | None = None
    template_id: int | None = None
    message_type: MessageType = MessageType.TEXT
    brand_id: int | None = None


class MockSendResponse(BaseModel):
    success: bool
    message: MessageRead
    provider_message_id: str
    mock: bool = True


class MessageTemplateCreate(BaseModel):
    template_name: str = Field(min_length=1, max_length=255)
    channel: MessageChannel
    category: str = "Promotions"
    language: str = "English"
    body: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    provider_template_id: str | None = None
    status: TemplateStatus = TemplateStatus.DRAFT
    brand_id: int | None = None


class MessageTemplateUpdate(BaseModel):
    template_name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = None
    language: str | None = None
    body: str | None = Field(default=None, min_length=1)
    variables: list[str] | None = None
    provider_template_id: str | None = None
    status: TemplateStatus | None = None


class MessageTemplateRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    channel: MessageChannel
    template_name: str
    category: str
    language: str
    body: str
    variables: list[str] = []
    provider_template_id: str | None
    status: TemplateStatus
    is_active: bool


class ProviderCreate(BaseModel):
    channel: MessageChannel
    provider_name: ProviderName = ProviderName.MOCK
    status: ProviderStatus = ProviderStatus.ACTIVE
    config: dict = Field(default_factory=dict)
    api_key: str | None = None
    is_default: bool = False
    brand_id: int | None = None


class ProviderUpdate(BaseModel):
    provider_name: ProviderName | None = None
    status: ProviderStatus | None = None
    config: dict | None = None
    api_key: str | None = None
    is_default: bool | None = None


class ProviderRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    channel: MessageChannel
    provider_name: ProviderName
    status: ProviderStatus
    config: dict = {}
    api_key_last4: str | None
    is_default: bool
    is_active: bool


class ProviderTestResponse(BaseModel):
    success: bool
    message: str
    mock: bool = False


class WebhookAckResponse(BaseModel):
    success: bool
    message: str
    processed: bool = False
    mock: bool = True


class WebhookInboundPayload(BaseModel):
    tenant_id: int | None = None
    outlet_id: int | None = None
    customer_id: int | None = None
    lead_id: int | None = None
    conversation_id: int | None = None
    sender: str | None = None
    receiver: str | None = None
    message_text: str | None = None
    provider_message_id: str | None = None
    external_thread_id: str | None = None
    event_type: str | None = None
    raw: dict = Field(default_factory=dict)
