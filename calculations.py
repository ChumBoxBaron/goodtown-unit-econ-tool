"""
calculations.py — the financial math.

Deliberately has NO Streamlit import. Every function is pure: same inputs in,
same numbers out. That means the money math can be read and unit-tested without
launching the UI, so we trust the numbers before we trust the charts.

Conventions
-----------
* `inputs` is a flat dict of all input values: every registry cost key (hub_cost,
  smart_lock_hw, ...) plus every HEADLINE_DEFAULTS key (utilization_pct, ...).
* `items` is the list of cost-item definitions in effect = COST_ITEMS plus any
  runtime "custom costs". Passing it in (rather than importing COST_ITEMS) is what
  lets a custom cost behave exactly like a built-in one.
* Money is monthly unless a name says otherwise. Percentages are fractions (0.20).
* A None payback/ROIC means "undefined" — the UI renders it as "bleeds" / "n/a".
"""

from cost_items import COST_ITEMS, MODELS


# ---------------------------------------------------------------------------
# Input resolution
# ---------------------------------------------------------------------------
def resolve_inputs(inputs):
    """Return a shallow copy with derived overrides applied.

    Currently: the 'use undiscounted ($88k)' toggle overrides hub_cost. Doing it
    here (once) keeps every downstream sum from having to know about the toggle.
    """
    resolved = dict(inputs)
    if resolved.get("use_undiscounted"):
        resolved["hub_cost"] = resolved.get("undiscounted_hub_cost", 88000)
    return resolved


# ---------------------------------------------------------------------------
# Registry-driven cost sums (the heart of the extensibility design)
# ---------------------------------------------------------------------------
def _sum_items(model_key, inputs, items, category):
    """Sum every item of `category` that applies to `model_key`, honoring per_door."""
    rooms = inputs.get("rooms_per_hub", 1)
    total = 0.0
    for item in items:
        if item.get("category") != category:
            continue
        if model_key not in item.get("applies_to", []):
            continue
        value = inputs.get(item["key"], item.get("default", 0))
        if item.get("per_door"):
            value *= rooms
        total += value
    return total


def capital_at_risk(model_key, inputs, items=COST_ITEMS):
    """One-time capital Goodtown puts at risk per deployed unit, for this model."""
    return _sum_items(model_key, resolve_inputs(inputs), items, "capex")


def fixed_opex(model_key, inputs, items=COST_ITEMS):
    """Recurring monthly fixed opex for this model (excludes %-of-revenue costs)."""
    return _sum_items(model_key, inputs, items, "opex_fixed")


# ---------------------------------------------------------------------------
# Revenue / variable-cost helpers
# ---------------------------------------------------------------------------
def usage_hours(inputs):
    """Booked hours/month across the hub = prime hrs × rooms × utilization."""
    return (inputs["prime_hours_per_month"]
            * inputs["rooms_per_hub"]
            * inputs["utilization_pct"])


def venue_charge(gross, inputs, rev_share_pct):
    """What the venue takes: a % of gross (rev-share) OR a flat rent — never both."""
    if inputs.get("venue_charge_mode") == "rent":
        return inputs.get("flat_rent", 0)
    return rev_share_pct * gross


def payment_processing(gross, inputs):
    """Payment processing as a % of gross revenue (scales with usage, not flat)."""
    return inputs.get("payment_proc_pct", 0) * gross


# ---------------------------------------------------------------------------
# Per-model gross + net (monthly, equity basis before financing)
# ---------------------------------------------------------------------------
def _gross_net(model_key, inputs, items):
    if model_key == "b2c":
        gross = usage_hours(inputs) * inputs["blended_hourly_rate"]
        net = (gross
               - venue_charge(gross, inputs, inputs["venue_rev_share_pct"])
               - payment_processing(gross, inputs)
               - fixed_opex("b2c", inputs, items))
        return gross, net

    if model_key == "b2b":
        # Venue pays Goodtown a fixed subscription; no rev-share, no consumer payment friction.
        gross = inputs["monthly_subscription_price"]
        net = gross - fixed_opex("b2b", inputs, items)
        return gross, net

    if model_key == "venue_buys":
        # Venue owns the unit; Goodtown earns a recurring service/software fee.
        gross = inputs["service_fee_venue_buys"]
        net = gross - fixed_opex("venue_buys", inputs, items)
        return gross, net

    if model_key == "hybrid":
        overflow_hours = max(0.0, usage_hours(inputs) - inputs["overflow_cap_hours"])
        overflow_rev = overflow_hours * inputs["blended_hourly_rate"]
        gross = inputs["base_fee_hybrid"] + overflow_rev
        # Rev-share applies to the overflow usage portion only; rent is flat.
        if inputs.get("venue_charge_mode") == "rent":
            vcost = inputs.get("flat_rent", 0)
        else:
            vcost = inputs["venue_rev_share_pct_on_overflow"] * overflow_rev
        net = (gross - vcost
               - payment_processing(gross, inputs)
               - fixed_opex("hybrid", inputs, items))
        return gross, net

    raise ValueError(f"Unknown model key: {model_key}")


# ---------------------------------------------------------------------------
# Financing
# ---------------------------------------------------------------------------
def debt_service(capital, inputs):
    """Level monthly payment to amortize `capital` over the loan term.

    Computed on the FULL capital-at-risk (hub + lock + router + install), not just
    the hub — so financing the add-ons is reflected. Returns 0 when capital is ~0.
    """
    if capital <= 0:
        return 0.0
    mr = inputs["annual_interest_rate"] / 12.0
    n = inputs["loan_term_months"]
    if mr == 0:
        return capital / n
    factor = (mr * (1 + mr) ** n) / ((1 + mr) ** n - 1)
    return capital * factor


# ---------------------------------------------------------------------------
# Payback / ROIC (guarded)
# ---------------------------------------------------------------------------
def payback_months(capital, monthly_net):
    """Months to recover capital. None == 'bleeds' (net ≤ 0). 0 == capital-free."""
    if capital <= 0:
        return 0.0
    if monthly_net <= 0:
        return None
    return capital / monthly_net


def roic_annual(monthly_net, capital):
    """Simple annual ROIC. None when capital is ~0 (return is undefined/infinite)."""
    if capital <= 0:
        return None
    return (monthly_net * 12) / capital


# ---------------------------------------------------------------------------
# Top-level: compute one model into a result dict the UI can render directly
# ---------------------------------------------------------------------------
def compute_model(model_key, inputs, items=COST_ITEMS):
    inputs = resolve_inputs(inputs)
    gross, net = _gross_net(model_key, inputs, items)
    capital = capital_at_risk(model_key, inputs, items)

    is_debt = inputs.get("financing_mode") == "debt"
    ds = debt_service(capital, inputs) if is_debt else 0.0
    financed_net = net - ds

    return {
        "model": model_key,
        "gross": gross,
        "net": net,                       # equity-basis monthly net (before financing)
        "capital": capital,
        "is_debt": is_debt,
        "debt_service": ds,
        "financed_net": financed_net,
        "payback": payback_months(capital, net),
        "financed_payback": payback_months(capital, financed_net) if is_debt else None,
        "roic": roic_annual(net, capital),
        "bleeds": net <= 0,
        "financed_bleeds": is_debt and financed_net <= 0,
    }


def compute_all(inputs, items=COST_ITEMS, model_keys=None):
    """Compute every model. Returns {model_key: result_dict}."""
    keys = model_keys or [m["key"] for m in MODELS]
    return {k: compute_model(k, inputs, items) for k in keys}


# ---------------------------------------------------------------------------
# Sweeps for the crossover chart
# ---------------------------------------------------------------------------
def _payback_for_chart(result, financed):
    """Pick the payback value to plot; None (bleeds) maps to None so the line breaks."""
    if financed and result["is_debt"]:
        return result["financed_payback"]
    return result["payback"]


def sweep(inputs, items, x_key, x_values, model_keys, financed=False):
    """Recompute payback for every model across a swept input.

    Returns {model_key: [payback or None, ...]} aligned to x_values. Used for the
    crossover chart: sweep 'utilization_pct' (B2C line collapses) or
    'monthly_subscription_price' (B2B line moves).
    """
    series = {k: [] for k in model_keys}
    for x in x_values:
        probe = dict(inputs)
        probe[x_key] = x
        for k in model_keys:
            res = compute_model(k, probe, items)
            series[k].append(_payback_for_chart(res, financed))
    return series


def find_crossover(x_values, line_a, line_b):
    """Return the x where two payback lines cross (linear interp), or None.

    Used to annotate the utilization at which B2C overtakes B2B. Skips segments
    where either line is None (bleeds / undefined).
    """
    for i in range(1, len(x_values)):
        a0, a1 = line_a[i - 1], line_a[i]
        b0, b1 = line_b[i - 1], line_b[i]
        if None in (a0, a1, b0, b1):
            continue
        d0, d1 = a0 - b0, a1 - b1
        if d0 == 0:
            return x_values[i - 1]
        if d0 * d1 < 0:  # sign change → they crossed between these points
            t = d0 / (d0 - d1)
            return x_values[i - 1] + t * (x_values[i] - x_values[i - 1])
    return None
