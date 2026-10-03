"""Guest-portal booking add-ons — meals, extra bed, parking, etc."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

AddonUnit = Literal["per_guest_night", "per_night", "per_stay"]


@dataclass(frozen=True)
class AddonCatalogItem:
    code: str
    name: str
    description: str
    price: float
    unit: AddonUnit
    max_quantity: int | None = None
    default_qty_mode: Literal["guests", "one", "zero"] = "zero"


DEFAULT_PUBLIC_ADDONS: list[AddonCatalogItem] = [
    AddonCatalogItem(
        code="breakfast",
        name="Breakfast",
        description="Buffet breakfast per guest, per night",
        price=450,
        unit="per_guest_night",
        default_qty_mode="zero",
    ),
    AddonCatalogItem(
        code="lunch",
        name="Lunch",
        description="Set lunch per guest, per night",
        price=650,
        unit="per_guest_night",
        default_qty_mode="zero",
    ),
    AddonCatalogItem(
        code="dinner",
        name="Dinner",
        description="Set dinner per guest, per night",
        price=850,
        unit="per_guest_night",
        default_qty_mode="zero",
    ),
    AddonCatalogItem(
        code="extra_bed",
        name="Extra bed",
        description="Extra bed / rollaway, per night",
        price=1200,
        unit="per_night",
        max_quantity=2,
        default_qty_mode="zero",
    ),
    AddonCatalogItem(
        code="parking",
        name="Parking",
        description="On-site parking, per night",
        price=200,
        unit="per_night",
        max_quantity=2,
        default_qty_mode="zero",
    ),
]


def addon_catalog_map() -> dict[str, AddonCatalogItem]:
    return {item.code: item for item in DEFAULT_PUBLIC_ADDONS}


@dataclass
class ResolvedAddonLine:
    code: str
    name: str
    unit: AddonUnit
    unit_price: float
    quantity: int
    nights: int
    guests: int
    total: float
    description: str


def resolve_addon_lines(
    selections: list[dict[str, Any]] | None,
    *,
    nights: int,
    adults: int,
    children: int,
) -> list[ResolvedAddonLine]:
    if not selections:
        return []
    catalog = addon_catalog_map()
    guests = max(1, int(adults) + int(children))
    nights = max(1, int(nights))
    lines: list[ResolvedAddonLine] = []

    for raw in selections:
        code = str(raw.get("code") or "").strip().lower()
        item = catalog.get(code)
        if item is None:
            continue
        qty = int(raw.get("quantity") or 0)
        if qty <= 0:
            continue
        if item.max_quantity is not None:
            qty = min(qty, item.max_quantity)
        if item.unit == "per_guest_night":
            # quantity = number of guests covered
            qty = min(qty, guests)
            total = round(item.price * qty * nights, 2)
            description = f"{item.name} x {qty} guest(s) x {nights} night(s)"
        elif item.unit == "per_night":
            total = round(item.price * qty * nights, 2)
            description = f"{item.name} x {qty} x {nights} night(s)"
        else:
            total = round(item.price * qty, 2)
            description = f"{item.name} x {qty}"

        if total <= 0:
            continue
        lines.append(
            ResolvedAddonLine(
                code=item.code,
                name=item.name,
                unit=item.unit,
                unit_price=float(item.price),
                quantity=qty,
                nights=nights,
                guests=guests,
                total=total,
                description=description,
            )
        )
    return lines


def dump_addon_lines(lines: list[ResolvedAddonLine]) -> str:
    payload = [
        {
            "code": line.code,
            "name": line.name,
            "unit": line.unit,
            "unit_price": line.unit_price,
            "quantity": line.quantity,
            "nights": line.nights,
            "total": line.total,
            "description": line.description,
        }
        for line in lines
    ]
    return json.dumps(payload)


def parse_addon_lines(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def addon_total(lines: list[ResolvedAddonLine]) -> float:
    return round(sum(line.total for line in lines), 2)
