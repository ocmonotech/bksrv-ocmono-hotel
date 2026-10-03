"""Import all module models so Alembic and create_all register metadata."""

from app.modules.audit.models import AuditLog
from app.modules.auth.models import RevokedToken
from app.modules.ai.models import AiAutomationRule, AiInsight, AiPrompt, AiProvider, AiUsageLog
from app.modules.automation.models import AutomationRule, AutomationRun
from app.modules.brands.models import Brand
from app.modules.campaigns.models import AutomationFlow, Campaign, CampaignEvent, CampaignRecipient
from app.modules.communications.models import (
    CommunicationProvider,
    Conversation,
    Message,
    MessageTemplate,
)
from app.modules.bookings.models import OutletBookingIntegration, TableBooking
from app.modules.ota.models import (
    OtaRatePlanMapping,
    OtaReservationLink,
    OtaRoomTypeMapping,
    OtaSyncLog,
    OutletOtaIntegration,
)
from app.modules.events.models import EventActivity, EventPreOrderItem, EventTableAssignment, RestaurantEvent
from app.modules.pms.models import (
    FolioEntry,
    GuestFolio,
    GuestReservation,
    GuestServiceRequest,
    CashierShift,
    CityLedgerEntry,
    NightAuditLog,
    RatePlan,
    RatePlanInclusion,
    ReservationGroup,
    ReservationPackageEntitlement,
    RoomBlock,
)
from app.modules.spa.models import SpaBooking, SpaService, SpaTherapist
from app.modules.housekeeping.models import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    HotelRoom,
    HousekeepingFloorAssignment,
    HousekeepingSweepSchedule,
    HousekeepingTask,
    MaintenanceTicket,
    RoomType,
    TaskChecklistItem,
    TicketComment,
)
from app.modules.delivery.models import (
    DeliveryMenuMapping,
    DeliveryOrderLink,
    OutletDeliveryIntegration,
)
from app.modules.minibar.models import MinibarCatalogItem, MinibarPosting, MinibarPostingLine
from app.modules.loyalty.models import LoyaltyLedger, LoyaltyTier
from app.modules.staff.models import StaffShift, TipPool, TipPoolLine
from app.modules.customers.models import (
    Customer,
    CustomerTag,
    CustomerTagMap,
    CustomerVisit,
    Feedback,
)
from app.modules.inventory.models import (
    Purchase,
    PurchaseItem,
    RawMaterial,
    StockLedger,
    StockTransfer,
    StockTransferItem,
    Vendor,
    Wastage,
)
from app.modules.kot.models import KOT, KOTItem, KotTicket
from app.modules.leads.models import Lead, LeadActivity, Segment
from app.modules.auth.models import RevokedToken
from app.modules.menu.models import (
    Combo,
    ComboItem,
    ItemAddon,
    MenuCategory,
    MenuItem,
    MenuItemIngredient,
    MenuItemOutlet,
)
from app.modules.offers.models import Offer
from app.modules.payments.models import OutletPaymentIntegration, TerminalPayment
from app.modules.outlets.models import Outlet
from app.modules.pos.models import Bill, CancelReason, Order, OrderItem, Payment, PosOrder, PosOrderItem
from app.modules.tables.models import Floor, RestaurantTable
from app.modules.roles.models import Permission as PermissionModel, Role, RolePermission
from app.modules.settings.models import BrandSetting, OutletSetting
from app.modules.tenants.models import Tenant
from app.modules.users.models import User, UserOutlet

__all__ = [
    "Tenant",
    "Brand",
    "Outlet",
    "User",
    "UserOutlet",
    "Role",
    "PermissionModel",
    "RolePermission",
    "MenuCategory",
    "MenuItem",
    "MenuItemOutlet",
    "MenuItemIngredient",
    "Offer",
    "ItemAddon",
    "Combo",
    "ComboItem",
    "Floor",
    "RestaurantTable",
    "Order",
    "OrderItem",
    "Bill",
    "Payment",
    "CancelReason",
    "PosOrder",
    "PosOrderItem",
    "KOT",
    "KOTItem",
    "KotTicket",
    "RawMaterial",
    "Vendor",
    "Purchase",
    "PurchaseItem",
    "StockLedger",
    "StockTransfer",
    "StockTransferItem",
    "Wastage",
    "Customer",
    "CustomerVisit",
    "LoyaltyLedger",
    "LoyaltyTier",
    "MinibarCatalogItem",
    "MinibarPosting",
    "MinibarPostingLine",
    "CustomerTag",
    "CustomerTagMap",
    "Feedback",
    "Lead",
    "LeadActivity",
    "Segment",
    "CommunicationProvider",
    "Conversation",
    "Message",
    "MessageTemplate",
    "Campaign",
    "CampaignRecipient",
    "CampaignEvent",
    "AutomationFlow",
    "AutomationRule",
    "AutomationRun",
    "AiProvider",
    "AiPrompt",
    "AiUsageLog",
    "AiInsight",
    "AiAutomationRule",
    "BrandSetting",
    "OutletSetting",
    "OutletDeliveryIntegration",
    "DeliveryMenuMapping",
    "DeliveryOrderLink",
    "OutletBookingIntegration",
    "TableBooking",
    "OutletOtaIntegration",
    "OtaRoomTypeMapping",
    "OtaRatePlanMapping",
    "OtaReservationLink",
    "OtaSyncLog",
    "RatePlan",
    "RatePlanInclusion",
    "ReservationPackageEntitlement",
    "RestaurantEvent",
    "EventTableAssignment",
    "EventActivity",
    "GuestReservation",
    "GuestServiceRequest",
    "GuestFolio",
    "FolioEntry",
    "RoomBlock",
    "ReservationGroup",
    "NightAuditLog",
    "CashierShift",
    "CityLedgerEntry",
    "SpaService",
    "SpaBooking",
    "SpaTherapist",
    "HotelRoom",
    "RoomType",
    "ChecklistTemplate",
    "ChecklistTemplateItem",
    "HousekeepingTask",
    "TaskChecklistItem",
    "MaintenanceTicket",
    "TicketComment",
    "OutletPaymentIntegration",
    "TerminalPayment",
    "AuditLog",
    "RevokedToken",
]
