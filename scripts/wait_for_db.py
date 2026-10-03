"""Wait until MySQL accepts connections (used by Docker entrypoint)."""

from __future__ import annotations

import os
import sys
import time

from sqlalchemy import create_engine, text

from app.core.config import settings


def main() -> int:
    max_retries = int(os.getenv("DB_WAIT_RETRIES", "30"))
    delay = float(os.getenv("DB_WAIT_INTERVAL", "2"))

    engine = create_engine(settings.database_url, pool_pre_ping=True)

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database is ready.")
            return 0
        except Exception as exc:
            print(f"Waiting for database ({attempt}/{max_retries}): {exc}")
            time.sleep(delay)

    print("Database not ready in time.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
