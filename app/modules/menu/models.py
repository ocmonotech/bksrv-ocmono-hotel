from __future__ import annotations

from typing import Optional

import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class FoodType(str, enum.Enum):
    VEG = "veg"
    NON_VEG = "non_veg"
    EGG = "egg"


class PreparationArea(str, enum.Enum):
    KITCHEN = "kitchen"
    BAR = "bar"
    TANDOOR = "tandoor"
    DESSERT = "dessert"


class MenuCategory(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "menu_categories"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    items: Mapped[list["MenuItem"]] = relationship(back_populates="category")


class MenuItem(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "menu_items"

    category_id: Mapped[int] = mapped_column(ForeignKey("menu_categories.id"), index=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    food_type: Mapped[FoodType] = mapped_column(Enum(FoodType), default=FoodType.VEG)
    base_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    gst_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=5)
    recipe_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    food_cost_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    preparation_area: Mapped[PreparationArea] = mapped_column(
        Enum(PreparationArea), default=PreparationArea.KITCHEN
    )
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    category: Mapped["MenuCategory"] = relationship(back_populates="items")
    outlet_mappings: Mapped[list["MenuItemOutlet"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
    )
    addons: Mapped[list["ItemAddon"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
    )


class MenuItemOutlet(Base, TenantBrandMixin):
    __tablename__ = "menu_item_outlets"
    __table_args__ = (UniqueConstraint("outlet_id", "menu_item_id", name="uq_menu_item_outlet"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"), index=True)
    outlet_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    menu_item: Mapped["MenuItem"] = relationship(back_populates="outlet_mappings")


class ItemAddon(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "item_addons"

    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"), index=True)
    addon_name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    menu_item: Mapped["MenuItem"] = relationship(back_populates="addons")


class Combo(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "combos"

    combo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    combo_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    items: Mapped[list["ComboItem"]] = relationship(
        back_populates="combo",
        cascade="all, delete-orphan",
    )


class ComboItem(Base):
    __tablename__ = "combo_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    combo_id: Mapped[int] = mapped_column(ForeignKey("combos.id", ondelete="CASCADE"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    combo: Mapped["Combo"] = relationship(back_populates="items")


class MenuItemIngredient(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "menu_item_ingredients"

    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE"), index=True
    )
    raw_material_id: Mapped[int] = mapped_column(ForeignKey("raw_materials.id"), index=True)
    quantity_per_serving: Mapped[float] = mapped_column(Numeric(10, 3), default=1)

    menu_item: Mapped["MenuItem"] = relationship()
