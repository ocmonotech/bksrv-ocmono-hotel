# RestroChain OS — Backend

FastAPI backend for multi-outlet restaurant chain SaaS (POS, KOT, menu, inventory, CRM, communications, AI, campaigns, reports).

**Backend only** — not connected to the React frontend in this phase.

External services (WhatsApp, SMS, Email, AI) use **mock/stub providers** only. Do not put real API keys in `.env`.

---

## Prerequisites

- Python 3.11+
- MySQL 8.x
- (Optional) Redis + Celery — background jobs only; see [app/workers/README.md](app/workers/README.md)

---

## Install

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Configure environment

Copy the example env file and edit values locally:

```bash
# Windows
copy .env.example .env

# macOS / Linux
# cp .env.example .env
```

Required settings in `.env`:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | MySQL connection string |
| `JWT_SECRET_KEY` | Secret for signing JWT tokens — change in production |
| `BACKEND_CORS_ORIGINS` | Allowed origins (comma-separated) |
| `AI_MASTER_ENCRYPTION_KEY` | Master key for encrypting stored provider secrets |

**Never commit `.env`.** Only `.env.example` belongs in git.

### Create MySQL database

```sql
CREATE DATABASE restrochain_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'user'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON restrochain_db.* TO 'user'@'localhost';
FLUSH PRIVILEGES;
```

Update `DATABASE_URL` in `.env` to match your credentials.

---

## Database migrations (Alembic)

Alembic is configured to read `DATABASE_URL` from `.env` via `app.core.config`.
All module models are registered through `import app.modules` in `alembic/env.py`.

Run commands from the `backend/` directory:

```bash
cd backend

# 1. Generate migration from SQLAlchemy models (first time or after model changes)
alembic revision --autogenerate -m "initial migration"

# 2. Apply migrations to MySQL
alembic upgrade head
```

Other useful commands:

```bash
# Show current revision
alembic current

# Roll back one revision
alembic downgrade -1

# View migration history
alembic history
```

**Note:** No checked-in migration revision is generated yet. Run autogenerate once models and MySQL are ready.

### Development-only bootstrap (optional)

For local quick setup without Alembic:

```bash
python -m scripts.create_tables
```

Prefer Alembic for any shared or production environment.

Verify imports and route wiring:

```bash
python scripts/verify_backend.py
```

---

## Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:

| URL | Purpose |
|-----|---------|
| http://localhost:8000/health | Health check |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/api/v1/... | Versioned REST API |

**Remote server deployment:** see [README_DEPLOYMENT.md](README_DEPLOYMENT.md) (Gunicorn, MySQL, systemd).

On first startup the app seeds demo data:

- Tenant: Bombay Bite Collective
- 5 outlets
- Admin user: `admin@restrochain.test` / `Admin@123`

---

## Test the backend

### 1. Health check

```bash
curl http://localhost:8000/health
```

Expected: JSON with `"status": "ok"`.

### 2. Login (get JWT)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"admin@restrochain.test\",\"password\":\"Admin@123\"}"
```

On macOS/Linux replace `^` with `\` for line continuation.

Response includes `access_token`, `token_type`, `user`, `role`, `tenant_id`, `brand_id`, and `allowed_outlets`.

Copy `access_token` from the response.

### 3. Authenticated request

```bash
curl http://localhost:8000/api/v1/auth/me ^
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Interactive testing

Open http://localhost:8000/docs, click **Authorize**, paste `Bearer YOUR_ACCESS_TOKEN`, and try endpoints from the Swagger UI.

### 5. Optional: HTTP client file

Use Postman, Insomnia, or `httpx` in a Python shell:

```python
import httpx

r = httpx.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "admin@restrochain.test", "password": "Admin@123"},
)
print(r.json())
```

---

## Project layout

```
backend/
├── app/
│   ├── main.py              # FastAPI entrypoint
│   ├── core/                # config, database, security, permissions, exceptions
│   ├── api/v1/router.py     # Aggregates module routers
│   ├── modules/             # Domain modules (models, schemas, routes, service)
│   │   ├── auth/
│   │   ├── tenants/
│   │   ├── brands/
│   │   ├── outlets/
│   │   ├── users/
│   │   ├── roles/
│   │   ├── menu/
│   │   ├── pos/
│   │   ├── kot/
│   │   ├── inventory/
│   │   ├── customers/
│   │   ├── leads/
│   │   ├── communications/
│   │   ├── campaigns/
│   │   ├── ai/
│   │   ├── reports/
│   │   └── settings/
│   ├── common/              # base_model, dependencies, pagination, response
│   ├── workers/             # Optional Celery jobs (Redis not required for API)
│   └── utils/               # datetime, currency, validators
├── alembic/                 # Migrations
├── scripts/                 # Dev scripts (create_tables, etc.)
├── requirements.txt
├── gunicorn_conf.py       # Production Gunicorn config
├── start.sh               # local (uvicorn) / server (gunicorn)
├── README.md
├── README_DEPLOYMENT.md   # Remote server deployment guide
└── .env.example
```

Each module follows the same pattern:

- `models.py` — SQLAlchemy models
- `schemas.py` — Pydantic request/response schemas
- `routes.py` — thin HTTP handlers
- `service.py` — business logic

---

## Provider modes

Integration providers are configured as **mock** in `.env.example`:

```
WHATSAPP_PROVIDER=mock
SMS_PROVIDER=mock
EMAIL_PROVIDER=mock
```

No real messages are sent. Replace with production adapters when ready.

---

## Background jobs (optional)

Celery + Redis workers are **optional**. The API starts without Redis.

See **[app/workers/README.md](app/workers/README.md)** for:

- Enabling `CELERY_ENABLED=true`
- Starting a worker: `celery -A app.workers.celery_app worker --loglevel=info`
- Mock tasks: campaign send, WhatsApp inbound, AI insights, daily sales, low-stock alerts

---

## Production checklist

- [ ] Rotate `JWT_SECRET_KEY` and `AI_MASTER_ENCRYPTION_KEY`
- [ ] Use strong MySQL credentials
- [ ] Set `DEBUG=false` and `APP_ENV=production`
- [ ] Enable HTTPS behind a reverse proxy
- [ ] Replace mock providers with real integrations
- [ ] Enable Celery workers for background jobs — see `app/workers/README.md`
