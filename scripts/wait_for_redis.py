"""Wait until Redis accepts connections (used by Celery Docker entrypoint)."""

from __future__ import annotations

import os
import sys
import time

import redis

from app.core.config import settings


def main() -> int:
    max_retries = int(os.getenv("REDIS_WAIT_RETRIES", "30"))
    delay = float(os.getenv("REDIS_WAIT_INTERVAL", "2"))
    client = redis.from_url(settings.celery_broker_url, socket_connect_timeout=2)

    for attempt in range(1, max_retries + 1):
        try:
            if client.ping():
                print("Redis is ready.")
                return 0
        except Exception as exc:
            print(f"Waiting for Redis ({attempt}/{max_retries}): {exc}")
            time.sleep(delay)

    print("Redis not ready in time.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
