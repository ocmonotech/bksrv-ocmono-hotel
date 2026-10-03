"""Tenant operating model — drives which modules appear in the product UI."""

from __future__ import annotations

import enum


class BusinessType(str, enum.Enum):
    RESORT = "resort"
    MULTICHAIN = "multichain"
    CAFE = "cafe"
    RESTAURANT = "restaurant"


BUSINESS_TYPE_VALUES = {item.value for item in BusinessType}
