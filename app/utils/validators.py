import re

MOBILE_IN_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")


def is_valid_mobile(mobile: str) -> bool:
    cleaned = mobile.replace(" ", "").replace("-", "")
    return bool(MOBILE_IN_PATTERN.match(cleaned))


def normalize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "tenant"
