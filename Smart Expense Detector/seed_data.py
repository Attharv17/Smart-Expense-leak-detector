"""
seed_data.py
------------
Sample dummy data loader for the Smart Expense Leak Detector.

Run this script directly to populate the database with realistic test expenses:
    python seed_data.py

The data includes:
  - A variety of categories, vendors, and amounts
  - Some intentional anomalies to trigger alerts (duplicates, high-spend)
  - Dates spread across the past 3 months
"""

from database import SessionLocal, engine
from models import Base, Expense
from services.alert_engine import run_alert_engine

# Ensure all tables exist before seeding
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# Sample expense data — realistic SaaS company spend
# ---------------------------------------------------------------------------

SAMPLE_EXPENSES = [
    # ---- Food & Beverages ---------------------------------------------------
    {"date": "2024-01-05", "amount": 42.50,  "category": "Food",          "vendor": "Swiggy",             "description": "Team lunch order"},
    {"date": "2024-01-12", "amount": 18.75,  "category": "Food",          "vendor": "Zomato",             "description": "Coffee and snacks"},
    {"date": "2024-01-20", "amount": 95.00,  "category": "Food",          "vendor": "Ambrosia Restaurant","description": "Client dinner"},
    {"date": "2024-02-03", "amount": 38.20,  "category": "Food",          "vendor": "Swiggy",             "description": "Friday team lunch"},
    {"date": "2024-02-18", "amount": 22.10,  "category": "Food",          "vendor": "Café Coffee Day",    "description": "Working session snacks"},
    {"date": "2024-03-07", "amount": 42.50,  "category": "Food",          "vendor": "Swiggy",             "description": "Team lunch order"},  # DUPLICATE of Jan 5

    # ---- SaaS Subscriptions -------------------------------------------------
    {"date": "2024-01-01", "amount": 299.00, "category": "SaaS",          "vendor": "Slack",              "description": "Pro plan - Jan 2024"},
    {"date": "2024-01-01", "amount": 49.00,  "category": "SaaS",          "vendor": "Notion",             "description": "Team plan - Jan 2024"},
    {"date": "2024-01-15", "amount": 120.00, "category": "SaaS",          "vendor": "GitHub",             "description": "Team plan monthly"},
    {"date": "2024-02-01", "amount": 299.00, "category": "SaaS",          "vendor": "Slack",              "description": "Pro plan - Feb 2024"},
    {"date": "2024-02-01", "amount": 49.00,  "category": "SaaS",          "vendor": "Notion",             "description": "Team plan - Feb 2024"},
    {"date": "2024-02-15", "amount": 120.00, "category": "SaaS",          "vendor": "GitHub",             "description": "Team plan monthly"},
    {"date": "2024-03-01", "amount": 299.00, "category": "SaaS",          "vendor": "Slack",              "description": "Pro plan - Mar 2024"},
    {"date": "2024-03-15", "amount": 85.00,  "category": "SaaS",          "vendor": "Figma",              "description": "Design team license"},

    # ---- Travel & Accommodation ---------------------------------------------
    {"date": "2024-01-10", "amount": 850.00, "category": "Travel",        "vendor": "Make My Trip",       "description": "Flight BLR→DEL for conference"},  # HIGH_SPEND
    {"date": "2024-01-11", "amount": 450.00, "category": "Accommodation", "vendor": "Taj Hotels",         "description": "2-night stay Delhi"},
    {"date": "2024-02-22", "amount": 620.00, "category": "Travel",        "vendor": "IndiGo Airlines",    "description": "Flight for client visit"},         # HIGH_SPEND
    {"date": "2024-03-05", "amount": 180.00, "category": "Travel",        "vendor": "Ola Cabs",          "description": "Airport transfers"},

    # ---- Office Supplies ----------------------------------------------------
    {"date": "2024-01-08", "amount": 75.00,  "category": "Office Supplies","vendor": "Amazon Business",  "description": "Stationery and pens"},
    {"date": "2024-02-14", "amount": 340.00, "category": "Office Supplies","vendor": "Dell",              "description": "External keyboard and mouse"},
    {"date": "2024-03-12", "amount": 89.00,  "category": "Office Supplies","vendor": "Amazon Business",  "description": "Printer paper and toner"},

    # ---- Utilities ----------------------------------------------------------
    {"date": "2024-01-31", "amount": 210.00, "category": "Utilities",     "vendor": "AWS",               "description": "Cloud infrastructure - Jan"},
    {"date": "2024-02-29", "amount": 245.00, "category": "Utilities",     "vendor": "AWS",               "description": "Cloud infrastructure - Feb"},
    {"date": "2024-03-31", "amount": 890.00, "category": "Utilities",     "vendor": "AWS",               "description": "Cloud infrastructure - Mar (spike!)"},  # CATEGORY_SPIKE

    # ---- Marketing ----------------------------------------------------------
    {"date": "2024-01-25", "amount": 500.00, "category": "Marketing",     "vendor": "Google Ads",        "description": "Q1 ad campaign"},
    {"date": "2024-02-20", "amount": 500.00, "category": "Marketing",     "vendor": "Google Ads",        "description": "Q1 ad campaign continuation"},
    {"date": "2024-03-10", "amount": 1200.00,"category": "Marketing",     "vendor": "Meta Ads",          "description": "Product launch campaign"},           # HIGH_SPEND

    # ---- Healthcare ---------------------------------------------------------
    {"date": "2024-01-18", "amount": 60.00,  "category": "Healthcare",    "vendor": "Pharmeasy",         "description": "Office first aid kit restock"},
    {"date": "2024-03-01", "amount": 150.00, "category": "Healthcare",    "vendor": "Medi Assist",       "description": "Employee health checkup"},

    # ---- Unusual categories (will trigger UNUSUAL_CATEGORY alert) -----------
    {"date": "2024-02-10", "amount": 320.00, "category": "Gifts",         "vendor": "Flipkart",          "description": "Employee appreciation gifts"},
    {"date": "2024-03-20", "amount": 75.00,  "category": "Parking",       "vendor": "Nexus Mall Parking","description": "Parking charges for client visit"},

    # ---- Consulting ---------------------------------------------------------
    {"date": "2024-01-15", "amount": 2500.00,"category": "Consulting",    "vendor": "McKinsey & Co.",    "description": "Strategy advisory session Q1"},      # HIGH_SPEND CRITICAL
    {"date": "2024-02-28", "amount": 1800.00,"category": "Consulting",    "vendor": "Deloitte",          "description": "Tax advisory services"},              # HIGH_SPEND
]


def seed_database():
    """
    Clear existing data and insert all sample expenses.
    Runs the alert engine for each expense to generate sample alerts.
    """
    db = SessionLocal()
    try:
        # Optional: clear existing expense + alert data before seeding
        existing = db.query(Expense).count()
        if existing > 0:
            print(f"ℹ  Database already has {existing} expense(s). Skipping seed.")
            print("   To force re-seed, delete expenses.db and run again.")
            return

        print("🌱  Seeding database with sample expenses...\n")

        total_alerts = 0
        for i, exp_data in enumerate(SAMPLE_EXPENSES, start=1):
            expense = Expense(**exp_data)
            db.add(expense)
            db.flush()  # Get the id before alert engine runs

            alerts = run_alert_engine(db, expense)
            total_alerts += len(alerts)

            print(
                f"  [{i:02d}] ${exp_data['amount']:>8.2f}  |  "
                f"{exp_data['category']:<18} |  "
                f"{exp_data['vendor']:<25} "
                f"{'⚠' * len(alerts)}"
            )

        db.commit()
        print(f"\n✅  Seeded {len(SAMPLE_EXPENSES)} expenses successfully.")
        print(f"🚨  Generated {total_alerts} alert(s) from anomaly detection.\n")

    except Exception as e:
        db.rollback()
        print(f"❌  Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
