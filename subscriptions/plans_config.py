"""
================================================================================
 SUBSCRIPTION PLANS — SINGLE SOURCE OF TRUTH
================================================================================

Jab bhi price, limit ya feature change karna ho — SIRF isi file me karo.
Kahin aur (views.py, templates, admin) me hardcoded price/limit NAHI likhna.

Change karne ke baad ye command chalao taaki database sync ho jaye:

    python manage.py sync_plans

Ye command:
  - Agar plan naam DB me nahi hai  -> naya row create karega
  - Agar plan naam DB me hai       -> price/limits/features update karega
  - Agar plan yaha se hata diya    -> DB me use is_active=False kar dega
    (delete nahi karega, kyunki purane subscribers ka data safe rehna chahiye)

--------------------------------------------------------------------------------
Har plan dictionary ke fields:
  name          -> Plan ka naam (unique identifier, isse mat badlo baad me
                    warna naya plan ban jayega instead of update)
  audience      -> "builder" ya "agent" (sirf reference/grouping ke liye)
  description   -> Chhota sa tagline
  price_monthly -> ₹ me monthly price (0 = free plan)
  price_yearly  -> ₹ me yearly price (discounted)
  max_properties-> Kitni properties list kar sakta hai
  max_agents    -> Builder plan me kitne agents add ho sakte hain
                   (Agent plans ke liye ye 0 rakho, matter nahi karta)
  max_leads     -> Kitne leads handle kar sakta hai
  features      -> List of feature flags (strings) — inhe code me
                    `has_feature(subscription, "whatsapp_alerts")` se check karo
  is_active     -> False karne se plan naye users ko dikhna band ho jayega
                    (purane subscribers par asar nahi padega)
--------------------------------------------------------------------------------
"""

BUILDER_PLANS = [
    {
        "name": "Builder Starter",
        "audience": "builder",
        "description": "Chhote builders / naye projects ke liye",
        "price_monthly": 999,
        "price_yearly": 9999,
        "max_properties": 15,
        "max_agents": 3,
        "max_leads": 200,
        "features": [
            "basic_crm",
            "email_notifications",
            "lead_capture",
        ],
        "is_active": True,
    },
    {
        "name": "Builder Growth",
        "audience": "builder",
        "description": "Badhte hue builders, multiple agents ke saath",
        "price_monthly": 2499,
        "price_yearly": 24999,
        "max_properties": 50,
        "max_agents": 10,
        "max_leads": 1000,
        "features": [
            "basic_crm",
            "email_notifications",
            "lead_capture",
            "whatsapp_alerts",
            "auto_lead_assignment",
            "basic_reports",
        ],
        "is_active": True,
    },
    {
        "name": "Builder Business",
        "audience": "builder",
        "description": "Multiple projects, bade sales team ke liye",
        "price_monthly": 5999,
        "price_yearly": 59999,
        "max_properties": 150,
        "max_agents": 25,
        "max_leads": 5000,
        "features": [
            "basic_crm",
            "email_notifications",
            "lead_capture",
            "whatsapp_alerts",
            "auto_lead_assignment",
            "basic_reports",
            "advanced_analytics",
            "multi_project",
            "priority_support",
        ],
        "is_active": True,
    },
    {
        "name": "Builder Enterprise",
        "audience": "builder",
        "description": "Bade developers, unlimited scale, custom setup",
        "price_monthly": 15000,
        "price_yearly": 150000,
        "max_properties": 100000,   # effectively "unlimited"
        "max_agents": 100000,
        "max_leads": 100000,
        "features": [
            "basic_crm",
            "email_notifications",
            "lead_capture",
            "whatsapp_alerts",
            "auto_lead_assignment",
            "basic_reports",
            "advanced_analytics",
            "multi_project",
            "priority_support",
            "api_access",
            "custom_branding",
            "dedicated_support",
        ],
        "is_active": True,
    },
]

AGENT_PLANS = [
    {
        "name": "Agent Free",
        "audience": "agent",
        "description": "Naye agents jo pehle CRM try karna chahte hain",
        "price_monthly": 0,
        "price_yearly": 0,
        "max_properties": 3,
        "max_agents": 0,
        "max_leads": 20,
        "features": [
            "basic_listing",
        ],
        "is_active": True,
    },
    {
        "name": "Agent Pro",
        "audience": "agent",
        "description": "Active agents jo roz leads follow-up karte hain",
        "price_monthly": 499,
        "price_yearly": 4999,
        "max_properties": 20,
        "max_agents": 0,
        "max_leads": 150,
        "features": [
            "basic_listing",
            "full_crm",
            "scheduler",
            "commission_tracking",
        ],
        "is_active": True,
    },
    {
        "name": "Agent Elite",
        "audience": "agent",
        "description": "Top performing agents, multiple builders ke saath",
        "price_monthly": 999,
        "price_yearly": 9999,
        "max_properties": 100000,
        "max_agents": 0,
        "max_leads": 100000,
        "features": [
            "basic_listing",
            "full_crm",
            "scheduler",
            "commission_tracking",
            "multi_builder_linking",
            "priority_leads",
            "rating_boost",
        ],
        "is_active": True,
    },
]

# sync_plans command dono list ko combine karke process karta hai
ALL_PLANS = BUILDER_PLANS + AGENT_PLANS
