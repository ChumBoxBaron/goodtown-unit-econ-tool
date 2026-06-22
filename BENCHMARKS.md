# Benchmark Rationale — Why These Numbers

This document is the justification layer for `BENCHMARK_BANDS` in `cost_items.py`.
The code holds the numbers; this holds the *reasoning* — so when an investor (or
Mark) asks "why is your acceptable payback 24 months and not 60?", the answer
lives in the repo next to the math instead of in someone's memory.

**One-line thesis:** the Goodtown pod is a *hybrid asset* — depreciating
manufactured hardware (a vending machine) running a utilization-revenue engine
(a hotel). Neither comp alone calibrates it. We borrow payback discipline from
vending, revenue-and-utilization shape from hospitality, and the single
make-or-break reality check from self-storage.

---

## Why three comparables, not one

The instinct to anchor on vending machines is half right. Vending teaches capital
discipline and the location-commission model, but its **dominant cost is product
COGS** (the soda, not the machine). Goodtown has almost no per-booking COGS — a
booking costs a little electricity, a cleaning amortization, and card processing.
So vending's *margin* benchmarks are meaningless here, while its *payback*
benchmarks are gold. You have to take vending apart and use only the half that
maps.

The half vending can't supply — what a utilization asset with near-zero marginal
cost looks like — comes from two real-estate comps that share Goodtown's cost
structure: **hospitality** (revenue per available room ≈ revenue per available
pod-hour) and **self-storage** (capex + occupancy, near-zero marginal cost).

| Comp | What it calibrates | What it does NOT calibrate |
|------|--------------------|----------------------------|
| Vending | Payback tolerance, location commission, card processing, downtime haircut | Gross margin (COGS-driven; we have none) |
| Hospitality (RevPAR) | Utilization expectations, revenue = occupancy × rate | Payback horizon (real estate has terminal/land value; our hardware depreciates) |
| Self-storage | Break-even occupancy, lease-up ramp, near-zero marginal cost shape | Payback horizon (cap-rate math assumes a sellable real-estate asset) |

The cautionary tale that ties it together is **Breather** — on-demand private
rooms by the hour, raised $100M+, collapsed out of the model. The most likely
cause: utilization never cleared the fixed location costs. Every band below
exists to answer one question early: *does our break-even sit comfortably below
realistic occupancy, or dangerously above it?* If a model can't explain why
Goodtown survives where Breather didn't, the model isn't done.

---

## 1. Vending — payback discipline

**What transfers.** Vending operators live and die by payback period on the
machine, which is exactly Goodtown's north-star metric, and the industry's
tolerance for it is a real benchmark. The placement/commission model transfers
too: pods in host venues on a revenue share is the most vending-like part of the
business.

**The numbers (operator data, 2025–26):**

- **Payback period:** traditional snack/drink machines recover cost in ~12–18
  months in a good location, as fast as 8–12 in high-traffic placements, with
  24 months as the outer tolerance. Specialty machines (cotton candy, phone
  cases) pay back faster, but those are high-margin *product* plays and don't
  map to a service asset.
- **Location commission / rent:** 10–25% of sales paid to the venue is the
  repeated figure across sources.
- **Card processing:** 2–4% of gross (2.5–3.5% typical).
- **Downtime:** ~3–5% revenue loss to machine downtime (NAMA data).
- **Gross margin:** 40–60% on snacks — **do not import.** This is COGS-driven
  and Goodtown has near-zero COGS.

**How we use it.** We anchor `target_payback_months` to vending's discipline but
stretch the band to 24–36 months, *only* because Goodtown's capex (~$50k landed
for the conjoined unit) is roughly 10× a vending machine. The principle is
vending's; the absolute number is scaled to the hardware cost. We do **not**
borrow vending's payback by assuming a real-estate-style multi-year horizon —
the hardware depreciates and has little resale value, so capital has to come back
inside the asset's useful life.

> **Design lesson:** vending is a knife to take apart, not a template to copy.
> Use the payback blade; throw away the margin blade.

---

## 2. Hospitality (RevPAR) — the revenue and utilization shape

**Why it's the strongest single anchor.** RevPAR — revenue per available room —
is defined by CBRE as *revenue divided by supply: the overall utilization of a
property's available rooms.* That is, line-for-line, revenue per available
pod-hour. Decades of occupancy × average-rate benchmarks exist, on Goodtown's
exact low-marginal-cost structure.

**The numbers (STR / CoStar, CBRE, PwC, AHLA, 2025):**

- **National occupancy:** ~62–63% for full-year 2025 (CoStar/STR 62.3%; PwC
  63.1%). This is what a *mature, normalized* lodging market sustains.
- **Premium / luxury occupancy:** ~67–75%. The ceiling that the best-run,
  best-located assets reach.
- **ADR:** ~$161 national; **RevPAR:** ~$100.
- **Decomposition:** RevPAR = occupancy × ADR. The lesson is structural: revenue
  is the product of a fill rate and a rate, and you can trade one for the other.

**How we use it.** The `sustainable_utilization` band (0.50 / 0.65 / 0.75) is
hospitality-calibrated. Any utilization assumption above ~0.75 is more optimistic
than what *good hotels* achieve and should be flagged, not accepted. Critically,
hotels measure occupancy against **bookable supply**, never against 24-hour clock
time — which forces the denominator discipline below.

---

## 3. Self-storage — the make-or-break metric

**Why it matters most.** Self-storage is the cleanest structural match for the
capital side: equipment capex, occupancy-driven revenue, near-zero marginal cost,
hyper-local demand. And it hands us the single most important number in the whole
exercise — **break-even occupancy.**

**The numbers (industry feasibility data, 2025–26):**

- **Break-even occupancy:** ~40–60% for operating expenses alone, rising to
  ~65% once debt service is included. *This is the Breather lens made
  quantitative.*
- **Stabilized occupancy target:** ~90–92% (storage is sticky long-term rental,
  so it stabilizes higher than transient lodging — treat as an upper reference,
  not a Goodtown target).
- **Lease-up ramp:** Year 1 reaches 30–50% occupancy, Year 2 reaches 50–70%,
  Year 3 reaches 70–90%. Stabilization now takes 3–4 years for larger facilities.
- **DSCR:** lenders require a minimum 1.25× debt-service-coverage ratio.
- **Construction cost:** ~$50–65/sq ft single-story, ~$90–130/sq ft multi-story
  (context for capex discipline, not a direct map).
- **Cap rates:** ~5.8–7.4%; developer yield-on-cost targets 8–10%. **Caution:**
  do *not* convert a cap rate into a payback period for Goodtown — cap-rate math
  assumes a sellable real-estate asset with terminal value, which a depreciating
  pod is not.

**How we use it.** Two things. First, the `breakeven_occupancy_ref` band
(0.40 / 0.55 / 0.65) is the reality check: if the model's *computed* break-even
pod-hour utilization lands above the sustainable hospitality band (~0.65–0.75),
the asset is structurally Breather and slider-tuning won't save it. Second, the
ramp data says the fleet-sim `ramp_months` lever should be set longer than
instinct suggests — venues fill over years, not weeks.

---

## The synthesized bands (mirror of `BENCHMARK_BANDS`)

These are **calibrations, not transcriptions** — judgment applied to the raw
figures above to fit Goodtown's parameters. Every `source` string in the code
preserves the underlying industry number so a tuned guess is never mistaken for
a finding.

| Band | Maps to | Low | Target | High | Source logic |
|------|---------|-----|--------|------|--------------|
| `target_payback` | `target_payback_months` | 12 | 24 | 36 | Vending 12–18mo, scaled up for 10× capex |
| `sustainable_utilization` | `utilization_pct` (per pod) | 0.50 | 0.65 | 0.75 | Hotel occupancy 62% national, 70–75% premium |
| `breakeven_occupancy_ref` | computed break-even util | 0.40 | 0.55 | 0.65 | Storage break-even 40–60% opex, 65% w/ debt |
| `location_commission` | `venue_rev_share_pct` | 0.10 | 0.15 | 0.25 | Vending location split 10–25% |
| `payment_processing` | `payment_proc_pct` | 0.02 | 0.03 | 0.04 | Vending card processing 2–4% |
| `downtime_haircut` | `availability_haircut_pct` | 0.03 | 0.04 | 0.05 | Vending downtime 3–5% (NAMA) |
| `gross_margin_DO_NOT_IMPORT` | — (note only) | 0.40 | 0.50 | 0.60 | Vending margin is COGS-driven; we have none |

---

## The denominator caveat (read before trusting any of this)

Every utilization and break-even number above is measured against **bookable
supply**, the way hospitality and storage measure occupancy — *not* against
24-hour clock time. If the tool's `bookable_hours_per_month` is left at a 24×30 =
720 denominator, then "20% utilization" silently means 20% of *every hour
including 3am*, and the benchmark comparison is off by 2–3×.

The break-even-occupancy verdict (the red/green Breather check on the heatmap) is
only as trustworthy as this denominator. Define bookable hours as realistic prime
demand hours before reading the verdict.

---

## A note on source quality

The hospitality and self-storage figures come from primary-grade industry
authorities: STR/CoStar, CBRE, PwC, AHLA, and self-storage REIT/feasibility
reporting. Treat those as reliable.

The vending figures are harder — most public vending ROI content is published by
machine manufacturers with an incentive to make the math look good, so the
individual blog numbers are SEO, not gospel. We've used only the figures that
(a) converge across many independent sources and (b) trace back to NAMA (National
Automatic Merchandising Association) or the SBA, and we've taken the conservative
end of each range. If anything here gets challenged, the vending payback band is
the softest and the first to re-derive from a primary NAMA source.

---

## Sources

Vending:
- InHand Networks, "AI Smart Vending Machine ROI" (2026)
- Wider Matrix, "What is the ROI of Vending Machines?" / "How long to pay for itself" (2026)
- CoinGamesMachine, "Vending Machine Profits: Margins, ROI" (2026)
- VMF USA, "Are Vending Machines Profitable?" (cites NAMA, SBA, 2026)
- (Authorities underneath: NAMA, U.S. Small Business Administration)

Hospitality:
- STR / CoStar + Tourism Economics, U.S. hotel forecast (Dec 2025)
- CBRE, U.S. Hotels State of the Union / Q-figures (2025–26)
- PwC Hospitality Directions; AHLA 2025 benchmarks

Self-storage:
- Loan Analytics, "Self-storage development feasibility in 2026"
- CRE Daily / Matthews / Skyview Advisors Q2–Q3 2025 industry reports
- Stora, "How to Value a Self-Storage Facility" (construction cost data)

*Last updated: June 2026. Re-validate figures annually — occupancy, ADR, cap
rates, and payback norms all drift.*
