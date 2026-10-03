from __future__ import annotations

from typing import Optional

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class AuditAction(str, enum.Enum):
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    BILL_CANCELLED = "bill_cancelled"
    DISCOUNT_APPROVED = "discount_approved"
    STOCK_ADJUSTED = "stock_adjusted"
    STOCK_SALE = "stock_sale"
    USER_ROLE_UPDATED = "user_role_updated"
    CAMPAIGN_LAUNCHED = "campaign_launched"
    AI_PROVIDER_UPDATED = "ai_provider_updated"
    COMMS_PROVIDER_UPDATED = "comms_provider_updated"
    TABLE_MERGED = "table_merged"
    OFFER_UPDATED = "offer_updated"


class AuditLog(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "audit_logs"

    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    module_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    old_data_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_data_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
