from __future__ import annotations

import random
import uuid

from app.modules.payments.models import PaymentProvider, TerminalPaymentStatus
from app.modules.payments.providers.base import (
    BasePaymentProvider,
    ProviderConnectionResult,
    ProviderCredentials,
    ProviderStatusResult,
    ProviderUploadResult,
    UploadTransactionRequest,
)
from app.modules.pos.models import PaymentMode

_MOCK_COMPLETED: set[str] = set()


class MockPineLabsProvider(BasePaymentProvider):
    provider = PaymentProvider.PINELABS

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if not credentials.merchant_id or not credentials.store_id:
            return ProviderConnectionResult(
                success=False,
                message="Merchant ID and Store ID are required for Pine Labs",
            )
        return ProviderConnectionResult(
            success=True,
            message="Mock Pine Labs terminal connection verified",
            terminal_name=f"Plutus Terminal · Store {credentials.store_id}",
        )

    async def upload_transaction(
        self,
        credentials: ProviderCredentials,
        request: UploadTransactionRequest,
    ) -> ProviderUploadResult:
        ptrid = str(random.randint(100000, 999999))
        return ProviderUploadResult(
            success=True,
            provider_reference_id=ptrid,
            status=TerminalPaymentStatus.PENDING_TERMINAL,
            message="Transaction uploaded to mock Plutus terminal",
            raw_response={
                "ResponseCode": 0,
                "ResponseMessage": "APPROVED",
                "PlutusTransactionReferenceID": int(ptrid),
            },
        )

    async def get_transaction_status(
        self,
        credentials: ProviderCredentials,
        *,
        provider_reference_id: str,
        transaction_number: str | None = None,
        user_id: str | None = None,
    ) -> ProviderStatusResult:
        if provider_reference_id in _MOCK_COMPLETED:
            return ProviderStatusResult(
                success=True,
                status=TerminalPaymentStatus.SUCCESS,
                provider_reference_id=provider_reference_id,
                auth_code="1234",
                reference_number=f"RRN{uuid.uuid4().hex[:8].upper()}",
                payment_mode=PaymentMode.CARD,
                message="TXN APPROVED",
                raw_response={"ResponseCode": 0, "ResponseMessage": "TXN APPROVED"},
            )
        return ProviderStatusResult(
            success=True,
            status=TerminalPaymentStatus.PENDING_TERMINAL,
            provider_reference_id=provider_reference_id,
            message="Awaiting customer on terminal",
            raw_response={"ResponseCode": 0, "ResponseMessage": "PENDING"},
        )

    def mark_mock_complete(self, provider_reference_id: str) -> None:
        _MOCK_COMPLETED.add(provider_reference_id)


class MockRazorpayProvider(MockPineLabsProvider):
    provider = PaymentProvider.RAZORPAY

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if not credentials.api_key:
            return ProviderConnectionResult(success=False, message="Razorpay API key is required")
        return ProviderConnectionResult(
            success=True,
            message="Mock Razorpay POS connection verified",
            terminal_name="Razorpay Terminal",
        )


class MockPaytmProvider(MockPineLabsProvider):
    provider = PaymentProvider.PAYTM

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if not credentials.merchant_id:
            return ProviderConnectionResult(success=False, message="Paytm merchant ID is required")
        return ProviderConnectionResult(
            success=True,
            message="Mock Paytm connection verified",
            terminal_name=f"Paytm · {credentials.merchant_id}",
        )


class MockPhonePeProvider(MockPineLabsProvider):
    provider = PaymentProvider.PHONEPE

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if not credentials.merchant_id:
            return ProviderConnectionResult(success=False, message="PhonePe merchant ID is required")
        return ProviderConnectionResult(
            success=True,
            message="Mock PhonePe connection verified",
            terminal_name=f"PhonePe · {credentials.merchant_id}",
        )


class MockCashfreeProvider(MockPineLabsProvider):
    provider = PaymentProvider.CASHFREE

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if not credentials.client_id or not credentials.api_key:
            return ProviderConnectionResult(
                success=False,
                message="Cashfree App ID (client ID) and secret key (API key) are required",
            )
        return ProviderConnectionResult(
            success=True,
            message="Mock Cashfree connection verified",
            terminal_name=f"Cashfree · {credentials.client_id}",
        )


class MockCCAvenueProvider(MockPineLabsProvider):
    provider = PaymentProvider.CCAVENUE

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if not credentials.merchant_id or not credentials.api_key:
            return ProviderConnectionResult(
                success=False,
                message="CCAvenue merchant ID and access code / working key (API key) are required",
            )
        return ProviderConnectionResult(
            success=True,
            message="Mock CCAvenue connection verified",
            terminal_name=f"CCAvenue · {credentials.merchant_id}",
        )
