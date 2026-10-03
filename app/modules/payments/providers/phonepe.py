"""PhonePe PG HTTP adapter (Pay Page / status)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid

import httpx

from app.modules.payments.models import PaymentProvider
from app.modules.payments.providers.base import (
    OnlineCheckoutRequest,
    OnlineCheckoutResult,
    OnlinePaymentVerifyResult,
    ProviderConnectionResult,
    ProviderCredentials,
)
from app.modules.payments.providers.mock import MockPhonePeProvider
from app.modules.payments.providers.online_common import (
    amount_paise,
    config_str,
    is_mock_credentials,
)

logger = logging.getLogger(__name__)


class PhonePeProvider(MockPhonePeProvider):
    provider = PaymentProvider.PHONEPE

    def _api_base(self, credentials: ProviderCredentials) -> str:
        env = config_str(credentials, "env", "sandbox").lower()
        default = (
            "https://api-preprod.phonepe.com/apis/pg-sandbox"
            if env != "production"
            else "https://api.phonepe.com/apis/hermes"
        )
        return config_str(credentials, "api_base_url", default).rstrip("/")

    def _salt_key(self, credentials: ProviderCredentials) -> str:
        return credentials.api_key or credentials.security_token or ""

    def _salt_index(self, credentials: ProviderCredentials) -> str:
        return config_str(credentials, "salt_index", "1")

    def _merchant_id(self, credentials: ProviderCredentials) -> str:
        return credentials.merchant_id or credentials.client_id or ""

    def _x_verify(self, payload_b64: str, path: str, credentials: ProviderCredentials) -> str:
        salt = self._salt_key(credentials)
        index = self._salt_index(credentials)
        digest = hashlib.sha256(f"{payload_b64}{path}{salt}".encode("utf-8")).hexdigest()
        return f"{digest}###{index}"

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if is_mock_credentials(credentials):
            return await super().test_connection(credentials)
        if not self._merchant_id(credentials) or not self._salt_key(credentials):
            return ProviderConnectionResult(
                success=False,
                message="PhonePe merchant ID and salt key (API key) are required",
            )
        return ProviderConnectionResult(
            success=True,
            message="PhonePe credentials accepted (live mode)",
            terminal_name=f"PhonePe · {self._merchant_id(credentials)}",
        )

    async def create_online_checkout(
        self,
        credentials: ProviderCredentials,
        request: OnlineCheckoutRequest,
    ) -> OnlineCheckoutResult:
        if is_mock_credentials(credentials):
            return await super().create_online_checkout(credentials, request)

        merchant_id = self._merchant_id(credentials)
        if not merchant_id or not self._salt_key(credentials):
            return OnlineCheckoutResult(success=False, message="PhonePe credentials not configured")

        txn_id = f"TX{uuid.uuid4().hex[:18].upper()}"
        payload = {
            "merchantId": merchant_id,
            "merchantTransactionId": txn_id,
            "merchantUserId": (request.customer_phone or request.order_id)[:36],
            "amount": amount_paise(request.amount_inr),
            "redirectUrl": request.return_url or "https://example.com/payments/return",
            "redirectMode": "REDIRECT",
            "callbackUrl": request.cancel_url or request.return_url or "https://example.com/payments/callback",
            "paymentInstrument": {"type": "PAY_PAGE"},
        }
        payload_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        path = "/pg/v1/pay"
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": self._x_verify(payload_b64, path, credentials),
        }
        url = f"{self._api_base(credentials)}{path}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json={"request": payload_b64}, headers=headers)
                data = response.json() if response.content else {}
                if response.status_code >= 400 or not data.get("success"):
                    return OnlineCheckoutResult(
                        success=False,
                        message=str(data.get("message") or data),
                        raw_response=data,
                    )
        except Exception as exc:
            logger.warning("PhonePe checkout failed: %s", exc)
            return OnlineCheckoutResult(success=False, message=str(exc))

        instrument = ((data.get("data") or {}).get("instrumentResponse") or {})
        redirect = instrument.get("redirectInfo") or {}
        return OnlineCheckoutResult(
            success=True,
            provider_order_id=txn_id,
            payment_session_id=txn_id,
            checkout_url=redirect.get("url"),
            message="PhonePe pay page created",
            raw_response=data,
        )

    async def verify_online_payment(
        self,
        credentials: ProviderCredentials,
        *,
        provider_order_id: str,
        payment_session_id: str | None = None,
        card_last4: str | None = None,
    ) -> OnlinePaymentVerifyResult:
        if is_mock_credentials(credentials):
            return await super().verify_online_payment(
                credentials,
                provider_order_id=provider_order_id,
                payment_session_id=payment_session_id,
                card_last4=card_last4,
            )
        if card_last4 == "0000":
            return OnlinePaymentVerifyResult(success=False, paid=False, message="Payment declined (simulated)")

        merchant_id = self._merchant_id(credentials)
        txn_id = payment_session_id or provider_order_id
        path = f"/pg/v1/status/{merchant_id}/{txn_id}"
        x_verify = hashlib.sha256(
            f"{path}{self._salt_key(credentials)}".encode("utf-8")
        ).hexdigest() + f"###{self._salt_index(credentials)}"
        headers = {"Content-Type": "application/json", "X-VERIFY": x_verify, "X-MERCHANT-ID": merchant_id}
        url = f"{self._api_base(credentials)}{path}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, headers=headers)
                data = response.json() if response.content else {}
        except Exception as exc:
            logger.warning("PhonePe verify failed: %s", exc)
            return OnlinePaymentVerifyResult(success=False, paid=False, message=str(exc))

        code = str((data.get("code") or data.get("data", {}).get("state") or "")).upper()
        paid = code in {"PAYMENT_SUCCESS", "COMPLETED", "SUCCESS"}
        amount = None
        try:
            amount = ((data.get("data") or {}).get("amount") or 0) / 100
        except Exception:
            amount = None
        return OnlinePaymentVerifyResult(
            success=True,
            paid=paid,
            provider_payment_id=str((data.get("data") or {}).get("transactionId") or txn_id),
            amount_inr=amount,
            message="PhonePe payment success" if paid else f"PhonePe status: {code or 'pending'}",
            raw_response=data,
        )
