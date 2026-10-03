from __future__ import annotations

import uuid

from app.modules.communications.models import MessageChannel, MessageStatus, ProviderName
from app.modules.communications.providers.base import BaseCommunicationProvider, ProviderSendResult


class MockWhatsAppProvider(BaseCommunicationProvider):
    provider_name = ProviderName.MOCK
    channel = MessageChannel.WHATSAPP

    async def send(
        self,
        *,
        sender: str,
        receiver: str,
        message_text: str,
        subject: str | None = None,
        config: dict | None = None,
    ) -> ProviderSendResult:
        return ProviderSendResult(
            success=True,
            provider_message_id=f"wa_mock_{uuid.uuid4().hex[:16]}",
            status=MessageStatus.SENT,
        )


class MockSmsProvider(BaseCommunicationProvider):
    provider_name = ProviderName.MOCK
    channel = MessageChannel.SMS

    async def send(
        self,
        *,
        sender: str,
        receiver: str,
        message_text: str,
        subject: str | None = None,
        config: dict | None = None,
    ) -> ProviderSendResult:
        return ProviderSendResult(
            success=True,
            provider_message_id=f"sms_mock_{uuid.uuid4().hex[:16]}",
            status=MessageStatus.SENT,
        )


class MockEmailProvider(BaseCommunicationProvider):
    provider_name = ProviderName.MOCK
    channel = MessageChannel.EMAIL

    async def send(
        self,
        *,
        sender: str,
        receiver: str,
        message_text: str,
        subject: str | None = None,
        config: dict | None = None,
    ) -> ProviderSendResult:
        return ProviderSendResult(
            success=True,
            provider_message_id=f"email_mock_{uuid.uuid4().hex[:16]}",
            status=MessageStatus.SENT,
        )
