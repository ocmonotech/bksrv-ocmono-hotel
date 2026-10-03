"""Loyalty earn/burn ledger and tier definitions."""

from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class LoyaltyTxnType(str, enum.Enum):
    EARN = "earn"
    BURN = "burn"
    ADJUST = "adjust"
    EXPIRE = "expire"


class LoyaltySource(str, enum.Enum):
    POS = "pos"
    PMS_STAY = "pms_stay"
    MANUAL = "manual"
    REDEEM_POS = "redeem_pos"
    REDEEM_FOLIO = "redeem_folio"


class LoyaltyTier(Base, BaseMixin, TenantBrandMixin):
    """Membership tier thresholds for a brand/tenant."""

    __tablename__ = "loyalty_tiers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_loyalty_tier_tenant_code"),
    )

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    min_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    earn_multiplier: Mapped[float] = mapped_column(Numeric(5, 2), default=1, nullable=False)
    color: Mapped[str] = mapped_column(String(32), default="slate", nullable=False)
    perks: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LoyaltyLedger(Base, BaseMixin, TenantBrandMixin):
    """Immutable-style points movement with idempotency on source+reference."""

    __tablename__ = "loyalty_ledger"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source",
            "reference_type",
            "reference_id",
            "txn_type",
            name="uq_loyalty_ledger_idempotent",
        ),
    )

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    txn_type: Mapped[LoyaltyTxnType] = mapped_column(
        Enum(LoyaltyTxnType, native_enum=False, length=16),
        nullable=False,
        index=True,
    )
    source: Mapped[LoyaltySource] = mapped_column(
        Enum(LoyaltySource, native_enum=False, length=24),
        nullable=False,
        index=True,
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_basis: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    customer = relationship("Customer", backref="loyalty_ledger")
