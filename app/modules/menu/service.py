from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import NotFoundError
from app.modules.brands.models import Brand
from app.modules.menu.models import (
    Combo,
    ComboItem,
    ItemAddon,
    MenuCategory,
    MenuItem,
    MenuItemIngredient,
    MenuItemOutlet,
)
from app.modules.menu.schemas import (
    ActiveMenuAddon,
    ActiveMenuCategory,
    ActiveMenuCombo,
    ActiveMenuItem,
    ActiveOutletMenuRead,
    ComboCreate,
    ComboItemRead,
    ComboRead,
    ItemAddonCreate,
    ItemAddonRead,
    MenuCategoryCreate,
    MenuCategoryRead,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemIngredientCreate,
    MenuItemIngredientRead,
    MenuItemIngredientUpdate,
    MenuRecipeCostRead,
    MenuItemOutletAvailabilitySet,
    MenuItemOutletPriceSet,
    MenuItemOutletRead,
    MenuItemRead,
    MenuItemUpdate,
)
from app.modules.inventory.models import RawMaterial
from app.modules.outlets.models import Outlet


def _money(value: float | None) -> float:
    return round(float(value or 0), 2)


def _pct(cost: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return round(cost / price * 100, 2)


def _material_cost_map(db: Session, tenant_id: int, material_ids: list[int]) -> dict[int, RawMaterial]:
    if not material_ids:
        return {}
    rows = (
        db.query(RawMaterial)
        .filter(RawMaterial.tenant_id == tenant_id, RawMaterial.id.in_(material_ids))
        .all()
    )
    return {row.id: row for row in rows}


def _ingredient_to_read(
    db: Session,
    tenant_id: int,
    ingredient: MenuItemIngredient,
    materials: dict[int, RawMaterial] | None = None,
) -> MenuItemIngredientRead:
    materials = materials or _material_cost_map(db, tenant_id, [ingredient.raw_material_id])
    material = materials.get(ingredient.raw_material_id)
    unit_cost = float(material.average_unit_cost or 0) if material else 0.0
    qty = float(ingredient.quantity_per_serving or 0)
    return MenuItemIngredientRead(
        id=ingredient.id,
        tenant_id=ingredient.tenant_id,
        brand_id=ingredient.brand_id,
        menu_item_id=ingredient.menu_item_id,
        raw_material_id=ingredient.raw_material_id,
        quantity_per_serving=qty,
        is_active=ingredient.is_active,
        raw_material_name=material.name if material else None,
        unit=material.unit.value if material else None,
        unit_cost=_money(unit_cost),
        line_cost=_money(unit_cost * qty),
    )


def refresh_menu_item_cost(
    db: Session,
    tenant_id: int,
    item_id: int,
    *,
    commit: bool = True,
) -> MenuRecipeCostRead:
    item = _get_item_entity(db, tenant_id, item_id)
    ingredients = (
        db.query(MenuItemIngredient)
        .filter(
            MenuItemIngredient.tenant_id == tenant_id,
            MenuItemIngredient.menu_item_id == item_id,
            MenuItemIngredient.is_active.is_(True),
        )
        .all()
    )
    materials = _material_cost_map(db, tenant_id, [row.raw_material_id for row in ingredients])
    recipe_cost = 0.0
    for ingredient in ingredients:
        material = materials.get(ingredient.raw_material_id)
        unit_cost = float(material.average_unit_cost or 0) if material else 0.0
        recipe_cost += unit_cost * float(ingredient.quantity_per_serving or 0)

    recipe_cost = _money(recipe_cost)
    base_price = float(item.base_price or 0)
    food_cost_percent = _pct(recipe_cost, base_price)
    item.recipe_cost = recipe_cost
    item.food_cost_percent = food_cost_percent
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return MenuRecipeCostRead(
        menu_item_id=item.id,
        item_name=item.item_name,
        base_price=base_price,
        recipe_cost=recipe_cost,
        food_cost_percent=food_cost_percent,
        gross_margin=_money(base_price - recipe_cost),
        ingredient_count=len(ingredients),
    )


def refresh_menu_items_for_material(
    db: Session,
    tenant_id: int,
    raw_material_id: int,
    *,
    commit: bool = True,
) -> None:
    menu_item_ids = (
        db.query(MenuItemIngredient.menu_item_id)
        .filter(
            MenuItemIngredient.tenant_id == tenant_id,
            MenuItemIngredient.raw_material_id == raw_material_id,
            MenuItemIngredient.is_active.is_(True),
        )
        .distinct()
        .all()
    )
    for (menu_item_id,) in menu_item_ids:
        refresh_menu_item_cost(db, tenant_id, menu_item_id, commit=commit)


def list_recipe_costs(
    db: Session,
    tenant_id: int,
    *,
    brand_id: int | None = None,
    high_food_cost_only: bool = False,
    threshold: float = 35.0,
) -> list[MenuRecipeCostRead]:
    query = db.query(MenuItem).filter(MenuItem.tenant_id == tenant_id, MenuItem.is_active.is_(True))
    if brand_id is not None:
        query = query.filter(MenuItem.brand_id == brand_id)
    if high_food_cost_only:
        query = query.filter(MenuItem.food_cost_percent >= threshold)
    items = query.order_by(MenuItem.food_cost_percent.desc(), MenuItem.item_name).all()
    return [
        MenuRecipeCostRead(
            menu_item_id=item.id,
            item_name=item.item_name,
            base_price=float(item.base_price or 0),
            recipe_cost=float(item.recipe_cost or 0),
            food_cost_percent=float(item.food_cost_percent or 0),
            gross_margin=_money(float(item.base_price or 0) - float(item.recipe_cost or 0)),
            ingredient_count=0,
        )
        for item in items
    ]


def list_categories(db: Session, tenant_id: int, brand_id: int | None = None) -> list[MenuCategoryRead]:
    query = db.query(MenuCategory).filter(MenuCategory.tenant_id == tenant_id)
    if brand_id is not None:
        query = query.filter(MenuCategory.brand_id == brand_id)
    categories = query.order_by(MenuCategory.sort_order, MenuCategory.name).all()
    return [MenuCategoryRead.model_validate(c) for c in categories]


def get_category(db: Session, tenant_id: int, category_id: int) -> MenuCategoryRead:
    category = _get_category_entity(db, tenant_id, category_id)
    return MenuCategoryRead.model_validate(category)


def create_category(
    db: Session,
    tenant_id: int,
    data: MenuCategoryCreate,
    default_brand_id: int | None = None,
) -> MenuCategoryRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    category = MenuCategory(
        tenant_id=tenant_id,
        brand_id=brand_id,
        name=data.name,
        description=data.description,
        sort_order=data.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return MenuCategoryRead.model_validate(category)


def update_category(
    db: Session,
    tenant_id: int,
    category_id: int,
    data: MenuCategoryUpdate,
) -> MenuCategoryRead:
    category = _get_category_entity(db, tenant_id, category_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return MenuCategoryRead.model_validate(category)


def delete_category(db: Session, tenant_id: int, category_id: int) -> None:
    category = _get_category_entity(db, tenant_id, category_id)
    category.is_active = False
    db.commit()


def list_items(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    brand_id: int | None = None,
    category_id: int | None = None,
) -> tuple[list[MenuItemRead], int]:
    query = db.query(MenuItem).filter(MenuItem.tenant_id == tenant_id)
    if brand_id is not None:
        query = query.filter(MenuItem.brand_id == brand_id)
    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)
    query = query.order_by(MenuItem.item_name)
    items, total = paginate_query(query, page, page_size)
    return [MenuItemRead.model_validate(item) for item in items], total


def get_item(db: Session, tenant_id: int, item_id: int) -> MenuItemRead:
    item = _get_item_entity(db, tenant_id, item_id)
    return MenuItemRead.model_validate(item)


def create_item(
    db: Session,
    tenant_id: int,
    data: MenuItemCreate,
    default_brand_id: int | None = None,
) -> MenuItemRead:
    category = _get_category_entity(db, tenant_id, data.category_id)
    brand_id = data.brand_id or category.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    item = MenuItem(
        tenant_id=tenant_id,
        brand_id=brand_id,
        category_id=data.category_id,
        item_name=data.item_name,
        description=data.description,
        food_type=data.food_type,
        base_price=data.base_price,
        gst_percent=data.gst_percent,
        preparation_area=data.preparation_area,
        image_url=data.image_url,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return MenuItemRead.model_validate(item)


def update_item(db: Session, tenant_id: int, item_id: int, data: MenuItemUpdate) -> MenuItemRead:
    item = _get_item_entity(db, tenant_id, item_id)
    payload = data.model_dump(exclude_unset=True)
    if "category_id" in payload and payload["category_id"] is not None:
        _get_category_entity(db, tenant_id, payload["category_id"])
    for key, value in payload.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    if "base_price" in payload:
        refresh_menu_item_cost(db, tenant_id, item_id)
        db.refresh(item)
    return MenuItemRead.model_validate(item)


def delete_item(db: Session, tenant_id: int, item_id: int) -> None:
    item = _get_item_entity(db, tenant_id, item_id)
    item.is_active = False
    db.commit()


def set_outlet_price(
    db: Session,
    tenant_id: int,
    item_id: int,
    data: MenuItemOutletPriceSet,
) -> MenuItemOutletRead:
    item = _get_item_entity(db, tenant_id, item_id)
    outlet = _get_outlet_entity(db, tenant_id, data.outlet_id)
    mapping = _get_or_create_outlet_mapping(db, item, outlet, float(item.base_price))
    mapping.outlet_price = data.outlet_price
    db.commit()
    db.refresh(mapping)
    return MenuItemOutletRead.model_validate(mapping)


def set_outlet_availability(
    db: Session,
    tenant_id: int,
    item_id: int,
    data: MenuItemOutletAvailabilitySet,
) -> MenuItemOutletRead:
    item = _get_item_entity(db, tenant_id, item_id)
    outlet = _get_outlet_entity(db, tenant_id, data.outlet_id)
    mapping = _get_or_create_outlet_mapping(db, item, outlet, float(item.base_price))
    mapping.is_available = data.is_available
    db.commit()
    db.refresh(mapping)
    return MenuItemOutletRead.model_validate(mapping)


def create_addon(
    db: Session,
    tenant_id: int,
    item_id: int,
    data: ItemAddonCreate,
    default_brand_id: int | None = None,
) -> ItemAddonRead:
    item = _get_item_entity(db, tenant_id, item_id)
    brand_id = data.brand_id or item.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    addon = ItemAddon(
        tenant_id=tenant_id,
        brand_id=brand_id,
        menu_item_id=item.id,
        addon_name=data.addon_name,
        price=data.price,
    )
    db.add(addon)
    db.commit()
    db.refresh(addon)
    return ItemAddonRead.model_validate(addon)


def list_addons_for_item(
    db: Session,
    tenant_id: int,
    item_id: int,
) -> list[ItemAddonRead]:
    _get_item_entity(db, tenant_id, item_id)
    addons = (
        db.query(ItemAddon)
        .filter(
            ItemAddon.tenant_id == tenant_id,
            ItemAddon.menu_item_id == item_id,
            ItemAddon.is_active.is_(True),
        )
        .order_by(ItemAddon.id)
        .all()
    )
    return [ItemAddonRead.model_validate(addon) for addon in addons]


def list_ingredients_by_item(
    db: Session,
    tenant_id: int,
    item_id: int,
) -> list[MenuItemIngredientRead]:
    _get_item_entity(db, tenant_id, item_id)
    ingredients = (
        db.query(MenuItemIngredient)
        .filter(
            MenuItemIngredient.tenant_id == tenant_id,
            MenuItemIngredient.menu_item_id == item_id,
            MenuItemIngredient.is_active.is_(True),
        )
        .order_by(MenuItemIngredient.id)
        .all()
    )
    materials = _material_cost_map(db, tenant_id, [row.raw_material_id for row in ingredients])
    return [_ingredient_to_read(db, tenant_id, row, materials) for row in ingredients]


def create_ingredient(
    db: Session,
    tenant_id: int,
    item_id: int,
    data: MenuItemIngredientCreate,
    default_brand_id: int | None = None,
) -> MenuItemIngredientRead:
    item = _get_item_entity(db, tenant_id, item_id)
    brand_id = data.brand_id or item.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)
    _get_raw_material_entity(db, tenant_id, data.raw_material_id)

    ingredient = MenuItemIngredient(
        tenant_id=tenant_id,
        brand_id=brand_id,
        menu_item_id=item.id,
        raw_material_id=data.raw_material_id,
        quantity_per_serving=data.quantity_per_serving,
    )
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    refresh_menu_item_cost(db, tenant_id, item.id)
    return _ingredient_to_read(db, tenant_id, ingredient)


def update_ingredient(
    db: Session,
    tenant_id: int,
    item_id: int,
    ingredient_id: int,
    data: MenuItemIngredientUpdate,
) -> MenuItemIngredientRead:
    _get_item_entity(db, tenant_id, item_id)
    ingredient = _get_ingredient_entity(db, tenant_id, item_id, ingredient_id)
    payload = data.model_dump(exclude_unset=True)

    if "raw_material_id" in payload and payload["raw_material_id"] is not None:
        _get_raw_material_entity(db, tenant_id, payload["raw_material_id"])

    for key, value in payload.items():
        setattr(ingredient, key, value)

    db.commit()
    db.refresh(ingredient)
    refresh_menu_item_cost(db, tenant_id, item_id)
    return _ingredient_to_read(db, tenant_id, ingredient)


def delete_ingredient(
    db: Session,
    tenant_id: int,
    item_id: int,
    ingredient_id: int,
) -> None:
    _get_item_entity(db, tenant_id, item_id)
    ingredient = _get_ingredient_entity(db, tenant_id, item_id, ingredient_id)
    ingredient.is_active = False
    db.commit()
    refresh_menu_item_cost(db, tenant_id, item_id)


def create_combo(
    db: Session,
    tenant_id: int,
    data: ComboCreate,
    default_brand_id: int | None = None,
) -> ComboRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    combo = Combo(
        tenant_id=tenant_id,
        brand_id=brand_id,
        combo_name=data.combo_name,
        combo_price=data.combo_price,
    )
    db.add(combo)
    db.flush()

    for line in data.items:
        menu_item = _get_item_entity(db, tenant_id, line.menu_item_id)
        if menu_item.brand_id and brand_id and menu_item.brand_id != brand_id:
            raise NotFoundError(f"Menu item {line.menu_item_id} does not belong to this brand")
        db.add(
            ComboItem(
                combo_id=combo.id,
                menu_item_id=line.menu_item_id,
                quantity=line.quantity,
            )
        )

    db.commit()
    return get_combo(db, tenant_id, combo.id)


def get_combo(db: Session, tenant_id: int, combo_id: int) -> ComboRead:
    combo = (
        db.query(Combo)
        .options(joinedload(Combo.items))
        .filter(Combo.id == combo_id, Combo.tenant_id == tenant_id)
        .first()
    )
    if combo is None:
        raise NotFoundError("Combo not found")
    return _to_combo_read(combo)


def list_combos(
    db: Session,
    tenant_id: int,
    brand_id: int | None = None,
) -> list[ComboRead]:
    q = (
        db.query(Combo)
        .options(joinedload(Combo.items))
        .filter(Combo.tenant_id == tenant_id, Combo.is_active.is_(True))
    )
    if brand_id is not None:
        q = q.filter(Combo.brand_id == brand_id)
    combos = q.order_by(Combo.id.desc()).all()
    return [_to_combo_read(combo) for combo in combos]


def get_active_menu_for_outlet(db: Session, tenant_id: int, outlet_id: int) -> ActiveOutletMenuRead:
    outlet = _get_outlet_entity(db, tenant_id, outlet_id)

    categories = (
        db.query(MenuCategory)
        .filter(
            MenuCategory.tenant_id == tenant_id,
            MenuCategory.brand_id == outlet.brand_id,
            MenuCategory.is_active.is_(True),
        )
        .order_by(MenuCategory.sort_order, MenuCategory.name)
        .all()
    )

    items = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.addons), joinedload(MenuItem.outlet_mappings))
        .filter(
            MenuItem.tenant_id == tenant_id,
            MenuItem.brand_id == outlet.brand_id,
            MenuItem.is_active.is_(True),
        )
        .all()
    )

    outlet_map = {
        mapping.menu_item_id: mapping
        for mapping in db.query(MenuItemOutlet).filter(MenuItemOutlet.outlet_id == outlet_id).all()
    }

    items_by_category: dict[int, list[ActiveMenuItem]] = {category.id: [] for category in categories}
    for item in items:
        mapping = outlet_map.get(item.id)
        if mapping is not None and not mapping.is_available:
            continue
        outlet_price = float(mapping.outlet_price) if mapping else float(item.base_price)
        active_item = ActiveMenuItem(
            id=item.id,
            item_name=item.item_name,
            description=item.description,
            food_type=item.food_type,
            base_price=float(item.base_price),
            outlet_price=outlet_price,
            gst_percent=float(item.gst_percent),
            preparation_area=item.preparation_area,
            image_url=item.image_url,
            is_available=mapping.is_available if mapping else True,
            addons=[
                ActiveMenuAddon(id=addon.id, addon_name=addon.addon_name, price=float(addon.price))
                for addon in item.addons
                if addon.is_active
            ],
        )
        if item.category_id in items_by_category:
            items_by_category[item.category_id].append(active_item)

    active_categories = [
        ActiveMenuCategory(
            id=category.id,
            name=category.name,
            description=category.description,
            sort_order=category.sort_order,
            items=items_by_category.get(category.id, []),
        )
        for category in categories
        if items_by_category.get(category.id)
    ]

    combos = (
        db.query(Combo)
        .options(joinedload(Combo.items))
        .filter(
            Combo.tenant_id == tenant_id,
            Combo.brand_id == outlet.brand_id,
            Combo.is_active.is_(True),
        )
        .all()
    )

    combo_reads: list[ActiveMenuCombo] = []
    for combo in combos:
        lines: list[ComboItemRead] = []
        for line in combo.items:
            menu_item = db.get(MenuItem, line.menu_item_id)
            lines.append(
                ComboItemRead(
                    id=line.id,
                    menu_item_id=line.menu_item_id,
                    quantity=line.quantity,
                    item_name=menu_item.item_name if menu_item else None,
                )
            )
        combo_reads.append(
            ActiveMenuCombo(
                id=combo.id,
                combo_name=combo.combo_name,
                combo_price=float(combo.combo_price),
                items=lines,
            )
        )

    return ActiveOutletMenuRead(
        outlet_id=outlet.id,
        brand_id=outlet.brand_id,
        categories=active_categories,
        combos=combo_reads,
    )


def get_public_outlet_menu(db: Session, outlet_id: int) -> "PublicOutletMenuRead":
    from app.modules.brands.models import Brand
    from app.modules.menu.schemas import (
        PublicClickCollectInfo,
        PublicMenuTableOption,
        PublicOutletMenuRead,
    )
    from app.modules.pos.service import build_click_collect_slots, get_click_collect_config
    from app.modules.tables.models import RestaurantTable

    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    brand = db.get(Brand, outlet.brand_id) if outlet.brand_id else None
    menu = get_active_menu_for_outlet(db, outlet.tenant_id, outlet_id)
    tables = (
        db.query(RestaurantTable)
        .filter(
            RestaurantTable.tenant_id == outlet.tenant_id,
            RestaurantTable.outlet_id == outlet_id,
            RestaurantTable.is_active.is_(True),
        )
        .order_by(RestaurantTable.table_number)
        .all()
    )
    cfg = get_click_collect_config(db, outlet.tenant_id, outlet_id)
    slots = build_click_collect_slots(cfg)
    click_collect = PublicClickCollectInfo(
        enabled=bool(cfg.get("enabled", True)),
        open=str(cfg.get("open") or "08:00"),
        close=str(cfg.get("close") or "22:00"),
        slot_minutes=int(cfg.get("slot_minutes") or 15),
        prep_sla_minutes=int(cfg.get("prep_sla_minutes") or 20),
        min_lead_minutes=int(cfg.get("min_lead_minutes") or 20),
        horizon_hours=int(cfg.get("horizon_hours") or 4),
        slots=[slot.isoformat(timespec="seconds") for slot in slots],
    )
    return PublicOutletMenuRead(
        outlet_id=menu.outlet_id,
        outlet_name=outlet.outlet_name,
        location=outlet.location,
        address=outlet.address,
        brand_id=menu.brand_id,
        brand_name=brand.brand_name if brand else None,
        logo_url=brand.logo_url if brand else None,
        support_number=brand.support_number if brand else None,
        categories=menu.categories,
        combos=menu.combos,
        tables=[
            PublicMenuTableOption(
                id=table.id,
                table_number=table.table_number,
                capacity=int(table.capacity or 2),
                status=table.status.value if hasattr(table.status, "value") else str(table.status),
            )
            for table in tables
        ],
        click_collect=click_collect,
    )


def _get_category_entity(db: Session, tenant_id: int, category_id: int) -> MenuCategory:
    category = (
        db.query(MenuCategory)
        .filter(MenuCategory.id == category_id, MenuCategory.tenant_id == tenant_id)
        .first()
    )
    if category is None:
        raise NotFoundError("Category not found")
    return category


def _get_item_entity(db: Session, tenant_id: int, item_id: int) -> MenuItem:
    item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.tenant_id == tenant_id).first()
    if item is None:
        raise NotFoundError("Menu item not found")
    return item


def _get_ingredient_entity(
    db: Session,
    tenant_id: int,
    item_id: int,
    ingredient_id: int,
) -> MenuItemIngredient:
    ingredient = (
        db.query(MenuItemIngredient)
        .filter(
            MenuItemIngredient.id == ingredient_id,
            MenuItemIngredient.menu_item_id == item_id,
            MenuItemIngredient.tenant_id == tenant_id,
        )
        .first()
    )
    if ingredient is None:
        raise NotFoundError("Menu item ingredient not found")
    return ingredient


def _get_raw_material_entity(db: Session, tenant_id: int, raw_material_id: int) -> RawMaterial:
    material = (
        db.query(RawMaterial)
        .filter(RawMaterial.id == raw_material_id, RawMaterial.tenant_id == tenant_id)
        .first()
    )
    if material is None:
        raise NotFoundError("Raw material not found")
    return material


def _get_outlet_entity(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id)
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _validate_brand(db: Session, tenant_id: int, brand_id: int | None) -> None:
    if brand_id is None:
        return
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.tenant_id == tenant_id).first()
    if brand is None:
        raise NotFoundError("Brand not found")


def _get_or_create_outlet_mapping(
    db: Session,
    item: MenuItem,
    outlet: Outlet,
    default_price: float,
) -> MenuItemOutlet:
    mapping = (
        db.query(MenuItemOutlet)
        .filter(
            MenuItemOutlet.outlet_id == outlet.id,
            MenuItemOutlet.menu_item_id == item.id,
        )
        .first()
    )
    if mapping:
        return mapping

    mapping = MenuItemOutlet(
        tenant_id=item.tenant_id,
        brand_id=item.brand_id or outlet.brand_id,
        outlet_id=outlet.id,
        menu_item_id=item.id,
        outlet_price=default_price,
        is_available=True,
    )
    db.add(mapping)
    db.flush()
    return mapping


def _to_combo_read(combo: Combo) -> ComboRead:
    return ComboRead(
        id=combo.id,
        tenant_id=combo.tenant_id,
        brand_id=combo.brand_id,
        combo_name=combo.combo_name,
        combo_price=float(combo.combo_price),
        is_active=combo.is_active,
        created_at=combo.created_at,
        updated_at=combo.updated_at,
        items=[
            ComboItemRead(
                id=line.id,
                menu_item_id=line.menu_item_id,
                quantity=line.quantity,
            )
            for line in combo.items
        ],
    )
