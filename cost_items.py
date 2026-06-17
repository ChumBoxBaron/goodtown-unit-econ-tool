"""
cost_items.py — the single source of truth for every cost input.

This module is intentionally *data only* (plus a couple of tiny helpers). The UI
(app.py), the math (calculations.py), and the Reset-to-defaults logic all read
from the structures defined here, so there is exactly one place to edit when a
cost changes or a new one is added.

Three things live here:
  1. MODELS         — the four revenue models we compare, by key.
  2. COST_ITEMS     — the cost-item registry. Add a dict here and it automatically
                      appears as an input and flows into capital-at-risk / opex.
  3. HEADLINE_DEFAULTS — the non-registry inputs (sliders, toggles, % rates) that
                      aren't simple per-unit sums.
  4. BENCHMARKS     — hardcoded real-world anchors surfaced in tooltips/help text.

------------------------------------------------------------------------------
HOW TO ADD A NEW COST VARIABLE (the whole point of this design)
------------------------------------------------------------------------------
Append one dict to COST_ITEMS, e.g.:

    {"key": "permit_fee", "label": "Municipal permit", "category": "opex_fixed",
     "default": 120, "min": 0, "max": 1000, "step": 10, "per_door": False,
     "applies_to": ["b2c", "b2b", "hybrid"], "help": "Annualised monthly permit cost."}

That's it. No edits to the UI or the math are required. (Or, at runtime, use the
"Add custom cost" form in the app — same shape, no code change at all.)
"""

# ---------------------------------------------------------------------------
# The four models, by key. Order here drives the table/column order in the UI.
# ---------------------------------------------------------------------------
MODELS = [
    {"key": "b2c", "label": "B2C pay-per-use"},
    {"key": "b2b", "label": "B2B subscription (Goodtown-owned)"},
    {"key": "venue_buys", "label": "Venue-buys + service"},
    {"key": "hybrid", "label": "Base + overflow"},
]
MODEL_KEYS = [m["key"] for m in MODELS]

# Models where Goodtown owns the hub and therefore carries the capital.
# (venue_buys is excluded — the venue owns the unit, Goodtown's capital ≈ $0.)
GOODTOWN_OWNED = ["b2c", "b2b", "hybrid"]


# ---------------------------------------------------------------------------
# THE COST-ITEM REGISTRY
# ---------------------------------------------------------------------------
# Each entry is one cost input. Fields:
#   key        — unique id; the value the user sets is stored under this key.
#   label      — shown in the UI.
#   category   — "capex"      → one-time, per-unit, adds to capital-at-risk.
#                "opex_fixed" → recurring monthly, adds to fixed opex.
#                (Payment processing is NOT here — it scales with revenue, so it
#                 lives in calculations.py, not as a flat sum.)
#   default/min/max/step — for the input widget and the Reset button.
#   per_door   — if True, the value is multiplied by rooms_per_hub (e.g. 2 locks).
#   applies_to — which model keys this cost hits. This is how the B2C-vs-B2B opex
#                difference emerges from data instead of two hand-tuned lump sums:
#                consumer-facing support only applies_to the consumer models.
#   help       — tooltip; cite the real-world anchor where one exists.
# ---------------------------------------------------------------------------
COST_ITEMS = [
    # ---- CAPEX (one-time, per unit → capital-at-risk) --------------------
    {
        "key": "hub_cost", "label": "Hub hardware (landed)", "category": "capex",
        "default": 44000, "min": 30000, "max": 95000, "step": 1000,
        "per_door": False, "applies_to": GOODTOWN_OWNED,
        "help": "~$44k landed/hub from Mute Modular at the 50% discount; ~$88k "
                "undiscounted. Use the 'undiscounted' toggle to model discount erosion. "
                "Excludes smart lock / LTE / install — those are separate line items below.",
    },
    {
        "key": "smart_lock_hw", "label": "Smart lock hardware (per door)", "category": "capex",
        "default": 400, "min": 0, "max": 2000, "step": 50,
        "per_door": True, "applies_to": GOODTOWN_OWNED,
        "help": "Keyless smart lock per room door. Scales with rooms_per_hub "
                "(a 2-room hub needs 2 locks). Excluded from the Mute hub quote.",
    },
    {
        "key": "lte_router_hw", "label": "LTE router hardware", "category": "capex",
        "default": 250, "min": 0, "max": 1500, "step": 25,
        "per_door": False, "applies_to": GOODTOWN_OWNED,
        "help": "Cellular router so the pod has its own Wi-Fi independent of the "
                "venue's network. Excluded from the Mute hub quote.",
    },
    {
        "key": "install_cost", "label": "Delivery + install + setup", "category": "capex",
        "default": 2000, "min": 0, "max": 15000, "step": 250,
        "per_door": False, "applies_to": GOODTOWN_OWNED,
        "help": "Freight, placement, electrical/network setup, commissioning labor. "
                "Not in the hub quote; can be material and is easy to forget.",
    },

    # ---- OPEX (recurring monthly → fixed opex) --------------------------
    {
        "key": "lock_saas", "label": "Smart-lock software (per door/mo)", "category": "opex_fixed",
        "default": 20, "min": 0, "max": 200, "step": 5,
        "per_door": True, "applies_to": ["b2c", "b2b", "venue_buys", "hybrid"],
        "help": "Access-control SaaS per lock. Applies even when the venue owns the "
                "unit, because Goodtown still runs the booking/access layer.",
    },
    {
        "key": "lte_data_plan", "label": "LTE data plan (/mo)", "category": "opex_fixed",
        "default": 50, "min": 0, "max": 300, "step": 5,
        "per_door": False, "applies_to": ["b2c", "b2b", "venue_buys", "hybrid"],
        "help": "Monthly cellular data plan for in-pod Wi-Fi.",
    },
    {
        "key": "cleaning", "label": "Cleaning (/mo)", "category": "opex_fixed",
        "default": 600, "min": 0, "max": 3000, "step": 50,
        "per_door": False, "applies_to": ["b2c", "b2b", "hybrid"],
        "help": "Recurring cleaning/turn cost. Excluded for venue-buys: the venue "
                "owns and maintains the physical unit.",
    },
    {
        "key": "insurance", "label": "Liability insurance (/mo)", "category": "opex_fixed",
        "default": 150, "min": 0, "max": 1500, "step": 25,
        "per_door": False, "applies_to": ["b2c", "b2b", "hybrid"],
        "help": "Liability/insurance premium. The primer makes institutional "
                "liability the strategic crux, so it's a first-class line item. "
                "Excluded for venue-buys: the venue insures its owned unit.",
    },
    {
        "key": "support_base", "label": "Base support / monitoring (/mo)", "category": "opex_fixed",
        "default": 300, "min": 0, "max": 2000, "step": 25,
        "per_door": False, "applies_to": ["b2c", "b2b", "venue_buys", "hybrid"],
        "help": "Light remote support/monitoring that every model needs.",
    },
    {
        "key": "consumer_ops", "label": "Consumer support + marketing (/mo)", "category": "opex_fixed",
        "default": 400, "min": 0, "max": 3000, "step": 25,
        "per_door": False, "applies_to": ["b2c", "hybrid"],
        "help": "Consumer-facing support and demand marketing. Applies ONLY to the "
                "pay-per-use models — this single item is why B2B opex is 'lighter' "
                "than B2C, derived from data instead of a hand-tuned lump sum.",
    },
]


# ---------------------------------------------------------------------------
# HEADLINE + NON-REGISTRY DEFAULTS
# ---------------------------------------------------------------------------
# Inputs that aren't simple per-unit cost sums: the three load-bearing sliders,
# pricing levers, the venue-charge toggle, financing, and capital-to-scale knobs.
# Kept here so cost_items.py is the single source of truth for ALL defaults and
# the Reset button has one place to read from.
# ---------------------------------------------------------------------------
HEADLINE_DEFAULTS = {
    # --- The three load-bearing assumptions (prominent sliders) ---
    "utilization_pct": 0.20,            # THE B2C lever. 5%–60%.
    "monthly_subscription_price": 2500, # THE B2B lever. $1k–$9k.
    "annual_interest_rate": 0.14,       # cost of capital. 6%–25%.

    # --- Shared unit economics ---
    "rooms_per_hub": 2,
    "prime_hours_per_month": 720,       # bookable prime hrs/room/month
    "blended_hourly_rate": 30,          # ALCOVE benchmark is $18/hr single-occupancy

    # --- B2C / venue economics ---
    "venue_charge_mode": "rev_share",   # "rev_share" | "rent"
    "venue_rev_share_pct": 0.15,        # share of B2C gross paid to venue
    "flat_rent": 1500,                  # used when venue_charge_mode == "rent"
    "payment_proc_pct": 0.035,          # % of gross, NOT flat — scales with usage

    # --- Other model levers ---
    "service_fee_venue_buys": 1000,     # recurring fee when venue owns the unit
    "base_fee_hybrid": 800,             # recurring floor in base+overflow
    "overflow_cap_hours": 40,           # hours included before overflow billing
    "venue_rev_share_pct_on_overflow": 0.15,

    # --- Capital & financing ---
    "financing_mode": "equity",         # "equity" | "debt"
    "loan_term_months": 36,
    "use_undiscounted": False,          # overrides hub_cost to the undiscounted figure
    "undiscounted_hub_cost": 88000,
    "target_unit_count": 5,
    "available_capital": 150000,

    # --- Fleet / scaling projection (month-by-month cohort sim) ---
    # cadence is a tunable what-if, not a forecast: 0 = deploy all units at once.
    "fleet_cadence_months": 2,          # months between deployments (0–12)
    "fleet_ramp_months": 6,             # linear utilization ramp per cohort (1–24)
    "fleet_horizon_months": 36,         # projection window (6–120)
}


# ---------------------------------------------------------------------------
# BENCHMARKS — real-world anchors (spec §5). Surfaced in help text so the user
# always sees the data next to their assumptions and never mistakes a tuned
# guess for a finding.
# ---------------------------------------------------------------------------
BENCHMARKS = {
    "ALCOVE": "Closest comparable (premium private pods): $18/hr single-occupancy, "
              "15-min min, app-based keyless access. 5 locations, 4 of 5 inside hotels.",
    "Throne": "B2B subscription comparable: $4,250–$9,000 per unit/month, 10-unit "
              "minimum at steady state. No upfront capital to buyer — Throne absorbs "
              "unit cost, funded by $15M+ Series B. Goodtown cannot do this.",
    "Jabbrrbox": "Airport pods: $15 / 30 min B2C. Scaled as the hardware+tech layer "
                 "for partners (IWG/Regus 3,750-unit deal) rather than operating solo.",
    "Goodtown_unit": "~$44k landed/hub discounted (Mute Modular), ~$88k undiscounted. "
                     "Excludes smart lock, LTE modem, and ops.",
}


# ---------------------------------------------------------------------------
# Tiny helpers (no Streamlit, no heavy logic) so callers don't reimplement them.
# ---------------------------------------------------------------------------
def registry_defaults():
    """Return {key: default} for every registry cost item."""
    return {item["key"]: item["default"] for item in COST_ITEMS}


def all_defaults():
    """Full default input set: registry values + headline/non-registry values."""
    return {**registry_defaults(), **HEADLINE_DEFAULTS}


def find_item(key, custom_items=None):
    """Look up a cost item by key across the registry and any custom items."""
    for item in COST_ITEMS + (custom_items or []):
        if item["key"] == key:
            return item
    return None
