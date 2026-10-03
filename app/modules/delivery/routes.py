from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.delivery import service
from app.modules.delivery.models import DeliveryPlatform, ExternalOrderStatus
from app.modules.delivery.providers.registry import get_delivery_provider
from app.modules.delivery.schemas import (
    DeliveryOrderAction,
    DeliveryOrderRead,
    InboundOrderPayload,
    IntegrationCreate,
    IntegrationDeleteResponse,
    IntegrationRead,
    IntegrationUpdate,
    MenuMappingCreate,
    MenuMappingRead,
    MenuMappingUpdate,
    MockOrderRequest,
    PlatformInfo,
    WebhookAckResponse,
)
from app.modules.users.models import User
from app.utils.encryption import decrypt_secret

router = APIRouter()


@router.get("/platforms", response_model=list[PlatformInfo])
def list_platforms(
    current_user: User = Depends(require_permission(Permission.DELIVERY_READ)),
) -> list[PlatformInfo]:
    return service.list_platforms()


@router.get("/integrations", response_model=PaginatedSuccessResponse[IntegrationRead])
def list_integrations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    platform: DeliveryPlatform | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_READ)),
) -> PaginatedSuccessResponse[IntegrationRead]:
    items, total = service.list_integrations(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        platform=platform,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/integrations", response_model=IntegrationRead, status_code=status.HTTP_201_CREATED)
def create_integration(
    body: IntegrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
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
    current_user: User = Depends(require_permission(Permission.DELIVERY_READ)),
) -> IntegrationRead:
    return service.get_integration(db, current_user.tenant_id, integration_id)


@router.patch("/integrations/{integration_id}", response_model=IntegrationRead)
def update_integration(
    integration_id: int,
    body: IntegrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> IntegrationRead:
    return service.update_integration(db, current_user.tenant_id, integration_id, body)


@router.delete("/integrations/{integration_id}", response_model=IntegrationDeleteResponse)
def delete_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> IntegrationDeleteResponse:
    return service.delete_integration(db, current_user.tenant_id, integration_id)


@router.post("/integrations/{integration_id}/test", response_model=IntegrationRead)
async def test_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> IntegrationRead:
    return await service.test_integration_connection(db, current_user.tenant_id, integration_id)


@router.get("/integrations/{integration_id}/menu-mappings", response_model=list[MenuMappingRead])
def list_menu_mappings(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_READ)),
) -> list[MenuMappingRead]:
    return service.list_menu_mappings(db, current_user.tenant_id, integration_id)


@router.post(
    "/integrations/{integration_id}/menu-mappings",
    response_model=MenuMappingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_menu_mapping(
    integration_id: int,
    body: MenuMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> MenuMappingRead:
    return service.create_menu_mapping(db, current_user.tenant_id, integration_id, body)


@router.patch(
    "/integrations/{integration_id}/menu-mappings/{mapping_id}",
    response_model=MenuMappingRead,
)
def update_menu_mapping(
    integration_id: int,
    mapping_id: int,
    body: MenuMappingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> MenuMappingRead:
    return service.update_menu_mapping(
        db,
        current_user.tenant_id,
        integration_id,
        mapping_id,
        body,
    )


@router.get("/orders", response_model=PaginatedSuccessResponse[DeliveryOrderRead])
def list_delivery_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    platform: DeliveryPlatform | None = Query(None),
    external_status: ExternalOrderStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_READ)),
) -> PaginatedSuccessResponse[DeliveryOrderRead]:
    items, total = service.list_delivery_orders(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        platform=platform,
        external_status=external_status,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/orders/{delivery_order_id}", response_model=DeliveryOrderRead)
def get_delivery_order(
    delivery_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_READ)),
) -> DeliveryOrderRead:
    return service.get_delivery_order(db, current_user.tenant_id, delivery_order_id)


@router.post("/orders/{delivery_order_id}/accept", response_model=DeliveryOrderRead)
async def accept_delivery_order(
    delivery_order_id: int,
    body: DeliveryOrderAction | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> DeliveryOrderRead:
    notes = body.notes if body else None
    return await service.accept_delivery_order(
        db,
        current_user.tenant_id,
        delivery_order_id,
        notes=notes,
    )


@router.post("/orders/{delivery_order_id}/reject", response_model=DeliveryOrderRead)
async def reject_delivery_order(
    delivery_order_id: int,
    body: DeliveryOrderAction | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> DeliveryOrderRead:
    notes = body.notes if body else None
    return await service.reject_delivery_order(
        db,
        current_user.tenant_id,
        delivery_order_id,
        notes=notes,
    )


@router.post("/orders/{delivery_order_id}/ready", response_model=DeliveryOrderRead)
async def mark_delivery_order_ready(
    delivery_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> DeliveryOrderRead:
    return await service.mark_delivery_order_ready(
        db,
        current_user.tenant_id,
        delivery_order_id,
    )


@router.post(
    "/integrations/{integration_id}/simulate-order",
    response_model=DeliveryOrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def simulate_mock_order(
    integration_id: int,
    body: MockOrderRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELIVERY_WRITE)),
) -> DeliveryOrderRead:
    return await service.simulate_mock_order(
        db,
        current_user.tenant_id,
        integration_id,
        body or MockOrderRequest(),
    )


@router.post("/webhooks/{webhook_token}", response_model=WebhookAckResponse)
async def receive_delivery_webhook(
    webhook_token: str,
    body: InboundOrderPayload,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> WebhookAckResponse:
    from app.modules.delivery.models import OutletDeliveryIntegration

    integration = (
        db.query(OutletDeliveryIntegration)
        .filter(
            OutletDeliveryIntegration.webhook_token == webhook_token,
            OutletDeliveryIntegration.is_active.is_(True),
        )
        .first()
    )
    if integration is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Delivery integration not found")

    provider = get_delivery_provider(integration.platform)
    payload_bytes = body.model_dump_json().encode("utf-8")
    if not provider.verify_webhook_signature(
        payload=payload_bytes,
        signature=x_signature,
        webhook_secret=decrypt_secret(integration.encrypted_webhook_secret),
    ):
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Invalid webhook signature")

    return await service.ingest_inbound_order(
        db,
        webhook_token,
        body,
        raw_payload=body.model_dump(),
    )
