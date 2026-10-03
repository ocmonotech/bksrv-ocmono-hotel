from __future__ import annotations

import logging

import httpx

from app.core.config import settings
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

logger = logging.getLogger(__name__)

_PAYMENT_MODE_MAP: dict[PaymentMode, str] = {
    PaymentMode.CARD: "1",
    PaymentMode.UPI: "10",
    PaymentMode.CASH: "2",
    PaymentMode.ONLINE: "0",
    PaymentMode.SPLIT: "0",
}


def _is_stub(value: str | None) -> bool:
    if not value:
        return True
    return settings.enable_stub_external_services and value.startswith("stub")


def _amount_paisa(amount_inr: float) -> int:
    return int(round(amount_inr * 100))


def _api_base(credentials: ProviderCredentials) -> str:
    config = credentials.config or {}
    return str(
        config.get("api_base_url")
        or settings.pinelabs_api_base_url
    ).rstrip("/")


class PineLabsProvider(BasePaymentProvider):
    provider = PaymentProvider.PINELABS

    async def test_connection(self, credentials: ProviderCredentials) -> ProviderConnectionResult:
        if _is_stub(credentials.security_token) or not credentials.merchant_id:
            return ProviderConnectionResult(
                success=False,
                message="Pine Labs merchant ID and security token are required",
            )
        if not credentials.store_id:
            return ProviderConnectionResult(
                success=False,
                message="Pine Labs store ID is required",
            )
        return ProviderConnectionResult(
            success=True,
            message="Pine Labs credentials validated",
            terminal_name=f"Plutus · Store {credentials.store_id}",
        )

    async def upload_transaction(
        self,
        credentials: ProviderCredentials,
        request: UploadTransactionRequest,
    ) -> ProviderUploadResult:
        if _is_stub(credentials.security_token):
            return ProviderUploadResult(
                success=False,
                message="Pine Labs security token not configured",
            )

        allowed_mode = _PAYMENT_MODE_MAP.get(request.payment_mode, "0")
        payload = {
            "TransactionNumber": request.transaction_number,
            "SequenceNumber": request.sequence_number,
            "AllowedPaymentMode": allowed_mode,
            "Amount": _amount_paisa(request.amount_inr),
            "MerchantID": credentials.merchant_id,
            "SecurityToken": credentials.security_token,
            "StoreId": credentials.store_id,
            "Invoicenumber": request.bill_number[:10],
            "UserID": request.user_id or "POS",
        }
        if credentials.client_id:
            payload["ClientId"] = credentials.client_id
        if request.total_invoice_amount_inr is not None:
            payload["TotalInvoiceAmount"] = _amount_paisa(request.total_invoice_amount_inr)

        config = credentials.config or {}
        auto_cancel = config.get("auto_cancel_duration_minutes")
        if auto_cancel is not None:
            payload["AutoCancelDurationInMinutes"] = auto_cancel

        url = f"{_api_base(credentials)}/API/CloudBasedIntegration/V1/UploadBilledTransaction"

        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Pine Labs upload failed: %s", exc)
            return ProviderUploadResult(success=False, message=str(exc))

        response_code = int(data.get("ResponseCode", 1))
        if response_code != 0:
            return ProviderUploadResult(
                success=False,
                message=data.get("ResponseMessage", "Upload declined"),
                raw_response=data,
            )

        ptrid = str(data.get("PlutusTransactionReferenceID", ""))
        return ProviderUploadResult(
            success=True,
            provider_reference_id=ptrid,
            status=TerminalPaymentStatus.PENDING_TERMINAL,
            message=data.get("ResponseMessage", "APPROVED"),
            raw_response=data,
        )

    async def get_transaction_status(
        self,
        credentials: ProviderCredentials,
        *,
        provider_reference_id: str,
        transaction_number: str | None = None,
        user_id: str | None = None,
    ) -> ProviderStatusResult:
        if _is_stub(credentials.security_token):
            return ProviderStatusResult(
                success=False,
                status=TerminalPaymentStatus.FAILED,
                message="Pine Labs security token not configured",
            )

        payload = {
            "MerchantID": credentials.merchant_id,
            "SecurityToken": credentials.security_token,
            "StoreID": credentials.store_id,
            "PlutusTransactionReferenceID": int(provider_reference_id),
            "UserID": user_id or "POS",
        }
        if credentials.client_id:
            payload["ClientID"] = credentials.client_id
        if transaction_number:
            payload["TransactionNumber"] = transaction_number

        url = f"{_api_base(credentials)}/API/CloudBasedIntegration/V1/GetStatus"

        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Pine Labs status check failed: %s", exc)
            return ProviderStatusResult(
                success=False,
                status=TerminalPaymentStatus.FAILED,
                message=str(exc),
            )

        response_code = int(data.get("ResponseCode", 1))
        message = data.get("ResponseMessage", "")
        txn_data = {
            item.get("Tag"): item.get("Value")
            for item in data.get("TransactionData", [])
            if isinstance(item, dict)
        }

        if response_code != 0:
            if "PENDING" in message.upper() or "OPEN" in message.upper():
                return ProviderStatusResult(
                    success=True,
                    status=TerminalPaymentStatus.PENDING_TERMINAL,
                    provider_reference_id=provider_reference_id,
                    message=message,
                    raw_response=data,
                )
            return ProviderStatusResult(
                success=False,
                status=TerminalPaymentStatus.FAILED,
                provider_reference_id=provider_reference_id,
                message=message,
                raw_response=data,
            )

        payment_mode_raw = (txn_data.get("PaymentMode") or "").upper()
        payment_mode = PaymentMode.CARD
        if "UPI" in payment_mode_raw:
            payment_mode = PaymentMode.UPI
        elif "CASH" in payment_mode_raw:
            payment_mode = PaymentMode.CASH

        return ProviderStatusResult(
            success=True,
            status=TerminalPaymentStatus.SUCCESS,
            provider_reference_id=provider_reference_id,
            auth_code=txn_data.get("ApprovalCode"),
            reference_number=txn_data.get("RRN") or txn_data.get("TransactionLogId"),
            payment_mode=payment_mode,
            message=message,
            raw_response=data,
        )
