from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.modules.ota import service
from app.modules.ota.models import OtaPlatform
from app.modules.ota.providers.registry import get_ota_provider
from app.modules.ota.schemas import (
    AutoAriPushResponse,
    AriPreviewRead,
    AriPushRequest,
    AriPushResponse,
    InboundOtaReservationPayload,
    IntegrationCreate,
    IntegrationDeleteResponse,
    IntegrationRead,
    IntegrationUpdate,
    MockOtaReservationRequest,
    MockOtaReservationActionRequest,
    OtaReservationRead,
    OtaSyncLogRead,
    PlatformInfo,
    RatePlanMappingCreate,
    RatePlanMappingRead,
    ReservationPullResponse,
    RoomTypeMappingCreate,
    RoomTypeMappingRead,
    WebhookAckResponse,
)
from app.modules.users.models import User
from app.utils.encryption import decrypt_secret

router = APIRouter()


@router.get("/platforms", response_model=list[PlatformInfo])
def list_platforms(
    current_user: User = Depends(require_permission(Permission.OTA_READ)),
) -> list[PlatformInfo]:
    return service.list_platforms()


@router.get("/integrations", response_model=PaginatedSuccessResponse[IntegrationRead])
def list_integrations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    platform: OtaPlatform | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_READ)),
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
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
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
    current_user: User = Depends(require_permission(Permission.OTA_READ)),
) -> IntegrationRead:
    return service.get_integration(db, current_user.tenant_id, integration_id)


@router.patch("/integrations/{integration_id}", response_model=IntegrationRead)
def update_integration(
    integration_id: int,
    body: IntegrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> IntegrationRead:
    return service.update_integration(db, current_user.tenant_id, integration_id, body)


@router.delete("/integrations/{integration_id}", response_model=IntegrationDeleteResponse)
def delete_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> IntegrationDeleteResponse:
    return service.delete_integration(db, current_user.tenant_id, integration_id)


@router.post("/integrations/{integration_id}/test", response_model=IntegrationRead)
async def test_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> IntegrationRead:
    return await service.test_integration_connection(db, current_user.tenant_id, integration_id)


@router.get("/integrations/{integration_id}/room-mappings", response_model=list[RoomTypeMappingRead])
def list_room_mappings(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_READ)),
) -> list[RoomTypeMappingRead]:
    return service.list_room_mappings(db, current_user.tenant_id, integration_id)


@router.post(
    "/integrations/{integration_id}/room-mappings",
    response_model=RoomTypeMappingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_room_mapping(
    integration_id: int,
    body: RoomTypeMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> RoomTypeMappingRead:
    return service.create_room_mapping(db, current_user.tenant_id, integration_id, body)


@router.delete(
    "/integrations/{integration_id}/room-mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_room_mapping(
    integration_id: int,
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> Response:
    service.delete_room_mapping(db, current_user.tenant_id, integration_id, mapping_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/integrations/{integration_id}/rate-plan-mappings",
    response_model=list[RatePlanMappingRead],
)
def list_rate_plan_mappings(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_READ)),
) -> list[RatePlanMappingRead]:
    return service.list_rate_plan_mappings(db, current_user.tenant_id, integration_id)


@router.post(
    "/integrations/{integration_id}/rate-plan-mappings",
    response_model=RatePlanMappingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_rate_plan_mapping(
    integration_id: int,
    body: RatePlanMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> RatePlanMappingRead:
    return service.create_rate_plan_mapping(db, current_user.tenant_id, integration_id, body)


@router.delete(
    "/integrations/{integration_id}/rate-plan-mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_rate_plan_mapping(
    integration_id: int,
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> Response:
    service.delete_rate_plan_mapping(db, current_user.tenant_id, integration_id, mapping_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reservations", response_model=PaginatedSuccessResponse[OtaReservationRead])
def list_ota_reservations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    platform: OtaPlatform | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_READ)),
) -> PaginatedSuccessResponse[OtaReservationRead]:
    items, total = service.list_ota_reservations(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        platform=platform,
    )
    return success_paginated(items, total, page, page_size)


@router.post(
    "/integrations/{integration_id}/simulate-reservation",
    response_model=OtaReservationRead,
    status_code=status.HTTP_201_CREATED,
)
async def simulate_mock_reservation(
    integration_id: int,
    body: MockOtaReservationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> OtaReservationRead:
    return await service.simulate_mock_reservation(
        db,
        current_user.tenant_id,
        integration_id,
        body or MockOtaReservationRequest(),
    )


@router.post(
    "/integrations/{integration_id}/simulate-modify",
    response_model=OtaReservationRead,
)
async def simulate_modify_reservation(
    integration_id: int,
    body: MockOtaReservationActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> OtaReservationRead:
    return await service.simulate_modify_reservation(
        db,
        current_user.tenant_id,
        integration_id,
        body,
    )


@router.post(
    "/integrations/{integration_id}/simulate-cancel",
    response_model=OtaReservationRead,
)
async def simulate_cancel_reservation(
    integration_id: int,
    body: MockOtaReservationActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> OtaReservationRead:
    return await service.simulate_cancel_reservation(
        db,
        current_user.tenant_id,
        integration_id,
        body,
    )


@router.get("/integrations/{integration_id}/ari-preview", response_model=AriPreviewRead)
def preview_ari(
    integration_id: int,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    max_days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_READ)),
) -> AriPreviewRead:
    request = AriPushRequest(start_date=start_date, end_date=end_date, max_days=max_days)
    return service.get_ari_preview(db, current_user.tenant_id, integration_id, request)


@router.post("/integrations/{integration_id}/push-ari", response_model=AriPushResponse)
async def push_ari(
    integration_id: int,
    body: AriPushRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> AriPushResponse:
    return await service.push_ari(
        db,
        current_user.tenant_id,
        integration_id,
        body or AriPushRequest(),
    )


@router.post(
    "/integrations/{integration_id}/pull-reservations",
    response_model=ReservationPullResponse,
)
async def pull_reservations(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> ReservationPullResponse:
    return await service.pull_reservations(
        db,
        current_user.tenant_id,
        integration_id,
    )


@router.get(
    "/integrations/{integration_id}/sync-logs",
    response_model=PaginatedSuccessResponse[OtaSyncLogRead],
)
def list_sync_logs(
    integration_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_READ)),
) -> PaginatedSuccessResponse[OtaSyncLogRead]:
    items, total = service.list_sync_logs(
        db,
        current_user.tenant_id,
        integration_id,
        page,
        page_size,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/push-auto-ari", response_model=AutoAriPushResponse)
async def push_auto_ari(
    outlet_id: int | None = Query(None),
    max_days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OTA_WRITE)),
) -> AutoAriPushResponse:
    request = AriPushRequest(max_days=max_days)
    if outlet_id is not None:
        return await service.push_auto_ari_for_outlet(
            db,
            current_user.tenant_id,
            outlet_id,
            request,
        )
    return await service.push_auto_ari_for_tenant(db, current_user.tenant_id, request)


@router.post("/webhooks/{webhook_token}", response_model=WebhookAckResponse)
async def receive_ota_webhook(
    webhook_token: str,
    body: InboundOtaReservationPayload,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> WebhookAckResponse:
    from app.modules.ota.models import OutletOtaIntegration

    integration = (
        db.query(OutletOtaIntegration)
        .filter(
            OutletOtaIntegration.webhook_token == webhook_token,
            OutletOtaIntegration.is_active.is_(True),
        )
        .first()
    )
    if integration is None:
        raise NotFoundError("OTA integration not found")

    import json

    config = json.loads(integration.config_json or "{}")
    provider = get_ota_provider(integration.platform, config)
    payload_bytes = body.model_dump_json().encode("utf-8")
    if not provider.verify_webhook_signature(
        payload=payload_bytes,
        signature=x_signature,
        webhook_secret=decrypt_secret(integration.encrypted_webhook_secret),
    ):
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Invalid webhook signature")

    return await service.ingest_inbound_reservation(
        db,
        webhook_token,
        body,
        raw_payload=body.model_dump(mode="json"),
    )
