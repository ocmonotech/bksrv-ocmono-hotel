"""Create all database tables from SQLAlchemy models (development bootstrap)."""

import sys

from app.core.database import Base, engine
import app.modules  # noqa: F401


def main() -> int:
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        print(f"Failed to create tables: {exc}", file=sys.stderr)
        print("Check DATABASE_URL in .env and ensure MySQL is running.", file=sys.stderr)
        return 1

    print("Database tables created successfully.")
    print("Next: python -m app.seed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
