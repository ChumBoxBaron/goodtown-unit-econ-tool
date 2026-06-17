"""
app.py — Goodtown Revenue Model Explorer (Streamlit UI).

This file is UI only. All the money math lives in calculations.py; every cost
input is defined once in cost_items.py and this file just LOOPS over that
registry to build the sidebar, so adding a cost never means editing this file.

Run:  streamlit run app.py
"""

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import config_io
from cost_items import (
    COST_ITEMS, MODELS, MODEL_KEYS, BENCHMARKS, all_defaults,
)

st.set_page_config(page_title="Goodtown Revenue Model Explorer", layout="wide")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def init_state():
    for key, value in all_defaults().items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("custom_costs", [])


def reset_defaults():
    """on_click callback: restore every input to its default and clear custom costs."""
    for c in st.session_state.get("custom_costs", []):
        st.session_state.pop(c["key"], None)
    for key, value in all_defaults().items():
        st.session_state[key] = value
    st.session_state["custom_costs"] = []


def load_scenario(name):
    """on_click callback: replace current inputs with a saved scenario."""
    inputs, custom = config_io.load_config(name)
    # clear any custom costs not present in the loaded set
    for c in st.session_state.get("custom_costs", []):
        st.session_state.pop(c["key"], None)
    for key, value in inputs.items():
        st.session_state[key] = value
    st.session_state["custom_costs"] = custom
    for c in custom:
        st.session_state[c["key"]] = inputs.get(c["key"], c.get("default", 0))


init_state()


# ---------------------------------------------------------------------------
# Small input helpers — all bind to st.session_state[key] via value=/write-back,
# so reset/load just set session_state and the widgets follow on the next run.
# ---------------------------------------------------------------------------
def num(label, key, **kw):
    out = st.number_input(label, value=float(st.session_state[key]), **kw)
    st.session_state[key] = out
    return out


def int_num(label, key, **kw):
    out = st.number_input(label, value=int(st.session_state[key]), step=1, **kw)
    st.session_state[key] = int(out)
    return int(out)


def pct_slider(label, key, lo, hi, step, help=None):
    """Slider in percent points; session_state[key] stays a fraction (0.20)."""
    cur = float(st.session_state[key]) * 100
    out = st.slider(label, float(lo), float(hi), cur, step=float(step), help=help, format="%.1f%%")
    st.session_state[key] = out / 100
    return out / 100


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Assumptions")

    # --- The three load-bearing sliders, front and center ---
    st.subheader("The 3 numbers that decide everything")
    pct_slider("Utilization %", "utilization_pct", 5, 60, 1,
               help="THE B2C lever — unvalidated. ~10% weak location, ~20% base, "
                    "~35%+ strong. Validate this with real booking data.")
    num("Monthly subscription price ($)", "monthly_subscription_price",
        min_value=1000.0, max_value=9000.0, step=100.0,
        help="THE B2B lever = venue's willingness-to-pay. " + BENCHMARKS["Throne"])
    pct_slider("Annual interest rate %", "annual_interest_rate", 6, 25, 0.5,
               help="Cost of capital for debt-financed deployment. Asset-backed "
                    "financing only works above a viability threshold (see banner).")

    # --- Unit economics ---
    with st.expander("Unit economics (shared)"):
        int_num("Rooms per hub", "rooms_per_hub", min_value=1, max_value=6,
                help="2 = a 2-person + 4-person room sharing a wall. Drives per-door costs.")
        num("Prime hours / room / month", "prime_hours_per_month",
            min_value=0.0, max_value=720.0, step=10.0,
            help="Bookable prime hours per room per month. 720 ≈ 24/day (generous).")
        num("Blended hourly rate ($)", "blended_hourly_rate",
            min_value=5.0, max_value=120.0, step=1.0,
            help="ALCOVE benchmark: $18/hr single-occupancy. Goodtown's 2- and "
                 "4-person rooms justify higher.")

    # --- Cost build-up: the registry-driven section ---
    with st.expander("Cost build-up (capex + opex line items)"):
        st.caption("Capital at risk (one-time, per unit)")
        for item in [i for i in COST_ITEMS if i["category"] == "capex"]:
            suffix = " ×doors" if item.get("per_door") else ""
            num(item["label"] + suffix, item["key"],
                min_value=float(item["min"]), max_value=float(item["max"]),
                step=float(item["step"]), help=item["help"])

        st.checkbox("Use undiscounted hub ($88k) — models discount erosion",
                    key="use_undiscounted",
                    help=BENCHMARKS["Goodtown_unit"])

        st.caption("Monthly opex (recurring)")
        for item in [i for i in COST_ITEMS if i["category"] == "opex_fixed"]:
            suffix = " ×doors" if item.get("per_door") else ""
            num(item["label"] + suffix, item["key"],
                min_value=float(item["min"]), max_value=float(item["max"]),
                step=float(item["step"]), help=item["help"])

        # Custom costs (runtime extensibility) ---------------------------------
        if st.session_state["custom_costs"]:
            st.caption("Custom costs")
        for c in list(st.session_state["custom_costs"]):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.session_state.setdefault(c["key"], c.get("default", 0))
                num(f"{c['label']} ({c['category'].replace('opex_fixed','opex')})", c["key"],
                    min_value=0.0, max_value=1_000_000.0, step=10.0,
                    help=f"Custom cost · applies to: {', '.join(c['applies_to'])}")
            with col2:
                st.write("")
                if st.button("✕", key=f"rm_{c['key']}", help="Remove this custom cost"):
                    st.session_state["custom_costs"] = [
                        x for x in st.session_state["custom_costs"] if x["key"] != c["key"]
                    ]
                    st.session_state.pop(c["key"], None)
                    st.rerun()

        with st.form("add_custom_cost", clear_on_submit=True):
            st.caption("➕ Add a cost we didn't foresee")
            cname = st.text_input("Name", placeholder="e.g. Municipal permit")
            camount = st.number_input("Amount ($)", min_value=0.0, value=100.0, step=10.0)
            ccat = st.radio("Type", ["opex_fixed", "capex"],
                            format_func=lambda x: "Recurring opex" if x == "opex_fixed" else "One-time capex",
                            horizontal=True)
            cper_door = st.checkbox("Per door (×rooms_per_hub)")
            capplies = st.multiselect("Applies to models", MODEL_KEYS, default=MODEL_KEYS)
            if st.form_submit_button("Add cost") and cname.strip() and capplies:
                base = config_io._slug(cname)
                key = base
                i = 1
                existing = {x["key"] for x in st.session_state["custom_costs"]} | set(all_defaults())
                while key in existing:
                    i += 1
                    key = f"{base}-{i}"
                st.session_state["custom_costs"].append({
                    "key": key, "label": cname.strip(), "category": ccat,
                    "default": camount, "per_door": cper_door, "applies_to": capplies,
                })
                st.session_state[key] = camount
                st.rerun()

    # --- Venue + pricing levers ---
    with st.expander("Venue & pricing"):
        st.radio("Venue charge structure", ["rev_share", "rent"], key="venue_charge_mode",
                 format_func=lambda x: "Rev-share (% of gross)" if x == "rev_share" else "Flat monthly rent",
                 help="The primer says venue deals are rev-share OR small-footprint rent — "
                      "not both. Flat rent is the likely hotel/B2B structure.")
        if st.session_state["venue_charge_mode"] == "rev_share":
            pct_slider("Venue rev-share % (B2C)", "venue_rev_share_pct", 0, 40, 1)
            pct_slider("Venue rev-share % on overflow (hybrid)",
                       "venue_rev_share_pct_on_overflow", 0, 40, 1)
        else:
            num("Flat monthly rent ($)", "flat_rent", min_value=0.0, max_value=10000.0, step=100.0)
        pct_slider("Payment processing % (of gross)", "payment_proc_pct", 0, 8, 0.1,
                   help="Scales with revenue, not flat — so it bites hardest exactly where "
                        "B2C is supposed to win.")
        num("Venue-buys service fee ($/mo)", "service_fee_venue_buys",
            min_value=300.0, max_value=2500.0, step=50.0)
        num("Hybrid base fee ($/mo)", "base_fee_hybrid",
            min_value=0.0, max_value=5000.0, step=50.0)
        num("Hybrid overflow cap (hours included)", "overflow_cap_hours",
            min_value=0.0, max_value=400.0, step=5.0)

    # --- Capital & financing ---
    with st.expander("Capital & financing"):
        st.radio("Financing mode", ["equity", "debt"], key="financing_mode",
                 format_func=lambda x: "Equity (cash)" if x == "equity" else "Debt-financed",
                 horizontal=True)
        int_num("Loan term (months)", "loan_term_months", min_value=6, max_value=84)
        int_num("Target unit count to deploy", "target_unit_count", min_value=1, max_value=50)
        num("Available capital ($)", "available_capital",
            min_value=0.0, max_value=5_000_000.0, step=10000.0,
            help="Deployable cash. Drives 'units you can self-fund'.")

    # --- Fleet / scaling projection ---
    with st.expander("Fleet / scaling projection"):
        st.caption(
            "Replicate the hero SKU across locations, deployed gradually. Uses "
            "**Target unit count** and **Available capital** from *Capital & financing*."
        )
        int_num("Cadence — months between deployments", "fleet_cadence_months",
                min_value=0, max_value=12,
                help="0 = deploy all units at once (steady-state read). 2 = a new unit "
                     "every 2 months. This is a tunable what-if, not a forecast.")
        int_num("Utilization ramp (months)", "fleet_ramp_months",
                min_value=1, max_value=24,
                help="Each new location climbs from ~0 to the utilization slider over "
                     "this many months. Affects usage-based models only (B2C, hybrid) — "
                     "B2B / venue-buys earn full net from month one.")
        int_num("Projection horizon (months)", "fleet_horizon_months",
                min_value=6, max_value=120,
                help="How far out to simulate. Units scheduled past the horizon are dropped.")

    # --- Scenarios + reset ---
    with st.expander("Scenarios (save / load)"):
        save_name = st.text_input("Save current as…", placeholder="weak hotel deal")
        if st.button("💾 Save scenario") and save_name.strip():
            inputs = {k: st.session_state[k] for k in all_defaults()}
            for c in st.session_state["custom_costs"]:
                inputs[c["key"]] = st.session_state.get(c["key"], c.get("default", 0))
            config_io.save_config(save_name, inputs, st.session_state["custom_costs"])
            st.success(f"Saved '{save_name}'.")
        saved = config_io.list_configs()
        if saved:
            chosen = st.selectbox("Load scenario", saved)
            st.button("📂 Load", on_click=load_scenario, args=(chosen,))

    st.button("↩︎ Reset to defaults", on_click=reset_defaults)


# ---------------------------------------------------------------------------
# Build the input dict + effective item list, then compute every model
# ---------------------------------------------------------------------------
inputs = {k: st.session_state[k] for k in all_defaults()}
for c in st.session_state["custom_costs"]:
    inputs[c["key"]] = st.session_state.get(c["key"], c.get("default", 0))
items = COST_ITEMS + st.session_state["custom_costs"]

results = calc.compute_all(inputs, items, MODEL_KEYS)
is_debt = inputs["financing_mode"] == "debt"
label_of = {m["key"]: m["label"] for m in MODELS}


def effective_payback(res):
    return res["financed_payback"] if (is_debt and res["is_debt"]) else res["payback"]


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Goodtown Revenue Model Explorer.")
st.caption(
    "Push your assumptions through all four revenue models at once. The whole point: "
    "watch the **model ranking flip** as utilization, subscription price, and cost of "
    "capital move — and never lose sight of **capital-at-risk**, the number that kills a "
    "2-person team."
)

# ---------------------------------------------------------------------------
# 3a. Per-unit comparison table
# ---------------------------------------------------------------------------
st.subheader("Per-unit comparison")

rows = []
for k in MODEL_KEYS:
    r = results[k]
    pb = effective_payback(r)
    rows.append({
        "Model": label_of[k],
        "Monthly gross": r["gross"],
        "Monthly net": r["financed_net"] if (is_debt and r["is_debt"]) else r["net"],
        "Capital at risk": r["capital"],
        "Payback (mo)": math.nan if pb is None else pb,
        "Annual ROIC": math.nan if r["roic"] is None else r["roic"],
    })
df = pd.DataFrame(rows).set_index("Model")


def color_payback(v):
    if pd.isna(v):
        return "background-color: #f8d7da; color: #842029"   # bleeds → red
    if v < 12:
        return "background-color: #d1e7dd; color: #0f5132"   # green
    if v <= 24:
        return "background-color: #fff3cd; color: #664d03"   # yellow
    return "background-color: #f8d7da; color: #842029"        # red


styler = (
    df.style
    .format({"Monthly gross": "${:,.0f}", "Monthly net": "${:,.0f}",
             "Capital at risk": "${:,.0f}", "Payback (mo)": "{:,.1f}",
             "Annual ROIC": "{:.0%}"}, na_rep="bleeds")
    .map(color_payback, subset=["Payback (mo)"])
)
st.dataframe(styler, width="stretch")
st.caption(
    f"Payback shown on {'**debt-financed** net (after debt service)' if is_debt else '**equity** net'}. "
    "Green <12mo · Yellow 12–24mo · Red >24mo or bleeds. Venue-buys is capital-free, so its "
    "payback is instant and ROIC is undefined — that empty capital column *is* the argument for it."
)

# ---------------------------------------------------------------------------
# 3b. Crossover chart
# ---------------------------------------------------------------------------
st.subheader("Crossover: where the winner flips")
x_axis = st.radio("Sweep the X axis by:", ["Utilization", "Subscription price"], horizontal=True)

if x_axis == "Utilization":
    xs = [round(0.05 + 0.01 * i, 2) for i in range(56)]   # 5% … 60%
    sweep_key = "utilization_pct"
    x_plot = [x * 100 for x in xs]
    x_title = "Utilization (%)"
    fmt_cross = lambda x: f"{x*100:.0f}%"
else:
    xs = list(range(1000, 9001, 250))
    sweep_key = "monthly_subscription_price"
    x_plot = xs
    x_title = "Monthly subscription price ($)"
    fmt_cross = lambda x: f"${x:,.0f}"

series = calc.sweep(inputs, items, sweep_key, xs, MODEL_KEYS, financed=is_debt)

fig = go.Figure()
for k in MODEL_KEYS:
    fig.add_trace(go.Scatter(x=x_plot, y=series[k], mode="lines", name=label_of[k],
                             connectgaps=False))
# annotate the B2C × B2B crossover — the headline decision point
cross = calc.find_crossover(xs, series["b2c"], series["b2b"])
if cross is not None:
    cx = cross * 100 if x_axis == "Utilization" else cross
    fig.add_vline(x=cx, line_dash="dash", line_color="gray")
    fig.add_annotation(x=cx, y=0, yshift=10,
                       text=f"B2C overtakes B2B at {fmt_cross(cross)}",
                       showarrow=False, font=dict(color="gray"))
fig.update_layout(xaxis_title=x_title, yaxis_title="Payback (months)",
                  yaxis_range=[0, 60], legend_title="Model", height=430,
                  margin=dict(t=20))
st.plotly_chart(fig, width="stretch")
st.caption(
    "Flat lines are utilization-independent (B2B / venue-buys). The steep line is B2C — its "
    "payback collapses as utilization rises. Below the crossover, B2B wins; above it, B2C wins. "
    "Lines break where a model bleeds (no payback)."
)

# ---------------------------------------------------------------------------
# 3c. Capital-to-scale panel
# ---------------------------------------------------------------------------
st.subheader("Capital to scale")
sel_label = st.selectbox("Model to scale", [label_of[k] for k in MODEL_KEYS])
sel_key = next(k for k in MODEL_KEYS if label_of[k] == sel_label)
sel = results[sel_key]
cap = sel["capital"]
N = inputs["target_unit_count"]

c1, c2, c3 = st.columns(3)
c1.metric(f"Capital to deploy {N} units", f"${cap * N:,.0f}")
if cap <= 0:
    c2.metric("Units you can self-fund", "∞", help="Venue-buys ties up ~no Goodtown capital.")
else:
    c2.metric("Units you can self-fund", f"{math.floor(inputs['available_capital'] / cap):,}")
pb = effective_payback(sel)
c3.metric("Months to recover deployment", "bleeds" if pb is None else f"{pb:,.1f}")

# Capital-tied-up bar: the visual gap is the argument for venue-pays
owned_cap = results["b2c"]["capital"] * N
vb_cap = results["venue_buys"]["capital"] * N
bar = go.Figure(go.Bar(
    x=["Goodtown-owned (B2C/B2B)", "Venue-buys"],
    y=[owned_cap, vb_cap],
    text=[f"${owned_cap:,.0f}", f"${vb_cap:,.0f}"], textposition="outside",
    marker_color=["#c1432f", "#2f7dc1"],
))
bar.update_layout(yaxis_title=f"Capital tied up at {N} units", height=320, margin=dict(t=20))
st.plotly_chart(bar, width="stretch")

# ---------------------------------------------------------------------------
# 3d. Fleet economics over time (staggered deployment + utilization ramp)
# ---------------------------------------------------------------------------
st.subheader("Fleet economics over time")
fleet_label = st.selectbox("Model to project", [label_of[k] for k in MODEL_KEYS],
                           key="fleet_model")
fleet_key = next(k for k in MODEL_KEYS if label_of[k] == fleet_label)

fleet = calc.simulate_fleet(
    fleet_key, inputs, items,
    total_units=inputs["target_unit_count"],
    cadence_months=inputs["fleet_cadence_months"],
    ramp_months=inputs["fleet_ramp_months"],
    horizon_months=inputs["fleet_horizon_months"],
)

if is_debt:
    st.info(
        "Fleet view is shown on an **equity basis** — capital is paid from cash at each "
        "deployment. Per-cohort debt amortization isn't modeled here yet (the per-unit "
        "table above does reflect your debt toggle)."
    )

cadence = inputs["fleet_cadence_months"]
schedule_txt = "all at once" if cadence == 0 else f"one every {cadence} mo"
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Peak funding need", f"${fleet['peak_funding_need']:,.0f}",
          help="Deepest the running cash position goes below zero — the most capital "
               "tied up at once on this schedule. The number that decides if you survive.")
m2.metric("Cash trough month",
          "—" if fleet["trough_month"] is None else f"M{fleet['trough_month']}")
m3.metric("Breakeven month",
          "never" if fleet["breakeven_month"] is None else f"M{fleet['breakeven_month']}",
          help="First month cumulative net cash repays cumulative capital deployed.")
m4.metric("Steady-state net (all live)",
          f"${fleet['steady_state_monthly_net'] * fleet['deployed_units']:,.0f}/mo")
m5.metric("Outside capital needed", f"${fleet['outside_capital_needed']:,.0f}",
          help=f"Peak funding need minus your available capital "
               f"(${inputs['available_capital']:,.0f}).")

if fleet["deployed_units"] < fleet["requested_units"]:
    st.warning(
        f"Only **{fleet['deployed_units']} of {fleet['requested_units']}** units fit in the "
        f"{inputs['fleet_horizon_months']}-month horizon at this cadence. Extend the horizon "
        f"or tighten the cadence to see the full fleet."
    )
if fleet["runs_dry"]:
    st.error(
        f"⚠️ **Cash goes negative at M{fleet['dry_month']}** — at {schedule_txt}, deployments "
        f"outrun your ${inputs['available_capital']:,.0f} of capital. Slow the cadence, raise "
        f"capital, or pick a lower-capital model."
    )

mo = fleet["months"]
# Chart A: the cash story — capital sunk (step) vs running balance, trough marked.
figA = go.Figure()
figA.add_trace(go.Scatter(x=mo, y=fleet["cumulative_capital"], name="Cumulative capital deployed",
                          mode="lines", line_shape="hv", line=dict(color="#c1432f")))
figA.add_trace(go.Scatter(x=mo, y=fleet["cash_curve"], name="Running cash balance",
                          mode="lines", line=dict(color="#2f7dc1")))
figA.add_hline(y=0, line_dash="dash", line_color="gray")
if fleet["trough_month"] is not None:
    figA.add_vline(x=fleet["trough_month"], line_dash="dot", line_color="#c1432f")
    figA.add_annotation(x=fleet["trough_month"], y=0, yshift=-10,
                        text=f"trough M{fleet['trough_month']}",
                        showarrow=False, font=dict(color="#c1432f"))
figA.update_layout(xaxis_title="Month", yaxis_title="$", legend_title=None,
                   height=400, margin=dict(t=20),
                   legend=dict(orientation="h", yanchor="bottom", y=1.02))
st.plotly_chart(figA, width="stretch")

# Chart B: the flywheel building — live units (step) vs portfolio net run-rate.
figB = go.Figure()
figB.add_trace(go.Scatter(x=mo, y=fleet["monthly_net"], name="Portfolio net / mo",
                          mode="lines", line=dict(color="#2f7dc1")))
figB.add_trace(go.Scatter(x=mo, y=fleet["live_units"], name="Live units",
                          mode="lines", line_shape="hv", line=dict(color="#888"), yaxis="y2"))
figB.update_layout(xaxis_title="Month", yaxis_title="Portfolio net ($/mo)",
                   yaxis2=dict(title="Live units", overlaying="y", side="right",
                               rangemode="tozero", showgrid=False),
                   height=360, margin=dict(t=20),
                   legend=dict(orientation="h", yanchor="bottom", y=1.02))
st.plotly_chart(figB, width="stretch")
st.caption(
    "Capital is paid from cash at each deployment (equity basis). The **ramp** affects "
    "usage-based models only (B2C, hybrid overflow); B2B / venue-buys earn full net from "
    "month one. Breakeven is the *first* month cumulative net repays cumulative capital — "
    "with staggered deployment the cash curve can dip again after a later unit lands."
)

# ---------------------------------------------------------------------------
# 3e. Financing viability banner
# ---------------------------------------------------------------------------
if is_debt:
    bleeders = [label_of[k] for k in MODEL_KEYS if results[k]["financed_bleeds"]]
    if bleeders:
        ds = calc.debt_service(results["b2b"]["capital"], inputs)
        st.error(
            f"⚠️ **Financing bleeds cash** for: {', '.join(bleeders)}. At this price/utilization "
            f"the signed contract can't service its own debt (monthly debt service ≈ ${ds:,.0f} on "
            f"${results['b2b']['capital']:,.0f} of capital). Raise the price, raise utilization, or "
            f"go equity-only. This is the finding that asset-backed financing only works above a "
            f"viability threshold."
        )

# ---------------------------------------------------------------------------
# 3f. Honest-assumptions footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "**Findings (real-world anchors):** Throne $4,250–9,000/unit/mo · ALCOVE $18/hr · "
    "Goodtown hub ~$44k discounted / ~$88k undiscounted · Jabbrrbox $15/30min.  \n"
    "**Assumptions (tuned guesses — validate before trusting):** utilization, venue "
    "willingness-to-pay (subscription price), all opex line items, install cost, insurance. "
    "Don't mistake a slider for data."
)
