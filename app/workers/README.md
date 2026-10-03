# Background workers (Celery + Redis)

Optional background job runtime for RestroChain OS. **The FastAPI API does not require Redis or Celery** — workers are a separate process you enable when ready.

All jobs are **mock-only**: they read/write local data where useful and never call external WhatsApp, SMS, email, or AI APIs.

---

## Prerequisites

- Redis 6+ running locally or reachable from the worker
- Same Python environment and `.env` as the API
- MySQL available (jobs that aggregate reports/inventory use the app database)

---

## Configuration

Add to `.env` (see `.env.example`):

```env
CELERY_ENABLED=false
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_APP_NAME=restrochain
CELERY_DEFAULT_QUEUE=default
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `CELERY_ENABLED` | `false` | When `false`, `enqueue_task()` in API code logs and skips dispatch |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis broker for Celery |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | Redis backend for task results |
| `CELERY_APP_NAME` | `restrochain` | Celery application name |
| `CELERY_DEFAULT_QUEUE` | `default` | Default queue name |

**FastAPI runs normally with `CELERY_ENABLED=false` and no Redis.**

---

## Start Redis (local)

```bash
# Docker
docker run -d --name restrochain-redis -p 6379:6379 redis:7-alpine

# Or use an existing Redis instance and point CELERY_BROKER_URL at it
```

---

## Run a Celery worker

From the `backend/` directory:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

celery -A app.workers.celery_app worker --loglevel=info
```

Worker loads tasks from:

- `app/workers/campaign_jobs.py`
- `app/workers/communication_jobs.py`
- `app/workers/ai_jobs.py`
- `app/workers/report_jobs.py`
- `app/workers/housekeeping_jobs.py`
- `app/workers/ota_jobs.py`

---

## Docker Compose

When you run `docker compose up` from the repo root, Redis, Celery worker, and Celery beat start automatically:

| Service | `START_MODE` | Purpose |
|---------|--------------|---------|
| `backend` | `server` | API |
| `celery-worker` | `worker` | Executes queued tasks |
| `celery-beat` | `beat` | Runs scheduled jobs (OTA ARI every 30 min, housekeeping sweeps every 15 min) |
| `redis` | — | Broker + result backend |

Set `CELERY_ENABLED=true` in `backend/.env.docker` (default in Docker). Local dev without Docker can keep `CELERY_ENABLED=false`.

---

## Run Celery Beat (scheduled jobs — optional)

Beat runs placeholder report jobs plus **housekeeping sweep schedules** every 15 minutes (`housekeeping.run_due_sweep_schedules`). Enable schedules per outlet under **Housekeeping → Settings**.

```bash
celery -A app.workers.celery_app beat --loglevel=info
```

Run **worker** and **beat** in separate terminals (or use a process manager).

---

## Enqueue tasks from application code (later)

```python
from app.workers.utils import enqueue_task
from app.workers.campaign_jobs import send_campaign_messages_mock

enqueue_task(send_campaign_messages_mock, campaign_id=1, tenant_id=1)
```

When `CELERY_ENABLED=false`, nothing is sent to Redis.

---

## Manual task invocation (testing)

With worker running:

```python
from app.workers.report_jobs import daily_sales_report_mock

result = daily_sales_report_mock.delay(tenant_id=1)
print(result.get(timeout=30))
```

Or via Celery CLI:

```bash
celery -A app.workers.celery_app call reports.daily_sales_report_mock --kwargs='{"tenant_id": 1}'
```

---

## Available tasks

| Task name | Module | Description |
|-----------|--------|-------------|
| `campaigns.send_campaign_messages_mock` | `campaign_jobs.py` | Simulates sending campaign messages |
| `communications.process_inbound_whatsapp_mock` | `communication_jobs.py` | Simulates inbound WhatsApp webhook handling |
| `ai.generate_ai_insight_mock` | `ai_jobs.py` | Returns placeholder AI insight JSON |
| `reports.daily_sales_report_mock` | `report_jobs.py` | Aggregates today's sales from DB |
| `reports.low_stock_alert_mock` | `report_jobs.py` | Lists low-stock raw materials |
| `housekeeping.run_due_sweep_schedules` | `housekeeping_jobs.py` | Runs due housekeeping sweep schedules |
| `ota.push_auto_ari_outlet` | `ota_jobs.py` | Pushes ARI to auto-enabled OTA channels for one outlet |
| `ota.push_auto_ari_all` | `ota_jobs.py` | Pushes ARI for all tenants (Beat schedule, every 30 min) |

---

## Production notes (later)

- [ ] Run worker(s) under systemd, supervisord, or Kubernetes
- [ ] Use dedicated Redis with persistence and auth
- [ ] Replace mock jobs with real provider adapters one at a time
- [ ] Tune Beat schedules per tenant/timezone
- [ ] Monitor tasks with Flower: `celery -A app.workers.celery_app flower`
- [ ] Keep `CELERY_ENABLED=false` in dev unless actively testing workers

---

## Layout

```
app/workers/
├── celery_app.py          # Celery app + beat schedule placeholders
├── utils.py               # DB session helper, optional enqueue_task()
├── campaign_jobs.py
├── communication_jobs.py
├── ai_jobs.py
├── report_jobs.py
├── housekeeping_jobs.py
├── ota_jobs.py
└── README.md
```
