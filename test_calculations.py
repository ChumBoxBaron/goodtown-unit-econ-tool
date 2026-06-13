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
from cost_items import COST_ITEMS, all_defaults
import config_io


def approx(a, b, tol=1e-6):
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)


# ---------------------------------------------------------------------------
# Hand-worked default scenario (see comments for the arithmetic)
# ---------------------------------------------------------------------------
# usage_hours = 720 * 2 * 0.20 = 288
# b2c_gross   = 288 * 30 = 8640
# venue (15%) = 1296 ; pay_proc (3.5%) = 302.4
# opex_b2c    = lock 40 + lte 50 + clean 600 + ins 150 + supp 300 + consumer 400 = 1540
# b2c_net     = 8640 - 1296 - 302.4 - 1540 = 5501.6
# capital     = hub 44000 + lock 800 + router 250 + install 2000 = 47050

def test_b2c_gross_and_net_default():
    inp = all_defaults()
    assert approx(calc.usage_hours(inp), 288)
    res = calc.compute_model("b2c", inp)
    assert approx(res["gross"], 8640)
    assert approx(res["net"], 5501.6)
    assert approx(res["capital"], 47050)
    assert approx(res["payback"], 47050 / 5501.6)
    assert approx(res["roic"], 5501.6 * 12 / 47050)


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
    # overflow = 288 - 40 = 248 hrs ; overflow_rev = 7440 ; gross = 800 + 7440 = 8240
    res = calc.compute_model("hybrid", inp)
    assert approx(res["gross"], 8240)
    # venue 0.15*7440=1116 ; pay 0.035*8240=288.4 ; opex 1540
    assert approx(res["net"], 8240 - 1116 - 288.4 - 1540)


# ---------------------------------------------------------------------------
# Registry behavior: per-door scaling, undiscounted toggle, applies_to
# ---------------------------------------------------------------------------
def test_per_door_scaling():
    inp = all_defaults()
    base = calc.capital_at_risk("b2c", inp)        # rooms=2
    inp["rooms_per_hub"] = 4
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
    low = calc.payment_processing(calc.usage_hours(inp) * inp["blended_hourly_rate"], inp)
    inp["utilization_pct"] = 0.40   # double utilization
    high = calc.payment_processing(calc.usage_hours(inp) * inp["blended_hourly_rate"], inp)
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
    xs = [0.10, 0.20, 0.40]
    series = calc.sweep(inp, COST_ITEMS, "utilization_pct", xs, ["b2c"])
    paybacks = series["b2c"]
    assert paybacks[0] > paybacks[1] > paybacks[2]   # monotonically faster


# ---------------------------------------------------------------------------
# Save / load round-trip (including a custom cost)
# ---------------------------------------------------------------------------
def test_save_load_roundtrip(tmp_path):
    inputs = all_defaults()
    inputs["utilization_pct"] = 0.33
    custom = [{
        "key": "permit_fee", "label": "Permit", "category": "opex_fixed",
        "default": 100, "per_door": False, "applies_to": ["b2c"],
    }]

    config_io.save_config("Weak Hotel Deal!", inputs, custom, configs_dir=tmp_path)
    assert "Weak Hotel Deal!" in config_io.list_configs(configs_dir=tmp_path)

    loaded_inputs, loaded_custom = config_io.load_config("Weak Hotel Deal!", configs_dir=tmp_path)
    assert loaded_inputs == inputs
    assert loaded_custom == custom


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
