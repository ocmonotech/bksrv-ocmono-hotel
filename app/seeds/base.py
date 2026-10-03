"""Shared seed context and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.ai.models import AiProvider
    from app.modules.bookings.models import OutletBookingIntegration, TableBooking
    from app.modules.brands.models import Brand
    from app.modules.campaigns.models import Campaign
    from app.modules.communications.models import MessageTemplate
    from app.modules.customers.models import Customer
    from app.modules.delivery.models import OutletDeliveryIntegration
    from app.modules.inventory.models import RawMaterial, Vendor
    from app.modules.leads.models import Lead
    from app.modules.menu.models import MenuCategory, MenuItem
    from app.modules.offers.models import Offer
    from app.modules.outlets.models import Outlet
    from app.modules.payments.models import OutletPaymentIntegration
    from app.modules.pos.models import Bill, Order
    from app.modules.tables.models import RestaurantTable
    from app.modules.tenants.models import Tenant
    from app.modules.users.models import User


@dataclass
class SeedContext:
    tenant: Tenant
    brand: Brand
    outlets: dict[str, Outlet]
    roles: dict[str, object]
    users: dict[str, User] = field(default_factory=dict)
    categories: dict[str, MenuCategory] = field(default_factory=dict)
    menu_items: dict[str, MenuItem] = field(default_factory=dict)
    customers: dict[str, Customer] = field(default_factory=dict)
    leads: dict[str, Lead] = field(default_factory=dict)
    tables: dict[tuple[str, str], RestaurantTable] = field(default_factory=dict)
    raw_materials: dict[str, RawMaterial] = field(default_factory=dict)
    vendors: dict[str, Vendor] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    bills: dict[str, Bill] = field(default_factory=dict)
    templates: dict[str, MessageTemplate] = field(default_factory=dict)
    offers: dict[str, Offer] = field(default_factory=dict)
    campaigns: dict[str, Campaign] = field(default_factory=dict)
    ai_providers: dict[str, AiProvider] = field(default_factory=dict)
    delivery_integrations: dict[str, OutletDeliveryIntegration] = field(default_factory=dict)
    booking_integrations: dict[str, OutletBookingIntegration] = field(default_factory=dict)
    payment_integrations: dict[str, OutletPaymentIntegration] = field(default_factory=dict)
    bookings: dict[str, TableBooking] = field(default_factory=dict)
