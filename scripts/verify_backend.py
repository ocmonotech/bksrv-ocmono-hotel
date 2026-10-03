"""Verify backend imports, SQLAlchemy mappers, and API route registration."""

from __future__ import annotations

import sys


def main() -> int:
    print("Checking imports...")
    import app.modules  # noqa: F401
    from app.main import app
    from sqlalchemy.orm import configure_mappers

    print("Configuring SQLAlchemy mappers...")
    configure_mappers()

    print("Checking API routes under /api/v1...")
    from app.core.config import settings

    prefix = settings.api_v1_prefix.rstrip("/")
    api_routes = [
        route
        for route in app.routes
        if hasattr(route, "path") and route.path.startswith(prefix)
    ]
    if not api_routes:
        print(f"ERROR: No routes found with prefix {prefix}", file=sys.stderr)
        return 1

    print(f"  Found {len(api_routes)} routes under {prefix}")

    expected_prefixes = [
        f"{prefix}/auth",
        f"{prefix}/tenants",
        f"{prefix}/brands",
        f"{prefix}/outlets",
        f"{prefix}/users",
        f"{prefix}/roles",
        f"{prefix}/menu",
        f"{prefix}/offers",
        f"{prefix}/pos",
        f"{prefix}/tables",
        f"{prefix}/kot",
        f"{prefix}/inventory",
        f"{prefix}/customers",
        f"{prefix}/leads",
        f"{prefix}/communications",
        f"{prefix}/campaigns",
        f"{prefix}/automation",
        f"{prefix}/ai",
        f"{prefix}/reports",
        f"{prefix}/settings",
        f"{prefix}/audit-logs",
    ]
    route_paths = {route.path for route in api_routes}
    missing = [
        expected
        for expected in expected_prefixes
        if not any(path.startswith(expected) for path in route_paths)
    ]
    if missing:
        print("ERROR: Missing expected route groups:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        return 1

    health_paths = {"/health", "/"}
    app_paths = {route.path for route in app.routes if hasattr(route, "path")}
    if not health_paths.issubset(app_paths):
        print("ERROR: /health or / root route missing", file=sys.stderr)
        return 1

    print("Backend verification passed.")
    print("  uvicorn app.main:app --reload")
    print("  python -m app.seed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
