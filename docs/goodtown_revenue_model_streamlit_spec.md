# Goodtown Revenue Model Explorer — Streamlit App Spec

> **What this is.** A design spec for a Streamlit app that lets you push assumptions through Goodtown's competing revenue models (B2C, B2B-owned, venue-buys, base+overflow) and see payback, capital-at-risk, and breakeven side by side. Built to be picked up cold in Cursor. The point of the app is that almost every conclusion in the business-model analysis hinges on inputs we had to *assume* — utilization and willingness-to-pay especially. This makes those inputs tunable instead of buried.

---

## 0. Why this exists (the modeling thesis)

The B2C-vs-B2B decision is not really a strategy question — it's a question about three numbers we don't yet know empirically:

1. **Utilization** (B2C upside lives or dies here)
2. **Monthly willingness-to-pay** of a venue for the amenity (B2B/venue-pays lives or dies here)
3. **Cost of capital / financing availability** (determines whether asset-heavy subscription is survivable for a 2-person team)

The app's job: make those three the primary sliders, and show how the model ranking *flips* as they move. A static table hides the flip. The whole value is seeing the crossover points.

**Key insight to preserve in the UI:** Throne (the B2B comparable) absorbs unit capital and funds it with $15M+ of VC. Goodtown cannot. So the app must always surface **capital-at-risk per deployment** and **total capital required to reach N units**, not just monthly margin — because the thing that kills a 2-person team is running out of cash deploying units, not thin per-unit margin.

---

## 1. Models to compare (the four columns)

| Model | Who owns the unit | Goodtown capital/unit | Revenue to Goodtown | Demand risk |
|---|---|---|---|---|
| **B2C pay-per-use** | Goodtown | Full unit cost | Usage × price × utilization − opex − venue rev-share | On Goodtown |
| **B2B subscription (Goodtown-owned)** | Goodtown | Full unit cost | Fixed monthly sub − opex | On venue |
| **Venue-buys + service** | Venue | ~$0 | Recurring service/software fee | On venue |
| **Base + overflow (hybrid)** | Goodtown | Full unit cost | Base fee + (overflow usage × price) − opex | Shared |

The app computes all four from a shared set of inputs so they're directly comparable on the same assumptions.

---

## 2. Inputs (sidebar sliders + number inputs)

Group these in the sidebar with `st.expander` sections.

### Unit economics (shared)
- `unit_cost` — landed cost per hub. Default **47000**. Range 30k–95k. *(Note in help text: ~$44k Mute discounted; ~$88k undiscounted. Add a checkbox "Use undiscounted ($88k)" that overrides — this models discount-erosion risk directly.)*
- `rooms_per_hub` — default **2** (2-person + 4-person sharing a wall).
- `prime_hours_per_month` — bookable prime hours per room/month. Default **720** (≈ 24 prime hrs/day, generous; let user dial down).
- `monthly_opex_b2c` — cleaning, connectivity, payment processing, support. Default **1500**.
- `monthly_opex_b2b` — lighter (no consumer payment friction/marketing). Default **700**.

### B2C levers
- `utilization_pct` — **THE key B2C slider.** Default **20%**. Range 5%–60%. Big, prominent. Help text: "Unvalidated. ~10% = weak location, ~20% = base, ~35%+ = strong. This is the number to validate with real booking data."
- `blended_hourly_rate` — default **30**. (ALCOVE benchmark: $18/hr single-occupancy in 2025; Goodtown's 2- and 4-person rooms justify higher. Cite in help text.)
- `venue_rev_share_pct` — share of B2C gross paid to venue. Default **15%**.

### B2B / venue-pays levers
- `monthly_subscription_price` — **THE key B2B slider.** Default **2500**. Range 1000–9000. Help text: "Venue's willingness-to-pay for the amenity. Throne charges cities $4,250–$9,000/unit/mo, but that buyer compares to a $500k–$2M permanent restroom. A hotel/retail venue comparing to 'a meeting room they sort of have' will pay far less. Don't anchor to Throne."
- `service_fee_venue_buys` — recurring fee when the venue owns the unit. Default **1000**. Range 300–2500.
- `base_fee_hybrid` — recurring floor in base+overflow. Default **800**.
- `overflow_cap_hours` — usage hours included before overflow billing. Default **40**.

### Capital & financing (this is the section that usually gets skipped — don't)
- `financing_mode` — radio: **Equity (cash)** | **Debt-financed**.
- `annual_interest_rate` — default **14%**. Range 6%–25%. (Asset-backed/equipment financing against a signed contract; only available above a viability threshold — see §4.)
- `loan_term_months` — default **36**.
- `target_unit_count` — how many hubs to model deploying. Default **5**. Range 1–50. Drives the "total capital required" output.
- `available_capital` — Goodtown's deployable cash. Default **150000**. Used to compute "how many units can you self-fund before you're out of runway."

---

## 3. Outputs (main panel)

### 3a. Per-unit comparison table (top, always visible)
One row per model, columns:
- Monthly gross revenue to Goodtown
- Monthly net (after opex, rev-share, financing if applicable)
- **Capital at risk per unit** (unit_cost if Goodtown owns, ~0 if venue buys)
- **Payback period (months)** = capital_at_risk / monthly_net (— or "bleeds" if net ≤ debt service)
- **Simple annual ROIC** = (monthly_net × 12) / capital_at_risk

Color-code payback: green < 12mo, yellow 12–24mo, red > 24mo or negative. The red cells are the story.

### 3b. The crossover chart (the centerpiece)
A line chart with **utilization on the X axis** (5%–60%) and **payback period (months) on the Y axis**, one line per model. The B2C line slopes steeply (payback collapses as utilization rises); the B2B/venue-pays lines are flat (utilization-independent). The **intersection points** are the decision: below the crossover, B2B wins; above it, B2C wins. Annotate the crossover utilization value.

Add a second toggle to swap the X axis to **subscription price** instead of utilization, holding utilization fixed — shows the mirror-image crossover from the B2B side.

### 3c. Capital-to-scale panel
- "**Total capital required to deploy N units**" = target_unit_count × capital_at_risk (per selected model).
- "**Units you can self-fund**" = floor(available_capital / capital_at_risk). Display prominently. For venue-buys this is effectively unbounded (flag as "capital-unconstrained").
- "**Months to recover full deployment**" under equity vs debt.
- A small bar: capital tied up at N units, B2C/B2B-owned vs venue-buys side by side. The visual gap *is* the argument for venue-pays.

### 3d. Financing viability flag
Compute monthly debt service for a unit_cost loan at the given rate/term. If `monthly_net < debt_service`, show a red banner: **"At this price/utilization, financing bleeds cash — the signed contract can't service its own debt. Equity-only or raise the price."** This directly encodes the finding that asset-backed financing only works above ~$2,300/unit/mo.

### 3e. Honest-assumptions footer
Persistent caption listing which numbers are *findings* (Throne pricing, ALCOVE $18/hr, unit cost) vs *assumptions* (utilization, venue WTP, opex). Don't let the user mistake a tuned guess for data.

---

## 4. Calculation reference (so it's unambiguous in Cursor)

```
# B2C
b2c_gross   = prime_hours_per_month * rooms_per_hub * utilization_pct * blended_hourly_rate
b2c_net     = b2c_gross * (1 - venue_rev_share_pct) - monthly_opex_b2c

# B2B subscription (Goodtown owns)
b2b_net     = monthly_subscription_price - monthly_opex_b2b

# Venue-buys + service (Goodtown owns ~nothing)
vb_net      = service_fee_venue_buys - (monthly_opex_b2b * 0.5)  # lighter still; venue may cover some opex — make this a toggle

# Base + overflow
overflow_hours = max(0, prime_hours_per_month * rooms_per_hub * utilization_pct - overflow_cap_hours)
hybrid_gross   = base_fee_hybrid + overflow_hours * blended_hourly_rate
hybrid_net     = hybrid_gross * (1 - venue_rev_share_pct_on_overflow) - monthly_opex_b2c

# Financing
monthly_rate   = annual_interest_rate / 12
debt_service   = unit_cost * (monthly_rate * (1+monthly_rate)**loan_term_months) / ((1+monthly_rate)**loan_term_months - 1)

# Payback (equity)
payback_months = capital_at_risk / monthly_net   # guard div-by-zero and negative net

# Payback (financed) — net after debt service; if positive, capital recovered over loan term + residual
financed_net   = monthly_net - debt_service
```

Guard every division. Render "bleeds" / "∞" rather than a number when `monthly_net <= 0` (equity) or `financed_net <= 0` (debt).

---

## 5. Benchmark data to hardcode as reference annotations (from primary sources)

Bake these into help text / tooltips so the user always sees the real-world anchors next to their sliders:

- **ALCOVE** (closest direct comparable; premium private pods): **$18/hr** single-occupancy standard rate, 15-min minimum, membership + hour-package tiers, app-based keyless access. 5 locations, **4 of 5 inside hotels** (Hilton Brooklyn, Claremont, Hyatt Regency Lake Washington, Fairmont SF). Scaled via hotel **management-company** partners (HHM, HEI, Ohana, Amex FHR).
- **Throne Labs** (B2B subscription comparable): **$4,250–$9,000 per unit/month**, 10-unit minimum at steady state; pilots run higher per-unit (Berkeley: $70k / 2 units / 4 months → $8,750/unit/mo; Long Beach: $99,200 / 4-month pilot). Pilot → multi-year conversion (Ann Arbor: 12-mo pilot → 5-yr). **No upfront capital to buyer; Throne absorbs unit cost, funded by $15M+ Series B + manufacturer (Satellite Industries) on cap table.** Deployment speed ~6 weeks signed-to-live.
- **Jabbrrbox** (airport pods): **$15 / 30 min** B2C; scaled by becoming the hardware+tech layer for partners (MAG USA/Escape Lounges; IWG/Regus 3,750-unit deal) rather than operating venues solo.
- **Goodtown unit**: ~**$44k** landed/hub discounted (Mute Modular), ~**$88k** undiscounted; excludes smart lock, LTE modem, ops.

---

## 6. Build notes / stack

- Single-file `app.py`, `streamlit run app.py`. Deps: `streamlit`, `pandas`, `plotly` (or `altair`).
- Use `st.session_state` to persist slider values across reruns.
- Put the four-model table at top, crossover chart center, capital-to-scale panel below. Sidebar = all inputs.
- No external data calls — fully offline, all benchmarks hardcoded as constants in a `BENCHMARKS` dict.
- Add a "Reset to defaults" button.
- Optional v2: a "Scenario compare" mode that snapshots two slider configurations side by side (e.g., "weak hotel deal" vs "strong hospital deal").

---

## 7. Future ideation (pick up later, not v1)

- **Plug in real Switchyards booking data** to replace the `utilization_pct` slider with an empirical distribution — this is the single highest-value upgrade, since utilization is the most load-bearing assumption. Let the app read a CSV of scraped bookings and derive the utilization range directly.
- **Sensitivity tornado chart**: rank inputs by how much they swing the model ranking. Almost certainly utilization and subscription_price dominate; proving that visually focuses the validation effort.
- **Portfolio mode**: model a *mix* (e.g., 2 hotel venue-pays + 1 retail base+overflow) and show blended capital-at-risk and runway impact — directly answers "focus vs portfolio."
- **Monte Carlo on utilization**: distribution of payback outcomes rather than point estimates, since the B2C downside variance is the real risk.
- **Discount-erosion timeline**: model unit_cost rising from $44k toward $88k over time and show how the deploy-now vs wait decision shifts.
- **CAC + sales-cycle layer**: add cost-per-contract and months-to-close per model; the venue-pays/B2B path has a longer, costlier sales cycle that per-unit margin hides. This is where the "2-person team can't run two motions" constraint becomes quantitative.

---

> **Note on this copy:** reproduced into the project from the original spec shared at kickoff,
> with encoding artifacts cleaned up. The app as built deliberately departs from this spec in a
> few places (itemized capital-at-risk instead of a single `unit_cost`; payment processing as a
> % of revenue; a venue rev-share-vs-rent toggle; insurance as its own line item; B2B opex as an
> emergent result of `applies_to` rather than two lump-sum numbers). See `README.md` for the
> as-built design and rationale.
