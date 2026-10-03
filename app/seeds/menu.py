"""Menu categories, items, addons, combos, and outlet mappings."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.menu.models import (
    Combo,
    ComboItem,
    ItemAddon,
    MenuCategory,
    MenuItem,
    MenuItemIngredient,
    MenuItemOutlet,
)
from app.seeds.base import SeedContext
from app.seeds.constants import COMBOS, ITEM_ADDONS, MENU_CATEGORIES, MENU_ITEMS


def seed_menu(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    categories = _seed_menu_categories(db, tenant.id, brand.id)
    ctx.categories = categories
    ctx.menu_items = _seed_menu_items(db, tenant.id, brand.id, categories, ctx.outlets)
    _seed_item_addons(db, tenant.id, brand.id, ctx.menu_items)
    _seed_combos(db, tenant.id, brand.id, ctx.menu_items)
    _seed_menu_ingredients(db, tenant.id, brand.id, ctx.menu_items, ctx.raw_materials)


def _seed_menu_categories(db: Session, tenant_id: int, brand_id: int) -> dict[str, MenuCategory]:
    categories: dict[str, MenuCategory] = {}
    for name, sort_order in MENU_CATEGORIES:
        category = (
            db.query(MenuCategory)
            .filter(
                MenuCategory.tenant_id == tenant_id,
                MenuCategory.brand_id == brand_id,
                MenuCategory.name == name,
            )
            .first()
        )
        if category is None:
            category = MenuCategory(
                tenant_id=tenant_id,
                brand_id=brand_id,
                name=name,
                description=f"{name} at Bombay Bite Collective",
                sort_order=sort_order,
            )
            db.add(category)
            db.flush()
        categories[name] = category
    return categories


def _seed_menu_items(
    db: Session,
    tenant_id: int,
    brand_id: int,
    categories: dict[str, MenuCategory],
    outlets: dict,
) -> dict[str, MenuItem]:
    items: dict[str, MenuItem] = {}
    for category_name, item_name, food_type, price, prep_area in MENU_ITEMS:
        category = categories[category_name]
        item = (
            db.query(MenuItem)
            .filter(
                MenuItem.tenant_id == tenant_id,
                MenuItem.brand_id == brand_id,
                MenuItem.item_name == item_name,
            )
            .first()
        )
        if item is None:
            item = MenuItem(
                tenant_id=tenant_id,
                brand_id=brand_id,
                category_id=category.id,
                item_name=item_name,
                description=f"Signature {item_name.lower()}",
                food_type=food_type,
                base_price=price,
                gst_percent=5,
                preparation_area=prep_area,
                image_url=_demo_image_for(item_name),
            )
            db.add(item)
            db.flush()
        elif not item.image_url:
            item.image_url = _demo_image_for(item_name)

        for outlet in outlets.values():
            mapping = (
                db.query(MenuItemOutlet)
                .filter(
                    MenuItemOutlet.outlet_id == outlet.id,
                    MenuItemOutlet.menu_item_id == item.id,
                )
                .first()
            )
            if mapping is None:
                db.add(
                    MenuItemOutlet(
                        tenant_id=tenant_id,
                        brand_id=brand_id,
                        outlet_id=outlet.id,
                        menu_item_id=item.id,
                        outlet_price=price,
                        is_available=True,
                    )
                )
        items[item_name] = item
    return items


def _seed_item_addons(
    db: Session,
    tenant_id: int,
    brand_id: int,
    menu_items: dict[str, MenuItem],
) -> None:
    for item_name, addon_name, price in ITEM_ADDONS:
        menu_item = menu_items.get(item_name)
        if menu_item is None:
            continue
        addon = (
            db.query(ItemAddon)
            .filter(
                ItemAddon.tenant_id == tenant_id,
                ItemAddon.menu_item_id == menu_item.id,
                ItemAddon.addon_name == addon_name,
            )
            .first()
        )
        if addon is None:
            db.add(
                ItemAddon(
                    tenant_id=tenant_id,
                    brand_id=brand_id,
                    menu_item_id=menu_item.id,
                    addon_name=addon_name,
                    price=price,
                )
            )


def _seed_combos(
    db: Session,
    tenant_id: int,
    brand_id: int,
    menu_items: dict[str, MenuItem],
) -> None:
    for combo_name, combo_price, combo_items in COMBOS:
        combo = (
            db.query(Combo)
            .filter(
                Combo.tenant_id == tenant_id,
                Combo.brand_id == brand_id,
                Combo.combo_name == combo_name,
            )
            .first()
        )
        if combo is None:
            combo = Combo(
                tenant_id=tenant_id,
                brand_id=brand_id,
                combo_name=combo_name,
                combo_price=combo_price,
            )
            db.add(combo)
            db.flush()

            for item_name, quantity in combo_items:
                menu_item = menu_items.get(item_name)
                if menu_item is None:
                    continue
                existing = (
                    db.query(ComboItem)
                    .filter(ComboItem.combo_id == combo.id, ComboItem.menu_item_id == menu_item.id)
                    .first()
                )
                if existing is None:
                    db.add(ComboItem(combo_id=combo.id, menu_item_id=menu_item.id, quantity=quantity))


def _seed_menu_ingredients(
    db: Session,
    tenant_id: int,
    brand_id: int,
    menu_items: dict[str, MenuItem],
    raw_materials: dict,
) -> None:
    ingredient_map = [
        ("Butter Chicken", "Chicken Breast", 0.25),
        ("Butter Chicken", "Butter", 0.05),
        ("Butter Chicken", "Fresh Cream", 0.05),
        ("Paneer Tikka", "Paneer", 0.2),
        ("Chicken Biryani", "Basmati Rice", 0.15),
        ("Chicken Biryani", "Chicken Breast", 0.2),
        ("Dal Makhani", "Tomato", 0.05),
        ("Dal Makhani", "Butter", 0.03),
        ("Garlic Naan", "Naan Flour", 0.08),
    ]
    for item_name, material_name, qty in ingredient_map:
        menu_item = menu_items.get(item_name)
        material = raw_materials.get(material_name)
        if menu_item is None or material is None:
            continue
        existing = (
            db.query(MenuItemIngredient)
            .filter(
                MenuItemIngredient.tenant_id == tenant_id,
                MenuItemIngredient.menu_item_id == menu_item.id,
                MenuItemIngredient.raw_material_id == material.id,
            )
            .first()
        )
        if existing is None:
            db.add(
                MenuItemIngredient(
                    tenant_id=tenant_id,
                    brand_id=brand_id,
                    menu_item_id=menu_item.id,
                    raw_material_id=material.id,
                    quantity_per_serving=qty,
                )
            )


_DEMO_IMAGES = {
    "Paneer Tikka": "https://images.unsplash.com/photo-1567188040759-fb8a803dbca4?w=640&q=80",
    "Butter Chicken": "https://images.unsplash.com/photo-1603894584373-5ac82b2ae958?w=640&q=80",
    "Dal Makhani": "https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=640&q=80",
    "Garlic Naan": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=640&q=80",
    "Masala Dosa": "https://images.unsplash.com/photo-1630383249896-424e482df921?w=640&q=80",
    "Veg Biryani": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=640&q=80",
    "Chicken Biryani": "https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=640&q=80",
    "Mango Lassi": "https://images.unsplash.com/photo-1577805947697-89e18249d767?w=640&q=80",
    "Gulab Jamun": "https://images.unsplash.com/photo-1666195590988-c6f0f8b2e8f8?w=640&q=80",
}


def _demo_image_for(item_name: str) -> str | None:
    if item_name in _DEMO_IMAGES:
        return _DEMO_IMAGES[item_name]
    # Stable Unsplash food fallback so guest menu cards never look empty
    seed = abs(hash(item_name)) % 1000
    return f"https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=640&q=80&sig={seed}"

