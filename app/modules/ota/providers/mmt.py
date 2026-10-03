from __future__ import annotations

from app.core.config import settings
from app.modules.ota.models import OtaPlatform
from app.modules.ota.providers.http_base import HttpOtaProvider


class MmtHttpProvider(HttpOtaProvider):
    platform = OtaPlatform.MMT
    label = "MakeMyTrip"
    default_base_url = settings.ota_mmt_api_base_url
