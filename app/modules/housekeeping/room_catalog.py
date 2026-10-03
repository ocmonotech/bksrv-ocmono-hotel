"""Helpers for room type catalog (amenities list + image gallery JSON)."""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.modules.housekeeping.models import Amenity, HotelRoom, RoomType, RoomTypeAmenity
from app.modules.housekeeping.schemas import AmenityRead, RoomTypeRead


def parse_amenities(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,;|]", raw) if part.strip()]


def parse_gallery_urls(raw: str | None) -> list[str]:
    if not raw:
        return []
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(url).strip() for url in data if str(url).strip()]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in re.split(r"[\n,]", raw) if part.strip()]


def dump_gallery_urls(urls: list[str] | None) -> str | None:
    if not urls:
        return None
    cleaned = [url.strip() for url in urls if url and url.strip()]
    return json.dumps(cleaned) if cleaned else None


def _linked_amenities(db: Session | None, row: RoomType) -> list[Amenity]:
    links = list(getattr(row, "amenity_links", None) or [])
    amenities: list[Amenity] = []
    for link in links:
        if not getattr(link, "is_active", True):
            continue
        amenity = getattr(link, "amenity", None)
        if amenity is None and db is not None:
            amenity = db.get(Amenity, link.amenity_id)
        if amenity is not None and getattr(amenity, "is_active", True):
            amenities.append(amenity)
    amenities.sort(key=lambda item: (item.sort_order, item.name.lower()))
    return amenities


def serialize_amenity(row: Amenity, *, room_type_count: int = 0) -> AmenityRead:
    return AmenityRead(
        id=row.id,
        name=row.name,
        code=row.code,
        category=row.category,
        icon=row.icon,
        description=row.description,
        sort_order=row.sort_order,
        is_active=bool(row.is_active),
        room_type_count=room_type_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def serialize_room_type(row: RoomType, db: Session | None = None) -> RoomTypeRead:
    linked = _linked_amenities(db, row)
    catalog = [serialize_amenity(item) for item in linked]
    names = [item.name for item in linked] or parse_amenities(row.amenities)
    room_count = 0
    if db is not None:
        room_count = (
            db.query(HotelRoom)
            .filter(
                HotelRoom.room_type_id == row.id,
                HotelRoom.is_active.is_(True),
            )
            .count()
        )
    return RoomTypeRead(
        id=row.id,
        name=row.name,
        description=row.description,
        base_rate=float(row.base_rate),
        max_occupancy=row.max_occupancy,
        amenities=", ".join(names) if names else row.amenities,
        amenities_list=names,
        amenity_ids=[item.id for item in linked],
        catalog_amenities=catalog,
        image_url=row.image_url,
        gallery_urls=parse_gallery_urls(row.gallery_urls),
        bed_type=row.bed_type,
        room_size_sqft=row.room_size_sqft,
        is_active=bool(row.is_active),
        room_count=room_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def sync_room_type_amenities(
    db: Session,
    room_type: RoomType,
    amenity_ids: list[int],
) -> None:
    unique_ids = list(dict.fromkeys(int(item) for item in amenity_ids if item))
    amenities = []
    if unique_ids:
        amenities = (
            db.query(Amenity)
            .filter(
                Amenity.tenant_id == room_type.tenant_id,
                Amenity.id.in_(unique_ids),
                Amenity.is_active.is_(True),
            )
            .all()
        )
    valid_ids = {item.id for item in amenities}

    existing = (
        db.query(RoomTypeAmenity)
        .filter(RoomTypeAmenity.room_type_id == room_type.id)
        .all()
    )
    by_amenity = {link.amenity_id: link for link in existing}

    for amenity_id, link in list(by_amenity.items()):
        if amenity_id not in valid_ids:
            db.delete(link)

    for amenity_id in unique_ids:
        if amenity_id not in valid_ids:
            continue
        if amenity_id not in by_amenity:
            db.add(
                RoomTypeAmenity(
                    room_type_id=room_type.id,
                    amenity_id=amenity_id,
                )
            )

    names = [item.name for item in amenities]
    # Preserve catalog order from unique_ids
    by_id = {item.id: item for item in amenities}
    ordered_names = [by_id[i].name for i in unique_ids if i in by_id]
    room_type.amenities = ", ".join(ordered_names) if ordered_names else room_type.amenities
    db.flush()
