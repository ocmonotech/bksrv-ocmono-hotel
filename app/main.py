from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.modules  # noqa: F401 — register SQLAlchemy models
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import register_exception_handlers
from app.modules.auth.service import seed_demo_data
from app.modules.kot.ws import kot_websocket_endpoint

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_seed_on_startup:
        db = SessionLocal()
        try:
            seed_demo_data(db)
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Demo seed skipped on startup (run `python -m app.seed` after DB is ready): %s",
                exc,
            )
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    enable_docs = settings.is_development

    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Multi-outlet restaurant chain SaaS API",
        lifespan=lifespan,
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
    )

    register_exception_handlers(application)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix=settings.api_v1_prefix)

    media_dir = Path(settings.media_root)
    media_dir.mkdir(parents=True, exist_ok=True)
    application.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    @application.websocket("/ws/kot/{outlet_id}")
    async def kot_websocket(websocket: WebSocket, outlet_id: int) -> None:
        await kot_websocket_endpoint(websocket, outlet_id)

    @application.get("/", tags=["Health"])
    def root() -> dict:
        return {
            "message": settings.app_name,
            "health": "/health",
            "api_v1": settings.api_v1_prefix,
            "docs": "/docs" if enable_docs else None,
        }

    @application.get("/health", tags=["Health"])
    def health_check() -> dict:
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
        }

    return application


app = create_app()
