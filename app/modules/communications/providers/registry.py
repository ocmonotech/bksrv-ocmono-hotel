from __future__ import annotations

from app.core.config import settings
from app.modules.communications.models import MessageChannel, ProviderName
from app.modules.communications.providers.base import BaseCommunicationProvider
from app.modules.communications.providers.http_providers import (
    HttpEmailProvider,
    HttpSmsProvider,
    HttpWhatsAppProvider,
)
from app.modules.communications.providers.mock import (
    MockEmailProvider,
    MockSmsProvider,
    MockWhatsAppProvider,
)

_MOCK_ADAPTERS: dict[MessageChannel, BaseCommunicationProvider] = {
    MessageChannel.WHATSAPP: MockWhatsAppProvider(),
    MessageChannel.SMS: MockSmsProvider(),
    MessageChannel.EMAIL: MockEmailProvider(),
}

_HTTP_WHATSAPP = HttpWhatsAppProvider()
_HTTP_SMS = HttpSmsProvider()
_HTTP_EMAIL = HttpEmailProvider()

_WHATSAPP_HTTP_PROVIDERS = {ProviderName.META_CLOUD_API, ProviderName.TWILIO, ProviderName.CUSTOM}
_SMS_HTTP_PROVIDERS = {ProviderName.TWILIO, ProviderName.MSG91, ProviderName.CUSTOM}
_EMAIL_HTTP_PROVIDERS = {ProviderName.SENDGRID, ProviderName.SMTP, ProviderName.CUSTOM}


def _settings_use_http(channel: MessageChannel) -> bool:
    if channel == MessageChannel.WHATSAPP:
        return settings.whatsapp_provider.lower() in {"meta", "meta_cloud_api", "twilio"}
    if channel == MessageChannel.SMS:
        return settings.sms_provider.lower() in {"twilio", "msg91"}
    if channel == MessageChannel.EMAIL:
        return settings.email_provider.lower() in {"sendgrid", "smtp"}
    return False


def get_provider_adapter(
    channel: MessageChannel,
    provider_name: ProviderName | None = None,
) -> BaseCommunicationProvider:
    """Return a provider adapter based on config and optional DB provider name."""
    if provider_name in {None, ProviderName.MOCK}:
        if _settings_use_http(channel):
            if channel == MessageChannel.WHATSAPP:
                return _HTTP_WHATSAPP
            if channel == MessageChannel.SMS:
                return _HTTP_SMS
            if channel == MessageChannel.EMAIL:
                return _HTTP_EMAIL
        return _MOCK_ADAPTERS[channel]

    if channel == MessageChannel.WHATSAPP and (
        provider_name in _WHATSAPP_HTTP_PROVIDERS or _settings_use_http(channel)
    ):
        return _HTTP_WHATSAPP

    if channel == MessageChannel.SMS and (
        provider_name in _SMS_HTTP_PROVIDERS or _settings_use_http(channel)
    ):
        return _HTTP_SMS

    if channel == MessageChannel.EMAIL and (
        provider_name in _EMAIL_HTTP_PROVIDERS or _settings_use_http(channel)
    ):
        return _HTTP_EMAIL

    return _MOCK_ADAPTERS[channel]
