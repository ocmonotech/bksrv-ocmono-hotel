from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class MessageChannel(str, enum.Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"


class ProviderName(str, enum.Enum):
    META_CLOUD_API = "meta_cloud_api"
    TWILIO = "twilio"
    MSG91 = "msg91"
    SENDGRID = "sendgrid"
    AMAZON_SES = "amazon_ses"
    SMTP = "smtp"
    CUSTOM = "custom"
    MOCK = "mock"


class ProviderStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class ConversationStatus(str, enum.Enum):
    OPEN = "open"
    PENDING = "pending"
    CLOSED = "closed"


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(str, enum.Enum):
    TEXT = "text"
    TEMPLATE = "template"
    MEDIA = "media"
    SYSTEM = "system"


class MessageStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    RECEIVED = "received"


class TemplateStatus(str, enum.Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"
    DRAFT = "draft"


class CommunicationProvider(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "communication_providers"

    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel), nullable=False)
    provider_name: Mapped[ProviderName] = mapped_column(Enum(ProviderName), nullable=False)
    status: Mapped[ProviderStatus] = mapped_column(
        Enum(ProviderStatus), default=ProviderStatus.PENDING
    )
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_key_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class Conversation(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "conversations"

    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leads.id"), nullable=True)
    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel), nullable=False)
    external_thread_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus), default=ConversationStatus.OPEN
    )
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    source_campaign_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaigns.id"), nullable=True
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "messages"

    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel), nullable=False)
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection), nullable=False)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    receiver: Mapped[str] = mapped_column(String(255), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType), default=MessageType.TEXT)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.QUEUED)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class MessageTemplate(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "message_templates"

    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel), nullable=False)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="Promotions")
    language: Mapped[str] = mapped_column(String(64), default="English")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[str] = mapped_column(Text, default="[]")
    provider_template_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[TemplateStatus] = mapped_column(Enum(TemplateStatus), default=TemplateStatus.DRAFT)
