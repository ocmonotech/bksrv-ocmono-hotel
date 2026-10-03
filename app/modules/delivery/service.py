from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.delivery.models import (
    DeliveryMenuMapping,
    DeliveryOrderLink,
    DeliveryPlatform,
    ExternalOrderStatus,
    IntegrationStatus,
    OutletDeliveryIntegration,
)
from app.modules.delivery.providers.registry import (
    PLATFORM_LABELS,
    build_webhook_url,
    get_delivery_provider,
)
from app.modules.delivery.schemas import (
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
from app.modules.kot import service as kot_service
from app.modules.menu.models import MenuItem
from app.modules.outlets.models import Outlet
from app.modules.pos.models import (
    Order,
    OrderItem,
    OrderItemStatus,
    OrderSource,
    OrderStatus,
    OrderType,
)
from app.utils.encryption import decrypt_secret, encrypt_secret


def list_platforms() -> list[PlatformInfo]:
    return [
        PlatformInfo(platform=platform, label=label, description=description)
        for platform, (label, description) in PLATFORM_LABELS.items()
    ]


def list_integrations(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    platform: DeliveryPlatform | None = None,
) -> tuple[list[IntegrationRead], int]:
    query = db.query(OutletDeliveryIntegration).filter(
        OutletDeliveryIntegration.tenant_id == tenant_id,
        OutletDeliveryIntegration.is_active.is_(True),
    )
    if outlet_id is not None:
        query = query.filter(OutletDeliveryIntegration.outlet_id == outlet_id)
    if platform is not None:
        query = query.filter(OutletDeliveryIntegration.platform == platform)

    rows, total = paginate_query(query.order_by(OutletDeliveryIntegration.id.desc()), page, page_size)
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
        db.query(OutletDeliveryIntegration)
        .filter(
            OutletDeliveryIntegration.outlet_id == data.outlet_id,
            OutletDeliveryIntegration.platform == data.platform,
            OutletDeliveryIntegration.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ConflictError(
            f"{data.platform.value} is already configured for this outlet"
        )

    integration = OutletDeliveryIntegration(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        platform=data.platform,
        external_store_id=data.external_store_id,
        status=IntegrationStatus.PENDING,
        is_enabled=data.is_enabled,
        auto_accept_orders=data.auto_accept_orders,
        auto_send_kot=data.auto_send_kot,
        webhook_token=uuid.uuid4().hex,
        config_json=json.dumps(data.config or {}),
        encrypted_api_key=encrypt_secret(data.api_key),
        encrypted_webhook_secret=encrypt_secret(data.webhook_secret),
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

    if "external_store_id" in payload:
        integration.external_store_id = payload["external_store_id"]
    if "status" in payload:
        integration.status = payload["status"]
    if "is_enabled" in payload:
        integration.is_enabled = payload["is_enabled"]
    if "auto_accept_orders" in payload:
        integration.auto_accept_orders = payload["auto_accept_orders"]
    if "auto_send_kot" in payload:
        integration.auto_send_kot = payload["auto_send_kot"]
    if "config" in payload and payload["config"] is not None:
        integration.config_json = json.dumps(payload["config"])
    if "api_key" in payload and payload["api_key"]:
        integration.encrypted_api_key = encrypt_secret(payload["api_key"])
    if "webhook_secret" in payload and payload["webhook_secret"]:
        integration.encrypted_webhook_secret = encrypt_secret(payload["webhook_secret"])

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
        message="Delivery integration removed",
        integration_id=integration_id,
    )


async def test_integration_connection(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> IntegrationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    provider = get_delivery_provider(integration.platform)
    config = _load_config(integration)
    result = await provider.test_connection(
        external_store_id=integration.external_store_id,
        api_key=decrypt_secret(integration.encrypted_api_key),
        config=config,
    )
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


def list_menu_mappings(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> list[MenuMappingRead]:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    mappings = (
        db.query(DeliveryMenuMapping)
        .filter(
            DeliveryMenuMapping.integration_id == integration.id,
            DeliveryMenuMapping.is_active.is_(True),
        )
        .order_by(DeliveryMenuMapping.external_item_name)
        .all()
    )
    return [_to_menu_mapping_read(db, mapping) for mapping in mappings]


def create_menu_mapping(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: MenuMappingCreate,
) -> MenuMappingRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    mapping = DeliveryMenuMapping(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        external_item_id=data.external_item_id,
        external_item_name=data.external_item_name,
        menu_item_id=data.menu_item_id,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return _to_menu_mapping_read(db, mapping)


def update_menu_mapping(
    db: Session,
    tenant_id: int,
    integration_id: int,
    mapping_id: int,
    data: MenuMappingUpdate,
) -> MenuMappingRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    mapping = _get_menu_mapping_entity(db, integration, mapping_id)
    payload = data.model_dump(exclude_unset=True)
    if "external_item_name" in payload:
        mapping.external_item_name = payload["external_item_name"]
    if "menu_item_id" in payload:
        mapping.menu_item_id = payload["menu_item_id"]
    db.commit()
    db.refresh(mapping)
    return _to_menu_mapping_read(db, mapping)


def list_delivery_orders(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    platform: DeliveryPlatform | None = None,
    external_status: ExternalOrderStatus | None = None,
) -> tuple[list[DeliveryOrderRead], int]:
    query = (
        db.query(DeliveryOrderLink)
        .join(OutletDeliveryIntegration)
        .join(Order, Order.id == DeliveryOrderLink.pos_order_id)
        .options(joinedload(DeliveryOrderLink.integration))
        .filter(
            DeliveryOrderLink.tenant_id == tenant_id,
            DeliveryOrderLink.is_active.is_(True),
        )
    )
    if outlet_id is not None:
        query = query.filter(OutletDeliveryIntegration.outlet_id == outlet_id)
    if platform is not None:
        query = query.filter(DeliveryOrderLink.platform == platform)
    if external_status is not None:
        query = query.filter(DeliveryOrderLink.external_status == external_status)

    rows, total = paginate_query(query.order_by(DeliveryOrderLink.id.desc()), page, page_size)
    return [_to_delivery_order_read(db, row) for row in rows], total


def get_delivery_order(db: Session, tenant_id: int, delivery_order_id: int) -> DeliveryOrderRead:
    row = _get_delivery_order_entity(db, tenant_id, delivery_order_id)
    return _to_delivery_order_read(db, row)


async def accept_delivery_order(
    db: Session,
    tenant_id: int,
    delivery_order_id: int,
    notes: str | None = None,
) -> DeliveryOrderRead:
    link = _get_delivery_order_entity(db, tenant_id, delivery_order_id)
    integration = link.integration
    order = db.get(Order, link.pos_order_id)
    if order is None:
        raise NotFoundError("Linked POS order not found")

    link.external_status = ExternalOrderStatus.ACCEPTED
    if notes:
        link.notes = notes
    order.order_status = OrderStatus.PREPARING

    await _sync_external_status(integration, link, ExternalOrderStatus.ACCEPTED)

    if integration.auto_send_kot and order.order_status != OrderStatus.KOT_SENT:
        kot_service.create_kots_from_order(db, tenant_id, order.id)

    db.commit()
    db.refresh(link)
    return _to_delivery_order_read(db, link)


async def reject_delivery_order(
    db: Session,
    tenant_id: int,
    delivery_order_id: int,
    notes: str | None = None,
) -> DeliveryOrderRead:
    link = _get_delivery_order_entity(db, tenant_id, delivery_order_id)
    integration = link.integration
    order = db.get(Order, link.pos_order_id)
    if order is None:
        raise NotFoundError("Linked POS order not found")

    link.external_status = ExternalOrderStatus.REJECTED
    if notes:
        link.notes = notes
    order.order_status = OrderStatus.CANCELLED

    await _sync_external_status(integration, link, ExternalOrderStatus.REJECTED)
    db.commit()
    db.refresh(link)
    return _to_delivery_order_read(db, link)


async def mark_delivery_order_ready(
    db: Session,
    tenant_id: int,
    delivery_order_id: int,
) -> DeliveryOrderRead:
    link = _get_delivery_order_entity(db, tenant_id, delivery_order_id)
    integration = link.integration
    order = db.get(Order, link.pos_order_id)
    if order is None:
        raise NotFoundError("Linked POS order not found")

    link.external_status = ExternalOrderStatus.READY
    order.order_status = OrderStatus.READY
    await _sync_external_status(integration, link, ExternalOrderStatus.READY)
    db.commit()
    db.refresh(link)
    return _to_delivery_order_read(db, link)


async def ingest_inbound_order(
    db: Session,
    webhook_token: str,
    payload: InboundOrderPayload,
    raw_payload: dict | None = None,
) -> WebhookAckResponse:
    integration = (
        db.query(OutletDeliveryIntegration)
        .filter(
            OutletDeliveryIntegration.webhook_token == webhook_token,
            OutletDeliveryIntegration.is_active.is_(True),
        )
        .first()
    )
    if integration is None:
        raise NotFoundError("Delivery integration not found")
    if not integration.is_enabled:
        raise ConflictError("Delivery integration is disabled")

    existing = (
        db.query(DeliveryOrderLink)
        .filter(
            DeliveryOrderLink.integration_id == integration.id,
            DeliveryOrderLink.external_order_id == payload.external_order_id,
        )
        .first()
    )
    if existing:
        return WebhookAckResponse(
            success=True,
            message="Order already received",
            delivery_order_id=existing.id,
            pos_order_id=existing.pos_order_id,
        )

    link = _create_delivery_order_from_payload(
        db,
        integration,
        payload,
        raw_payload=raw_payload,
    )
    db.commit()
    return WebhookAckResponse(
        success=True,
        message="Order ingested",
        delivery_order_id=link.id,
        pos_order_id=link.pos_order_id,
    )


async def simulate_mock_order(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: MockOrderRequest,
) -> DeliveryOrderRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    if not integration.is_enabled:
        raise ConflictError("Enable the integration before simulating orders")

    from app.modules.delivery.schemas import ExternalOrderItemPayload

    items = data.items
    if not items:
        mapping = (
            db.query(DeliveryMenuMapping)
            .filter(
                DeliveryMenuMapping.integration_id == integration.id,
                DeliveryMenuMapping.menu_item_id.isnot(None),
                DeliveryMenuMapping.is_active.is_(True),
            )
            .first()
        )
        if mapping:
            menu_item = db.get(MenuItem, mapping.menu_item_id)
            items = [
                ExternalOrderItemPayload(
                    external_item_id=mapping.external_item_id,
                    item_name=mapping.external_item_name,
                    quantity=1,
                    unit_price=float(menu_item.base_price) if menu_item else 199.0,
                )
            ]
        else:
            items = [
                ExternalOrderItemPayload(
                    external_item_id="mock-item-1",
                    item_name="Butter Chicken",
                    quantity=1,
                    unit_price=349.0,
                    note="Extra spicy",
                ),
                ExternalOrderItemPayload(
                    external_item_id="mock-item-2",
                    item_name="Garlic Naan",
                    quantity=2,
                    unit_price=65.0,
                ),
            ]

    payload = InboundOrderPayload(
        external_order_id=f"MOCK-{uuid.uuid4().hex[:10].upper()}",
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        delivery_address=data.delivery_address,
        items=items,
        notes="Simulated aggregator order",
    )
    link = _create_delivery_order_from_payload(db, integration, payload, raw_payload=payload.model_dump())
    db.commit()
    db.refresh(link)
    return _to_delivery_order_read(db, link)


def _create_delivery_order_from_payload(
    db: Session,
    integration: OutletDeliveryIntegration,
    payload: InboundOrderPayload,
    raw_payload: dict | None = None,
) -> DeliveryOrderLink:
    order_source = _platform_to_order_source(integration.platform)
    initial_status = (
        OrderStatus.PREPARING
        if integration.auto_accept_orders
        else OrderStatus.DRAFT
    )
    external_status = (
        ExternalOrderStatus.ACCEPTED
        if integration.auto_accept_orders
        else ExternalOrderStatus.RECEIVED
    )

    order = Order(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        outlet_id=integration.outlet_id,
        order_number=_next_order_number(integration.platform),
        order_type=OrderType.DELIVERY,
        order_status=initial_status,
        order_source=order_source,
        source_reference=payload.external_order_id,
        created_by=None,
    )
    db.add(order)
    db.flush()

    mappings = {
        mapping.external_item_id: mapping
        for mapping in db.query(DeliveryMenuMapping)
        .filter(
            DeliveryMenuMapping.integration_id == integration.id,
            DeliveryMenuMapping.is_active.is_(True),
        )
        .all()
    }
    fallback_menu_item = _get_fallback_menu_item(db, integration)

    for item_payload in payload.items:
        mapping = mappings.get(item_payload.external_item_id)
        menu_item_id = mapping.menu_item_id if mapping and mapping.menu_item_id else fallback_menu_item.id
        menu_item = db.get(MenuItem, menu_item_id)
        gst_percent = float(menu_item.gst_percent) if menu_item else 5.0

        line = OrderItem(
            tenant_id=integration.tenant_id,
            brand_id=integration.brand_id,
            order_id=order.id,
            menu_item_id=menu_item_id,
            item_name=item_payload.item_name,
            quantity=item_payload.quantity,
            price=item_payload.unit_price,
            gst_percent=gst_percent,
            note=item_payload.note,
            status=OrderItemStatus.NEW,
        )
        db.add(line)

    db.flush()
    _recalculate_order(order)

    link = DeliveryOrderLink(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        pos_order_id=order.id,
        platform=integration.platform,
        external_order_id=payload.external_order_id,
        external_status=external_status,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        delivery_address=payload.delivery_address,
        rider_name=payload.rider_name,
        rider_phone=payload.rider_phone,
        raw_payload_json=json.dumps(raw_payload or payload.model_dump()),
        notes=payload.notes,
    )
    db.add(link)

    if integration.auto_send_kot:
        kot_service.create_kots_from_order(db, integration.tenant_id, order.id)
        if order.order_status == OrderStatus.DRAFT:
            order.order_status = OrderStatus.KOT_SENT

    integration.last_sync_at = datetime.utcnow()
    integration.last_error = None
    return link


async def _sync_external_status(
    integration: OutletDeliveryIntegration,
    link: DeliveryOrderLink,
    status: ExternalOrderStatus,
) -> None:
    provider = get_delivery_provider(integration.platform)
    config = _load_config(integration)
    result = await provider.update_order_status(
        external_order_id=link.external_order_id,
        external_store_id=integration.external_store_id,
        api_key=decrypt_secret(integration.encrypted_api_key),
        status=status,
        config=config,
    )
    if not result.success:
        integration.last_error = result.error_message or "Failed to sync status to aggregator"
    else:
        integration.last_error = None
    integration.last_sync_at = datetime.utcnow()


def _platform_to_order_source(platform: DeliveryPlatform) -> OrderSource:
    mapping = {
        DeliveryPlatform.ZOMATO: OrderSource.ZOMATO,
        DeliveryPlatform.SWIGGY: OrderSource.SWIGGY,
        DeliveryPlatform.ONDC: OrderSource.ONDC,
        DeliveryPlatform.DUNZO: OrderSource.DUNZO,
        DeliveryPlatform.MAGICPIN: OrderSource.MAGICPIN,
    }
    return mapping[platform]


def _next_order_number(platform: DeliveryPlatform) -> str:
    prefix = platform.value[:3].upper()
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _recalculate_order(order: Order) -> None:
    subtotal = 0.0
    discount_total = 0.0
    gst_total = 0.0

    for item in order.items:
        if item.status == OrderItemStatus.CANCELLED:
            continue
        line_gross = float(item.price) * item.quantity
        line_discount = float(item.discount_amount)
        line_net = max(line_gross - line_discount, 0)
        line_gst = round(line_net * float(item.gst_percent) / 100, 2)
        subtotal += line_net
        discount_total += line_discount
        gst_total += line_gst

    order.subtotal = round(subtotal, 2)
    order.discount_amount = round(discount_total, 2)
    order.service_charge = 0.0
    order.gst_amount = round(gst_total, 2)
    order.grand_total = round(subtotal + gst_total, 2)


def _get_fallback_menu_item(db: Session, integration: OutletDeliveryIntegration) -> MenuItem:
    menu_item = (
        db.query(MenuItem)
        .filter(
            MenuItem.tenant_id == integration.tenant_id,
            MenuItem.is_active.is_(True),
        )
        .order_by(MenuItem.id.asc())
        .first()
    )
    if menu_item is None:
        raise ConflictError("No menu items available to map delivery order lines")
    return menu_item


def _load_config(integration: OutletDeliveryIntegration) -> dict:
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
) -> OutletDeliveryIntegration:
    row = (
        db.query(OutletDeliveryIntegration)
        .options(joinedload(OutletDeliveryIntegration.menu_mappings))
        .filter(
            OutletDeliveryIntegration.id == integration_id,
            OutletDeliveryIntegration.tenant_id == tenant_id,
            OutletDeliveryIntegration.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise NotFoundError("Delivery integration not found")
    return row


def _get_menu_mapping_entity(
    db: Session,
    integration: OutletDeliveryIntegration,
    mapping_id: int,
) -> DeliveryMenuMapping:
    mapping = (
        db.query(DeliveryMenuMapping)
        .filter(
            DeliveryMenuMapping.id == mapping_id,
            DeliveryMenuMapping.integration_id == integration.id,
            DeliveryMenuMapping.is_active.is_(True),
        )
        .first()
    )
    if mapping is None:
        raise NotFoundError("Menu mapping not found")
    return mapping


def _get_delivery_order_entity(
    db: Session,
    tenant_id: int,
    delivery_order_id: int,
) -> DeliveryOrderLink:
    row = (
        db.query(DeliveryOrderLink)
        .options(joinedload(DeliveryOrderLink.integration))
        .filter(
            DeliveryOrderLink.id == delivery_order_id,
            DeliveryOrderLink.tenant_id == tenant_id,
            DeliveryOrderLink.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise NotFoundError("Delivery order not found")
    return row


def _to_integration_read(integration: OutletDeliveryIntegration) -> IntegrationRead:
    return IntegrationRead(
        id=integration.id,
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        outlet_id=integration.outlet_id,
        platform=integration.platform,
        external_store_id=integration.external_store_id,
        status=integration.status,
        is_enabled=integration.is_enabled,
        auto_accept_orders=integration.auto_accept_orders,
        auto_send_kot=integration.auto_send_kot,
        webhook_token=integration.webhook_token,
        config=_load_config(integration),
        has_api_key=bool(integration.encrypted_api_key),
        has_webhook_secret=bool(integration.encrypted_webhook_secret),
        last_sync_at=integration.last_sync_at,
        last_error=integration.last_error,
        webhook_url=build_webhook_url(integration.webhook_token),
        is_active=integration.is_active,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


def _to_menu_mapping_read(db: Session, mapping: DeliveryMenuMapping) -> MenuMappingRead:
    menu_item_name = None
    if mapping.menu_item_id:
        menu_item = db.get(MenuItem, mapping.menu_item_id)
        menu_item_name = menu_item.item_name if menu_item else None
    return MenuMappingRead(
        id=mapping.id,
        integration_id=mapping.integration_id,
        external_item_id=mapping.external_item_id,
        external_item_name=mapping.external_item_name,
        menu_item_id=mapping.menu_item_id,
        menu_item_name=menu_item_name,
        is_active=mapping.is_active,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


def _to_delivery_order_read(db: Session, link: DeliveryOrderLink) -> DeliveryOrderRead:
    order = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.id == link.pos_order_id)
        .first()
    )
    if order is None:
        raise NotFoundError("Linked POS order not found")

    active_items = [
        item for item in order.items if item.status != OrderItemStatus.CANCELLED
    ]

    return DeliveryOrderRead(
        id=link.id,
        integration_id=link.integration_id,
        pos_order_id=link.pos_order_id,
        outlet_id=order.outlet_id,
        platform=link.platform,
        external_order_id=link.external_order_id,
        external_status=link.external_status,
        order_number=order.order_number,
        order_status=order.order_status,
        order_type=order.order_type,
        customer_name=link.customer_name,
        customer_phone=link.customer_phone,
        delivery_address=link.delivery_address,
        rider_name=link.rider_name,
        rider_phone=link.rider_phone,
        grand_total=float(order.grand_total),
        item_count=len(active_items),
        notes=link.notes,
        is_active=link.is_active,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )
