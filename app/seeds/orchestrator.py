"""Orchestrates all seed modules in dependency order."""

from __future__ import annotations

from sqlalchemy.orm import Session

import app.modules  # noqa: F401 — register models
from app.seeds.ai import seed_ai
from app.seeds.audit import seed_audit
from app.seeds.automation import seed_automation
from app.seeds.base import SeedContext
from app.seeds.bookings import seed_bookings
from app.seeds.campaigns import seed_campaigns
from app.seeds.comms import seed_comms
from app.seeds.core import seed_core
from app.seeds.crm import seed_crm, seed_customer_visits
from app.seeds.events import seed_events
from app.seeds.floor_plan import seed_floor_plan
from app.seeds.housekeeping import seed_housekeeping
from app.seeds.integrations import seed_integrations
from app.seeds.inventory import seed_inventory
from app.seeds.menu import seed_menu
from app.seeds.offers import seed_offers
from app.seeds.pms import seed_pms
from app.seeds.spa import seed_spa
from app.seeds.banquet import seed_banquet
from app.seeds.ota import seed_ota
from app.seeds.pos import seed_pos
from app.seeds.settings import seed_settings


def run_seed(db: Session) -> SeedContext:
    ctx = seed_core(db)
    seed_inventory(db, ctx)
    seed_menu(db, ctx)
    seed_floor_plan(db, ctx)
    seed_crm(db, ctx)
    seed_offers(db, ctx)
    seed_comms(db, ctx)
    seed_campaigns(db, ctx)
    seed_automation(db, ctx)
    seed_ai(db, ctx)
    seed_settings(db, ctx)
    seed_pos(db, ctx)
    seed_customer_visits(db, ctx)
    seed_integrations(db, ctx)
    seed_bookings(db, ctx)
    seed_events(db, ctx)
    seed_housekeeping(db, ctx)
    seed_pms(db, ctx)
    seed_spa(db, ctx)
    seed_banquet(db, ctx)
    seed_ota(db, ctx)
    seed_audit(db, ctx)
    db.commit()
    return ctx
