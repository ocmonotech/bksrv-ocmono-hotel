from __future__ import annotations

from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()
