"""Ensure demo DB has full seed coverage + local AI provider config (idempotent)."""

from __future__ import annotations

import sys

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.ai.models import AiProvider, AiProviderStatus
from app.seeds.orchestrator import run_seed


def _configure_local_ai_provider(db) -> None:
    """Point the default AI provider at the OpenAI-compatible endpoint (Ollama/Groq)."""
    provider = (
        db.query(AiProvider)
        .filter(AiProvider.is_default.is_(True), AiProvider.is_active.is_(True))
        .order_by(AiProvider.id.asc())
        .first()
    )
    if provider is None:
        provider = (
            db.query(AiProvider)
            .filter(AiProvider.is_active.is_(True))
            .order_by(AiProvider.id.asc())
            .first()
        )
    if provider is None:
        return

    base = settings.openai_api_base_url.rstrip("/")
    if base and "api.openai.com" not in base:
        provider.api_base_url = base
    if settings.ai_default_model:
        provider.default_model = settings.ai_default_model
    if settings.openai_api_key and not settings.openai_api_key.startswith("stub"):
        provider.status = AiProviderStatus.CONNECTED
        provider.is_default = True
        provider.api_key_last4 = settings.openai_api_key[-4:]
        provider.encrypted_api_key = f"ENV:{settings.openai_api_key[:8]}…"


def main() -> int:
    db = SessionLocal()
    try:
        run_seed(db)
        _configure_local_ai_provider(db)
        db.commit()
        print("Full demo seed applied and AI provider configured.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Seed extensions failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
