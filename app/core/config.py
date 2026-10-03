from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "RestroChain OS API"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = (
        "mysql+pymysql://user:password@10.122.0.7:3306/restrochain_db?charset=utf8mb4"
    )

    jwt_secret_key: str = "change_this_secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 7

    backend_cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        validation_alias="BACKEND_CORS_ORIGINS",
    )

    ai_master_encryption_key: str = "change_this_later"

    whatsapp_provider: str = "mock"
    sms_provider: str = "mock"
    email_provider: str = "mock"

    whatsapp_api_base_url: str = "https://stub.whatsapp.local"
    whatsapp_api_token: str = "stub-whatsapp-token"
    sms_api_base_url: str = "https://stub.sms.local"
    sms_api_key: str = "stub-sms-key"
    sms_sender_id: str = "BMBITE"
    email_api_base_url: str = "https://stub.email.local"
    email_api_key: str = "stub-email-key"
    email_from_address: str = "noreply@stub.bombaybite.local"
    openai_api_key: str = "stub-openai-key"
    openai_api_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = "stub-anthropic-key"
    ai_default_provider: str = "openai"
    # Used with local Ollama / Groq OpenAI-compatible endpoints
    ai_default_model: str = "llama3.2:1b"
    ai_monthly_budget_inr: float = 25000.0
    default_chain_name: str = "Bombay Bite Collective"
    default_timezone: str = "Asia/Kolkata"
    enable_stub_external_services: bool = True
    public_api_base_url: str = "http://localhost:8000"
    delivery_provider: str = "mock"
    payment_provider: str = "mock"
    pinelabs_api_base_url: str = "https://www.plutuscloudserviceuat.in:8201"
    razorpay_api_base_url: str = "https://api.razorpay.com/v1"
    cashfree_api_base_url: str = "https://sandbox.cashfree.com/pg"
    phonepe_api_base_url: str = "https://api-preprod.phonepe.com/apis/pg-sandbox"
    paytm_api_base_url: str = "https://securegw-stage.paytm.in"
    ccavenue_api_base_url: str = "https://test.ccavenue.com"

    celery_enabled: bool = False
    celery_app_name: str = "restrochain"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_default_queue: str = "default"

    ota_default_adapter_mode: str = "mock"
    ota_booking_com_api_base_url: str = "https://api.channel.booking.com/v1"
    ota_mmt_api_base_url: str = "https://api.mmt.com/hotel-connect/v1"
    ota_expedia_api_base_url: str = "https://services.expediapartnercentral.com/v1"
    ota_http_timeout_seconds: float = 30.0

    auto_seed_on_startup: bool = True

    spa_reminder_hours_before: int = 24
    spa_reminder_window_minutes: int = 30

    banquet_reminder_hours_before: int = 24
    banquet_reminder_window_minutes: int = 30

    pms_reminder_hours_before: int = 24
    pms_reminder_window_minutes: int = 30

    media_root: str = Field(default="/app/media", validation_alias="MEDIA_ROOT")

    guest_upi_vpa: str = Field(default="restrochain@upi", validation_alias="GUEST_UPI_VPA")
    guest_upi_payee_name: str = Field(default="RestroChain Cafe", validation_alias="GUEST_UPI_PAYEE_NAME")

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
