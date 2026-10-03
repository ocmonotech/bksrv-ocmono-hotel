"""Align MySQL enum labels with SQLAlchemy enum member names (uppercase)."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from app.core.config import settings

ALTERS = [
    "ALTER TABLE tenants MODIFY business_type ENUM('RESORT','MULTICHAIN','CAFE','RESTAURANT') NOT NULL DEFAULT 'RESORT'",
    "ALTER TABLE hotel_rooms MODIFY status ENUM('VACANT_CLEAN','VACANT_DIRTY','OCCUPIED','CHECKOUT_PENDING','INSPECTING','OUT_OF_ORDER','MAINTENANCE') NOT NULL",
    "ALTER TABLE checklist_templates MODIFY task_type ENUM('CHECKOUT','DAILY','DEEP_CLEAN','TURNDOWN','INSPECTION') NOT NULL",
    "ALTER TABLE housekeeping_tasks MODIFY task_type ENUM('CHECKOUT','DAILY','DEEP_CLEAN','TURNDOWN','INSPECTION') NOT NULL",
    "ALTER TABLE housekeeping_tasks MODIFY status ENUM('PENDING','IN_PROGRESS','COMPLETED','VERIFIED','SKIPPED') NOT NULL",
    "ALTER TABLE housekeeping_tasks MODIFY priority ENUM('LOW','MEDIUM','HIGH','URGENT') NOT NULL",
    "ALTER TABLE maintenance_tickets MODIFY category ENUM('PLUMBING','ELECTRICAL','HVAC','FURNITURE','APPLIANCE','CLEANING','OTHER') NOT NULL",
    "ALTER TABLE maintenance_tickets MODIFY priority ENUM('LOW','MEDIUM','HIGH','URGENT') NOT NULL",
    "ALTER TABLE maintenance_tickets MODIFY status ENUM('OPEN','ASSIGNED','IN_PROGRESS','ON_HOLD','RESOLVED','CLOSED') NOT NULL",
    "ALTER TABLE rate_plan_inclusions MODIFY inclusion_type ENUM('BREAKFAST','SPA','PARKING','OTHER') NOT NULL",
    "ALTER TABLE rate_plans MODIFY source ENUM('DIRECT','WALK_IN','PHONE','EMAIL','CORPORATE','OTA_BOOKING_COM','OTA_MMT','OTA_EXPEDIA') NULL",
    "ALTER TABLE guest_reservations MODIFY status ENUM('PENDING','CONFIRMED','CHECKED_IN','CHECKED_OUT','CANCELLED','NO_SHOW') NOT NULL",
    "ALTER TABLE guest_reservations MODIFY source ENUM('DIRECT','WALK_IN','PHONE','EMAIL','CORPORATE','OTA_BOOKING_COM','OTA_MMT','OTA_EXPEDIA') NOT NULL",
    "ALTER TABLE guest_folios MODIFY status ENUM('OPEN','CLOSED') NOT NULL",
    "ALTER TABLE folio_entries MODIFY entry_type ENUM('ROOM_CHARGE','TAX','DEPOSIT','PAYMENT','POS_CHARGE','SPA_CHARGE','BANQUET_CHARGE','ADJUSTMENT','REFUND') NOT NULL",
    "ALTER TABLE spa_services MODIFY category ENUM('SPA','ACTIVITY') NOT NULL",
    "ALTER TABLE spa_bookings MODIFY status ENUM('PENDING','CONFIRMED','CHECKED_IN','COMPLETED','CANCELLED','NO_SHOW') NOT NULL",
    "ALTER TABLE banquet_venues MODIFY venue_type ENUM('INDOOR','OUTDOOR','LAWN','CONFERENCE','POOL_DECK') NOT NULL",
    "ALTER TABLE banquet_bookings MODIFY event_type ENUM('WEDDING','CONFERENCE','RECEPTION','CORPORATE','SOCIAL','OTHER') NOT NULL",
    "ALTER TABLE banquet_bookings MODIFY status ENUM('INQUIRY','TENTATIVE','CONFIRMED','COMPLETED','CANCELLED') NOT NULL",
    "ALTER TABLE outlet_ota_integrations MODIFY platform ENUM('BOOKING_COM','MMT','EXPEDIA') NOT NULL",
    "ALTER TABLE outlet_ota_integrations MODIFY status ENUM('ACTIVE','INACTIVE','PENDING','ERROR') NOT NULL",
    "ALTER TABLE ota_reservation_links MODIFY platform ENUM('BOOKING_COM','MMT','EXPEDIA') NOT NULL",
    "ALTER TABLE ota_sync_logs MODIFY sync_type ENUM('ARI_PUSH') NOT NULL",
    "ALTER TABLE ota_sync_logs MODIFY status ENUM('SUCCESS','FAILED') NOT NULL",
]


def main() -> None:
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        for statement in ALTERS:
            try:
                conn.execute(text(statement))
                print(f"OK: {statement[:80]}...")
            except Exception as exc:  # noqa: BLE001
                print(f"SKIP: {exc}")
    print("Enum alignment complete")


if __name__ == "__main__":
    main()
