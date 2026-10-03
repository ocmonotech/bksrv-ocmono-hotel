from __future__ import annotations

from app.core.config import settings
from app.modules.payments.models import ONLINE_CHECKOUT_PROVIDERS, PaymentProvider
from app.modules.payments.providers.base import BasePaymentProvider, ProviderCredentials
from app.modules.payments.providers.cashfree import CashfreeProvider
from app.modules.payments.providers.ccavenue import CCAvenueProvider
from app.modules.payments.providers.mock import (
    MockCashfreeProvider,
    MockCCAvenueProvider,
    MockPaytmProvider,
    MockPhonePeProvider,
    MockPineLabsProvider,
    MockRazorpayProvider,
)
from app.modules.payments.providers.online_common import is_mock_credentials
from app.modules.payments.providers.paytm import PaytmProvider
from app.modules.payments.providers.phonepe import PhonePeProvider
from app.modules.payments.providers.pinelabs import PineLabsProvider
from app.modules.payments.providers.razorpay import RazorpayProvider

_MOCK_ADAPTERS: dict[PaymentProvider, BasePaymentProvider] = {
    PaymentProvider.PINELABS: MockPineLabsProvider(),
    PaymentProvider.RAZORPAY: MockRazorpayProvider(),
    PaymentProvider.PAYTM: MockPaytmProvider(),
    PaymentProvider.PHONEPE: MockPhonePeProvider(),
    PaymentProvider.CASHFREE: MockCashfreeProvider(),
    PaymentProvider.CCAVENUE: MockCCAvenueProvider(),
}

_HTTP_ADAPTERS: dict[PaymentProvider, BasePaymentProvider] = {
    PaymentProvider.PINELABS: PineLabsProvider(),
    PaymentProvider.RAZORPAY: RazorpayProvider(),
    PaymentProvider.PAYTM: PaytmProvider(),
    PaymentProvider.PHONEPE: PhonePeProvider(),
    PaymentProvider.CASHFREE: CashfreeProvider(),
    PaymentProvider.CCAVENUE: CCAvenueProvider(),
}

PROVIDER_LABELS: dict[PaymentProvider, tuple[str, str]] = {
    PaymentProvider.PINELABS: (
        "Pine Labs",
        "Plutus smart terminals — card, UPI, and wallet payments (POS)",
    ),
    PaymentProvider.RAZORPAY: (
        "Razorpay",
        "Cards, UPI, netbanking — POS terminals and online checkout",
    ),
    PaymentProvider.PAYTM: (
        "Paytm",
        "Paytm EDC terminals, QR, and online checkout",
    ),
    PaymentProvider.PHONEPE: (
        "PhonePe",
        "PhonePe devices, QR, and online checkout",
    ),
    PaymentProvider.CASHFREE: (
        "Cashfree",
        "Cashfree Payments — online checkout, UPI, and cards",
    ),
    PaymentProvider.CCAVENUE: (
        "CCAvenue",
        "CCAvenue hosted checkout — cards, netbanking, and wallets",
    ),
}


def supports_online_checkout(provider: PaymentProvider) -> bool:
    return provider in ONLINE_CHECKOUT_PROVIDERS


def _global_live_mode() -> bool:
    mode = settings.payment_provider.lower()
    return mode in {
        "live",
        "http",
        "online",
        "razorpay",
        "phonepe",
        "cashfree",
        "ccavenue",
        "paytm",
        "pinelabs",
        "pine_labs",
        "plutus",
    }


def get_payment_provider(
    provider: PaymentProvider,
    credentials: ProviderCredentials | None = None,
) -> BasePaymentProvider:
    """
    Resolve mock vs HTTP adapter.

    - Default / PAYMENT_PROVIDER=mock → mock adapters
    - PAYMENT_PROVIDER=live (or provider name) → HTTP adapters
    - Per-integration config.mode=live with real keys → HTTP (credentials-aware)
    HTTP adapters still fall back to mock internals when secrets look like demo keys.
    """
    if credentials is not None:
        if not is_mock_credentials(credentials):
            return _HTTP_ADAPTERS.get(provider, _MOCK_ADAPTERS[provider])
        return _MOCK_ADAPTERS[provider]

    if _global_live_mode():
        # Prefer HTTP for the configured provider (or all when mode=live/http/online)
        mode = settings.payment_provider.lower()
        if mode in {"live", "http", "online"} or mode.replace("_", "") in {
            provider.value.replace("_", ""),
            "pinelabs",
            "pinelabs",
        }:
            if provider == PaymentProvider.PINELABS and mode in {"pinelabs", "pine_labs", "plutus", "live", "http"}:
                return _HTTP_ADAPTERS[PaymentProvider.PINELABS]
            if provider in _HTTP_ADAPTERS and (
                mode in {"live", "http", "online"} or mode == provider.value
            ):
                return _HTTP_ADAPTERS[provider]

    return _MOCK_ADAPTERS[provider]


def build_postback_url(webhook_token: str) -> str:
    base = settings.public_api_base_url.rstrip("/")
    return f"{base}/api/v1/payments/webhooks/{webhook_token}"
