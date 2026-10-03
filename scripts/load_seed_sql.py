"""Load demo data from database/restrochain.sql after Alembic migrations."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine, text

from app.core.config import settings


def _repo_seed_sql_path() -> Path:
    return Path(__file__).resolve().parents[2] / "database" / "restrochain.sql"


def _resolve_seed_sql_path() -> Path:
    configured = os.getenv("SEED_SQL_PATH", "").strip()
    if configured:
        return Path(configured)
    return _repo_seed_sql_path()


def _mysql_connection_args() -> dict[str, str]:
    url = settings.database_url.replace("mysql+pymysql://", "mysql://")
    parsed = urlparse(url)
    database = parsed.path.lstrip("/").split("?")[0]
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 3306),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
    }


def _is_enabled() -> bool:
    return os.getenv("LOAD_SEED_SQL", "true").lower() in ("true", "1", "yes")


def _already_seeded() -> bool:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM tenants")).scalar()
        return bool(count and count > 0)


def main() -> int:
    if not _is_enabled():
        print("SQL seed load disabled (LOAD_SEED_SQL=false).")
        return 0

    seed_path = _resolve_seed_sql_path()
    if not seed_path.is_file():
        print(f"Seed SQL not found: {seed_path}", file=sys.stderr)
        return 1

    if _already_seeded():
        print("Demo data already present — skipping SQL seed.")
        return 0

    mysql_args = _mysql_connection_args()
    print(f"Loading demo data from {seed_path} ...")

    env = os.environ.copy()
    if mysql_args["password"]:
        env["MYSQL_PWD"] = mysql_args["password"]

    result = subprocess.run(
        [
            "mysql",
            f"-h{mysql_args['host']}",
            f"-P{mysql_args['port']}",
            f"-u{mysql_args['user']}",
            mysql_args["database"],
        ],
        stdin=seed_path.open("rb"),
        env=env,
        check=False,
    )

    if result.returncode != 0:
        print("Failed to load seed SQL.", file=sys.stderr)
        return result.returncode

    print("Demo data loaded from SQL successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
