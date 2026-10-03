"""Local media uploads for room-type images."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import AppError

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def media_root() -> Path:
    root = Path(settings.media_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def public_media_url(relative_path: str) -> str:
    clean = relative_path.lstrip("/")
    return f"/media/{clean}"


async def save_room_type_image(tenant_id: int, upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower()
    ext = ALLOWED_IMAGE_TYPES.get(content_type)
    if ext is None:
        raise AppError("Only JPEG, PNG, WEBP, or GIF images are allowed", code="invalid_image")

    raw = await upload.read()
    if not raw:
        raise AppError("Empty upload", code="empty_upload")
    if len(raw) > MAX_IMAGE_BYTES:
        raise AppError("Image must be 8MB or smaller", code="image_too_large")

    folder = media_root() / "room-types" / str(tenant_id)
    folder.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", (upload.filename or "room").rsplit(".", 1)[0])[:40]
    filename = f"{safe_stem or 'room'}-{uuid.uuid4().hex[:10]}{ext}"
    path = folder / filename
    path.write_bytes(raw)
    return public_media_url(f"room-types/{tenant_id}/{filename}")
