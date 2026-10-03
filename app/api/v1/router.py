from fastapi import APIRouter

from app.modules.ai.routes import router as ai_router
from app.modules.audit.routes import router as audit_router
from app.modules.auth.routes import router as auth_router
from app.modules.automation.routes import router as automation_router
from app.modules.brands.routes import router as brands_router
from app.modules.campaigns.routes import router as campaigns_router
from app.modules.communications.routes import router as communications_router
from app.modules.bookings.routes import router as bookings_router
from app.modules.events.routes import router as events_router
from app.modules.housekeeping.routes import router as housekeeping_router
from app.modules.delivery.routes import router as delivery_router
from app.modules.customers.routes import router as customers_router
from app.modules.inventory.routes import router as inventory_router
from app.modules.kot.routes import router as kot_router
from app.modules.leads.routes import router as leads_router
from app.modules.loyalty.routes import router as loyalty_router
from app.modules.minibar.routes import router as minibar_router
from app.modules.staff.routes import router as staff_router
from app.modules.menu.routes import router as menu_router
from app.modules.offers.routes import router as offers_router
from app.modules.pms.routes import router as pms_router
from app.modules.payments.routes import router as payments_router
from app.modules.ota.routes import router as ota_router
from app.modules.outlets.routes import router as outlets_router
from app.modules.pos.routes import router as pos_router
from app.modules.spa.routes import router as spa_router
from app.modules.banquet.routes import router as banquet_router
from app.modules.tables.routes import router as tables_router
from app.modules.reports.routes import router as reports_router
from app.modules.roles.routes import router as roles_router
from app.modules.settings.routes import router as settings_router
from app.modules.tenants.routes import router as tenants_router
from app.modules.users.routes import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(tenants_router, prefix="/tenants", tags=["Tenants"])
api_router.include_router(brands_router, prefix="/brands", tags=["Brands"])
api_router.include_router(outlets_router, prefix="/outlets", tags=["Outlets"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(roles_router, prefix="/roles", tags=["Roles"])
api_router.include_router(menu_router, prefix="/menu", tags=["Menu"])
api_router.include_router(offers_router, prefix="/offers", tags=["Offers"])
api_router.include_router(pos_router, prefix="/pos", tags=["POS"])
api_router.include_router(delivery_router, prefix="/delivery", tags=["Delivery"])
api_router.include_router(pms_router, prefix="/pms", tags=["PMS"])
api_router.include_router(minibar_router, prefix="/pms/minibar", tags=["Minibar"])
api_router.include_router(ota_router, prefix="/ota", tags=["OTA"])
api_router.include_router(payments_router, prefix="/payments", tags=["Payments"])
api_router.include_router(bookings_router, prefix="/bookings", tags=["Bookings"])
api_router.include_router(events_router, prefix="/events", tags=["Events"])
api_router.include_router(housekeeping_router, prefix="/housekeeping", tags=["Housekeeping"])
api_router.include_router(spa_router, prefix="/spa", tags=["Spa"])
api_router.include_router(banquet_router, prefix="/banquet", tags=["Banquet"])
api_router.include_router(tables_router, prefix="/tables", tags=["Tables"])
api_router.include_router(kot_router, prefix="/kot", tags=["KOT"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(customers_router, prefix="/customers", tags=["Customers"])
api_router.include_router(loyalty_router, prefix="/loyalty", tags=["Loyalty"])
api_router.include_router(staff_router, prefix="/staff", tags=["Staff"])
api_router.include_router(leads_router, prefix="/leads", tags=["Leads"])
api_router.include_router(
    communications_router,
    prefix="/communications",
    tags=["Communications"],
)
api_router.include_router(campaigns_router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(automation_router, prefix="/automation", tags=["Automation"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
api_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
api_router.include_router(audit_router, prefix="/audit-logs", tags=["Audit"])
