"""
calculations.py — the financial math.

Deliberately has NO Streamlit import. Every function is pure: same inputs in,
same numbers out. That means the money math can be read and unit-tested without
launching the UI, so we trust the numbers before we trust the charts.

Conventions
-----------
* `inputs` is a flat dict of all input values: every registry cost key (hub_cost,
  smart_lock_hw, ...) plus every HEADLINE_DEFAULTS key (pod2_hourly_rate, ...).
* `items` is the list of cost-item definitions in effect = COST_ITEMS plus any
  runtime "custom costs". Passing it in (rather than importing COST_ITEMS) is what
  lets a custom cost behave exactly like a built-in one.
* Money is monthly unless a name says otherwise. Percentages are fractions (0.20).
* A None payback/ROIC means "undefined" — the UI renders it as "bleeds" / "n/a".
"""

from cost_items import COST_ITEMS, MODELS, PODS, total_doors


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
    doors = total_doors(inputs)
    total = 0.0
    for item in items:
        if item.get("category") != category:
            continue
        if model_key not in item.get("applies_to", []):
            continue
        value = inputs.get(item["key"], item.get("default", 0))
        if item.get("per_door"):
            value *= doors
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
def pod_usage_hours(pod, inputs, util_mult=1.0):
    """Booked hours/month for ONE pod = bookable hrs × utilization × multiplier.

    `util_mult` is a neutral 1.0 by default; the crossover sweep and the fleet
    utilization ramp pass a non-1.0 value to scale every pod together without
    mutating any per-pod key.
    """
    return (inputs[pod["bookable_key"]]
            * inputs[pod["util_key"]]
            * util_mult)


def usage_hours(inputs, util_mult=1.0):
    """Total booked hours/month across all pods (the hub aggregate)."""
    return sum(pod_usage_hours(p, inputs, util_mult) for p in PODS)


def pod_gross(inputs, util_mult=1.0):
    """Per-pod revenue summed = Σ (pod hours × pod rate).

    Returns (total_gross, total_hours) so callers that also need hours (the
    blended-rate display, hybrid overflow) don't recompute them.
    """
    gross = hours = 0.0
    for p in PODS:
        h = pod_usage_hours(p, inputs, util_mult)
        gross += h * inputs[p["rate_key"]]
        hours += h
    return gross, hours


def blended_hourly_rate(inputs, util_mult=1.0):
    """Revenue-weighted blended hourly rate — a COMPUTED, read-only display value.

    Falls back to the simple average of pod rates when there are zero booked
    hours (so the UI shows a sane number at 0% utilization instead of dividing
    by zero).
    """
    gross, hours = pod_gross(inputs, util_mult)
    if hours <= 0:
        return sum(inputs[p["rate_key"]] for p in PODS) / len(PODS)
    return gross / hours


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
def _gross_net(model_key, inputs, items, util_mult=1.0):
    if model_key == "b2c":
        gross, _ = pod_gross(inputs, util_mult)
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
        # Single hub-level cap on TOTAL booked hours across both pods; overflow is
        # priced at the revenue-weighted blended rate (the base+overflow deal is
        # struck at the hub level, not per room).
        overflow_hours = max(0.0, usage_hours(inputs, util_mult) - inputs["overflow_cap_hours"])
        overflow_rev = overflow_hours * blended_hourly_rate(inputs, util_mult)
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
    # The hidden utilization multiplier (default 1.0) is how the crossover sweep
    # turns the "utilization knob" across both pods through one input key.
    util_mult = inputs.get("util_multiplier", 1.0)
    gross, net = _gross_net(model_key, inputs, items, util_mult=util_mult)
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
# Fleet / scaling: a month-by-month cohort simulation
# ---------------------------------------------------------------------------
# The single-unit functions above are timeless snapshots. Real growth is a fleet
# of one hero SKU replicated across locations, deployed gradually — so the things
# that actually matter (peak cash needed, when the fleet turns cash-positive) only
# show up once you simulate month by month. Each unit is a "cohort" that deploys at
# some month and then earns net cash forever after; the portfolio is the sum across
# live cohorts. Cadence is a tunable what-if (0 = all units at once), not a forecast.
#
# Basis: EQUITY. Capital is paid from cash at deploy and we use the equity-basis net
# (before debt service). Per-cohort debt amortization is deliberately not modeled here.
def _net_by_age(model_key, inputs, items, ramp_months, horizon_months):
    """Monthly equity-net for a single cohort at each age 0..horizon-1.

    Applies a linear utilization ramp: a cohort fills up over `ramp_months` rather
    than hitting steady-state utilization on day one. The ramp factor is passed as
    the `util_mult` seam, which scales every pod's utilization together — no per-pod
    key mutation, no math duplicated.

    Usage-independent models (b2b, venue_buys) come out flat by construction: their
    net doesn't read utilization, so the ramp has no effect on them. That's honest,
    not a bug — surfaced in the UI caption.
    """
    inputs = resolve_inputs(inputs)
    out = []
    for age in range(horizon_months):
        if ramp_months <= 1:
            factor = 1.0
        else:
            # age 0 (deploy month) earns 1/ramp of steady-state, climbing to full.
            factor = min(1.0, (age + 1) / ramp_months)
        _, net = _gross_net(model_key, inputs, items, util_mult=factor)
        out.append(net)
    return out


def simulate_fleet(model_key, inputs, items=COST_ITEMS, *,
                   total_units, cadence_months, ramp_months, horizon_months):
    """Simulate a fleet of one model replicated across `total_units` locations.

    Deploys on a fixed cadence (months between deployments; 0 = all at once) with no
    cash-gating — units land on schedule regardless of balance. Returns time series
    plus the headline metrics (peak funding need, cash trough, breakeven month).

    Equity basis: capital is spent from cash at each deploy; net is before financing.
    """
    H = max(0, int(horizon_months))
    total_units = int(total_units)
    months = list(range(H))

    # Deployment schedule. cadence 0 => everyone lands in month 0. Drop any cohort
    # scheduled beyond the horizon, and report how many actually fit.
    if total_units <= 0 or H == 0:
        deploy_months = []
    elif cadence_months <= 0:
        deploy_months = [0] * total_units
    else:
        deploy_months = [i * int(cadence_months) for i in range(total_units)]
    deploy_months = [d for d in deploy_months if d < H]
    deployed_units = len(deploy_months)

    # Capex is utilization-independent, so compute it once; the per-cohort net curve
    # is also computed once and then just shifted in time per cohort (cheap adds).
    cap_per_unit = capital_at_risk(model_key, inputs, items)
    net_by_age = _net_by_age(model_key, inputs, items, ramp_months, H)
    steady_state_monthly_net = net_by_age[-1] if net_by_age else 0.0

    live_units = [0] * H
    monthly_net = [0.0] * H
    capital_outlay = [0.0] * H
    for d in deploy_months:
        capital_outlay[d] += cap_per_unit
        for t in range(d, H):
            live_units[t] += 1
            monthly_net[t] += net_by_age[t - d]

    cumulative_capital, net_cash_from_zero, cash_curve = [], [], []
    avail = inputs.get("available_capital", 0)
    cum_cap = cum_net = 0.0
    for t in range(H):
        cum_cap += capital_outlay[t]
        cum_net += monthly_net[t]
        ncz = cum_net - cum_cap            # cash generated minus capital sunk, from $0
        cumulative_capital.append(cum_cap)
        net_cash_from_zero.append(ncz)
        cash_curve.append(avail + ncz)     # actual balance given starting capital

    if net_cash_from_zero:
        trough_val = min(net_cash_from_zero)
        trough_month = net_cash_from_zero.index(trough_val)
        peak_funding_need = max(0.0, -trough_val)
    else:
        trough_month, peak_funding_need = None, 0.0

    # First month cumulative net has repaid cumulative capital. Staggered deploys can
    # re-dip after a later cohort lands, so this is the FIRST crossing (caveat in UI).
    # An empty fleet has nothing to recover, so breakeven is undefined, not month 0.
    if deployed_units == 0:
        breakeven_month = None
    else:
        breakeven_month = next((t for t in range(H) if net_cash_from_zero[t] >= 0), None)

    dry = [t for t in range(H) if cash_curve[t] < 0]
    runs_dry = len(dry) > 0
    dry_month = dry[0] if dry else None
    outside_capital_needed = max(0.0, peak_funding_need - avail)

    return {
        "months": months,
        "requested_units": total_units,
        "deployed_units": deployed_units,
        "deploy_months": deploy_months,
        "live_units": live_units,
        "monthly_net": monthly_net,
        "cumulative_capital": cumulative_capital,
        "net_cash_from_zero": net_cash_from_zero,
        "cash_curve": cash_curve,
        "peak_funding_need": peak_funding_need,
        "trough_month": trough_month,
        "breakeven_month": breakeven_month,
        "runs_dry": runs_dry,
        "dry_month": dry_month,
        "outside_capital_needed": outside_capital_needed,
        "steady_state_monthly_net": steady_state_monthly_net,
        "cap_per_unit": cap_per_unit,
    }


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
    crossover chart: sweep 'util_multiplier' (B2C line collapses as both pods fill)
    or 'monthly_subscription_price' (B2B line moves).
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
