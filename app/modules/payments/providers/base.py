from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.modules.payments.models import PaymentProvider, TerminalPaymentStatus
from app.modules.pos.models import PaymentMode


@dataclass
class ProviderConnectionResult:
    success: bool
    message: str
    terminal_name: str | None = None


@dataclass
class ProviderUploadResult:
    success: bool
    provider_reference_id: str | None = None
    status: TerminalPaymentStatus = TerminalPaymentStatus.PENDING_TERMINAL
    message: str | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class ProviderStatusResult:
    success: bool
    status: TerminalPaymentStatus
    provider_reference_id: str | None = None
    auth_code: str | None = None
    reference_number: str | None = None
    payment_mode: PaymentMode | None = None
    message: str | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class ProviderCredentials:
    merchant_id: str | None = None
    store_id: str | None = None
    client_id: str | None = None
    security_token: str | None = None
    api_key: str | None = None
    config: dict | None = None


@dataclass
class UploadTransactionRequest:
    transaction_number: str
    sequence_number: int
    amount_inr: float
    payment_mode: PaymentMode
    bill_number: str
    user_id: str | None = None
    total_invoice_amount_inr: float | None = None


@dataclass
class OnlineCheckoutRequest:
    """Hosted / redirect checkout for guest room, spa, and folio payments."""

    order_id: str
    amount_inr: float
    currency: str = "INR"
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    purpose: str = "booking"
    return_url: str | None = None
    cancel_url: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class OnlineCheckoutResult:
    success: bool
    provider_order_id: str | None = None
    checkout_url: str | None = None
    payment_session_id: str | None = None
    message: str | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class OnlinePaymentVerifyResult:
    success: bool
    paid: bool
    provider_payment_id: str | None = None
    amount_inr: float | None = None
    message: str | None = None
    raw_response: dict = field(default_factory=dict)


class BasePaymentProvider(ABC):
    provider: PaymentProvider

    @abstractmethod
    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        raise NotImplementedError

    @abstractmethod
    async def upload_transaction(
        self,
        credentials: ProviderCredentials,
        request: UploadTransactionRequest,
    ) -> ProviderUploadResult:
        raise NotImplementedError

    @abstractmethod
    async def get_transaction_status(
        self,
        credentials: ProviderCredentials,
        *,
        provider_reference_id: str,
        transaction_number: str | None = None,
        user_id: str | None = None,
    ) -> ProviderStatusResult:
        raise NotImplementedError

    def verify_postback(
        self,
        *,
        payload: dict,
        webhook_secret: str | None,
    ) -> bool:
        if not webhook_secret:
            return True
        return True

    async def create_online_checkout(
        self,
        credentials: ProviderCredentials,
        request: OnlineCheckoutRequest,
    ) -> OnlineCheckoutResult:
        """Optional: hosted payment page / UPI intent. Default is mock success."""
        session_id = f"{self.provider.value.upper()}-SES-{uuid.uuid4().hex[:10].upper()}"
        order_id = f"{self.provider.value.upper()}-ORD-{request.order_id[:24]}"
        return OnlineCheckoutResult(
            success=True,
            provider_order_id=order_id,
            payment_session_id=session_id,
            checkout_url=None,
            message=f"Mock {self.provider.value} checkout session created",
            raw_response={"mode": "mock", "amount": request.amount_inr},
        )

    async def verify_online_payment(
        self,
        credentials: ProviderCredentials,
        *,
        provider_order_id: str,
        payment_session_id: str | None = None,
        card_last4: str | None = None,
    ) -> OnlinePaymentVerifyResult:
        """Verify / capture an online payment. card_last4 0000 simulates decline in mock."""
        if card_last4 == "0000":
            return OnlinePaymentVerifyResult(
                success=False,
                paid=False,
                message="Payment declined by gateway (mock)",
                raw_response={"mode": "mock", "declined": True},
            )
        pay_id = f"{self.provider.value.upper()}-PAY-{uuid.uuid4().hex[:10].upper()}"
        return OnlinePaymentVerifyResult(
            success=True,
            paid=True,
            provider_payment_id=pay_id,
            amount_inr=None,
            message=f"Mock {self.provider.value} payment captured",
            raw_response={
                "mode": "mock",
                "order_id": provider_order_id,
                "session_id": payment_session_id,
                "card_last4": card_last4,
            },
        )
