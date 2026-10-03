from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.payments.models import (
    IntegrationStatus,
    PaymentProvider,
    TerminalPaymentStatus,
)
from app.modules.pos.models import PaymentMode


class IntegrationCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    provider: PaymentProvider
    merchant_id: str | None = None
    store_id: str | None = None
    client_id: str | None = None
    is_enabled: bool = False
    auto_settle_on_success: bool = True
    security_token: str | None = None
    api_key: str | None = None
    config: dict = Field(default_factory=dict)


class IntegrationUpdate(BaseModel):
    merchant_id: str | None = None
    store_id: str | None = None
    client_id: str | None = None
    status: IntegrationStatus | None = None
    is_enabled: bool | None = None
    auto_settle_on_success: bool | None = None
    security_token: str | None = None
    api_key: str | None = None
    config: dict | None = None


class IntegrationRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    provider: PaymentProvider
    merchant_id: str | None
    store_id: str | None
    client_id: str | None
    status: IntegrationStatus
    is_enabled: bool
    auto_settle_on_success: bool
    webhook_token: str
    config: dict = Field(default_factory=dict)
    has_security_token: bool = False
    has_api_key: bool = False
    last_sync_at: datetime | None = None
    last_error: str | None = None
    postback_url: str | None = None


class ProviderInfo(BaseModel):
    provider: PaymentProvider
    label: str
    description: str


class IntegrationDeleteResponse(MessageResponse):
    integration_id: int


class InitiatePaymentRequest(BaseModel):
    bill_id: int
    amount: float = Field(gt=0)
    payment_mode: PaymentMode
    integration_id: int | None = None
    sequence_number: int = Field(default=1, ge=1)


class TerminalPaymentRead(ORMSchema, TimestampSchema):
    id: int
    integration_id: int
    bill_id: int
    pos_payment_id: int | None
    transaction_number: str
    sequence_number: int
    amount: float
    payment_mode: PaymentMode
    allowed_payment_mode: str | None
    status: TerminalPaymentStatus
    provider_reference_id: str | None
    auth_code: str | None
    reference_number: str | None
    error_message: str | None
    provider: PaymentProvider | None = None
    bill_number: str | None = None


class PostbackAckResponse(BaseModel):
    success: bool
    message: str
    terminal_payment_id: int | None = None


class PublicOnlineGatewayRead(BaseModel):
    provider: PaymentProvider
    label: str
    description: str


class OnlineCheckoutCreate(BaseModel):
    outlet_id: int
    provider: PaymentProvider
    amount: float = Field(gt=0)
    order_id: str = Field(min_length=4, max_length=64)
    purpose: str = Field(default="booking", max_length=64)
    customer_name: str | None = Field(default=None, max_length=255)
    customer_email: str | None = Field(default=None, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=32)
    card_last4: str | None = Field(default=None, min_length=4, max_length=4, pattern=r"^\d{4}$")
    return_url: str | None = None
    cancel_url: str | None = None


class OnlineCheckoutResponse(BaseModel):
    provider: PaymentProvider
    paid: bool
    provider_order_id: str | None = None
    payment_session_id: str | None = None
    provider_payment_id: str | None = None
    amount: float
    message: str
    checkout_url: str | None = None
    card_last4: str | None = None
