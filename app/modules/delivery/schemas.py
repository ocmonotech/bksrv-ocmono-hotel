from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.delivery.models import (
    DeliveryPlatform,
    ExternalOrderStatus,
    IntegrationStatus,
)
from app.modules.pos.models import OrderStatus, OrderType


class IntegrationCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    platform: DeliveryPlatform
    external_store_id: str | None = None
    is_enabled: bool = False
    auto_accept_orders: bool = False
    auto_send_kot: bool = True
    api_key: str | None = None
    webhook_secret: str | None = None
    config: dict = Field(default_factory=dict)


class IntegrationUpdate(BaseModel):
    external_store_id: str | None = None
    status: IntegrationStatus | None = None
    is_enabled: bool | None = None
    auto_accept_orders: bool | None = None
    auto_send_kot: bool | None = None
    api_key: str | None = None
    webhook_secret: str | None = None
    config: dict | None = None


class IntegrationRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    platform: DeliveryPlatform
    external_store_id: str | None
    status: IntegrationStatus
    is_enabled: bool
    auto_accept_orders: bool
    auto_send_kot: bool
    webhook_token: str
    config: dict = Field(default_factory=dict)
    has_api_key: bool = False
    has_webhook_secret: bool = False
    last_sync_at: datetime | None = None
    last_error: str | None = None
    webhook_url: str | None = None


class MenuMappingCreate(BaseModel):
    external_item_id: str
    external_item_name: str
    menu_item_id: int | None = None


class MenuMappingUpdate(BaseModel):
    external_item_name: str | None = None
    menu_item_id: int | None = None


class MenuMappingRead(ORMSchema, TimestampSchema):
    id: int
    integration_id: int
    external_item_id: str
    external_item_name: str
    menu_item_id: int | None
    menu_item_name: str | None = None


class ExternalOrderItemPayload(BaseModel):
    external_item_id: str
    item_name: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    note: str | None = None


class InboundOrderPayload(BaseModel):
    external_order_id: str
    customer_name: str | None = None
    customer_phone: str | None = None
    delivery_address: str | None = None
    items: list[ExternalOrderItemPayload]
    notes: str | None = None
    rider_name: str | None = None
    rider_phone: str | None = None


class DeliveryOrderRead(ORMSchema, TimestampSchema):
    id: int
    integration_id: int
    pos_order_id: int
    outlet_id: int
    platform: DeliveryPlatform
    external_order_id: str
    external_status: ExternalOrderStatus
    order_number: str
    order_status: OrderStatus
    order_type: OrderType
    customer_name: str | None
    customer_phone: str | None
    delivery_address: str | None
    rider_name: str | None
    rider_phone: str | None
    grand_total: float
    item_count: int
    notes: str | None


class DeliveryOrderAction(BaseModel):
    notes: str | None = None


class MockOrderRequest(BaseModel):
    customer_name: str = "Test Customer"
    customer_phone: str = "+919876543210"
    delivery_address: str = "123 Test Street, Mumbai"
    items: list[ExternalOrderItemPayload] = Field(default_factory=list)


class WebhookAckResponse(BaseModel):
    success: bool
    message: str
    delivery_order_id: int | None = None
    pos_order_id: int | None = None


class PlatformInfo(BaseModel):
    platform: DeliveryPlatform
    label: str
    description: str


class IntegrationDeleteResponse(MessageResponse):
    integration_id: int
