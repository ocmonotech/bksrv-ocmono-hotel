from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


@contextmanager
def task_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def enqueue_task(task: Any, *args: Any, **kwargs: Any) -> Any | None:
    """Enqueue a Celery task when enabled; otherwise log and return None."""
    if not settings.celery_enabled:
        logger.info(
            "Celery disabled; skipped background task %s",
            getattr(task, "name", task),
        )
        return None

    return task.delay(*args, **kwargs)
