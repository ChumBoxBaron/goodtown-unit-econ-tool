# Goodtown Revenue Model Explorer

An interactive tool that pushes your assumptions through Goodtown's four competing
revenue models at once — **B2C pay-per-use**, **B2B subscription**, **venue-buys + service**,
and **base + overflow hybrid** — and shows payback, capital-at-risk, and breakeven side by
side on the *same* assumptions.

The point isn't a static table. It's watching the **model ranking flip** as the
numbers we can't yet measure move:

1. **Per-pod utilization** — B2C lives or dies here. The hub is two rooms (a 2-person pod and
   a 4-person pod), each with its own rate and utilization, so revenue is summed per pod.
2. **Venue willingness-to-pay** (subscription price) — B2B lives or dies here.
3. **Cost of capital** — decides whether asset-heavy subscription is survivable for a 2-person team.

And it always surfaces **capital-at-risk per unit** and **total capital to reach N units** —
because the thing that kills a 2-person team is running out of cash deploying units, not thin
per-unit margin.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
streamlit run app.py
```

Run the math tests:

```bash
python -m pytest test_calculations.py -v
```

## How it's built

| File | What it holds |
|---|---|
| `app.py` | Streamlit UI **only**. Loops over the cost registry to build inputs; renders the table, the break-even heatmap + contribution waterfall (with the crossover chart kept as a secondary line view), capital panel, banners, and scenario save/load. |
| `calculations.py` | The financial math as **pure functions** (no Streamlit). Testable in isolation, so we trust the numbers before the charts. |
| `cost_items.py` | The **single source of truth** for every input: the `COST_ITEMS` registry, the `PODS` structure (2-person + 4-person rooms), the headline/non-registry defaults, and the real-world `BENCHMARKS`. |
| `config_io.py` | Save/load named scenarios to `configs/*.json` (Streamlit-free, so the round-trip is unit-tested). |
| `test_calculations.py` | Hand-worked assertions on the math, registry sums, custom costs, and save/load. |

## Adding a new cost variable

This is the whole reason the tool is structured around a registry. **Two ways:**

**1. In the app, no code (for one-off / unforeseen costs):** open *Cost build-up → ➕ Add a
cost we didn't foresee*, give it a name, amount, capex/opex, and which models it applies to.
It immediately flows into capital-at-risk / opex, the table, and the charts — and it's saved
with your scenario.

**2. In code (to ship a new built-in cost):** add one dict to `COST_ITEMS` in `cost_items.py`:

```python
{"key": "permit_fee", "label": "Municipal permit", "category": "opex_fixed",
 "default": 120, "min": 0, "max": 1000, "step": 10, "per_door": False,
 "applies_to": ["b2c", "b2b", "hybrid"], "help": "Monthly permit cost."}
```

That's it — no edits to `app.py` or `calculations.py`. The UI, the math, and the Reset
button all loop over the registry, so there's exactly one place to change.

> **The design lesson:** the moment a variable's name has to appear in the UI *and* the math
> *and* the defaults, that duplication is the signal to make the data a list and loop over it.
> That single move turns "adding a variable is surgery" into "adding a variable is one line."

## What's modeled (and what's a guess)

**Departures from a naive model, on purpose:**

- **Two distinct pods, not N identical rooms.** A conjoined hub is physically a **2-person
  room + a 4-person room** with genuinely different pricing power. Each pod carries its own
  hourly rate, utilization, and bookable-hours capacity; hub revenue is the **sum** of per-pod
  revenue. The "blended hourly rate" is a *computed, revenue-weighted, read-only* display value
  — not an input you have to back into. Per-door capex (locks) is driven by total door count
  across pods (2 by default). Defined once in `PODS` (`cost_items.py`), looped over everywhere.
- **Honest utilization denominator.** Utilization is a share of each pod's
  `bookable_hours_per_month` — the *realistic* hours a pod can actually be booked (default 300 ≈
  10 hrs/day × 30), **not** 24/7 clock hours. That keeps "20% utilization" comparable to
  occupancy benchmarks (hotels, ALCOVE) instead of silently meaning 20% of all 720 clock hours.
- **Itemized capital-at-risk.** The Mute hub quote (~$44k) *excludes* the smart lock, LTE
  router, and install — so a hub-only `unit_cost` understates the exact number that kills a
  2-person team. We model the full capex stack (hub + lock×doors + router + install).
- **Payment processing as a % of revenue**, not a flat fee — so it bites hardest exactly where
  B2C is supposed to win (high utilization).
- **Venue charge is rev-share *or* flat rent** (a toggle), because real deals are one or the
  other; flat rent is the likely hotel/B2B structure.
- **Insurance is its own line item**, because institutional liability is the strategic crux.
- **B2B opex is lighter than B2C** as an *emergent* result: the consumer-support line only
  `applies_to` the consumer models, instead of two hand-tuned lump-sum opex numbers.
- **Debt service is computed on the full capital-at-risk**, not just the hub.

**Findings** (real-world anchors, in tooltips): Throne $4,250–9,000/unit/mo · ALCOVE $18/hr ·
hub ~$44k/$88k · Jabbrrbox $15/30min.

### Forward vs. Inverse (solve for max capex)

The per-unit comparison has two modes:

- **Forward (capex → payback)** — the default. Plug in the capex stack, read the payback
  period for each model.
- **Inverse (target payback → max capex)** — flip the question. Set a **target payback**
  (months you're willing to accept) and the tool solves for the **maximum landed hardware
  cost** that still hits it: `max_capex = monthly_net × target_payback`. It shows that ceiling
  next to our actual ~$50k landed estimate with a PASS/FAIL banner, so you can see at a glance
  whether a deal pencils. Equity-basis net only (financing isn't reflected); venue-buys is
  capital-free, so it passes at any target.

### Fleet / scaling over time

The per-unit view is a timeless snapshot. The **Fleet economics over time** section models
the real plan: a hero SKU (the 2-room hub) **replicated across locations, deployed gradually**.
It's a month-by-month cohort simulation — each unit is a cohort that deploys at some month and
earns net cash thereafter; the portfolio is the sum across live cohorts.

- **Cadence is a tunable what-if, not a forecast.** You set *months between deployments* (`0` =
  all units at once, the steady-state read) — exactly the same "we can't measure it, so make it
  a lever" stance as utilization and cost of capital. The staggered schedule is *generated*, so
  you never hand-build irregular timing.
- **Per-cohort utilization ramp.** Each new location climbs linearly to its steady-state
  per-pod utilization over *ramp months* — new venues take time to fill. (Mechanically, the ramp
  scales both pods together via a hidden utilization multiplier.) The ramp affects **usage-based
  models only** (B2C, hybrid overflow); B2B / venue-buys earn full net from month one because
  their revenue doesn't depend on utilization.
- **The headline metric is the peak cash trough** — the deepest the running cash balance goes,
  i.e. the most capital tied up at once on this schedule. That, plus "outside capital needed
  beyond your available cash" and the **breakeven month**, is the cash story that decides whether
  a 2-person team survives the scale-up.
- **Equity basis.** Capital is paid from cash at each deployment. The fleet view is shown on an
  equity basis even when the per-unit table is in debt mode (a banner says so); per-cohort debt
  amortization is a v2 item.

**Assumptions** (validate before trusting): utilization, subscription price, every opex line,
install cost, insurance. The footer in the app keeps this distinction visible.

## Roadmap (v2)

Scenario-compare (diff two saved configs side by side) · plug in real Switchyards booking
data to replace the utilization slider with an empirical distribution · sensitivity tornado
chart · Monte Carlo on utilization · discount-erosion timeline · CAC / sales-cycle layer.

**Fleet extensions:** self-funding / cash-gated deployment (reinvest net cash; throttle the
cadence to what you can actually afford) · per-cohort debt amortization in the fleet view ·
per-model fleet comparison (all four on one timeline).
