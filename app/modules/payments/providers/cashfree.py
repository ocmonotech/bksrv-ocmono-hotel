"""Cashfree Payments HTTP adapter (PG orders / sessions)."""

from __future__ import annotations

import logging

import httpx

from app.modules.payments.models import PaymentProvider
from app.modules.payments.providers.base import (
    OnlineCheckoutRequest,
    OnlineCheckoutResult,
    OnlinePaymentVerifyResult,
    ProviderConnectionResult,
    ProviderCredentials,
)
from app.modules.payments.providers.mock import MockCashfreeProvider
from app.modules.payments.providers.online_common import config_str, is_mock_credentials

logger = logging.getLogger(__name__)


class CashfreeProvider(MockCashfreeProvider):
    provider = PaymentProvider.CASHFREE

    def _api_base(self, credentials: ProviderCredentials) -> str:
        env = config_str(credentials, "env", "sandbox").lower()
        default = (
            "https://sandbox.cashfree.com/pg"
            if env != "production"
            else "https://api.cashfree.com/pg"
        )
        return config_str(credentials, "api_base_url", default).rstrip("/")

    def _headers(self, credentials: ProviderCredentials) -> dict[str, str]:
        return {
            "x-client-id": credentials.client_id or credentials.merchant_id or "",
            "x-client-secret": credentials.api_key or credentials.security_token or "",
            "x-api-version": config_str(credentials, "api_version", "2023-08-01"),
            "Content-Type": "application/json",
        }

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if is_mock_credentials(credentials):
            return await super().test_connection(credentials)
        if not (credentials.client_id or credentials.merchant_id) or not (
            credentials.api_key or credentials.security_token
        ):
            return ProviderConnectionResult(
                success=False,
                message="Cashfree App ID and secret key are required",
            )
        return ProviderConnectionResult(
            success=True,
            message="Cashfree credentials accepted (live mode)",
            terminal_name=f"Cashfree · {credentials.client_id or credentials.merchant_id}",
        )

    async def create_online_checkout(
        self,
        credentials: ProviderCredentials,
        request: OnlineCheckoutRequest,
    ) -> OnlineCheckoutResult:
        if is_mock_credentials(credentials):
            return await super().create_online_checkout(credentials, request)

        payload = {
            "order_id": request.order_id[:50],
            "order_amount": round(float(request.amount_inr), 2),
            "order_currency": request.currency or "INR",
            "customer_details": {
                "customer_id": (request.customer_phone or request.customer_email or request.order_id)[:50],
                "customer_name": request.customer_name or "Guest",
                "customer_email": request.customer_email or "guest@example.com",
                "customer_phone": (request.customer_phone or "9999999999")[-10:],
            },
            "order_meta": {
                "return_url": request.return_url or "",
                "notify_url": request.cancel_url or "",
            },
        }
        url = f"{self._api_base(credentials)}/orders"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self._headers(credentials))
                data = response.json() if response.content else {}
                if response.status_code >= 400:
                    return OnlineCheckoutResult(
                        success=False,
                        message=str(data.get("message") or data),
                        raw_response=data,
                    )
        except Exception as exc:
            logger.warning("Cashfree checkout failed: %s", exc)
            return OnlineCheckoutResult(success=False, message=str(exc))

        session_id = data.get("payment_session_id")
        return OnlineCheckoutResult(
            success=True,
            provider_order_id=str(data.get("order_id") or request.order_id),
            payment_session_id=str(session_id) if session_id else None,
            checkout_url=data.get("payments", {}).get("url") if isinstance(data.get("payments"), dict) else None,
            message="Cashfree order created",
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

        url = f"{self._api_base(credentials)}/orders/{provider_order_id}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, headers=self._headers(credentials))
                data = response.json() if response.content else {}
                if response.status_code >= 400:
                    return OnlinePaymentVerifyResult(
                        success=False,
                        paid=False,
                        message=str(data.get("message") or data),
                        raw_response=data,
                    )
        except Exception as exc:
            logger.warning("Cashfree verify failed: %s", exc)
            return OnlinePaymentVerifyResult(success=False, paid=False, message=str(exc))

        status = str(data.get("order_status") or "").upper()
        paid = status in {"PAID", "ACTIVE"} and float(data.get("order_amount") or 0) > 0 and status == "PAID"
        # Cashfree: PAID means settled
        paid = status == "PAID"
        return OnlinePaymentVerifyResult(
            success=True,
            paid=paid,
            provider_payment_id=str(data.get("cf_order_id") or data.get("order_id")),
            amount_inr=float(data.get("order_amount") or 0) or None,
            message="Cashfree payment captured" if paid else f"Cashfree status: {status or 'unknown'}",
            raw_response=data,
        )
