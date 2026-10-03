"""Shared helpers for online payment gateway HTTP adapters."""

from __future__ import annotations

from app.core.config import settings
from app.modules.payments.providers.base import ProviderCredentials


def amount_paise(amount_inr: float) -> int:
    return int(round(float(amount_inr) * 100))


def _looks_like_demo_secret(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return (
        lowered.startswith("mock_enc:")
        or lowered.startswith("stub")
        or lowered in {"demo-key", "demo", "test"}
        or lowered.startswith("demo-")
    )


def is_mock_credentials(credentials: ProviderCredentials) -> bool:
    """Prefer mock adapters for demo / stub secrets; honor explicit live mode."""
    config = credentials.config or {}
    mode = str(config.get("mode") or "").lower()

    api_key = (credentials.api_key or "").strip()
    merchant = (credentials.merchant_id or "").strip()
    client_id = (credentials.client_id or "").strip()
    security = (credentials.security_token or "").strip()

    real_secret = (api_key and not _looks_like_demo_secret(api_key)) or (
        security and not _looks_like_demo_secret(security)
    )
    real_id = (
        client_id
        and not client_id.upper().startswith("DEMO-")
        and not _looks_like_demo_secret(client_id)
    ) or (
        merchant
        and not merchant.upper().startswith("DEMO-")
        and not _looks_like_demo_secret(merchant)
    )

    # Per-outlet live override: use HTTP when keys look real.
    if mode in {"live", "production", "http"}:
        return not (real_secret and real_id)

    if mode in {"mock", "stub", "demo"}:
        return True

    # Global default stays mock unless PAYMENT_PROVIDER is live/http/online/provider-name.
    if settings.payment_provider.lower() in {"mock", "stub"}:
        return True

    if not (api_key or merchant or client_id or security):
        return True
    if not (real_secret and real_id):
        return True
    if settings.enable_stub_external_services and (
        _looks_like_demo_secret(api_key) or merchant.upper().startswith("DEMO-")
    ):
        return True
    return False


def config_str(credentials: ProviderCredentials, key: str, default: str = "") -> str:
    config = credentials.config or {}
    value = config.get(key)
    return str(value) if value is not None else default
