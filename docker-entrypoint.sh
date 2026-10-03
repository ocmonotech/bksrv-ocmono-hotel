#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

MODE="${START_MODE:-server}"

if [[ "$MODE" == "worker" || "$MODE" == "beat" ]]; then
  echo "Waiting for MySQL..."
  python -m scripts.wait_for_db
  echo "Waiting for Redis..."
  python -m scripts.wait_for_redis
else
  echo "Waiting for MySQL..."
  python -m scripts.wait_for_db

  echo "Running database migrations..."
  alembic upgrade head

  if [[ "${LOAD_SEED_SQL:-true}" == "true" ]]; then
    echo "Loading demo data from SQL (database/restrochain.sql)..."
    python -m scripts.load_seed_sql
  fi

  echo "Ensuring permissions, roles, and resort demo extensions..."
  python -m scripts.ensure_seed_extensions
fi

case "$MODE" in
  worker)
    echo "Starting Celery worker..."
    exec celery -A app.workers.celery_app worker --loglevel="${CELERY_LOG_LEVEL:-info}"
    ;;
  beat)
    echo "Starting Celery beat..."
    exec celery -A app.workers.celery_app beat --loglevel="${CELERY_LOG_LEVEL:-info}"
    ;;
  local|dev|development)
    echo "Starting API with Uvicorn (development)..."
    exec uvicorn app.main:app \
      --host "${HOST:-0.0.0.0}" \
      --port "${PORT:-8000}" \
      --reload
    ;;
  server|prod|production)
    echo "Starting API with Gunicorn (production)..."
    exec gunicorn app.main:app -c gunicorn_conf.py
    ;;
  *)
    echo "Unknown START_MODE: $MODE (use local, server, worker, or beat)"
    exit 1
    ;;
esac
