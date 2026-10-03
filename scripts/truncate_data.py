"""Truncate all application tables so demo seed can reload cleanly."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from app.core.config import settings


def main() -> None:
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name != 'alembic_version'"
            )
        ).fetchall()
        tables = [row[0] for row in rows]
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in tables:
            conn.execute(text(f"TRUNCATE TABLE `{table}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        print(f"Truncated {len(tables)} tables")


if __name__ == "__main__":
    main()
