from __future__ import annotations

from app.core.config import settings
from app.modules.ota.models import OtaPlatform
from app.modules.ota.providers.http_base import HttpOtaProvider


class ExpediaHttpProvider(HttpOtaProvider):
    platform = OtaPlatform.EXPEDIA
    label = "Expedia"
    default_base_url = settings.ota_expedia_api_base_url
