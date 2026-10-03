from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.outlets.models import Outlet
from app.modules.payments.models import (
    IntegrationStatus,
    ONLINE_CHECKOUT_PROVIDERS,
    OutletPaymentIntegration,
    PaymentProvider,
    TerminalPayment,
    TerminalPaymentStatus,
)
from app.modules.payments.providers.base import (
    OnlineCheckoutRequest,
    ProviderCredentials,
    UploadTransactionRequest,
)
from app.modules.payments.providers.registry import (
    PROVIDER_LABELS,
    build_postback_url,
    get_payment_provider,
    supports_online_checkout,
)
from app.modules.payments.schemas import (
    InitiatePaymentRequest,
    IntegrationCreate,
    IntegrationDeleteResponse,
    IntegrationRead,
    IntegrationUpdate,
    OnlineCheckoutCreate,
    OnlineCheckoutResponse,
    PostbackAckResponse,
    ProviderInfo,
    PublicOnlineGatewayRead,
    TerminalPaymentRead,
)
from app.modules.pos import service as pos_service
from app.modules.pos.models import Bill, PaymentMode
from app.modules.pos.schemas import PaymentCreate
from app.utils.encryption import decrypt_secret, encrypt_secret


def list_providers() -> list[ProviderInfo]:
    return [
        ProviderInfo(provider=provider, label=label, description=description)
        for provider, (label, description) in PROVIDER_LABELS.items()
    ]


def list_integrations(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    provider: PaymentProvider | None = None,
) -> tuple[list[IntegrationRead], int]:
    query = db.query(OutletPaymentIntegration).filter(
        OutletPaymentIntegration.tenant_id == tenant_id,
        OutletPaymentIntegration.is_active.is_(True),
    )
    if outlet_id is not None:
        query = query.filter(OutletPaymentIntegration.outlet_id == outlet_id)
    if provider is not None:
        query = query.filter(OutletPaymentIntegration.provider == provider)

    rows, total = paginate_query(
        query.order_by(OutletPaymentIntegration.id.desc()), page, page_size
    )
    return [_to_integration_read(row) for row in rows], total


def get_integration(db: Session, tenant_id: int, integration_id: int) -> IntegrationRead:
    row = _get_integration_entity(db, tenant_id, integration_id)
    return _to_integration_read(row)


def create_integration(
    db: Session,
    tenant_id: int,
    data: IntegrationCreate,
    default_brand_id: int | None = None,
) -> IntegrationRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id

    existing = (
        db.query(OutletPaymentIntegration)
        .filter(
            OutletPaymentIntegration.outlet_id == data.outlet_id,
            OutletPaymentIntegration.provider == data.provider,
            OutletPaymentIntegration.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ConflictError(
            f"{data.provider.value} is already configured for this outlet"
        )

    integration = OutletPaymentIntegration(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        provider=data.provider,
        merchant_id=data.merchant_id,
        store_id=data.store_id,
        client_id=data.client_id,
        status=IntegrationStatus.PENDING,
        is_enabled=data.is_enabled,
        auto_settle_on_success=data.auto_settle_on_success,
        webhook_token=uuid.uuid4().hex,
        config_json=json.dumps(data.config or {}),
        encrypted_security_token=encrypt_secret(data.security_token),
        encrypted_api_key=encrypt_secret(data.api_key),
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return _to_integration_read(integration)


def update_integration(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: IntegrationUpdate,
) -> IntegrationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    payload = data.model_dump(exclude_unset=True)

    for field in ("merchant_id", "store_id", "client_id", "status", "is_enabled", "auto_settle_on_success"):
        if field in payload:
            setattr(integration, field, payload[field])
    if "config" in payload and payload["config"] is not None:
        integration.config_json = json.dumps(payload["config"])
    if "security_token" in payload and payload["security_token"]:
        integration.encrypted_security_token = encrypt_secret(payload["security_token"])
    if "api_key" in payload and payload["api_key"]:
        integration.encrypted_api_key = encrypt_secret(payload["api_key"])

    db.commit()
    db.refresh(integration)
    return _to_integration_read(integration)


def delete_integration(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> IntegrationDeleteResponse:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    integration.is_active = False
    integration.is_enabled = False
    integration.status = IntegrationStatus.INACTIVE
    db.commit()
    return IntegrationDeleteResponse(
        message="Payment integration removed",
        integration_id=integration_id,
    )


async def test_integration_connection(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> IntegrationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    credentials = _build_credentials(integration)
    provider = get_payment_provider(integration.provider, credentials)
    result = await provider.test_connection(credentials)
    integration.last_sync_at = datetime.utcnow()
    if result.success:
        integration.status = IntegrationStatus.ACTIVE
        integration.last_error = None
    else:
        integration.status = IntegrationStatus.ERROR
        integration.last_error = result.message
    db.commit()
    db.refresh(integration)
    return _to_integration_read(integration)


def list_terminal_payments(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    bill_id: int | None = None,
    status: TerminalPaymentStatus | None = None,
) -> tuple[list[TerminalPaymentRead], int]:
    query = (
        db.query(TerminalPayment)
        .join(OutletPaymentIntegration)
        .join(Bill, Bill.id == TerminalPayment.bill_id)
        .filter(
            TerminalPayment.tenant_id == tenant_id,
            TerminalPayment.is_active.is_(True),
        )
    )
    if outlet_id is not None:
        query = query.filter(Bill.outlet_id == outlet_id)
    if bill_id is not None:
        query = query.filter(TerminalPayment.bill_id == bill_id)
    if status is not None:
        query = query.filter(TerminalPayment.status == status)

    rows, total = paginate_query(query.order_by(TerminalPayment.id.desc()), page, page_size)
    return [_to_terminal_payment_read(db, row) for row in rows], total


async def initiate_terminal_payment(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: InitiatePaymentRequest,
) -> TerminalPaymentRead:
    bill = _get_bill_entity(db, tenant_id, data.bill_id)
    integration = _resolve_integration(db, tenant_id, bill.outlet_id, data.integration_id)

    if not integration.is_enabled:
        raise ConflictError("Payment integration is disabled for this outlet")

    transaction_number = f"BILL-{bill.bill_number}-{uuid.uuid4().hex[:8].upper()}"
    credentials = _build_credentials(integration)
    provider = get_payment_provider(integration.provider, credentials)

    upload_request = UploadTransactionRequest(
        transaction_number=transaction_number,
        sequence_number=data.sequence_number,
        amount_inr=data.amount,
        payment_mode=data.payment_mode,
        bill_number=bill.bill_number,
        user_id=str(user_id),
        total_invoice_amount_inr=float(bill.grand_total),
    )

    terminal_payment = TerminalPayment(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        bill_id=bill.id,
        transaction_number=transaction_number,
        sequence_number=data.sequence_number,
        amount=data.amount,
        payment_mode=data.payment_mode,
        status=TerminalPaymentStatus.INITIATED,
        raw_request_json=json.dumps(upload_request.__dict__, default=str),
    )
    db.add(terminal_payment)
    db.flush()

    result = await provider.upload_transaction(credentials, upload_request)
    terminal_payment.raw_response_json = json.dumps(result.raw_response)

    if not result.success:
        terminal_payment.status = TerminalPaymentStatus.FAILED
        terminal_payment.error_message = result.message
        integration.last_error = result.message
        db.commit()
        db.refresh(terminal_payment)
        raise ConflictError(result.message or "Failed to initiate terminal payment")

    terminal_payment.status = result.status
    terminal_payment.provider_reference_id = result.provider_reference_id
    integration.last_sync_at = datetime.utcnow()
    integration.last_error = None
    db.commit()
    db.refresh(terminal_payment)
    return _to_terminal_payment_read(db, terminal_payment)


async def refresh_terminal_payment_status(
    db: Session,
    tenant_id: int,
    terminal_payment_id: int,
    user_id: int,
) -> TerminalPaymentRead:
    terminal_payment = _get_terminal_payment_entity(db, tenant_id, terminal_payment_id)
    if terminal_payment.status == TerminalPaymentStatus.SUCCESS:
        return _to_terminal_payment_read(db, terminal_payment)

    integration = terminal_payment.integration
    credentials = _build_credentials(integration)
    provider = get_payment_provider(integration.provider, credentials)

    if not terminal_payment.provider_reference_id:
        raise ConflictError("Terminal payment has no provider reference ID")

    result = await provider.get_transaction_status(
        credentials,
        provider_reference_id=terminal_payment.provider_reference_id,
        transaction_number=terminal_payment.transaction_number,
        user_id=str(user_id),
    )
    terminal_payment.raw_response_json = json.dumps(result.raw_response)
    terminal_payment.status = result.status
    if result.message:
        terminal_payment.error_message = None if result.success else result.message
    if result.auth_code:
        terminal_payment.auth_code = result.auth_code
    if result.reference_number:
        terminal_payment.reference_number = result.reference_number

    if result.status == TerminalPaymentStatus.SUCCESS and integration.auto_settle_on_success:
        _settle_terminal_payment(db, tenant_id, terminal_payment, result.payment_mode)

    integration.last_sync_at = datetime.utcnow()
    db.commit()
    db.refresh(terminal_payment)
    return _to_terminal_payment_read(db, terminal_payment)


async def simulate_terminal_payment_complete(
    db: Session,
    tenant_id: int,
    terminal_payment_id: int,
    user_id: int,
) -> TerminalPaymentRead:
    terminal_payment = _get_terminal_payment_entity(db, tenant_id, terminal_payment_id)
    integration = terminal_payment.integration

    if integration.provider != PaymentProvider.PINELABS:
        raise ConflictError("Simulation is only available for mock Pine Labs flows")

    from app.modules.payments.providers.mock import MockPineLabsProvider

    credentials = _build_credentials(integration)
    adapter = get_payment_provider(integration.provider, credentials)
    if isinstance(adapter, MockPineLabsProvider) and terminal_payment.provider_reference_id:
        adapter.mark_mock_complete(terminal_payment.provider_reference_id)

    return await refresh_terminal_payment_status(db, tenant_id, terminal_payment_id, user_id)


async def ingest_postback(
    db: Session,
    webhook_token: str,
    payload: dict,
) -> PostbackAckResponse:
    integration = (
        db.query(OutletPaymentIntegration)
        .filter(
            OutletPaymentIntegration.webhook_token == webhook_token,
            OutletPaymentIntegration.is_active.is_(True),
        )
        .first()
    )
    if integration is None:
        raise NotFoundError("Payment integration not found")

    credentials = _build_credentials(integration)
    provider = get_payment_provider(integration.provider, credentials)
    if not provider.verify_postback(payload=payload, webhook_secret=None):
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Invalid postback signature")

    ptrid = str(
        payload.get("PlutusTransactionReferenceID")
        or payload.get("plutusTransactionReferenceID")
        or ""
    )
    txn_number = payload.get("TransactionNumber") or payload.get("transactionNumber")

    query = db.query(TerminalPayment).filter(
        TerminalPayment.integration_id == integration.id,
        TerminalPayment.is_active.is_(True),
    )
    if ptrid:
        query = query.filter(TerminalPayment.provider_reference_id == ptrid)
    elif txn_number:
        query = query.filter(TerminalPayment.transaction_number == txn_number)
    else:
        raise ConflictError("Postback missing transaction identifiers")

    terminal_payment = query.order_by(TerminalPayment.id.desc()).first()
    if terminal_payment is None:
        raise NotFoundError("Terminal payment not found for postback")

    response_code = str(payload.get("ResponseCode", "1"))
    if response_code == "0":
        terminal_payment.status = TerminalPaymentStatus.SUCCESS
        terminal_payment.auth_code = payload.get("ApprovalCode")
        terminal_payment.reference_number = payload.get("RRN") or payload.get("TransactionLogId")
        terminal_payment.raw_response_json = json.dumps(payload)
        if integration.auto_settle_on_success and terminal_payment.pos_payment_id is None:
            payment_mode = _map_postback_payment_mode(payload.get("PaymenMode") or payload.get("PaymentMode"))
            _settle_terminal_payment(db, integration.tenant_id, terminal_payment, payment_mode)
    else:
        terminal_payment.status = TerminalPaymentStatus.FAILED
        terminal_payment.error_message = payload.get("ResponseMessage", "Declined")

    integration.last_sync_at = datetime.utcnow()
    db.commit()
    return PostbackAckResponse(
        success=True,
        message="Postback processed",
        terminal_payment_id=terminal_payment.id,
    )


def _settle_terminal_payment(
    db: Session,
    tenant_id: int,
    terminal_payment: TerminalPayment,
    payment_mode: PaymentMode | None,
) -> None:
    if terminal_payment.pos_payment_id is not None:
        return

    mode = payment_mode or terminal_payment.payment_mode
    payment = pos_service.add_payment(
        db,
        tenant_id,
        terminal_payment.bill_id,
        PaymentCreate(
            payment_mode=mode,
            amount=float(terminal_payment.amount),
            reference_number=terminal_payment.reference_number or terminal_payment.provider_reference_id,
        ),
    )
    terminal_payment.pos_payment_id = payment.id
    terminal_payment.status = TerminalPaymentStatus.SUCCESS


def _map_postback_payment_mode(raw: str | None) -> PaymentMode:
    value = (raw or "").upper()
    if "UPI" in value:
        return PaymentMode.UPI
    if "CASH" in value:
        return PaymentMode.CASH
    if "CARD" in value:
        return PaymentMode.CARD
    return PaymentMode.ONLINE


def _resolve_integration(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    integration_id: int | None,
) -> OutletPaymentIntegration:
    if integration_id is not None:
        return _get_integration_entity(db, tenant_id, integration_id)

    integration = (
        db.query(OutletPaymentIntegration)
        .filter(
            OutletPaymentIntegration.tenant_id == tenant_id,
            OutletPaymentIntegration.outlet_id == outlet_id,
            OutletPaymentIntegration.is_enabled.is_(True),
            OutletPaymentIntegration.is_active.is_(True),
            OutletPaymentIntegration.status == IntegrationStatus.ACTIVE,
        )
        .order_by(OutletPaymentIntegration.id.desc())
        .first()
    )
    if integration is None:
        raise ConflictError("No active payment integration found for this outlet")
    return integration


def _build_credentials(integration: OutletPaymentIntegration) -> ProviderCredentials:
    return ProviderCredentials(
        merchant_id=integration.merchant_id,
        store_id=integration.store_id,
        client_id=integration.client_id,
        security_token=decrypt_secret(integration.encrypted_security_token),
        api_key=decrypt_secret(integration.encrypted_api_key),
        config=_load_config(integration),
    )


def _load_config(integration: OutletPaymentIntegration) -> dict:
    try:
        return json.loads(integration.config_json or "{}")
    except json.JSONDecodeError:
        return {}


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_integration_entity(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> OutletPaymentIntegration:
    row = (
        db.query(OutletPaymentIntegration)
        .filter(
            OutletPaymentIntegration.id == integration_id,
            OutletPaymentIntegration.tenant_id == tenant_id,
            OutletPaymentIntegration.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise NotFoundError("Payment integration not found")
    return row


def _get_bill_entity(db: Session, tenant_id: int, bill_id: int) -> Bill:
    bill = (
        db.query(Bill)
        .filter(Bill.id == bill_id, Bill.tenant_id == tenant_id, Bill.is_active.is_(True))
        .first()
    )
    if bill is None:
        raise NotFoundError("Bill not found")
    return bill


def _get_terminal_payment_entity(
    db: Session,
    tenant_id: int,
    terminal_payment_id: int,
) -> TerminalPayment:
    row = (
        db.query(TerminalPayment)
        .options(joinedload(TerminalPayment.integration))
        .filter(
            TerminalPayment.id == terminal_payment_id,
            TerminalPayment.tenant_id == tenant_id,
            TerminalPayment.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise NotFoundError("Terminal payment not found")
    return row


def _to_integration_read(integration: OutletPaymentIntegration) -> IntegrationRead:
    return IntegrationRead(
        id=integration.id,
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        outlet_id=integration.outlet_id,
        provider=integration.provider,
        merchant_id=integration.merchant_id,
        store_id=integration.store_id,
        client_id=integration.client_id,
        status=integration.status,
        is_enabled=integration.is_enabled,
        auto_settle_on_success=integration.auto_settle_on_success,
        webhook_token=integration.webhook_token,
        config=_load_config(integration),
        has_security_token=bool(integration.encrypted_security_token),
        has_api_key=bool(integration.encrypted_api_key),
        last_sync_at=integration.last_sync_at,
        last_error=integration.last_error,
        postback_url=build_postback_url(integration.webhook_token),
        is_active=integration.is_active,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


def _to_terminal_payment_read(db: Session, payment: TerminalPayment) -> TerminalPaymentRead:
    bill = db.get(Bill, payment.bill_id)
    integration = db.get(OutletPaymentIntegration, payment.integration_id)
    return TerminalPaymentRead(
        id=payment.id,
        integration_id=payment.integration_id,
        bill_id=payment.bill_id,
        pos_payment_id=payment.pos_payment_id,
        transaction_number=payment.transaction_number,
        sequence_number=payment.sequence_number,
        amount=float(payment.amount),
        payment_mode=payment.payment_mode,
        allowed_payment_mode=payment.allowed_payment_mode,
        status=payment.status,
        provider_reference_id=payment.provider_reference_id,
        auth_code=payment.auth_code,
        reference_number=payment.reference_number,
        error_message=payment.error_message,
        provider=integration.provider if integration else None,
        bill_number=bill.bill_number if bill else None,
        is_active=payment.is_active,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


def list_public_online_gateways(db: Session, outlet_id: int) -> list[PublicOnlineGatewayRead]:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.is_active.is_(True)).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")

    rows = (
        db.query(OutletPaymentIntegration)
        .filter(
            OutletPaymentIntegration.outlet_id == outlet_id,
            OutletPaymentIntegration.is_active.is_(True),
            OutletPaymentIntegration.is_enabled.is_(True),
            OutletPaymentIntegration.status == IntegrationStatus.ACTIVE,
            OutletPaymentIntegration.provider.in_(tuple(ONLINE_CHECKOUT_PROVIDERS)),
        )
        .order_by(OutletPaymentIntegration.provider.asc())
        .all()
    )
    gateways: list[PublicOnlineGatewayRead] = []
    for row in rows:
        label, description = PROVIDER_LABELS.get(
            row.provider, (row.provider.value.title(), "Online payments")
        )
        gateways.append(
            PublicOnlineGatewayRead(provider=row.provider, label=label, description=description)
        )
    # Demo fallback so guest booking always has a gateway when none configured.
    if not gateways:
        for provider in (
            PaymentProvider.RAZORPAY,
            PaymentProvider.PHONEPE,
            PaymentProvider.CASHFREE,
            PaymentProvider.CCAVENUE,
            PaymentProvider.PAYTM,
        ):
            label, description = PROVIDER_LABELS[provider]
            gateways.append(
                PublicOnlineGatewayRead(provider=provider, label=label, description=description)
            )
    return gateways


async def create_online_checkout_charge(
    db: Session,
    data: OnlineCheckoutCreate,
) -> OnlineCheckoutResponse:
    if not supports_online_checkout(data.provider):
        raise ConflictError(f"{data.provider.value} does not support online checkout")

    outlet = db.query(Outlet).filter(Outlet.id == data.outlet_id, Outlet.is_active.is_(True)).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")

    integration = (
        db.query(OutletPaymentIntegration)
        .filter(
            OutletPaymentIntegration.outlet_id == data.outlet_id,
            OutletPaymentIntegration.provider == data.provider,
            OutletPaymentIntegration.is_active.is_(True),
        )
        .first()
    )
    # Allow mock demo charge without a saved integration.
    credentials = (
        _build_credentials(integration)
        if integration is not None
        else ProviderCredentials(
            merchant_id=f"DEMO-{data.provider.value.upper()}",
            api_key="demo-key",
            client_id=f"demo-{data.provider.value}",
            config={"mode": "mock"},
        )
    )
    provider = get_payment_provider(data.provider, credentials)
    checkout = await provider.create_online_checkout(
        credentials,
        OnlineCheckoutRequest(
            order_id=data.order_id,
            amount_inr=float(data.amount),
            customer_name=data.customer_name,
            customer_email=data.customer_email,
            customer_phone=data.customer_phone,
            purpose=data.purpose,
            return_url=data.return_url,
            cancel_url=data.cancel_url,
        ),
    )
    if not checkout.success:
        raise ConflictError(checkout.message or "Unable to start payment")

    verified = await provider.verify_online_payment(
        credentials,
        provider_order_id=checkout.provider_order_id or data.order_id,
        payment_session_id=checkout.payment_session_id,
        card_last4=data.card_last4,
    )
    if not verified.paid:
        raise ConflictError(verified.message or "Payment was not completed")

    return OnlineCheckoutResponse(
        provider=data.provider,
        paid=True,
        provider_order_id=checkout.provider_order_id,
        payment_session_id=checkout.payment_session_id,
        provider_payment_id=verified.provider_payment_id,
        amount=float(data.amount),
        message=verified.message or "Payment successful",
        checkout_url=checkout.checkout_url,
        card_last4=data.card_last4,
    )
