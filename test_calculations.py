"""
test_calculations.py — sanity tests on the math, the registry sums, custom
costs, and the save/load round-trip.

Run with:  python -m pytest test_calculations.py -v

The expected numbers below are hand-worked from the default inputs so a failure
means the math drifted, not that the test is just echoing the code.
"""

import math

import pytest

import calculations as calc
import cost_items
from cost_items import COST_ITEMS, all_defaults
import config_io


def approx(a, b, tol=1e-6):
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)


# ---------------------------------------------------------------------------
# Hand-worked default scenario — TWO pods summed (see comments for arithmetic)
# ---------------------------------------------------------------------------
# pod2: 300 bookable × 0.20 util = 60 hrs × $15 = 900
# pod4: 300 bookable × 0.20 util = 60 hrs × $30 = 1800
# usage_hours = 60 + 60 = 120 ; b2c_gross = 900 + 1800 = 2700
# blended     = 2700 / 120 = $22.50 (revenue-weighted, computed)
# venue (15%) = 405 ; pay_proc (3.5%) = 94.5
# opex_b2c    = lock 40 + lte 50 + clean 600 + ins 150 + supp 300 + consumer 400 = 1540
# b2c_net     = 2700 - 405 - 94.5 - 1540 = 660.5
# capital     = hub 44000 + lock 800 (2 doors × 400) + router 250 + install 2000 = 47050

def test_b2c_gross_and_net_default():
    inp = all_defaults()
    assert approx(calc.usage_hours(inp), 120)
    res = calc.compute_model("b2c", inp)
    assert approx(res["gross"], 2700)
    assert approx(res["net"], 660.5)
    assert approx(res["capital"], 47050)
    assert approx(res["payback"], 47050 / 660.5)
    assert approx(res["roic"], 660.5 * 12 / 47050)


def test_b2b_opex_is_lighter_than_b2c():
    """B2B should drop exactly the consumer_ops line (400) vs B2C — emergent, not hardcoded."""
    inp = all_defaults()
    assert approx(calc.fixed_opex("b2c", inp), 1540)
    assert approx(calc.fixed_opex("b2b", inp), 1140)  # 1540 - 400 consumer_ops
    res = calc.compute_model("b2b", inp)
    assert approx(res["gross"], 2500)
    assert approx(res["net"], 2500 - 1140)


def test_venue_buys_is_capital_free():
    inp = all_defaults()
    res = calc.compute_model("venue_buys", inp)
    assert res["capital"] == 0
    assert res["payback"] == 0          # capital-free
    assert res["roic"] is None          # undefined when capital is 0
    # opex = lock 40 + lte 50 + support 300 = 390 ; net = 1000 - 390
    assert approx(res["net"], 610)


def test_hybrid_overflow():
    inp = all_defaults()
    # total hours 120 ; overflow = 120 - 40 = 80 hrs, priced at blended $22.50
    # overflow_rev = 80 * 22.50 = 1800 ; gross = 800 + 1800 = 2600
    res = calc.compute_model("hybrid", inp)
    assert approx(res["gross"], 2600)
    # venue 0.15*1800=270 ; pay 0.035*2600=91 ; opex 1540
    assert approx(res["net"], 2600 - 270 - 91 - 1540)


# ---------------------------------------------------------------------------
# Two-pod model: per-pod sum, revenue-weighted blend, equivalence to old model
# ---------------------------------------------------------------------------
def test_two_pod_hub_sums_pods():
    """B2C gross is the SUM of per-pod revenue, not one blended rate × room count."""
    inp = all_defaults()
    gross, hours = calc.pod_gross(inp)
    assert approx(hours, 120)              # 60 (pod2) + 60 (pod4)
    assert approx(gross, 2700)             # 900 (pod2) + 1800 (pod4)
    assert approx(calc.blended_hourly_rate(inp), 22.5)   # 2700 / 120
    res = calc.compute_model("b2c", inp)
    assert approx(res["gross"], 2700)
    assert approx(res["net"], 660.5)


def test_blended_rate_is_revenue_weighted():
    """The blend weights by each pod's BOOKED HOURS, not a simple average of rates."""
    inp = all_defaults()
    assert approx(calc.blended_hourly_rate(inp), 22.5)   # equal hours → midpoint of 15/30
    # Push pod4 to twice pod2's hours; blend must rise above the simple $22.50 average.
    inp["pod4_utilization_pct"] = 0.40
    # pod2: 60 hrs × 15 = 900 ; pod4: 120 hrs × 30 = 3600 ; blend = 4500 / 180 = 25.0
    assert approx(calc.blended_hourly_rate(inp), 25.0)


def test_equivalence_to_old_single_rate():
    """A uniform two-pod hub reproduces the pre-refactor single-rate result exactly.

    Set both pods to the OLD defaults (rate 30, util 0.20, 720 bookable hrs). The
    per-pod sum then equals the old `prime_hours × rooms_per_hub(2) × util × rate`.
    """
    inp = all_defaults()
    for p in ("pod2", "pod4"):
        inp[f"{p}_hourly_rate"] = 30
        inp[f"{p}_utilization_pct"] = 0.20
        inp[f"{p}_bookable_hours_per_month"] = 720
    assert approx(calc.usage_hours(inp), 288)          # 144 + 144
    res = calc.compute_model("b2c", inp)
    assert approx(res["gross"], 8640)                  # old single-rate gross
    assert approx(res["net"], 5501.6)                  # old single-rate net
    assert approx(res["capital"], 47050)               # door count still 2


# ---------------------------------------------------------------------------
# Registry behavior: per-door scaling, undiscounted toggle, applies_to
# ---------------------------------------------------------------------------
def test_per_door_scaling_tracks_total_doors(monkeypatch):
    inp = all_defaults()
    base = calc.capital_at_risk("b2c", inp)        # 2 doors (pod2 + pod4)
    # Add two more doors by patching the pod set; total_doors reads cost_items.PODS.
    extra = [
        {"key": "podX", "label": "x", "doors": 1, "rate_key": "pod2_hourly_rate",
         "util_key": "pod2_utilization_pct", "bookable_key": "pod2_bookable_hours_per_month"},
        {"key": "podY", "label": "y", "doors": 1, "rate_key": "pod2_hourly_rate",
         "util_key": "pod2_utilization_pct", "bookable_key": "pod2_bookable_hours_per_month"},
    ]
    monkeypatch.setattr(cost_items, "PODS", cost_items.PODS + extra)
    bumped = calc.capital_at_risk("b2c", inp)
    # two extra doors × $400 smart lock = +$800 in capital
    assert approx(bumped - base, 800)


def test_undiscounted_toggle_raises_capital():
    inp = all_defaults()
    base = calc.capital_at_risk("b2c", inp)
    inp["use_undiscounted"] = True
    assert approx(calc.capital_at_risk("b2c", inp) - base, 88000 - 44000)


def test_capex_excludes_venue_buys():
    """No capex item applies to venue_buys, so its capital is exactly 0."""
    inp = all_defaults()
    assert calc.capital_at_risk("venue_buys", inp) == 0


# ---------------------------------------------------------------------------
# Custom cost flows through exactly like a built-in
# ---------------------------------------------------------------------------
def test_custom_cost_respects_applies_to():
    inp = all_defaults()
    custom = {
        "key": "permit_fee", "label": "Permit", "category": "opex_fixed",
        "default": 100, "per_door": False, "applies_to": ["b2c"],
    }
    inp["permit_fee"] = 100
    items = COST_ITEMS + [custom]

    # B2C opex rises by 100; B2B (not in applies_to) is unchanged.
    assert approx(calc.fixed_opex("b2c", inp, items), 1540 + 100)
    assert approx(calc.fixed_opex("b2b", inp, items), 1140)


def test_payment_processing_scales_with_utilization():
    inp = all_defaults()
    low_gross, _ = calc.pod_gross(inp)
    high_gross, _ = calc.pod_gross(inp, util_mult=2.0)   # double utilization on both pods
    low = calc.payment_processing(low_gross, inp)
    high = calc.payment_processing(high_gross, inp)
    assert approx(high, 2 * low)


# ---------------------------------------------------------------------------
# Guards: bleeds sentinel + financing
# ---------------------------------------------------------------------------
def test_payback_bleeds_when_net_nonpositive():
    inp = all_defaults()
    inp["monthly_subscription_price"] = 500   # below the 1140 opex → net negative
    res = calc.compute_model("b2b", inp)
    assert res["bleeds"] is True
    assert res["payback"] is None             # UI renders this as "bleeds"


def test_debt_service_known_amortization():
    # $10,000 at 1%/mo for 12 months → ~$888.49/mo (standard amortization).
    inp = {"annual_interest_rate": 0.12, "loan_term_months": 12}
    assert approx(calc.debt_service(10000, inp), 888.49, tol=0.01)


def test_debt_service_zero_rate():
    inp = {"annual_interest_rate": 0.0, "loan_term_months": 10}
    assert approx(calc.debt_service(5000, inp), 500)


def test_financing_can_flip_net_to_bleed():
    inp = all_defaults()
    inp["financing_mode"] = "debt"
    res = calc.compute_model("b2b", inp)      # net 1360 vs debt service ~1600
    assert res["is_debt"] is True
    assert res["debt_service"] > 0
    # default B2B net (1360) is below debt service on $47,050 at 14%/36mo → bleeds financed
    assert res["financed_bleeds"] is True


# ---------------------------------------------------------------------------
# Crossover sweep
# ---------------------------------------------------------------------------
def test_b2c_payback_falls_as_utilization_rises():
    inp = all_defaults()
    # The hidden utilization multiplier scales both pods. Stay above ~0.7× where
    # B2C net turns positive (below it the line bleeds → payback is None).
    xs = [1.0, 1.5, 2.0]
    series = calc.sweep(inp, COST_ITEMS, "util_multiplier", xs, ["b2c"])
    paybacks = series["b2c"]
    assert paybacks[0] > paybacks[1] > paybacks[2]   # monotonically faster


# ---------------------------------------------------------------------------
# Fleet / scaling cohort simulation
# ---------------------------------------------------------------------------
# Defaults: b2c steady net = 660.5/mo, capital = 47050/unit.
# Note on month indexing: series are 0-based and net accrues starting in the
# deploy month, so a single unit recovers in month index 71 (the 72nd month):
#   (t+1)*660.5 >= 47050  →  t+1 >= 71.23  →  t = 71.
# (Horizons widened from 24 → 120: at the honest baseline B2C no longer pays back
#  inside two years.)

def test_fleet_all_at_once_instant_ramp():
    inp = all_defaults()
    f = calc.simulate_fleet("b2c", inp, total_units=2, cadence_months=0,
                            ramp_months=1, horizon_months=120)
    assert f["deployed_units"] == 2
    assert f["live_units"][0] == 2                       # both land in month 0
    assert approx(f["monthly_net"][0], 2 * 660.5)        # full net, instant ramp
    assert approx(f["cumulative_capital"][0], 2 * 47050)  # 2x capital sunk at t0
    # Both capital and net scale 2x, so breakeven matches a single unit: month 71.
    assert f["breakeven_month"] == math.ceil(47050 / 660.5) - 1


def test_fleet_staggered_schedule_and_trough():
    inp = all_defaults()
    f = calc.simulate_fleet("b2c", inp, total_units=3, cadence_months=2,
                            ramp_months=1, horizon_months=24)
    assert f["deploy_months"] == [0, 2, 4]
    assert f["live_units"][0] == 1
    assert f["live_units"][2] == 2
    assert f["live_units"][4] == 3
    assert f["peak_funding_need"] > 0       # capital lumps outrun early net
    assert f["trough_month"] is not None


def test_fleet_venue_buys_is_capital_free():
    inp = all_defaults()
    f = calc.simulate_fleet("venue_buys", inp, total_units=5, cadence_months=1,
                            ramp_months=6, horizon_months=24)
    assert f["peak_funding_need"] == 0      # never sinks capital
    assert f["breakeven_month"] == 0        # cash-positive from the first month
    assert not f["runs_dry"]


def test_fleet_ramp_lowers_early_net_for_b2c():
    inp = all_defaults()
    f = calc.simulate_fleet("b2c", inp, total_units=1, cadence_months=0,
                            ramp_months=6, horizon_months=24)
    assert f["monthly_net"][0] < f["monthly_net"][5]    # utilization climbs
    assert approx(f["steady_state_monthly_net"], 660.5)  # full util by the end


def test_fleet_zero_units_is_safe():
    inp = all_defaults()
    f = calc.simulate_fleet("b2c", inp, total_units=0, cadence_months=2,
                            ramp_months=6, horizon_months=12)
    assert f["deployed_units"] == 0
    assert all(c == inp["available_capital"] for c in f["cash_curve"])
    assert f["peak_funding_need"] == 0
    assert f["breakeven_month"] is None


# ---------------------------------------------------------------------------
# Save / load round-trip (including a custom cost)
# ---------------------------------------------------------------------------
def test_save_load_roundtrip(tmp_path):
    inputs = all_defaults()
    inputs["pod2_utilization_pct"] = 0.33
    custom = [{
        "key": "permit_fee", "label": "Permit", "category": "opex_fixed",
        "default": 100, "per_door": False, "applies_to": ["b2c"],
    }]

    config_io.save_config("Weak Hotel Deal!", inputs, custom, configs_dir=tmp_path)
    assert "Weak Hotel Deal!" in config_io.list_configs(configs_dir=tmp_path)

    loaded_inputs, loaded_custom = config_io.load_config("Weak Hotel Deal!", configs_dir=tmp_path)
    assert loaded_inputs == inputs
    assert loaded_custom == custom


def test_config_v1_to_v2_migration():
    """An old (v1) single-rate save loads onto BOTH pods and drops the dead keys."""
    v1_state = {
        "version": 1,
        "name": "old deal",
        "inputs": {
            "blended_hourly_rate": 30,
            "utilization_pct": 0.25,
            "prime_hours_per_month": 600,
            "rooms_per_hub": 2,
            "monthly_subscription_price": 2500,   # an untouched key survives
        },
        "custom_costs": [],
    }
    inputs, _ = config_io.from_state(v1_state)

    # Old single values are mapped onto both pods.
    for p in ("pod2", "pod4"):
        assert inputs[f"{p}_hourly_rate"] == 30
        assert inputs[f"{p}_utilization_pct"] == 0.25
        assert inputs[f"{p}_bookable_hours_per_month"] == 600
    assert inputs["util_multiplier"] == 1.0
    assert inputs["monthly_subscription_price"] == 2500   # untouched

    # Dead v1 keys are gone.
    for dead in ("blended_hourly_rate", "utilization_pct",
                 "prime_hours_per_month", "rooms_per_hub"):
        assert dead not in inputs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
