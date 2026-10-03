"""
Gunicorn configuration for production deployment.

Usage (from backend/ with virtualenv active):

    gunicorn app.main:app -c gunicorn_conf.py

Or:

    ./start.sh server

Uses Uvicorn workers for FastAPI (HTTP + WebSocket support).
Environment variables are read from the process environment / .env (via app settings
when workers load the app). Gunicorn-specific vars below can be set in .env or
exported before start.
"""

from __future__ import annotations

import multiprocessing
import os

# Bind address — default HOST:PORT from .env or 0.0.0.0:8000
_host = os.getenv("HOST", "0.0.0.0")
_port = os.getenv("PORT", "8000")
bind = os.getenv("GUNICORN_BIND", f"{_host}:{_port}")

# Workers
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("WEB_CONCURRENCY", max(2, multiprocessing.cpu_count() * 2 + 1)))
threads = int(os.getenv("GUNICORN_THREADS", "1"))

# Timeouts (seconds) — increase if long-running report/export endpoints are added
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Logging
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = os.getenv(
    "GUNICORN_ACCESS_LOG_FORMAT",
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s',
)

# Process naming
proc_name = os.getenv("GUNICORN_PROC_NAME", "restrochain-api")

# Reload is for development only — keep false in production
reload = os.getenv("GUNICORN_RELOAD", "false").lower() == "true"

# Preload can reduce memory per worker but delays worker restarts; default off
preload_app = os.getenv("GUNICORN_PRELOAD", "false").lower() == "true"

# Trust X-Forwarded-* headers when behind Nginx / a load balancer
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")
proxy_allow_ips = forwarded_allow_ips

# Worker lifecycle hooks (optional diagnostics)
def on_starting(server) -> None:
    server.log.info("Gunicorn master starting bind=%s workers=%s", bind, workers)


def when_ready(server) -> None:
    server.log.info("Gunicorn ready bind=%s worker_class=%s", bind, worker_class)
