"""Demo seed constants — credentials, specs, and sample records."""

from app.modules.communications.models import MessageChannel
from app.modules.leads.models import LeadSource, LeadStage
from app.modules.menu.models import FoodType, PreparationArea
from app.modules.outlets.demo_locations import OUTLET_SPECS

SUPER_ADMIN_EMAIL = "admin@restrochain.test"
SUPER_ADMIN_PASSWORD = "Admin@123"
DEMO_TENANT_COMPANY = "Bombay Bite Collective"
DEMO_BRAND_NAME = "Bombay Bite Collective"
DEMO_TENANT_EMAIL = "owner@restrochain.test"
DEMO_USER_PASSWORD = "Demo@12345"

MENU_CATEGORIES = [
    ("Starters", 1),
    ("Main Course", 2),
    ("Breads", 3),
    ("Rice & Biryani", 4),
    ("Desserts", 5),
    ("Beverages", 6),
]

MENU_ITEMS: list[tuple[str, str, FoodType, float, PreparationArea]] = [
    ("Starters", "Paneer Tikka", FoodType.VEG, 280, PreparationArea.TANDOOR),
    ("Starters", "Chicken Tikka", FoodType.NON_VEG, 320, PreparationArea.TANDOOR),
    ("Starters", "Veg Seekh Kebab", FoodType.VEG, 260, PreparationArea.TANDOOR),
    ("Starters", "Fish Amritsari", FoodType.NON_VEG, 340, PreparationArea.KITCHEN),
    ("Starters", "Corn Cheese Balls", FoodType.VEG, 220, PreparationArea.KITCHEN),
    ("Main Course", "Butter Chicken", FoodType.NON_VEG, 420, PreparationArea.KITCHEN),
    ("Main Course", "Paneer Lababdar", FoodType.VEG, 360, PreparationArea.KITCHEN),
    ("Main Course", "Dal Makhani", FoodType.VEG, 280, PreparationArea.KITCHEN),
    ("Main Course", "Chicken Curry", FoodType.NON_VEG, 380, PreparationArea.KITCHEN),
    ("Main Course", "Mix Veg", FoodType.VEG, 300, PreparationArea.KITCHEN),
    ("Main Course", "Prawn Masala", FoodType.NON_VEG, 460, PreparationArea.KITCHEN),
    ("Main Course", "Palak Paneer", FoodType.VEG, 320, PreparationArea.KITCHEN),
    ("Breads", "Butter Naan", FoodType.VEG, 60, PreparationArea.TANDOOR),
    ("Breads", "Garlic Naan", FoodType.VEG, 80, PreparationArea.TANDOOR),
    ("Breads", "Tandoori Roti", FoodType.VEG, 40, PreparationArea.TANDOOR),
    ("Breads", "Cheese Naan", FoodType.VEG, 110, PreparationArea.TANDOOR),
    ("Breads", "Laccha Paratha", FoodType.VEG, 70, PreparationArea.TANDOOR),
    ("Rice & Biryani", "Veg Biryani", FoodType.VEG, 320, PreparationArea.KITCHEN),
    ("Rice & Biryani", "Chicken Biryani", FoodType.NON_VEG, 380, PreparationArea.KITCHEN),
    ("Rice & Biryani", "Jeera Rice", FoodType.VEG, 180, PreparationArea.KITCHEN),
    ("Rice & Biryani", "Mutton Biryani", FoodType.NON_VEG, 450, PreparationArea.KITCHEN),
    ("Rice & Biryani", "Steamed Rice", FoodType.VEG, 150, PreparationArea.KITCHEN),
    ("Desserts", "Gulab Jamun", FoodType.VEG, 120, PreparationArea.DESSERT),
    ("Desserts", "Rasmalai", FoodType.VEG, 140, PreparationArea.DESSERT),
    ("Desserts", "Brownie Sundae", FoodType.VEG, 180, PreparationArea.DESSERT),
    ("Desserts", "Kulfi Falooda", FoodType.VEG, 160, PreparationArea.DESSERT),
    ("Desserts", "Chocolate Mousse", FoodType.VEG, 190, PreparationArea.DESSERT),
    ("Beverages", "Masala Chai", FoodType.VEG, 60, PreparationArea.BAR),
    ("Beverages", "Fresh Lime Soda", FoodType.VEG, 90, PreparationArea.BAR),
    ("Beverages", "Mango Lassi", FoodType.VEG, 110, PreparationArea.BAR),
    ("Beverages", "Sweet Lassi", FoodType.VEG, 100, PreparationArea.BAR),
    ("Beverages", "Filter Coffee", FoodType.VEG, 80, PreparationArea.BAR),
    ("Beverages", "Virgin Mojito", FoodType.VEG, 160, PreparationArea.BAR),
    ("Starters", "Hara Bhara Kebab", FoodType.VEG, 240, PreparationArea.KITCHEN),
    ("Starters", "Chicken Wings", FoodType.NON_VEG, 300, PreparationArea.KITCHEN),
    ("Main Course", "Kadhai Paneer", FoodType.VEG, 340, PreparationArea.KITCHEN),
    ("Main Course", "Egg Curry", FoodType.EGG, 280, PreparationArea.KITCHEN),
    ("Desserts", "Gajar Halwa", FoodType.VEG, 150, PreparationArea.DESSERT),
]

ITEM_ADDONS: list[tuple[str, str, float]] = [
    ("Butter Chicken", "Extra Gravy", 50),
    ("Butter Chicken", "Boneless Upgrade", 80),
    ("Paneer Tikka", "Extra Mint Chutney", 30),
    ("Chicken Biryani", "Raita", 40),
    ("Garlic Naan", "Cheese Topping", 35),
]

COMBOS: list[tuple[str, float, list[tuple[str, int]]]] = [
    ("Lunch Thali Combo", 499, [("Dal Makhani", 1), ("Butter Naan", 2), ("Jeera Rice", 1), ("Gulab Jamun", 1)]),
    ("Family Feast", 1299, [("Paneer Tikka", 1), ("Butter Chicken", 1), ("Chicken Biryani", 1), ("Garlic Naan", 4)]),
]

DEMO_USERS = [
    ("owner@restrochain.test", "Chain Owner", "Owner", False, True),
    ("ops@restrochain.test", "Operations Manager", "Operations Manager", False, True),
    ("marketing@restrochain.test", "Marketing Manager", "Marketing Manager", False, True),
    ("cashier.andheri@restrochain.test", "Andheri Cashier", "Cashier", False, False),
    ("waiter.bandra@restrochain.test", "Bandra Waiter", "Waiter", False, False),
    ("housekeeper@restrochain.test", "Priya Sharma", "Housekeeper", False, False),
]

SAMPLE_CUSTOMERS = [
    ("Aarav Mehta", "+919800000001", "aarav@example.com", True, True, False),
    ("Priya Shah", "+919800000002", "priya@example.com", True, False, True),
    ("Rahul Desai", "+919800000003", "rahul@example.com", False, True, True),
    ("Neha Kapoor", "+919800000004", "neha@example.com", True, True, True),
    ("Vikram Singh", "+919800000005", None, True, False, False),
    ("Sunita Joshi", "+919800000006", "sunita@example.com", True, True, True),
    ("Arjun Malhotra", "+919800000007", "arjun@example.com", False, True, False),
    ("Kavya Reddy", "+919800000008", "kavya@example.com", True, True, True),
    ("Ishaan Khanna", "+919800000009", "ishaan@example.com", True, True, False),
    ("Myra Banerjee", "+919800000010", "myra@example.com", True, False, True),
    ("Devansh Gupta", "+919800000011", "devansh@example.com", False, True, True),
    ("Anvi Chopra", "+919800000012", "anvi@example.com", True, True, True),
    ("Kabir Nanda", "+919800000013", None, True, True, False),
    ("Riya Menon", "+919800000014", "riya@example.com", True, False, True),
    ("Samar Joshi", "+919800000015", "samar@example.com", False, True, False),
    ("Tara Sen", "+919800000016", "tara@example.com", True, True, True),
]

CUSTOMER_TAGS = ["VIP", "Regular", "Birthday Club", "Corporate", "High Spender", "Loyalty Gold", "Weekend Guest"]

SAMPLE_LEADS = [
    ("Ananya Rao", "+919810000001", "ananya@example.com", LeadSource.WHATSAPP, LeadStage.NEW, 72),
    ("Karan Patel", "+919810000002", "karan@example.com", LeadSource.INSTAGRAM, LeadStage.INTERESTED, 65),
    ("Sneha Iyer", "+919810000003", None, LeadSource.WEBSITE, LeadStage.FOLLOW_UP, 58),
    ("Mohit Agarwal", "+919810000004", "mohit@example.com", LeadSource.GOOGLE, LeadStage.TABLE_BOOKED, 81),
    ("Divya Nair", "+919810000005", "divya@example.com", LeadSource.REFERRAL, LeadStage.NEW, 49),
    ("Rohan Verma", "+919810000006", "rohan@example.com", LeadSource.WHATSAPP, LeadStage.INTERESTED, 61),
    ("Meera Pillai", "+919810000007", "meera@example.com", LeadSource.INSTAGRAM, LeadStage.FOLLOW_UP, 74),
    ("Nikhil Shetty", "+919810000008", None, LeadSource.GOOGLE, LeadStage.NEW, 53),
    ("Pooja Bhat", "+919810000009", "pooja@example.com", LeadSource.WHATSAPP, LeadStage.INTERESTED, 68),
    ("Aditya Rao", "+919810000010", "aditya@example.com", LeadSource.WEBSITE, LeadStage.NEW, 55),
    ("Shreya Das", "+919810000011", "shreya@example.com", LeadSource.INSTAGRAM, LeadStage.FOLLOW_UP, 70),
    ("Varun Krishnan", "+919810000012", None, LeadSource.REFERRAL, LeadStage.TABLE_BOOKED, 79),
    ("Nisha Fernandes", "+919810000013", "nisha@example.com", LeadSource.GOOGLE, LeadStage.NEW, 52),
    ("Harsh Mehta", "+919810000014", "harsh@example.com", LeadSource.WHATSAPP, LeadStage.INTERESTED, 63),
    ("Aisha Khan", "+919810000015", "aisha@example.com", LeadSource.WEBSITE, LeadStage.FOLLOW_UP, 71),
    ("Yash Thakur", "+919810000016", "yash@example.com", LeadSource.INSTAGRAM, LeadStage.NEW, 47),
]

LEAD_SEGMENTS = [
    ("High Intent Leads", "Leads with score above 70", '{"min_score": 70}', 2),
    ("WhatsApp Inbound", "Leads from WhatsApp channel", '{"source": "whatsapp"}', 1),
    ("Follow-up Due", "Leads needing follow-up", '{"stage": "follow_up"}', 1),
]

MESSAGE_TEMPLATES = [
    (
        MessageChannel.WHATSAPP,
        "welcome_message",
        "Welcome",
        "Hi {{name}}, welcome to Bombay Bite Collective! Reply MENU to explore.",
        ["name"],
    ),
    (
        MessageChannel.WHATSAPP,
        "order_ready",
        "Transactional",
        "Hi {{name}}, your order is ready for pickup at {{outlet}}.",
        ["name", "outlet"],
    ),
    (
        MessageChannel.SMS,
        "otp_verification",
        "OTP",
        "Your RestroChain OTP is {{otp}}. Valid for 10 minutes.",
        ["otp"],
    ),
    (
        MessageChannel.EMAIL,
        "newsletter_promo",
        "Promotions",
        "Hello {{name}}, enjoy {{discount}} off this week at Bombay Bite Collective.",
        ["name", "discount"],
    ),
    (
        MessageChannel.WHATSAPP,
        "booking_confirmation",
        "Transactional",
        "Hi {{name}}, your table for {{guests}} is confirmed on {{date}} at {{time}}. See you soon!",
        ["name", "guests", "date", "time"],
    ),
    (
        MessageChannel.SMS,
        "feedback_request",
        "Promotions",
        "Hi {{name}}, how was your experience at Bombay Bite Collective? Reply 1-5 to rate us.",
        ["name"],
    ),
    (
        MessageChannel.EMAIL,
        "birthday_greeting",
        "Welcome",
        "Dear {{name}}, wishing you a wonderful birthday! Enjoy {{discount}}% off your next visit.",
        ["name", "discount"],
    ),
]

RAW_MATERIALS = [
    ("Chicken Breast", "Protein", "kg", 10),
    ("Paneer", "Dairy", "kg", 8),
    ("Basmati Rice", "Grains", "kg", 25),
    ("Tomato", "Vegetables", "kg", 15),
    ("Onion", "Vegetables", "kg", 20),
    ("Butter", "Dairy", "kg", 5),
    ("Cooking Oil", "Pantry", "litre", 10),
    ("Garam Masala", "Spices", "kg", 2),
    ("Fresh Cream", "Dairy", "litre", 5),
    ("Naan Flour", "Grains", "kg", 15),
    ("Eggs", "Protein", "dozen", 12),
    ("Potato", "Vegetables", "kg", 18),
    ("Garlic", "Vegetables", "kg", 3),
    ("Ginger", "Vegetables", "kg", 3),
    ("Yogurt", "Dairy", "kg", 6),
    ("Cashew", "Pantry", "kg", 2),
]

VENDORS = [
    ("Fresh Farms Mumbai", "+919900000001", "freshfarms@example.com", "27AABFF1234A1Z5"),
    ("Spice Traders Co", "+919900000002", "spice@example.com", "27AABST5678B1Z5"),
    ("Dairy Direct", "+919900000003", "dairy@example.com", None),
    ("Mumbai Meat Suppliers", "+919900000004", "meatco@example.com", "27AABMM9012C1Z5"),
    ("Ocean Fresh Seafood", "+919900000005", "seafood@example.com", "27AABOF3456D1Z5"),
    ("Green Basket Produce", "+919900000006", "greenbasket@example.com", "27AABGB7890E1Z5"),
    ("City Bakery Supplies", "+919900000007", "bakery@example.com", "27AABCB2345F1Z5"),
]

CANCEL_REASONS = [
    ("order_cancel", "Customer changed mind"),
    ("order_cancel", "Wrong item ordered"),
    ("bill_cancel", "Billing error"),
    ("item_cancel", "Item unavailable"),
]
