from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.payments import service
from app.modules.payments.models import PaymentProvider, TerminalPaymentStatus
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
from app.modules.users.models import User

router = APIRouter()


@router.get("/public/gateways", response_model=list[PublicOnlineGatewayRead])
def list_public_gateways(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
) -> list[PublicOnlineGatewayRead]:
    return service.list_public_online_gateways(db, outlet_id)


@router.post("/public/checkout", response_model=OnlineCheckoutResponse)
async def public_online_checkout(
    body: OnlineCheckoutCreate,
    db: Session = Depends(get_db),
) -> OnlineCheckoutResponse:
    return await service.create_online_checkout_charge(db, body)


@router.get("/providers", response_model=list[ProviderInfo])
def list_providers(
    current_user: User = Depends(require_permission(Permission.PAYMENTS_READ)),
) -> list[ProviderInfo]:
    return service.list_providers()


@router.get("/integrations", response_model=PaginatedSuccessResponse[IntegrationRead])
def list_integrations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    provider: PaymentProvider | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PAYMENTS_READ)),
) -> PaginatedSuccessResponse[IntegrationRead]:
    items, total = service.list_integrations(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        provider=provider,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/integrations", response_model=IntegrationRead, status_code=status.HTTP_201_CREATED)
def create_integration(
    body: IntegrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PAYMENTS_WRITE)),
) -> IntegrationRead:
    return service.create_integration(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/integrations/{integration_id}", response_model=IntegrationRead)
def get_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PAYMENTS_READ)),
) -> IntegrationRead:
    return service.get_integration(db, current_user.tenant_id, integration_id)


@router.patch("/integrations/{integration_id}", response_model=IntegrationRead)
def update_integration(
    integration_id: int,
    body: IntegrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PAYMENTS_WRITE)),
) -> IntegrationRead:
    return service.update_integration(db, current_user.tenant_id, integration_id, body)


@router.delete("/integrations/{integration_id}", response_model=IntegrationDeleteResponse)
def delete_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PAYMENTS_WRITE)),
) -> IntegrationDeleteResponse:
    return service.delete_integration(db, current_user.tenant_id, integration_id)


@router.post("/integrations/{integration_id}/test", response_model=IntegrationRead)
async def test_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PAYMENTS_WRITE)),
) -> IntegrationRead:
    return await service.test_integration_connection(db, current_user.tenant_id, integration_id)


@router.get("/transactions", response_model=PaginatedSuccessResponse[TerminalPaymentRead])
def list_terminal_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    bill_id: int | None = Query(None),
    status: TerminalPaymentStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PAYMENTS_READ)),
) -> PaginatedSuccessResponse[TerminalPaymentRead]:
    items, total = service.list_terminal_payments(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        bill_id=bill_id,
        status=status,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/transactions/initiate", response_model=TerminalPaymentRead, status_code=status.HTTP_201_CREATED)
async def initiate_terminal_payment(
    body: InitiatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TerminalPaymentRead:
    return await service.initiate_terminal_payment(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
    )


@router.post("/transactions/{terminal_payment_id}/refresh", response_model=TerminalPaymentRead)
async def refresh_terminal_payment(
    terminal_payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TerminalPaymentRead:
    return await service.refresh_terminal_payment_status(
        db,
        current_user.tenant_id,
        terminal_payment_id,
        current_user.id,
    )


@router.post("/transactions/{terminal_payment_id}/simulate-complete", response_model=TerminalPaymentRead)
async def simulate_terminal_payment(
    terminal_payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PAYMENTS_WRITE)),
) -> TerminalPaymentRead:
    return await service.simulate_terminal_payment_complete(
        db,
        current_user.tenant_id,
        terminal_payment_id,
        current_user.id,
    )


@router.post("/webhooks/{webhook_token}", response_model=PostbackAckResponse)
async def receive_payment_postback(
    webhook_token: str,
    db: Session = Depends(get_db),
    ResponseCode: str | None = Form(default=None),
    ResponseMessage: str | None = Form(default=None),
    PlutusTransactionReferenceID: str | None = Form(default=None),
    TransactionNumber: str | None = Form(default=None),
    PaymenMode: str | None = Form(default=None),
    PaymentMode: str | None = Form(default=None),
    ApprovalCode: str | None = Form(default=None),
    RRN: str | None = Form(default=None),
    TransactionLogId: str | None = Form(default=None),
    Amount: str | None = Form(default=None),
) -> PostbackAckResponse:
    payload = {
        key: value
        for key, value in {
            "ResponseCode": ResponseCode,
            "ResponseMessage": ResponseMessage,
            "PlutusTransactionReferenceID": PlutusTransactionReferenceID,
            "TransactionNumber": TransactionNumber,
            "PaymenMode": PaymenMode,
            "PaymentMode": PaymentMode,
            "ApprovalCode": ApprovalCode,
            "RRN": RRN,
            "TransactionLogId": TransactionLogId,
            "Amount": Amount,
        }.items()
        if value is not None
    }
    return await service.ingest_postback(db, webhook_token, payload)
