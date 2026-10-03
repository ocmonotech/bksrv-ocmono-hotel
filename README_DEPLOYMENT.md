# RestroChain OS — Remote Server Deployment

Deploy the FastAPI backend on a Linux VPS or cloud VM **without Docker**. Use **Uvicorn** locally and **Gunicorn + Uvicorn workers** on the server.

---

## Overview

| Environment | Start command | Process |
|-------------|---------------|---------|
| Local dev | `./start.sh local` | Uvicorn with `--reload` |
| Remote server | `./start.sh server` | Gunicorn + `uvicorn.workers.UvicornWorker` |

Configuration is loaded from a **`.env`** file in the `backend/` directory (never commit it). MySQL can run on the same server or a **remote managed database**.

Optional later: **systemd** service, **Nginx** reverse proxy, **CORS** for your frontend domain.

---

## 1. Create virtual environment

On the server (Ubuntu/Debian example):

```bash
cd /opt/restrochain/backend   # or your deploy path

sudo apt update
sudo apt install -y python3 python3-venv python3-pip

python3 -m venv .venv
source .venv/bin/activate
```

On **Windows** (local dev only):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
```

---

## 2. Install requirements

With the virtualenv activated:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, Gunicorn, SQLAlchemy, Alembic, PyMySQL, and other dependencies.

---

## 3. Set `.env`

Copy the example file and edit for your server:

```bash
cp .env.example .env
nano .env
```

### Minimum production settings

```env
APP_NAME=RestroChain OS API
APP_ENV=production
DEBUG=false
API_V1_PREFIX=/api/v1

HOST=0.0.0.0
PORT=8000

# Remote MySQL — replace host, user, password, database
DATABASE_URL=mysql+pymysql://restrochain:STRONG_PASSWORD@db.example.com:3306/restrochain_db?charset=utf8mb4

JWT_SECRET_KEY=generate_a_long_random_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

AI_MASTER_ENCRYPTION_KEY=generate_another_long_random_secret

# CORS — add your frontend domain when ready (comma-separated)
BACKEND_CORS_ORIGINS=https://app.yourdomain.com

WHATSAPP_PROVIDER=mock
SMS_PROVIDER=mock
EMAIL_PROVIDER=mock

CELERY_ENABLED=false
```

### Remote MySQL notes

- Create the database and user on the MySQL server.
- Allow the app server IP in the MySQL firewall / security group.
- Always include `?charset=utf8mb4` in `DATABASE_URL`.
- Test connectivity before migrating:

```bash
python -c "from app.core.config import settings; print(settings.database_url.split('@')[-1])"
```

### CORS (frontend domain later)

When your React app is deployed, set:

```env
BACKEND_CORS_ORIGINS=https://app.yourdomain.com,https://www.yourdomain.com
```

Multiple origins are comma-separated. Restart the app after changing CORS.

### Optional Gunicorn tuning (`.env`)

```env
WEB_CONCURRENCY=4
GUNICORN_TIMEOUT=120
GUNICORN_BIND=0.0.0.0:8000
FORWARDED_ALLOW_IPS=127.0.0.1
START_MODE=server
```

---

## 4. Run Alembic migration

From `backend/` with virtualenv active and `.env` configured:

```bash
# Generate a migration after model changes (development machine)
alembic revision --autogenerate -m "describe change"

# Apply all migrations on the server
alembic upgrade head
```

Verify:

```bash
alembic current
```

**Important:** Run migrations **before** starting the app on a fresh database.

---

## 5. Run seed script

Seed demo tenant data (idempotent — safe to run more than once):

```bash
python -m app.seed
```

Expected output includes tenant name, brand, outlet count, and super admin credentials.

The app also runs an idempotent seed on startup via `app.main` lifespan. Running `python -m app.seed` explicitly is recommended on first deploy so you can confirm success before serving traffic.

---

## 6. Start app with Gunicorn

Make the start script executable (once):

```bash
chmod +x start.sh
```

### Local development (Uvicorn)

```bash
./start.sh local
```

Or directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Remote server (Gunicorn + Uvicorn worker)

```bash
./start.sh server
```

Or directly:

```bash
gunicorn app.main:app -c gunicorn_conf.py
```

### Verify

```bash
curl http://127.0.0.1:8000/health
```

In production (`APP_ENV=production`), Swagger `/docs` is disabled. Use `/health` and `/api/v1/...` endpoints.

### Behind Nginx (recommended later)

- Proxy `http://127.0.0.1:8000`
- Terminate TLS at Nginx
- Set `FORWARDED_ALLOW_IPS` to your proxy IP (or `*` only if you trust the network path)

---

## 7. Use systemd service (later)

Run Gunicorn as a systemd unit so it restarts on failure and starts on boot.

Create `/etc/systemd/system/restrochain-api.service`:

```ini
[Unit]
Description=RestroChain OS API
After=network.target

[Service]
Type=simple
User=restrochain
Group=restrochain
WorkingDirectory=/opt/restrochain/backend
EnvironmentFile=/opt/restrochain/backend/.env
Environment=START_MODE=server
ExecStart=/opt/restrochain/backend/.venv/bin/gunicorn app.main:app -c gunicorn_conf.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable restrochain-api
sudo systemctl start restrochain-api
sudo systemctl status restrochain-api
```

Logs:

```bash
journalctl -u restrochain-api -f
```

Adjust `User`, paths, and `WorkingDirectory` to match your deployment.

---

## Optional: Celery workers

Background jobs are optional and **not required** for the API. See [app/workers/README.md](app/workers/README.md).

---

## Deployment checklist

- [ ] Python 3.11+ virtualenv created
- [ ] `pip install -r requirements.txt`
- [ ] `.env` created from `.env.example` (not committed)
- [ ] Strong `JWT_SECRET_KEY` and `AI_MASTER_ENCRYPTION_KEY`
- [ ] Remote `DATABASE_URL` tested
- [ ] `alembic upgrade head`
- [ ] `python -m app.seed` (first deploy)
- [ ] `./start.sh server` or systemd service running
- [ ] `curl /health` returns `"status": "ok"`
- [ ] `BACKEND_CORS_ORIGINS` updated when frontend is deployed
- [ ] Nginx + HTTPS in front of Gunicorn (production)
- [ ] Firewall allows only 80/443 publicly; app port 8000 internal

---

## File reference

| File | Purpose |
|------|---------|
| `gunicorn_conf.py` | Gunicorn + Uvicorn worker settings |
| `start.sh` | Local (Uvicorn) vs server (Gunicorn) entrypoint |
| `.env.example` | Template for environment variables |
| `alembic/` | Database migrations |
| `app/seed.py` | Demo data seed (`python -m app.seed`) |

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| `Can't connect to MySQL` | `DATABASE_URL`, firewall, MySQL user host `%` or app IP |
| `ModuleNotFoundError: app` | Run commands from `backend/` directory |
| CORS errors in browser | `BACKEND_CORS_ORIGINS` includes exact frontend origin (scheme + host) |
| 502 from Nginx | Gunicorn running on `HOST:PORT`, proxy_pass URL correct |
| Migrations fail | DB exists, user has DDL privileges, `alembic upgrade head` from `backend/` |

For local development details, see [README.md](README.md).

For remote server deployment (Gunicorn, MySQL, systemd), see [README_DEPLOYMENT.md](README_DEPLOYMENT.md).
