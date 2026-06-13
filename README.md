# Goodtown Revenue Model Explorer

An interactive tool that pushes your assumptions through Goodtown's four competing
revenue models at once — **B2C pay-per-use**, **B2B subscription**, **venue-buys + service**,
and **base + overflow hybrid** — and shows payback, capital-at-risk, and breakeven side by
side on the *same* assumptions.

The point isn't a static table. It's watching the **model ranking flip** as the three
numbers we can't yet measure move:

1. **Utilization** — B2C lives or dies here.
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
| `app.py` | Streamlit UI **only**. Loops over the cost registry to build inputs; renders the table, crossover chart, capital panel, banners, and scenario save/load. |
| `calculations.py` | The financial math as **pure functions** (no Streamlit). Testable in isolation, so we trust the numbers before the charts. |
| `cost_items.py` | The **single source of truth** for every cost input: the `COST_ITEMS` registry, the headline/non-registry defaults, and the real-world `BENCHMARKS`. |
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

**Assumptions** (validate before trusting): utilization, subscription price, every opex line,
install cost, insurance. The footer in the app keeps this distinction visible.

## Roadmap (v2)

Scenario-compare (diff two saved configs side by side) · plug in real Switchyards booking
data to replace the utilization slider with an empirical distribution · sensitivity tornado
chart · Monte Carlo on utilization · discount-erosion timeline · CAC / sales-cycle layer.
