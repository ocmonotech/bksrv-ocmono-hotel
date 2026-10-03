from __future__ import annotations

from app.core.config import settings
from app.modules.ota.models import OtaPlatform
from app.modules.ota.providers.http_base import HttpOtaProvider


class BookingComHttpProvider(HttpOtaProvider):
    platform = OtaPlatform.BOOKING_COM
    label = "Booking.com"
    default_base_url = settings.ota_booking_com_api_base_url
