# Fresh-session prompt — interrogate / test / ideate on the tool

> Copy everything in the fenced block below into a new Claude Code window opened
> on this project folder. The business-context docs now live in `docs/` and the
> prompt points the new session at them — no need to re-attach anything.

```
I'm Drew. We've already built a working Streamlit tool — the "Goodtown Revenue Model
Explorer" — in this folder. I want to spend this session USING and INTERROGATING it:
poke at the numbers in real time, question whether the variables and assumptions are
right, and ideate new features/tweaks. We are NOT mid-build on a specific task — this
is exploratory. Be a collaborator: teach the "why," push back, surface tradeoffs, and
tell me when a number is a guess vs a finding.

WHAT THE TOOL IS
A single-screen app that pushes my assumptions through Goodtown's four competing
revenue models at once and shows payback, capital-at-risk, and the crossover point
where the winner flips. Goodtown places on-demand private meeting pods inside
high-footfall venues (retail, hotel/hospital lobbies). The whole reason the tool
exists: the B2C-vs-B2B decision hinges on three numbers we can't yet measure —
utilization, venue willingness-to-pay (subscription price), and cost of capital — so
the tool makes those tunable and shows how the ranking flips as they move. It always
surfaces capital-at-risk, because what kills a 2-person team is running out of cash
deploying units, not thin per-unit margin.

FIRST, GET ORIENTED (please do this before we start)
1. Read these files so you know the current state exactly:
   - README.md            (overview + how it's built + design decisions)
   - cost_items.py        (THE registry: every cost variable + headline defaults + benchmarks)
   - calculations.py      (the financial math — pure functions, no Streamlit)
   - app.py               (the UI: sidebar inputs, table, crossover chart, capital panel)
   - test_calculations.py (hand-worked expected numbers — a good spec of intended behavior)
   And for the business background behind the numbers (read these too):
   - docs/goodtown_context_primer.md              (what Goodtown is, the strategy, venue history)
   - docs/goodtown_revenue_model_streamlit_spec.md (the original tool spec + benchmark sources)
2. Launch the app so we can look at it together. There's a one-click launcher
   (run_app.bat), or run:  .venv\Scripts\streamlit.exe run app.py
   If you change code, you can also exercise it headlessly with
   streamlit.testing.v1.AppTest to check for errors without me clicking around.

THE FOUR MODELS (keys in code)
- b2c        — pay-per-use; Goodtown owns the unit; revenue = usage × price × utilization
- b2b        — fixed monthly subscription; Goodtown owns; demand risk on the venue
- venue_buys — venue owns the unit (~$0 Goodtown capital); Goodtown earns a service fee
- hybrid     — base fee + overflow usage billing

THE VARIABLES CURRENTLY MODELED
Headline (the 3 load-bearing sliders): utilization_pct, monthly_subscription_price,
annual_interest_rate.
Shared unit economics: rooms_per_hub, prime_hours_per_month, blended_hourly_rate.
Capex line items (sum into capital-at-risk): hub_cost, smart_lock_hw (per door),
lte_router_hw, install_cost — plus a "use undiscounted $88k hub" toggle.
Opex line items (recurring): lock_saas (per door), lte_data_plan, cleaning, insurance,
support_base, consumer_ops (consumer support+marketing — applies ONLY to b2c & hybrid,
which is why B2B opex comes out lighter without a separate hand-tuned number).
Venue & pricing: venue_charge_mode (rev_share OR flat rent — a toggle), venue_rev_share_pct,
venue_rev_share_pct_on_overflow, flat_rent, payment_proc_pct (% of revenue, not flat),
service_fee_venue_buys, base_fee_hybrid, overflow_cap_hours.
Capital & financing: financing_mode (equity|debt), loan_term_months, target_unit_count,
available_capital.

KEY MODELING DECISIONS ALREADY MADE (so you don't re-litigate them blind)
- Capital-at-risk is itemized (hub + lock×doors + router + install), because the Mute
  hub quote (~$44k) excludes lock/LTE/install — a hub-only number understates the thing
  that matters most.
- Payment processing is a % of revenue, so it bites hardest where B2C is supposed to win.
- Venue cost is rev-share OR flat rent (one or the other), not both.
- Insurance is its own line item (institutional liability is the strategic crux).
- Debt service is computed on the FULL capital-at-risk, not just the hub.
- venue_buys is capital-free, so its payback is "instant" and ROIC is undefined.

THE EXTENSIBILITY DESIGN (important for ideation)
Every cost input is one dict in the COST_ITEMS registry in cost_items.py. The UI, the
math, and the Reset button all LOOP over that list, so adding a built-in cost is a
one-line change in one file. There's also an in-app "Add custom cost" form (runtime, no
code) and JSON scenario save/load (configs/). So when we ideate a new cost variable,
adding it is cheap — factor that into what we consider.

WHAT'S DELIBERATELY NOT BUILT YET (v2 backlog)
Scenario-compare (diff two saved configs side by side) · plug in real Switchyards
booking data to replace the utilization slider with an empirical distribution ·
sensitivity tornado chart · Monte Carlo on utilization · discount-erosion timeline ·
CAC / sales-cycle layer.

HOW I WANT TO WORK THIS SESSION
- Help me stress-test the assumptions: which defaults are shaky, which variable swings
  the conclusion most, where the model might flatter one option unfairly.
- Answer "what does this variable do and is its default defensible?" questions.
- When I propose a feature or new variable, give me the tradeoff and a rough sense of how
  invasive it is to build given the registry design.
- Don't change code unless I ask — default to discussion and running/observing the app.
- Keep me honest about findings vs assumptions; don't let a slider masquerade as data.

Start by reading the files above, launching the app, and then giving me a short read on
the 2–3 assumptions you'd most want to pressure-test first. Then I'll start poking.
```
