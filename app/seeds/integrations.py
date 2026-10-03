"""Delivery, booking, and payment integrations with sample links."""

from __future__ import annotations

import json
import secrets

from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingPlatform, OutletBookingIntegration
from app.modules.delivery.models import (
    DeliveryMenuMapping,
    DeliveryOrderLink,
    DeliveryPlatform,
    ExternalOrderStatus,
    IntegrationStatus,
    OutletDeliveryIntegration,
)
from app.modules.payments.models import OutletPaymentIntegration, PaymentProvider, TerminalPayment, TerminalPaymentStatus
from app.modules.pos.models import PaymentMode
from app.seeds.base import SeedContext


def seed_integrations(db: Session, ctx: SeedContext) -> None:
    ctx.delivery_integrations = _seed_delivery_integrations(db, ctx)
    _seed_delivery_menu_mappings(db, ctx)
    _seed_delivery_order_links(db, ctx)
    ctx.booking_integrations = _seed_booking_integrations(db, ctx)
    ctx.payment_integrations = _seed_payment_integrations(db, ctx)
    _seed_terminal_payments(db, ctx)


def _demo_token(prefix: str) -> str:
    return f"demo-{prefix}-{secrets.token_hex(8)}"


def _seed_delivery_integrations(db: Session, ctx: SeedContext) -> dict[str, OutletDeliveryIntegration]:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    integrations: dict[str, OutletDeliveryIntegration] = {}

    for platform in (DeliveryPlatform.ZOMATO, DeliveryPlatform.SWIGGY):
        key = f"{andheri.outlet_name}-{platform.value}"
        integration = (
            db.query(OutletDeliveryIntegration)
            .filter(
                OutletDeliveryIntegration.tenant_id == tenant.id,
                OutletDeliveryIntegration.outlet_id == andheri.id,
                OutletDeliveryIntegration.platform == platform,
            )
            .first()
        )
        if integration is None:
            integration = OutletDeliveryIntegration(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                platform=platform,
                external_store_id=f"DEMO-{platform.value.upper()}-001",
                status=IntegrationStatus.ACTIVE,
                is_enabled=True,
                auto_accept_orders=False,
                auto_send_kot=True,
                webhook_token=_demo_token(platform.value),
                config_json=json.dumps({"mode": "mock"}),
                encrypted_api_key="MOCK_ENC:delivery-key",
            )
            db.add(integration)
            db.flush()
        integrations[key] = integration
    return integrations


def _seed_delivery_menu_mappings(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    integration = next(iter(ctx.delivery_integrations.values()), None)
    if integration is None:
        return

    mappings = [
        ("ZMT-BC-001", "Butter Chicken", "Butter Chicken"),
        ("ZMT-PT-001", "Paneer Tikka", "Paneer Tikka"),
        ("ZMT-CB-001", "Chicken Biryani", "Chicken Biryani"),
    ]
    for external_id, external_name, item_name in mappings:
        menu_item = ctx.menu_items.get(item_name)
        existing = (
            db.query(DeliveryMenuMapping)
            .filter(
                DeliveryMenuMapping.integration_id == integration.id,
                DeliveryMenuMapping.external_item_id == external_id,
            )
            .first()
        )
        if existing is None and menu_item is not None:
            db.add(
                DeliveryMenuMapping(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    integration_id=integration.id,
                    external_item_id=external_id,
                    external_item_name=external_name,
                    menu_item_id=menu_item.id,
                )
            )


def _seed_delivery_order_links(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    integration = next(
        (i for i in ctx.delivery_integrations.values() if i.platform == DeliveryPlatform.ZOMATO),
        None,
    )
    order = ctx.orders.get("ORD-AND-004")
    if integration is None or order is None:
        return

    existing = (
        db.query(DeliveryOrderLink)
        .filter(
            DeliveryOrderLink.integration_id == integration.id,
            DeliveryOrderLink.external_order_id == "ZMT-987654",
        )
        .first()
    )
    if existing is not None:
        return

    db.add(
        DeliveryOrderLink(
            tenant_id=tenant.id,
            brand_id=brand.id,
            integration_id=integration.id,
            pos_order_id=order.id,
            platform=DeliveryPlatform.ZOMATO,
            external_order_id="ZMT-987654",
            external_status=ExternalOrderStatus.PREPARING,
            customer_name="Rahul Kumar",
            customer_phone="+919900112233",
            delivery_address="Andheri West, Mumbai 400058",
            rider_name="Demo Rider",
            rider_phone="+919900445566",
            raw_payload_json=json.dumps({"demo": True}),
        )
    )


def _seed_booking_integrations(db: Session, ctx: SeedContext) -> dict[str, OutletBookingIntegration]:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    bandra = ctx.outlets["Bandra"]
    integrations: dict[str, OutletBookingIntegration] = {}

    specs = [
        (andheri, BookingPlatform.ZOMATO),
        (andheri, BookingPlatform.DIRECT),
        (bandra, BookingPlatform.SWIGGY_DINEOUT),
    ]
    for outlet, platform in specs:
        key = f"{outlet.outlet_name}-{platform.value}"
        integration = (
            db.query(OutletBookingIntegration)
            .filter(
                OutletBookingIntegration.tenant_id == tenant.id,
                OutletBookingIntegration.outlet_id == outlet.id,
                OutletBookingIntegration.platform == platform,
            )
            .first()
        )
        if integration is None:
            integration = OutletBookingIntegration(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=outlet.id,
                platform=platform,
                external_store_id=f"DEMO-BOOK-{platform.value.upper()}",
                status=IntegrationStatus.ACTIVE,
                is_enabled=True,
                auto_confirm_bookings=platform == BookingPlatform.DIRECT,
                auto_reserve_table=True,
                webhook_token=_demo_token(f"book-{platform.value}"),
                config_json=json.dumps({"mode": "mock"}),
            )
            db.add(integration)
            db.flush()
        integrations[key] = integration
    return integrations


def _seed_payment_integrations(db: Session, ctx: SeedContext) -> dict[str, OutletPaymentIntegration]:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    integrations: dict[str, OutletPaymentIntegration] = {}

    for provider in (
        PaymentProvider.RAZORPAY,
        PaymentProvider.PINELABS,
        PaymentProvider.PHONEPE,
        PaymentProvider.CASHFREE,
        PaymentProvider.CCAVENUE,
        PaymentProvider.PAYTM,
    ):
        key = f"{andheri.outlet_name}-{provider.value}"
        integration = (
            db.query(OutletPaymentIntegration)
            .filter(
                OutletPaymentIntegration.tenant_id == tenant.id,
                OutletPaymentIntegration.outlet_id == andheri.id,
                OutletPaymentIntegration.provider == provider,
            )
            .first()
        )
        if integration is None:
            integration = OutletPaymentIntegration(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                provider=provider,
                merchant_id=f"DEMO-MERCHANT-{provider.value.upper()}",
                store_id="STORE-001",
                client_id=f"DEMO-CLIENT-{provider.value.upper()}",
                status=IntegrationStatus.ACTIVE,
                is_enabled=True,
                auto_settle_on_success=True,
                webhook_token=_demo_token(f"pay-{provider.value}"),
                config_json=json.dumps({"mode": "mock"}),
                encrypted_api_key="MOCK_ENC:payment-key",
            )
            db.add(integration)
            db.flush()
        integrations[key] = integration
    return integrations


def _seed_terminal_payments(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    integration = next(iter(ctx.payment_integrations.values()), None)
    bill = ctx.bills.get("BILL-AND-001")
    if integration is None or bill is None:
        return

    existing = (
        db.query(TerminalPayment)
        .filter(
            TerminalPayment.tenant_id == tenant.id,
            TerminalPayment.transaction_number == "TXN-DEMO-001",
        )
        .first()
    )
    if existing is not None:
        return

    db.add(
        TerminalPayment(
            tenant_id=tenant.id,
            brand_id=brand.id,
            integration_id=integration.id,
            bill_id=bill.id,
            transaction_number="TXN-DEMO-001",
            sequence_number=1,
            amount=float(bill.grand_total),
            payment_mode=PaymentMode.UPI,
            status=TerminalPaymentStatus.SUCCESS,
            provider_reference_id="RAZOR-DEMO-REF-001",
            auth_code="AUTH123",
            reference_number="UPI-DEMO-001",
            raw_request_json=json.dumps({"demo": True}),
            raw_response_json=json.dumps({"status": "success"}),
        )
    )
