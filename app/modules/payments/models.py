from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin
from app.modules.pos.models import PaymentMode


class PaymentProvider(str, enum.Enum):
    PINELABS = "pinelabs"
    RAZORPAY = "razorpay"
    PAYTM = "paytm"
    PHONEPE = "phonepe"
    CASHFREE = "cashfree"
    CCAVENUE = "ccavenue"


# Providers that support guest / online checkout (not only POS terminals).
ONLINE_CHECKOUT_PROVIDERS: frozenset[PaymentProvider] = frozenset(
    {
        PaymentProvider.RAZORPAY,
        PaymentProvider.PAYTM,
        PaymentProvider.PHONEPE,
        PaymentProvider.CASHFREE,
        PaymentProvider.CCAVENUE,
    }
)


class IntegrationStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"


class TerminalPaymentStatus(str, enum.Enum):
    INITIATED = "initiated"
    PENDING_TERMINAL = "pending_terminal"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutletPaymentIntegration(Base, BaseMixin, TenantBrandMixin):
    """Per-outlet connection to a payment terminal / gateway provider."""

    __tablename__ = "outlet_payment_integrations"
    __table_args__ = (
        UniqueConstraint("outlet_id", "provider", name="uq_outlet_payment_provider"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    provider: Mapped[PaymentProvider] = mapped_column(Enum(PaymentProvider), nullable=False)
    merchant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    store_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus), default=IntegrationStatus.PENDING, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_settle_on_success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    webhook_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    encrypted_security_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    terminal_payments: Mapped[list["TerminalPayment"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )


class TerminalPayment(Base, BaseMixin, TenantBrandMixin):
    """Tracks an in-flight or completed terminal payment linked to a POS bill."""

    __tablename__ = "terminal_payments"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "transaction_number",
            "sequence_number",
            name="uq_terminal_payment_sequence",
        ),
    )

    integration_id: Mapped[int] = mapped_column(
        ForeignKey("outlet_payment_integrations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    bill_id: Mapped[int] = mapped_column(
        ForeignKey("pos_bills.id", ondelete="CASCADE"), index=True, nullable=False
    )
    pos_payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pos_payments.id", ondelete="SET NULL"), nullable=True
    )
    transaction_number: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_mode: Mapped[PaymentMode] = mapped_column(Enum(PaymentMode), nullable=False)
    allowed_payment_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[TerminalPaymentStatus] = mapped_column(
        Enum(TerminalPaymentStatus), default=TerminalPaymentStatus.INITIATED, nullable=False
    )
    provider_reference_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    auth_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_request_json: Mapped[str] = mapped_column(Text, default="{}")
    raw_response_json: Mapped[str] = mapped_column(Text, default="{}")

    integration: Mapped["OutletPaymentIntegration"] = relationship(back_populates="terminal_payments")
