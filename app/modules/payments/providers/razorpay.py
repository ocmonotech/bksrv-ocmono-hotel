"""Razorpay Orders / Payment Links HTTP adapter."""

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
from app.modules.payments.providers.mock import MockRazorpayProvider
from app.modules.payments.providers.online_common import (
    amount_paise,
    config_str,
    is_mock_credentials,
)

logger = logging.getLogger(__name__)


class RazorpayProvider(MockRazorpayProvider):
    provider = PaymentProvider.RAZORPAY

    def _key_id(self, credentials: ProviderCredentials) -> str | None:
        return credentials.client_id or credentials.merchant_id

    def _key_secret(self, credentials: ProviderCredentials) -> str | None:
        return credentials.api_key or credentials.security_token

    def _api_base(self, credentials: ProviderCredentials) -> str:
        return config_str(
            credentials,
            "api_base_url",
            "https://api.razorpay.com/v1",
        ).rstrip("/")

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if is_mock_credentials(credentials):
            return await super().test_connection(credentials)
        key_id = self._key_id(credentials)
        key_secret = self._key_secret(credentials)
        if not key_id or not key_secret:
            return ProviderConnectionResult(
                success=False,
                message="Razorpay Key ID (client/merchant) and Key Secret (API key) are required",
            )
        url = f"{self._api_base(credentials)}/orders"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, auth=(key_id, key_secret), params={"count": 1})
            if response.status_code in {200, 401}:
                # 401 still proves endpoint reachability; treat missing auth as bad keys
                if response.status_code == 401:
                    return ProviderConnectionResult(success=False, message="Razorpay credentials rejected")
                return ProviderConnectionResult(
                    success=True,
                    message="Razorpay API credentials verified",
                    terminal_name=f"Razorpay · {key_id[:8]}…",
                )
            return ProviderConnectionResult(
                success=False,
                message=f"Razorpay returned HTTP {response.status_code}",
            )
        except Exception as exc:
            logger.warning("Razorpay connection test failed: %s", exc)
            return ProviderConnectionResult(success=False, message=str(exc))

    async def create_online_checkout(
        self,
        credentials: ProviderCredentials,
        request: OnlineCheckoutRequest,
    ) -> OnlineCheckoutResult:
        if is_mock_credentials(credentials):
            return await super().create_online_checkout(credentials, request)

        key_id = self._key_id(credentials)
        key_secret = self._key_secret(credentials)
        if not key_id or not key_secret:
            return OnlineCheckoutResult(success=False, message="Razorpay keys not configured")

        payload = {
            "amount": amount_paise(request.amount_inr),
            "currency": request.currency or "INR",
            "receipt": request.order_id[:40],
            "notes": {
                "purpose": request.purpose,
                **{str(k): str(v) for k, v in (request.metadata or {}).items()},
            },
        }
        if request.customer_name or request.customer_email or request.customer_phone:
            payload["notes"]["customer_name"] = request.customer_name or ""
            payload["notes"]["customer_email"] = request.customer_email or ""
            payload["notes"]["customer_phone"] = request.customer_phone or ""

        # Prefer Payment Links for hosted redirect checkout.
        link_payload = {
            "amount": payload["amount"],
            "currency": payload["currency"],
            "accept_partial": False,
            "reference_id": request.order_id[:40],
            "description": request.purpose or "Payment",
            "customer": {
                k: v
                for k, v in {
                    "name": request.customer_name,
                    "email": request.customer_email,
                    "contact": request.customer_phone,
                }.items()
                if v
            },
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": payload["notes"],
        }
        if request.return_url:
            link_payload["callback_url"] = request.return_url
            link_payload["callback_method"] = "get"

        url = f"{self._api_base(credentials)}/payment_links"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=link_payload, auth=(key_id, key_secret))
                data = response.json() if response.content else {}
                if response.status_code >= 400:
                    # Fallback to Orders API (Checkout.js / custom UI)
                    order_url = f"{self._api_base(credentials)}/orders"
                    order_resp = await client.post(order_url, json=payload, auth=(key_id, key_secret))
                    order_data = order_resp.json() if order_resp.content else {}
                    if order_resp.status_code >= 400:
                        return OnlineCheckoutResult(
                            success=False,
                            message=str(data.get("error", {}).get("description") or data or order_data),
                            raw_response={"payment_link": data, "order": order_data},
                        )
                    return OnlineCheckoutResult(
                        success=True,
                        provider_order_id=str(order_data.get("id")),
                        payment_session_id=str(order_data.get("id")),
                        checkout_url=None,
                        message="Razorpay order created — complete via Checkout",
                        raw_response=order_data,
                    )
        except Exception as exc:
            logger.warning("Razorpay checkout failed: %s", exc)
            return OnlineCheckoutResult(success=False, message=str(exc))

        return OnlineCheckoutResult(
            success=True,
            provider_order_id=str(data.get("id") or data.get("order_id") or ""),
            payment_session_id=str(data.get("id") or ""),
            checkout_url=data.get("short_url") or data.get("checkout_url"),
            message="Razorpay payment link created",
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
            return OnlinePaymentVerifyResult(
                success=False,
                paid=False,
                message="Payment declined (simulated)",
            )

        key_id = self._key_id(credentials)
        key_secret = self._key_secret(credentials)
        if not key_id or not key_secret:
            return OnlinePaymentVerifyResult(success=False, paid=False, message="Razorpay keys missing")

        # Payment link id or order id
        link_id = payment_session_id or provider_order_id
        url = f"{self._api_base(credentials)}/payment_links/{link_id}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, auth=(key_id, key_secret))
                data = response.json() if response.content else {}
                if response.status_code >= 400:
                    # Try payments by order
                    payments_url = f"{self._api_base(credentials)}/orders/{provider_order_id}/payments"
                    pay_resp = await client.get(payments_url, auth=(key_id, key_secret))
                    pay_data = pay_resp.json() if pay_resp.content else {}
                    items = pay_data.get("items") or []
                    paid_item = next((row for row in items if row.get("status") == "captured"), None)
                    if paid_item:
                        return OnlinePaymentVerifyResult(
                            success=True,
                            paid=True,
                            provider_payment_id=str(paid_item.get("id")),
                            amount_inr=(paid_item.get("amount") or 0) / 100,
                            message="Razorpay payment captured",
                            raw_response=pay_data,
                        )
                    return OnlinePaymentVerifyResult(
                        success=False,
                        paid=False,
                        message="Payment not captured yet",
                        raw_response={"link": data, "payments": pay_data},
                    )
        except Exception as exc:
            logger.warning("Razorpay verify failed: %s", exc)
            return OnlinePaymentVerifyResult(success=False, paid=False, message=str(exc))

        status = str(data.get("status") or "").lower()
        paid = status in {"paid", "partially_paid"}
        return OnlinePaymentVerifyResult(
            success=True,
            paid=paid,
            provider_payment_id=str(data.get("id")),
            amount_inr=(data.get("amount_paid") or data.get("amount") or 0) / 100,
            message="Razorpay payment link paid" if paid else f"Razorpay status: {status or 'unknown'}",
            raw_response=data,
        )
