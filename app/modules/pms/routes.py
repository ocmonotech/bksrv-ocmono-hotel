from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.pms import service
from app.modules.pms.models import ReservationSource, ReservationStatus
from app.modules.pms.schemas import (
    AssignRoomRequest,
    AvailabilityResponse,
    CancelReservationRequest,
    CaptureDepositRequest,
    CardHoldReleaseRequest,
    CardHoldRequest,
    CashierShiftCloseRequest,
    CashierShiftOpenRequest,
    CashierShiftRead,
    CheckInRequest,
    CheckOutRequest,
    CityLedgerRead,
    CityLedgerSettleRequest,
    CityLedgerTransferRequest,
    CityLedgerTransferResponse,
    CityLedgerWriteOffRequest,
    FolioChargeCreate,
    FolioEmailRequest,
    FolioEmailResponse,
    FolioEntryVoidRequest,
    FolioPaymentCreate,
    FolioRead,
    FolioTransferToMasterRequest,
    FrontDeskReadinessResponse,
    GroupFolioCloseRequest,
    GroupFolioSweepRequest,
    GroupRoomingCreate,
    GuestServiceRequestFulfillRequest,
    GuestServiceRequestFulfillResponse,
    GuestServiceRequestRead,
    GuestServiceRequestStatus,
    GuestStayHistoryRead,
    InHouseGuestRead,
    MoveRoomRequest,
    NightAuditLogRead,
    NightAuditResult,
    NightAuditRunRequest,
    AccountsDayBookRead,
    PmsDashboard,
    PmsReportsSummary,
    PickupCalendarResponse,
    RateInventoryCalendarResponse,
    RateInventoryOverrideUpsert,
    SpecialRequestFulfillResponse,
    PostToRoomRequest,
    PostToRoomResponse,
    PublicReservationCreate,
    PublicReservationResponse,
    PublicReservationStatus,
    PublicCardHoldCreate,
    PublicCancelRequest,
    PublicFolioEmailRequest,
    PublicModifyStayRequest,
    PublicPreCheckInRequest,
    PreCheckInReviewRequest,
    PublicRoomHubClaimRequest,
    PublicExpressCheckoutRequest,
    ExpressCheckoutCompleteRequest,
    PublicRoomHubUpsellRequest,
    PackageEntitlementClaimRequest,
    PackageEntitlementClaimRead,
    PublicStayModifiersRequest,
    PublicSpecialRequest,
    PublicStayFeedbackRequest,
    PublicAddonRead,
    PublicRoomHubResponse,
    PublicRoomTypeRead,
    PublicGuestServiceRequestRead,
    PublicServiceRequestCreate,
    PublicServiceRequestResponse,
    PmsNotificationKind,
    PmsNotificationRequest,
    PmsNotificationResponse,
    RatePlanCreate,
    RatePlanInclusionCreate,
    RatePlanInclusionRead,
    RatePlanRead,
    RatePlanUpdate,
    RefundDepositRequest,
    ReservationCreate,
    ReservationDetailRead,
    ReservationConfirmRequest,
    ReservationGroupCreate,
    ReservationGroupRead,
    ReservationGroupUpdate,
    ReservationRead,
    ReservationUpdate,
    RoomBlockCreate,
    RoomBlockRead,
    RoomBlockUpdate,
    StayModifierUpdate,
    TapeChartResponse,
    WalkInCreate,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/public/room-types", response_model=list[PublicRoomTypeRead])
def list_public_room_types(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
) -> list[PublicRoomTypeRead]:
    return service.list_public_room_types(db, outlet_id)


@router.get("/public/addons", response_model=list[PublicAddonRead])
def list_public_addons() -> list[PublicAddonRead]:
    return service.list_public_addons()


@router.get("/public/availability", response_model=AvailabilityResponse)
def public_room_availability(
    outlet_id: int = Query(...),
    check_in_date: date = Query(...),
    check_out_date: date = Query(...),
    db: Session = Depends(get_db),
) -> AvailabilityResponse:
    return service.get_public_availability(db, outlet_id, check_in_date, check_out_date)


@router.post("/public/reservations", response_model=PublicReservationResponse, status_code=status.HTTP_201_CREATED)
async def submit_public_reservation(
    body: PublicReservationCreate,
    db: Session = Depends(get_db),
) -> PublicReservationResponse:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType
    from app.modules.outlets.models import Outlet

    result = await service.submit_public_reservation(db, body)
    outlet = db.query(Outlet).filter(Outlet.id == body.outlet_id).first()
    if outlet is not None:
        await service.send_public_reservation_acknowledgment(db, outlet.tenant_id, result.reservation_id)
        reservation = service.get_reservation(db, outlet.tenant_id, result.reservation_id)
        await automation_service.dispatch_trigger(
            db,
            outlet.tenant_id,
            AutomationTriggerType.RESERVATION_CREATED,
            service.build_reservation_automation_payload(reservation),
        )
    return result


@router.get("/public/reservations/lookup", response_model=PublicReservationStatus)
def lookup_public_reservation(
    confirmation_number: str = Query(..., min_length=3, max_length=32),
    guest_mobile: str = Query(..., min_length=6, max_length=32),
    db: Session = Depends(get_db),
) -> PublicReservationStatus:
    return service.lookup_public_reservation(db, confirmation_number, guest_mobile)


@router.post("/public/reservations/payment/hold", response_model=PublicReservationStatus)
def place_public_card_hold(
    body: PublicCardHoldCreate,
    db: Session = Depends(get_db),
) -> PublicReservationStatus:
    return service.place_public_card_hold(db, body)


@router.post("/public/reservations/cancel", response_model=PublicReservationStatus)
def cancel_public_reservation(
    body: PublicCancelRequest,
    db: Session = Depends(get_db),
) -> PublicReservationStatus:
    return service.cancel_public_reservation(db, body)


@router.post("/public/reservations/modify", response_model=PublicReservationStatus)
def modify_public_reservation(
    body: PublicModifyStayRequest,
    db: Session = Depends(get_db),
) -> PublicReservationStatus:
    return service.modify_public_reservation(db, body)


@router.post("/public/reservations/stay-modifiers", response_model=PublicReservationStatus)
def modify_public_stay_modifiers(
    body: PublicStayModifiersRequest,
    db: Session = Depends(get_db),
) -> PublicReservationStatus:
    return service.modify_public_stay_modifiers(db, body)


@router.post("/public/reservations/special-request", response_model=PublicReservationStatus)
def add_public_special_request(
    body: PublicSpecialRequest,
    db: Session = Depends(get_db),
) -> PublicReservationStatus:
    return service.add_public_special_request(db, body)


@router.post("/public/reservations/pre-check-in", response_model=PublicReservationStatus)
def submit_public_pre_check_in(
    body: PublicPreCheckInRequest,
    db: Session = Depends(get_db),
) -> PublicReservationStatus:
    return service.submit_public_pre_check_in(db, body)


@router.post("/public/room-hub/claim", response_model=PackageEntitlementClaimRead)
def public_claim_package_entitlement(
    body: PublicRoomHubClaimRequest,
    db: Session = Depends(get_db),
) -> PackageEntitlementClaimRead:
    return service.public_claim_package_entitlement(db, body)


@router.post("/public/room-hub/express-checkout", response_model=PublicRoomHubResponse)
def submit_public_express_checkout(
    body: PublicExpressCheckoutRequest,
    db: Session = Depends(get_db),
) -> PublicRoomHubResponse:
    return service.submit_public_express_checkout(db, body)


@router.post("/public/room-hub/upsell", response_model=PublicRoomHubResponse)
def submit_public_room_hub_upsell(
    body: PublicRoomHubUpsellRequest,
    db: Session = Depends(get_db),
) -> PublicRoomHubResponse:
    return service.submit_public_room_hub_upsell(db, body)


@router.get("/public/room-hub", response_model=PublicRoomHubResponse)
def get_public_room_hub(
    outlet_id: int = Query(...),
    room_number: str = Query(..., min_length=1, max_length=32),
    guest_mobile: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
) -> PublicRoomHubResponse:
    return service.get_public_room_hub(db, outlet_id, room_number, guest_mobile=guest_mobile)


@router.post(
    "/public/service-requests",
    response_model=PublicServiceRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_public_service_request(
    body: PublicServiceRequestCreate,
    db: Session = Depends(get_db),
) -> PublicServiceRequestResponse:
    return service.create_public_service_request(db, body)


@router.get(
    "/public/service-requests",
    response_model=list[PublicGuestServiceRequestRead],
)
def list_public_service_requests(
    outlet_id: int = Query(...),
    room_number: str = Query(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
) -> list[PublicGuestServiceRequestRead]:
    return service.list_public_service_requests(db, outlet_id, room_number)


@router.post("/public/reservations/feedback", response_model=PublicReservationStatus)
def submit_public_stay_feedback(
    body: PublicStayFeedbackRequest,
    db: Session = Depends(get_db),
) -> PublicReservationStatus:
    return service.submit_public_stay_feedback(db, body)


@router.get("/public/reservations/folio/pdf")
def download_public_folio_pdf(
    confirmation_number: str = Query(..., min_length=3, max_length=32),
    guest_mobile: str = Query(..., min_length=6, max_length=32),
    db: Session = Depends(get_db),
) -> Response:
    pdf_bytes, filename = service.build_public_folio_pdf(
        db, confirmation_number, guest_mobile
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/public/reservations/folio/email",
    response_model=FolioEmailResponse,
)
async def email_public_folio(
    body: PublicFolioEmailRequest,
    db: Session = Depends(get_db),
) -> FolioEmailResponse:
    return await service.email_public_folio_statement(db, body)


@router.get("/dashboard", response_model=PmsDashboard)
def pms_dashboard(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> PmsDashboard:
    return service.get_dashboard(db, current_user.tenant_id, outlet_id)


@router.get("/front-desk/readiness", response_model=FrontDeskReadinessResponse)
def front_desk_readiness(
    outlet_id: int = Query(...),
    business_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> FrontDeskReadinessResponse:
    return service.get_front_desk_readiness(
        db, current_user.tenant_id, outlet_id, business_date
    )


@router.get("/availability", response_model=AvailabilityResponse)
def room_availability(
    outlet_id: int = Query(...),
    check_in_date: date = Query(...),
    check_out_date: date = Query(...),
    source: ReservationSource | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> AvailabilityResponse:
    return service.get_availability(
        db,
        current_user.tenant_id,
        outlet_id,
        check_in_date,
        check_out_date,
        source=source,
    )


@router.get("/rate-plans", response_model=list[RatePlanRead])
def list_rate_plans(
    room_type_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[RatePlanRead]:
    return service.list_rate_plans(db, current_user.tenant_id, room_type_id)


@router.post("/rate-plans", response_model=RatePlanRead, status_code=status.HTTP_201_CREATED)
def create_rate_plan(
    body: RatePlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> RatePlanRead:
    return service.create_rate_plan(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/rate-plans/{plan_id}", response_model=RatePlanRead)
def update_rate_plan(
    plan_id: int,
    body: RatePlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> RatePlanRead:
    return service.update_rate_plan(db, current_user.tenant_id, plan_id, body)


@router.delete("/rate-plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def deactivate_rate_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> Response:
    service.deactivate_rate_plan(db, current_user.tenant_id, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/rate-plans/{plan_id}/inclusions", response_model=list[RatePlanInclusionRead])
def list_rate_plan_inclusions(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[RatePlanInclusionRead]:
    return service.list_rate_plan_inclusions(db, current_user.tenant_id, plan_id)


@router.post(
    "/rate-plans/{plan_id}/inclusions",
    response_model=RatePlanInclusionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_rate_plan_inclusion(
    plan_id: int,
    body: RatePlanInclusionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> RatePlanInclusionRead:
    return service.create_rate_plan_inclusion(
        db,
        current_user.tenant_id,
        plan_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.delete(
    "/rate-plans/{plan_id}/inclusions/{inclusion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def deactivate_rate_plan_inclusion(
    plan_id: int,
    inclusion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> Response:
    service.deactivate_rate_plan_inclusion(db, current_user.tenant_id, plan_id, inclusion_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/in-house", response_model=list[InHouseGuestRead])
def list_in_house_guests(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[InHouseGuestRead]:
    return service.list_in_house_guests(db, current_user.tenant_id, outlet_id)


@router.post("/post-to-room", response_model=PostToRoomResponse, status_code=status.HTTP_201_CREATED)
def post_to_room(
    body: PostToRoomRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> PostToRoomResponse:
    return service.post_bill_to_room(db, current_user.tenant_id, current_user.id, body)


@router.get("/reservations", response_model=PaginatedSuccessResponse[ReservationRead])
def list_reservations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    status: ReservationStatus | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> PaginatedSuccessResponse[ReservationRead]:
    items, total = service.list_reservations(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        search=search,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/reservations", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    body: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType

    result = service.create_reservation(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )
    await automation_service.dispatch_trigger(
        db,
        current_user.tenant_id,
        AutomationTriggerType.RESERVATION_CREATED,
        service.build_reservation_automation_payload(result),
    )
    return result


@router.get("/reservations/{reservation_id}", response_model=ReservationDetailRead)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> ReservationDetailRead:
    return service.get_reservation(db, current_user.tenant_id, reservation_id)


@router.patch("/reservations/{reservation_id}", response_model=ReservationRead)
def update_reservation(
    reservation_id: int,
    body: ReservationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.update_reservation(db, current_user.tenant_id, reservation_id, body)


@router.post("/reservations/{reservation_id}/confirm", response_model=ReservationRead)
async def confirm_reservation(
    reservation_id: int,
    body: ReservationConfirmRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType

    payload = body or ReservationConfirmRequest()
    result = service.confirm_reservation(db, current_user.tenant_id, reservation_id)
    if payload.send_sms or payload.send_email or payload.send_whatsapp:
        await service.send_reservation_notifications(
            db,
            current_user.tenant_id,
            current_user.id,
            reservation_id,
            kind=PmsNotificationKind.CONFIRMATION,
            send_sms=payload.send_sms,
            send_email=payload.send_email,
            send_whatsapp=payload.send_whatsapp,
        )
    await automation_service.dispatch_trigger(
        db,
        current_user.tenant_id,
        AutomationTriggerType.GUEST_RESERVATION_CONFIRMED,
        service.build_reservation_automation_payload(result),
    )
    return result


@router.post("/reservations/{reservation_id}/send-notification", response_model=PmsNotificationResponse)
async def send_reservation_notification(
    reservation_id: int,
    body: PmsNotificationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> PmsNotificationResponse:
    payload = body or PmsNotificationRequest()
    return await service.send_reservation_notifications(
        db,
        current_user.tenant_id,
        current_user.id,
        reservation_id,
        kind=payload.kind,
        send_sms=payload.send_sms,
        send_email=payload.send_email,
        send_whatsapp=payload.send_whatsapp,
    )


@router.post("/reservations/{reservation_id}/check-in", response_model=ReservationDetailRead)
def check_in(
    reservation_id: int,
    body: CheckInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationDetailRead:
    return service.check_in_reservation(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )


@router.post("/reservations/{reservation_id}/pre-check-in/review", response_model=ReservationRead)
def review_pre_check_in(
    reservation_id: int,
    body: PreCheckInReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.review_pre_check_in(
        db, current_user.tenant_id, reservation_id, body
    )


@router.post(
    "/reservations/{reservation_id}/express-checkout/complete",
    response_model=ReservationDetailRead,
)
def complete_express_checkout(
    reservation_id: int,
    body: ExpressCheckoutCompleteRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationDetailRead:
    return service.complete_express_checkout(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )


@router.post(
    "/reservations/{reservation_id}/entitlements/{entitlement_id}/claim",
    response_model=PackageEntitlementClaimRead,
)
def staff_claim_package_entitlement(
    reservation_id: int,
    entitlement_id: int,
    body: PackageEntitlementClaimRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> PackageEntitlementClaimRead:
    return service.staff_claim_package_entitlement(
        db,
        current_user.tenant_id,
        current_user.id,
        reservation_id,
        entitlement_id,
        body or PackageEntitlementClaimRequest(),
    )


@router.post("/reservations/{reservation_id}/check-out", response_model=ReservationDetailRead)
async def check_out(
    reservation_id: int,
    body: CheckOutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationDetailRead:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType

    result = service.check_out_reservation(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )
    await automation_service.dispatch_trigger(
        db,
        current_user.tenant_id,
        AutomationTriggerType.GUEST_RESERVATION_CHECKED_OUT,
        service.build_reservation_automation_payload(result),
    )
    # Best-effort thank-you — never fail checkout if messaging is unavailable.
    try:
        if result.guest_email or result.guest_mobile:
            await service.send_reservation_notifications(
                db,
                current_user.tenant_id,
                current_user.id,
                reservation_id,
                kind=PmsNotificationKind.THANK_YOU,
                send_sms=bool(result.guest_mobile),
                send_email=bool(result.guest_email),
                send_whatsapp=bool(result.guest_mobile),
            )
    except Exception:
        pass
    return result


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(
    reservation_id: int,
    body: CancelReservationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.cancel_reservation(db, current_user.tenant_id, reservation_id, body)


@router.post("/reservations/{reservation_id}/no-show", response_model=ReservationRead)
def no_show(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.mark_no_show(db, current_user.tenant_id, reservation_id)


@router.post("/reservations/{reservation_id}/assign-room", response_model=ReservationRead)
def assign_room(
    reservation_id: int,
    body: AssignRoomRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.assign_room(db, current_user.tenant_id, reservation_id, body)


@router.post("/reservations/{reservation_id}/move-room", response_model=ReservationDetailRead)
def move_room(
    reservation_id: int,
    body: MoveRoomRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationDetailRead:
    return service.move_room(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )


@router.patch("/reservations/{reservation_id}/stay-modifiers", response_model=ReservationRead)
def apply_stay_modifiers(
    reservation_id: int,
    body: StayModifierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.apply_stay_modifiers(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )


@router.post("/reservations/{reservation_id}/payment/hold", response_model=ReservationRead)
def place_card_hold(
    reservation_id: int,
    body: CardHoldRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.place_card_hold(db, current_user.tenant_id, reservation_id, body)


@router.post("/reservations/{reservation_id}/payment/release", response_model=ReservationRead)
def release_card_hold(
    reservation_id: int,
    body: CardHoldReleaseRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.release_card_hold(
        db, current_user.tenant_id, reservation_id, body or CardHoldReleaseRequest()
    )


@router.post("/reservations/{reservation_id}/deposit/capture", response_model=ReservationRead)
def capture_deposit(
    reservation_id: int,
    body: CaptureDepositRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.capture_deposit(
        db,
        current_user.tenant_id,
        current_user.id,
        reservation_id,
        body or CaptureDepositRequest(),
    )


@router.post("/reservations/{reservation_id}/deposit/refund", response_model=ReservationRead)
def refund_deposit(
    reservation_id: int,
    body: RefundDepositRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.refund_deposit(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )


@router.post("/reservations/{reservation_id}/deposit/forfeit", response_model=ReservationRead)
def forfeit_deposit(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationRead:
    return service.forfeit_deposit(db, current_user.tenant_id, reservation_id)


@router.get("/reservations/{reservation_id}/folio", response_model=FolioRead)
def get_folio(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> FolioRead:
    return service.get_folio(db, current_user.tenant_id, reservation_id)


@router.get("/reservations/{reservation_id}/folio/pdf")
def download_folio_pdf(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> Response:
    pdf_bytes, filename = service.build_folio_pdf(
        db, current_user.tenant_id, reservation_id
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/reservations/{reservation_id}/folio/email",
    response_model=FolioEmailResponse,
)
async def email_folio(
    reservation_id: int,
    body: FolioEmailRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> FolioEmailResponse:
    return await service.email_folio_statement(
        db,
        current_user.tenant_id,
        current_user.id,
        reservation_id,
        body or FolioEmailRequest(),
    )


@router.post("/reservations/{reservation_id}/folio/charges", response_model=FolioRead)
def add_folio_charge(
    reservation_id: int,
    body: FolioChargeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> FolioRead:
    return service.add_folio_charge(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )


@router.post("/reservations/{reservation_id}/folio/payments", response_model=FolioRead)
def add_folio_payment(
    reservation_id: int,
    body: FolioPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> FolioRead:
    return service.add_folio_payment(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )


@router.post(
    "/reservations/{reservation_id}/folio/entries/{entry_id}/void",
    response_model=FolioRead,
)
def void_folio_entry(
    reservation_id: int,
    entry_id: int,
    body: FolioEntryVoidRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> FolioRead:
    return service.void_folio_entry(
        db,
        current_user.tenant_id,
        current_user.id,
        reservation_id,
        entry_id,
        body,
    )


@router.post(
    "/reservations/{reservation_id}/folio/transfer-to-city-ledger",
    response_model=CityLedgerTransferResponse,
)
def transfer_to_city_ledger(
    reservation_id: int,
    body: CityLedgerTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> CityLedgerTransferResponse:
    return service.transfer_folio_to_city_ledger(
        db, current_user.tenant_id, current_user.id, reservation_id, body
    )


@router.get("/city-ledger", response_model=list[CityLedgerRead])
def list_city_ledger(
    outlet_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[CityLedgerRead]:
    return service.list_city_ledger(
        db, current_user.tenant_id, outlet_id=outlet_id, status=status, limit=limit
    )


@router.get("/city-ledger/{entry_id}", response_model=CityLedgerRead)
def get_city_ledger_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> CityLedgerRead:
    return service.get_city_ledger_entry(db, current_user.tenant_id, entry_id)


@router.post("/city-ledger/{entry_id}/settle", response_model=CityLedgerRead)
def settle_city_ledger(
    entry_id: int,
    body: CityLedgerSettleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> CityLedgerRead:
    return service.settle_city_ledger(
        db, current_user.tenant_id, current_user.id, entry_id, body
    )


@router.post("/city-ledger/{entry_id}/write-off", response_model=CityLedgerRead)
def write_off_city_ledger(
    entry_id: int,
    body: CityLedgerWriteOffRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> CityLedgerRead:
    return service.write_off_city_ledger(
        db,
        current_user.tenant_id,
        current_user.id,
        entry_id,
        body or CityLedgerWriteOffRequest(),
    )


@router.post(
    "/reservations/{reservation_id}/special-requests/fulfill",
    response_model=SpecialRequestFulfillResponse,
)
def fulfill_special_requests(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> SpecialRequestFulfillResponse:
    return service.fulfill_guest_special_requests(
        db, current_user.tenant_id, reservation_id
    )


@router.get("/service-requests", response_model=list[GuestServiceRequestRead])
def list_service_requests(
    outlet_id: int = Query(...),
    status: GuestServiceRequestStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[GuestServiceRequestRead]:
    return service.list_service_requests(
        db, current_user.tenant_id, outlet_id, status_filter=status
    )


@router.post(
    "/service-requests/{request_id}/fulfill",
    response_model=GuestServiceRequestFulfillResponse,
)
async def fulfill_service_request(
    request_id: int,
    body: GuestServiceRequestFulfillRequest = GuestServiceRequestFulfillRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> GuestServiceRequestFulfillResponse:
    return await service.fulfill_service_request(
        db,
        current_user.tenant_id,
        current_user.id,
        request_id,
        data=body,
    )


@router.get("/calendar/tape-chart", response_model=TapeChartResponse)
def tape_chart(
    outlet_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> TapeChartResponse:
    return service.get_tape_chart(
        db, current_user.tenant_id, outlet_id, from_date, to_date
    )


@router.get("/calendar/pickup", response_model=PickupCalendarResponse)
def pickup_calendar(
    outlet_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> PickupCalendarResponse:
    return service.get_pickup_calendar(
        db, current_user.tenant_id, outlet_id, from_date, to_date
    )


@router.get("/calendar/rates", response_model=RateInventoryCalendarResponse)
def rate_inventory_calendar(
    outlet_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    source: ReservationSource | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> RateInventoryCalendarResponse:
    return service.get_rate_inventory_calendar(
        db,
        current_user.tenant_id,
        outlet_id,
        from_date,
        to_date,
        source=source,
    )


@router.patch("/calendar/rates", response_model=RateInventoryCalendarResponse)
def upsert_rate_inventory_override(
    body: RateInventoryOverrideUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> RateInventoryCalendarResponse:
    return service.upsert_rate_inventory_override(db, current_user.tenant_id, body)


@router.post("/walk-in", response_model=ReservationDetailRead, status_code=status.HTTP_201_CREATED)
def create_walk_in(
    body: WalkInCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationDetailRead | ReservationRead:
    result = service.create_walk_in(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )
    if isinstance(result, ReservationDetailRead):
        return result
    return service.get_reservation(db, current_user.tenant_id, result.id)


@router.get("/room-blocks", response_model=list[RoomBlockRead])
def list_room_blocks(
    outlet_id: int | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[RoomBlockRead]:
    return service.list_room_blocks(
        db, current_user.tenant_id, outlet_id=outlet_id, from_date=from_date, to_date=to_date
    )


@router.post("/room-blocks", response_model=RoomBlockRead, status_code=status.HTTP_201_CREATED)
def create_room_block(
    body: RoomBlockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> RoomBlockRead:
    return service.create_room_block(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/room-blocks/{block_id}", response_model=RoomBlockRead)
def update_room_block(
    block_id: int,
    body: RoomBlockUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> RoomBlockRead:
    return service.update_room_block(db, current_user.tenant_id, block_id, body)


@router.delete("/room-blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_room_block(
    block_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> Response:
    service.delete_room_block(db, current_user.tenant_id, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/groups", response_model=list[ReservationGroupRead])
def list_groups(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[ReservationGroupRead]:
    return service.list_reservation_groups(db, current_user.tenant_id, outlet_id)


@router.post("/groups", response_model=ReservationGroupRead, status_code=status.HTTP_201_CREATED)
def create_group(
    body: ReservationGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationGroupRead:
    return service.create_reservation_group(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/groups/{group_id}", response_model=ReservationGroupRead)
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> ReservationGroupRead:
    return service.get_reservation_group(db, current_user.tenant_id, group_id)


@router.patch("/groups/{group_id}", response_model=ReservationGroupRead)
def update_group(
    group_id: int,
    body: ReservationGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationGroupRead:
    return service.update_reservation_group(db, current_user.tenant_id, group_id, body)


@router.get("/groups/{group_id}/folio", response_model=FolioRead)
def get_group_folio(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> FolioRead:
    return service.get_group_master_folio(db, current_user.tenant_id, group_id)


@router.post("/groups/{group_id}/folio/charges", response_model=FolioRead)
def add_group_folio_charge(
    group_id: int,
    body: FolioChargeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> FolioRead:
    return service.add_group_folio_charge(
        db, current_user.tenant_id, current_user.id, group_id, body
    )


@router.post("/groups/{group_id}/folio/payments", response_model=FolioRead)
def add_group_folio_payment(
    group_id: int,
    body: FolioPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> FolioRead:
    return service.add_group_folio_payment(
        db, current_user.tenant_id, current_user.id, group_id, body
    )


@router.post("/groups/{group_id}/folio/transfer-from-room", response_model=ReservationGroupRead)
def transfer_to_master_folio(
    group_id: int,
    body: FolioTransferToMasterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationGroupRead:
    return service.transfer_room_charge_to_master(
        db, current_user.tenant_id, current_user.id, group_id, body
    )


@router.post("/groups/{group_id}/folio/sweep-rooms", response_model=ReservationGroupRead)
def sweep_group_room_folios(
    group_id: int,
    body: GroupFolioSweepRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationGroupRead:
    return service.sweep_room_folios_to_master(
        db, current_user.tenant_id, current_user.id, group_id, body
    )


@router.post(
    "/groups/{group_id}/folio/transfer-to-city-ledger",
    response_model=CityLedgerTransferResponse,
)
def transfer_group_master_to_city_ledger(
    group_id: int,
    body: CityLedgerTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> CityLedgerTransferResponse:
    return service.transfer_group_folio_to_city_ledger(
        db, current_user.tenant_id, current_user.id, group_id, body
    )


@router.post("/groups/{group_id}/folio/close", response_model=FolioRead)
def close_group_master_folio(
    group_id: int,
    body: GroupFolioCloseRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> FolioRead:
    return service.close_group_master_folio(
        db,
        current_user.tenant_id,
        current_user.id,
        group_id,
        body or GroupFolioCloseRequest(),
    )


@router.post("/groups/{group_id}/reservations", response_model=ReservationGroupRead)
def add_group_reservations(
    group_id: int,
    body: GroupRoomingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> ReservationGroupRead:
    return service.add_group_reservations(
        db,
        current_user.tenant_id,
        current_user.id,
        group_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/night-audit/run", response_model=NightAuditResult)
def run_night_audit(
    body: NightAuditRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> NightAuditResult:
    return service.run_night_audit(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/night-audit/logs", response_model=list[NightAuditLogRead])
def list_night_audit_logs(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[NightAuditLogRead]:
    return service.list_night_audit_logs(db, current_user.tenant_id, outlet_id)


@router.get("/reports/accounts-day-book", response_model=AccountsDayBookRead)
def accounts_day_book(
    outlet_id: int = Query(...),
    business_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> AccountsDayBookRead:
    return service.get_accounts_day_book(
        db, current_user.tenant_id, outlet_id, business_date
    )


@router.get("/reports/accounts-day-book.csv")
def accounts_day_book_csv(
    outlet_id: int = Query(...),
    business_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> Response:
    book = service.get_accounts_day_book(
        db, current_user.tenant_id, outlet_id, business_date
    )
    csv_text = service.build_accounts_day_book_csv(book)
    filename = f"accounts-day-book-{outlet_id}-{business_date.isoformat()}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cashier/shifts/current", response_model=CashierShiftRead | None)
def get_current_cashier_shift(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> CashierShiftRead | None:
    return service.get_open_cashier_shift(db, current_user.tenant_id, outlet_id)


@router.get("/cashier/shifts", response_model=list[CashierShiftRead])
def list_cashier_shifts(
    outlet_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[CashierShiftRead]:
    return service.list_cashier_shifts(db, current_user.tenant_id, outlet_id, limit)


@router.get("/cashier/shifts/{shift_id}", response_model=CashierShiftRead)
def get_cashier_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> CashierShiftRead:
    return service.get_cashier_shift(db, current_user.tenant_id, shift_id)


@router.post(
    "/cashier/shifts/open",
    response_model=CashierShiftRead,
    status_code=status.HTTP_201_CREATED,
)
def open_cashier_shift(
    body: CashierShiftOpenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> CashierShiftRead:
    return service.open_cashier_shift(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/cashier/shifts/{shift_id}/close", response_model=CashierShiftRead)
def close_cashier_shift(
    shift_id: int,
    body: CashierShiftCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> CashierShiftRead:
    return service.close_cashier_shift(
        db, current_user.tenant_id, current_user.id, shift_id, body
    )


@router.get("/reports/summary", response_model=PmsReportsSummary)
def pms_reports_summary(
    outlet_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> PmsReportsSummary:
    return service.get_pms_reports(
        db, current_user.tenant_id, outlet_id, from_date, to_date
    )


@router.get("/guests/{customer_id}/stay-history", response_model=GuestStayHistoryRead)
def guest_stay_history_by_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> GuestStayHistoryRead:
    return service.list_guest_stay_history(
        db, current_user.tenant_id, customer_id=customer_id
    )


@router.get("/guests/stay-history", response_model=GuestStayHistoryRead)
def guest_stay_history(
    customer_id: int | None = Query(None),
    guest_mobile: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> GuestStayHistoryRead:
    return service.list_guest_stay_history(
        db,
        current_user.tenant_id,
        customer_id=customer_id,
        guest_mobile=guest_mobile,
    )
