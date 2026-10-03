#!/usr/bin/env bash
set -euo pipefail

# RestroChain OS API — start script
#
# Local development (uvicorn + reload):
#   ./start.sh local
#
# Remote server (gunicorn + uvicorn workers):
#   ./start.sh server
#
# Or set START_MODE=server in .env and run ./start.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

MODE="${1:-${START_MODE:-local}}"

case "$MODE" in
  local|dev|development)
    echo "Starting RestroChain API with Uvicorn (development)..."
    exec uvicorn app.main:app \
      --host "${HOST:-0.0.0.0}" \
      --port "${PORT:-8000}" \
      --reload
    ;;
  server|prod|production)
    echo "Starting RestroChain API with Gunicorn + Uvicorn workers..."
    exec gunicorn app.main:app -c gunicorn_conf.py
    ;;
  *)
    echo "Usage: $0 [local|server]"
    echo ""
    echo "  local   Uvicorn with --reload (default, for development)"
    echo "  server  Gunicorn + UvicornWorker (for remote/production server)"
    exit 1
    ;;
esac
