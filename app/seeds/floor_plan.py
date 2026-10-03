"""Floor plan and restaurant table seeds."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.tables.models import Floor, RestaurantTable, TableStatus
from app.seeds.base import SeedContext


def seed_floor_plan(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    tables: dict[tuple[str, str], RestaurantTable] = {}

    for outlet_name, outlet in ctx.outlets.items():
        table_count = 10 if outlet_name == "Andheri West" else 6
        floor = (
            db.query(Floor)
            .filter(Floor.tenant_id == tenant.id, Floor.outlet_id == outlet.id, Floor.name == "Ground Floor")
            .first()
        )
        if floor is None:
            floor = Floor(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=outlet.id,
                name="Ground Floor",
                sort_order=1,
            )
            db.add(floor)
            db.flush()

        for index in range(1, table_count + 1):
            table_number = f"T{index}"
            table = (
                db.query(RestaurantTable)
                .filter(
                    RestaurantTable.tenant_id == tenant.id,
                    RestaurantTable.outlet_id == outlet.id,
                    RestaurantTable.table_number == table_number,
                )
                .first()
            )
            if table is None:
                table = RestaurantTable(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    outlet_id=outlet.id,
                    floor_id=floor.id,
                    table_number=table_number,
                    capacity=4 if index % 3 else 6,
                    status=TableStatus.AVAILABLE,
                )
                db.add(table)
                db.flush()
            tables[(outlet_name, table_number)] = table

    ctx.tables = tables
