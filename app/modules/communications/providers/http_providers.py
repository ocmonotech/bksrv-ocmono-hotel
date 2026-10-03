from __future__ import annotations

import logging
import uuid

import httpx

from app.core.config import settings
from app.modules.communications.models import MessageChannel, MessageStatus, ProviderName
from app.modules.communications.providers.base import BaseCommunicationProvider, ProviderSendResult

logger = logging.getLogger(__name__)


def _is_stub(value: str) -> bool:
    return settings.enable_stub_external_services and value.startswith("stub")


class HttpWhatsAppProvider(BaseCommunicationProvider):
    provider_name = ProviderName.META_CLOUD_API
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
        config = config or {}
        base_url = config.get("api_base_url") or settings.whatsapp_api_base_url
        token = config.get("api_token") or settings.whatsapp_api_token

        if _is_stub(token) or _is_stub(base_url):
            return _fallback_result(MessageChannel.WHATSAPP, "WhatsApp provider not configured")

        phone_number_id = config.get("phone_number_id", sender)
        url = f"{base_url.rstrip('/')}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": receiver.lstrip("+"),
            "type": "text",
            "text": {"body": message_text},
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                message_id = data.get("messages", [{}])[0].get("id", uuid.uuid4().hex)
                return ProviderSendResult(
                    success=True,
                    provider_message_id=str(message_id),
                    status=MessageStatus.SENT,
                )
        except Exception as exc:
            logger.warning("WhatsApp send failed, falling back: %s", exc)
            return _fallback_result(MessageChannel.WHATSAPP, str(exc))


class HttpSmsProvider(BaseCommunicationProvider):
    provider_name = ProviderName.TWILIO
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
        config = config or {}
        base_url = config.get("api_base_url") or settings.sms_api_base_url
        api_key = config.get("api_key") or settings.sms_api_key
        sender_id = config.get("sender_id") or settings.sms_sender_id or sender

        if _is_stub(api_key) or _is_stub(base_url):
            return _fallback_result(MessageChannel.SMS, "SMS provider not configured")

        provider = config.get("provider") or settings.sms_provider.lower()
        headers = {"Content-Type": "application/json"}
        payload: dict

        if provider == "msg91":
            url = f"{base_url.rstrip('/')}/flow/"
            headers["authkey"] = api_key
            payload = {
                "template_id": config.get("template_id", ""),
                "short_url": "0",
                "recipients": [{"mobiles": receiver.lstrip("+"), "message": message_text}],
            }
            auth = None
        else:
            auth = None
            url = f"{base_url.rstrip('/')}/Messages.json"
            payload = {"To": receiver, "From": sender_id, "Body": message_text}
            if ":" in api_key:
                account_sid, auth_token = api_key.split(":", 1)
                url = f"{base_url.rstrip('/')}/2010-04-01/Accounts/{account_sid}/Messages.json"
                auth = (account_sid, auth_token)
            else:
                headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if provider == "msg91":
                    response = await client.post(url, json=payload, headers=headers)
                elif auth:
                    response = await client.post(url, data=payload, auth=auth)
                else:
                    response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                message_id = (
                    data.get("sid")
                    or data.get("message_id")
                    or data.get("request_id")
                    or uuid.uuid4().hex
                )
                return ProviderSendResult(
                    success=True,
                    provider_message_id=str(message_id),
                    status=MessageStatus.SENT,
                )
        except Exception as exc:
            logger.warning("SMS send failed, falling back: %s", exc)
            return _fallback_result(MessageChannel.SMS, str(exc))


class HttpEmailProvider(BaseCommunicationProvider):
    provider_name = ProviderName.SENDGRID
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
        config = config or {}
        base_url = config.get("api_base_url") or settings.email_api_base_url
        api_key = config.get("api_key") or settings.email_api_key
        from_address = config.get("from_address") or settings.email_from_address or sender

        if _is_stub(api_key) or _is_stub(base_url):
            return _fallback_result(MessageChannel.EMAIL, "Email provider not configured")

        provider = config.get("provider") or settings.email_provider.lower()
        headers = {"Content-Type": "application/json"}

        if provider == "smtp":
            return ProviderSendResult(
                success=False,
                provider_message_id=f"email_unconfigured_{uuid.uuid4().hex[:12]}",
                status=MessageStatus.FAILED,
                error_message="SMTP requires a dedicated mailer; configure sendgrid or mock",
            )

        url = f"{base_url.rstrip('/')}/v3/mail/send"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "personalizations": [{"to": [{"email": receiver}]}],
            "from": {"email": from_address},
            "subject": subject or "Notification",
            "content": [{"type": "text/plain", "value": message_text}],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                message_id = response.headers.get("X-Message-Id", uuid.uuid4().hex)
                return ProviderSendResult(
                    success=True,
                    provider_message_id=str(message_id),
                    status=MessageStatus.SENT,
                )
        except Exception as exc:
            logger.warning("Email send failed, falling back: %s", exc)
            return _fallback_result(MessageChannel.EMAIL, str(exc))


def _fallback_result(channel: MessageChannel, error: str) -> ProviderSendResult:
    prefix = {"whatsapp": "wa", "sms": "sms", "email": "email"}.get(channel.value, "msg")
    return ProviderSendResult(
        success=False,
        provider_message_id=f"{prefix}_fallback_{uuid.uuid4().hex[:12]}",
        status=MessageStatus.FAILED,
        error_message=error,
    )
