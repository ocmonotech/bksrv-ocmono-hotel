from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class BrandSetting(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "brand_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "brand_id", "setting_key", name="uq_brand_setting_key"),
    )

    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True, nullable=False)
    setting_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    setting_value_json: Mapped[str] = mapped_column(Text, default="{}")


class OutletSetting(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "outlet_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "outlet_id", "setting_key", name="uq_outlet_setting_key"),
    )

    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True, nullable=False)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    setting_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    setting_value_json: Mapped[str] = mapped_column(Text, default="{}")
