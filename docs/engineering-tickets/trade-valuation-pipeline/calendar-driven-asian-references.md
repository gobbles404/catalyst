# Calendar driven Asian pricing references

**Status:** Built in #NN on the prototype stack above #164, the page as a ticket; the
[As built](#as-built-nn) section at the end says what was built and what was not.
Engineering ticket, 8 October 2026. Owner direction agreed during Excel UAT.
The inspected prototype is `14130240` through PR #163. Implemented on its current successor
as one focused PR; this ticket makes no decision about landing or rebuilding the prototype.

## Outcome

An Asian trade averages the eligible pricing days in its booked window. **The supplied
index schedule and calendar determine the nearby pricing contract on each observation
day. It need not match the trade's averaging month.** Use this one rule across supported
commodities, with no ethane, crude, exchange or contract-name branches.

A December Asian may reference December throughout on a month-aligned index, or January
and then February on a WTI-like index. Its booked quantity, fixed leg and payment remain
those of the December component. Schedule and calendar data determine the difference.

This supersedes the own-contract restriction in the [first Asian ticket](asian-trades.md).
It preserves the prototype's later partial periods, calendar-day quantities, multiple
payment groups and mixed fields. The [ticket-period UX proposal](surface-uat-notes.md#4-contract-codes-and-dates-on-one-ticket)
and [lot-delta reporting](lot-delta-reporting.md) are separate work; neither blocks this PR.

## Problem and product evidence

The reported December crude booking fails with:

```text
trade at row 1 observes z26 on 2026-12-01, a day of f27 prices;
an observation of a contract other than the day's pricing contract
has no settle in a futures history, not supported
```

In `trades/encoding.py`, `_the_references` already computes F27 from the observation
date using the calendar's `contract_on`. It then rejects the reference because it differs
from the booked component Z26. That equality encodes the original narrow Asian scope.
For a daily-prompt Asian, the required fixing is precisely the calendar's settle for that
day; no second contract's settle on the same day is needed.

[ICE WTI 1st Line](https://www.ice.com/products/6753542/WTI-1st-Line-Future) averages
NYMEX front-month WTI settlements over the production month. [CME chapter 510](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf)
also specifies a calendar-month average of first-nearby settlements. By comparison,
[ICE ETE](https://www.ice.com/products/6590286) averages daily OPIS assessments for its
contract period. These support different daily input series; they do not justify a
universal equality between the averaging-month label and pricing reference.

## Responsibilities and unchanged public functions

```text
_CreateTradeTemplate(instrument, fields, values)
_CreateTrades(index, fields, trade_rows, template)
_PrepareTrades(trades, history)
_EvaluateTrades(prepared, market)
_ReportValues(results)
_ReportRisk(results)
```

| Responsibility | Owns |
|---|---|
| Trade period resolution | Inclusive booked dates and their monthly components, from a code/strip or explicit dates |
| Asian observation rule | Eligible pricing days and equal weights within each component |
| Index schedule/calendar | The pricing reference for each of those dates |
| Encoding | Static quantities, fixed leg, payment groups, dated exposures and reference mapping |
| Preparation | Historical fixings, remaining live exposures, payment state and reference-aligned risk |
| Evaluation | Current quotes for the distinct live references and the resulting values |
| Readers | Saved values, risks and inspectable mappings |

Creation uses the same date-to-reference logic as the market calendar without needing
a valuation-date-dependent calendar handle or a market. It retains the mapping once.
Changing `as_of` never changes the booked window, weights or reference assigned to a date.
A new index/schedule is a changed creation input, not something a tick discovers.

## Resolution and encoding rules

1. Preserve the existing period resolution. Split strips and explicit periods by calendar
   month. The component month identifies the averaging/payment component, not a constraint
   on which futures may price its days.
2. Select the eligible pricing days within each component's inclusive boundaries using
   the supplied pricing calendar. Require at least one. Assign weight `1/N` for that
   component's original count; fixing progress never renormalizes the remaining weights.
3. Resolve every observation through the existing index date-to-reference authority.
   In today's futures calendar, this is the first contract whose expiry is on or after
   the observation day. Remove the component/reference equality requirement for `asian`.
   Retain it for `lastday`, `penultimate` and `last3day`; this PR does not redefine them.
4. Preserve coverage and publication checks. An observation must have a supported pricing
   reference and eligible date. Do not truncate a window, clamp to the last contract,
   silently substitute the booked month or discard observations that cross a roll.
5. Keep existing quantity normalization, unit conversion and the fixed leg. `month`
   applies the entered quantity per component, including partial months; `calday` counts
   covered calendar days. Pricing-day weights allocate that quantity, not another copy of it.
6. Keep payment ownership by booked component month and resolved payment date. Anchor the
   lag at the component's last observation on its payment calendar. A pricing-reference
   change creates neither a new fixed leg nor a new payment.

The existing encoding already distinguishes `group_contract` from `slot_reference`.
Document the former as component/payment ownership; do not force them equal or rename
all internal records just to implement this ticket. Slots remain compact `(group, date)`
coordinates because the index still assigns one pricing reference to a date. Do not
merge equal dates belonging to different payment groups.

The preceding schedule boundary remains a coverage condition on **observation dates**.
A booked December component may occupy schedule row zero, with expiry in November,
while all its December observations lie inside the calendar and reference later rows.
Do not introduce a blanket refusal of that valid booking.

## History, live prices and risk

History supplies the daily underlying observations being averaged. Preparation reads
the settle for each fixed observation date and folds it into the owning payment group.
The existing one-settle-per-day history suffices when its daily reference convention
matches the index used at creation. Preserve both index/history identity checks.

For each live slot, evaluation gathers the quote of its resolved reference. A December
booking may therefore require F27 and G27 prices, without requiring a Z26 quote. Missing
coverage must identify the actual missing reference. The stable risk axis is the unique
set of pricing references, including zero entries after their observations have fixed.

```text
fixed_leg[g]        = sum(component fixed legs owned by g)
floating_leg_set[g] = sum(exposure[s] * fixing[date[s]] for fixed slots in g)
floating_leg_live[g]= sum(exposure[s] * quote[reference[s]] for live slots in g)
price_delta[r]     = sum(exposure[s] for live slots referencing r)
```

Keep the existing aggregate mark/cash transition by payment group. Fully fixed but
unpaid amounts remain in mark; on payment they move to cash. Readers use retained
vectors without repricing. The separate lot-reporting change normalizes sensitivity by
the index's reporting lot; this PR must not silently relabel monetary sensitivity as lots.

Live input meaning remains explicit. For a WTI prompt average, the projection for a future
observation is its referenced outright future's current price. For a month-aligned daily
assessment index, the existing input projects remaining assessments. A raw quote of a
whole-month averaging future is not automatically either input once fixing has begun.
This PR adds no whole-month-quote conversion and must not substitute exchange settlements
of an averaging future for the daily underlying observations.

## Calendar conventions and the supported boundary

The trade consumes the index's daily mapping. Do not infer a roll from a commodity name,
hard-code a one-month lead, assume at most two references, or add a trade-level roll offset.
The currently supported calendar includes the expiring future on expiry day and switches
on the following day; holiday filtering determines which of those days are observations.
Pin this boundary rather than changing it incidentally while removing the Asian restriction.

Other contracts can specify other rules. For example, the
[Brent leg of ICE's WTI/Brent BALMO specification](https://www.ice.com/products/31687082/Crude-Diff---WTI-1st-Line-vs-Brent-1st-Line-Balmo-Future)
rolls on expiry day. General Asian machinery must consume such a convention when the
index/calendar/history can represent it consistently. Today's calendar has no separate
roll selector. Do not fake that support by shifting physical futures expiries, which would
also change futures and penultimate observations, or by changing only the trade mapping.

Implement the general consumer of the current mapping now. An alternative roll rule,
second-nearby convention, fixed-contract daily averaging, or two references on the same
date needs an explicit later index/history design. Do not claim every exchange Asian is
supported merely because its month now books successfully. The supplied schedule,
publication calendar and underlying history must represent the intended contract.

## Independent worked acceptance

Use synthetic WTI-like inputs, explicitly supplied rather than represented as a verified
exchange holiday calendar. Quantity and quote units are BBL and USD/BBL; settlement is USD.
Specification `BBL` is size 1 BBL. Both calendars exclude weekends, 25 December 2026 and
1 January 2027. The schedule is:

| Code | Supplied expiry | Role |
|---|---|---|
| Z26 | 20-Nov-2026 | Calendar boundary and booked December component |
| F27 | 21-Dec-2026 | Early December pricing reference |
| G27 | 20-Jan-2027 | Later December pricing reference |
| H27 | 22-Feb-2027 | Later coverage |

Book a cleared financial Asian over **18–28 December 2026**, quantity **1,200 BBL**,
`quantity_per = month`, fixed price **70 USD/BBL**, payment lag **+2bd**. Payment is
**30 December**, counted from the final observation on 28 December.

| Observation | Reference | Weight | Exposure in BBL | Fixing when available |
|---|---|---:|---:|---:|
| 18-Dec | F27 | 1/6 | 200 | 71 |
| 21-Dec | F27 | 1/6 | 200 | 73 |
| 22-Dec | G27 | 1/6 | 200 | 74 |
| 23-Dec | G27 | 1/6 | 200 | 76 |
| 24-Dec | G27 | 1/6 | 200 | 75 |
| 28-Dec | G27 | 1/6 | 200 | 77 |

The fixed leg is `-1200 * 70 = -84,000`. With live F27 at 72 and G27 at 75:

| State / as_of | Mark USD | Cash USD | F27 price delta | G27 price delta |
|---|---:|---:|---:|---:|
| 18-Dec, all observations live | 4,800 | 0 | 400 | 800 |
| 19-Dec, first observation fixed | 4,600 | 0 | 200 | 800 |
| 22-Dec, both F27 observations fixed | 4,800 | 0 | 0 | 800 |
| 22-Dec, G27 ticks from 75 to 76 | 5,600 | 0 | 0 | 800 |
| 29-Dec, all observations fixed, unpaid | 5,200 | 0 | 0 | 0 |
| 30-Dec, paid | 0 | 5,200 | 0 | 0 |

Price deltas above are USD sensitivity per +1 USD/BBL, numerically equal to BBL exposure
in this fixture. With a 1,000-BBL reporting lot, the first row's lot vector is `[0.4, 0.8]`,
total 1.2; the third row is `[0, 0.8]`. Assert that reporting if the separate lot ticket is
present; do not make that implementation a dependency of the reference correction.

Hand checks: the initial mark is `-84000 + 400*72 + 800*75 = 4800`. The final amount is
`-84000 + 200*(71+73+74+76+75+77) = 5200`. Correcting the first fixing from 71 to 70
reduces the final amount by 200. A new history requires new preparation; old handles remain
unchanged. An observation stays live on its own date under the existing cutoff.

Supply the complete history required by the market, including priced days outside this
trade's window: fixed pricing days from 23 November, including 29 December for the
30 December state. Changing that unrelated 29 December fixing must not change this trade.
Keep the market valid with its later live reference even when the trade is fully fixed;
evaluation then reads zero live prices for the trade.

Respect the current positional price-vector convention. Before/on 21 December `[72, 75]`
starts at F27 and covers F27/G27; from 22 December `[75]` starts at G27. Read only G27 for
this trade at that point; the retained zero F27 risk entry must not cause an expired F27
quote request. Independently bump each available reference by one to verify its delta.
Do not bypass the public market's validation to make the acceptance example work.

Also pin a **full December** case under the same calendars: 22 observations, 15 referencing
F27 and 7 G27. Quantity 2,200 BBL at fixed 70 gives exposure `[1500, 700]` and initial mark
6,500 with quotes `[72, 75]`. Code entry `Z26` and explicit 1–31 December dates must agree.

## Coverage and inspection

Required cases beyond the worked arithmetic:

- Month-aligned ethane-style dates retain their current values, weights and reference.
  A supplied schedule with a larger month lead, and a synthetic window with more than two
  references, use the same algorithm. No commodity-name dispatch or fixed month offset.
- An observation before, on and after expiry selects the calendar's documented reference.
  Exercise a weekend/holiday at a roll and a roll outside the booked window.
- Strips preserve separate monthly quantities, observation denominators and payments.
  Partial periods/BAL helper dates, `month`/`calday`, mixed entry units, signs, zero rows,
  duplicate occurrences and ticket reordering retain their existing meanings.
- Mixed Asians and expiry-based trades in one index batch value like their singletons.
  Same pricing reference/day with different payment ownership remains distinguishable;
  different payment dates still form separate groups. Expiry-based own-contract refusals stay.
- Missing actual-reference prices, missing required fixings, observations outside calendar
  coverage and a component with no pricing day fail visibly. No clipping or fallback.
- A tick reuses preparation. Advancing `as_of` rolls exposure from live to fixed without
  changing dates or weights; correcting a fixing changes only its weighted contribution.
  All payment states and stable zero risk entries remain correct.

`util_ReadHandle` must distinguish **booked component/payment ownership** from **pricing
reference**. Current prepared/result columns show reference, date and payment date; these
alone can be identical for two groups. A December Asian ending 21 December and an F27
lastday trade can both reference F27 on that date and pay 22 December. Include a clear
group identifier or component-month column derived from retained mappings, without a new
reader or per-trade valuation store. Keep actual reference labels beside their exposures
and risk. Any repeated contract-total risk column remains repeated data, not rows to sum.

## Delivery and completion

Reuse `calendar.contract_on` and the existing observation, group, slot, preparation and
evaluation paths. Update `_the_references` and the test currently pinning the Asian
own-contract refusal. Audit comments and help that assume component month equals daily
reference, especially `observations.py`, `encoding.py`, `preparation.py`, `kernel.md`,
the Asian/create/prepare/evaluate pages, and readback descriptions.

Add the rolling example to the kept workbook through the public functions, with its daily
references and expected values visible. Update relevant discovery/help, seam, smoke and
host assertions for changed messages or readback layout. Do not leave the old Asian
restriction documented as a current limitation.

Measure rows, components, groups, observations, compressed slots and distinct live
references using the existing counters. At least two batch sizes must show that a tick
does no resolution, unit conversion, observation generation or fixing read; it reads each
distinct live reference once. Keep allocation checks sensitive to slot/group growth, not
an expanded dense trade-by-calendar matrix. Run the full repository gate. Follow the
separate-review rule for any existing golden changes; independent expectations above
must not be generated from the implementation under test.

Done means both month-aligned and rolling-calendar Asians traverse the same public
pipeline with correct mark, cash and reference risk, inspectable ownership, preserved
expiry-method behavior and no extra work on ticks. No new signature, instrument type,
rate model, quote adapter, roll convention, or general trade-input blank policy is part
of this PR.

## As built, #NN

Engineering's record of what landed, in the ticket's terms.
[kernel.md](../../library/trades/kernel.md),
[create-trades.md](../../library/trades/create-trades.md),
[prepare-trades.md](../../library/trades/prepare-trades.md),
[evaluate-trades.md](../../library/trades/evaluate-trades.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the pages.

- **The rule.** `_the_references` in `src/goosedove/trades/encoding.py` keeps deriving every
  observation's reference from the calendar's rule, `contract_on`, the first contract whose
  expiry is on or after the day, and keeps the own-contract equality for `lastday`,
  `penultimate` and `last3day`, each refused by its method, `trade 'A' at row 1 observes Z26
  on 2026-12-02, a day X26 prices; the last3day method takes the contract's own days, and a
  futures history holds no settle of Z26 for a day X26 prices`; under `asian` the day's
  contract is the reference, one gather of the methods onto the observations and nothing else
  new. The slots stay `(group, date)`, the groups stay contract and payment day, the delta
  axis is the distinct references, F27 and G27 for a December booked as Z26 and never Z26;
  the preparation, the evaluation, the history and the market are unchanged, the vector
  starting at the first unfixed day's contract so that on 22 December `[76]` is G27's and the
  retained F27 entry at zero asks for nothing. No commodity, exchange or contract-name branch,
  and no roll convention but the calendar's, the expiring contract on its expiry day and the
  next from the day after.
- **The words.** A slot is named by its day and the contract pricing it, `trade 'W1' at row 1
  on 2026-12-18, a day F27 prices`, so the finiteness refusal of #164 reads `trade 'H' at row 1
  on 2026-11-25, a day Z26 prices, has inf live lots, ...`; the boundary refusal names the day
  the calendar begins and the contract that bounds it, `trade at row 1 observes 2026-10-28,
  before the calendar begins on 2026-10-29; the schedule's first contract, X26, bounds the
  calendar and nothing prices its days`; a closed day's refusal names the day alone.
- **The readbacks.** The prepared and results spills begin `pricing_contract`,
  `booked_contract`, `observation_date`: the contract pricing the day, whose settle fixes the
  slot and whose quote projects it, and the contract the slot's payment group was booked on,
  which owns the fixed leg and the payment, both `str`. The old `contract_code` is gone from
  the slot spills, the owner's choice, so that neither reading is mistaken for the other;
  `contract_sensitivity` and `contract_lot_delta` stay the pricing contract's, as the risk axis
  is. Every other column keeps its name and moves one to the right, and the smoke, the host
  facts and the kept workbook read the wider spills.
- **The numbers pinned.** The ticket's booking, 18 to 28 December, 1,200 barrels at 70, six
  days of 200, F27's 18th and 21st and G27's four, paying 30 December: 4,800, 4,600, 4,800,
  5,600, 5,200 and 5,200 of cash through the six states of its table, lots 0.4 and 0.8, the
  first fixing corrected 200 less through a new history and a new preparation, the 29th's
  fixing moving nothing, each reference bumped alone moving its own delta; the whole December
  15 and 7 of 22 days, 6,500, a code entry and the month's dates agreeing; two groups on one
  pricing day apart by their booked contracts and summing as their singletons; a roll across a
  holiday, a window within one contract, four references in a month; the batch refused after
  the last expiry and before the calendar; a strip's two months each on their own days,
  quantity and payment; a row booked twice. The month-aligned ethane cases keep every number,
  and the NG-like asian the first slice refused is made, its 22 days F27's then G27's.
- **The work.** No ledger moved: the encoding, the preparation and the tick run the same
  functions and numpy calls over a rolling batch as over a month-aligned one, pinned at five
  and two thousand trades on a schedule whose contracts expire the month before their own,
  one group a booked month, one reference more than months booked, a tick reading each
  distinct live reference once and resolving, converting, generating and reading nothing
  else. The counts by row, component, group, observation, slot and live reference are the
  existing counters'.
- **Where it is proved.** `tests/unit/test_trades.py` at the kernel,
  `tests/unit/test_create_trades.py` through resolution, `tests/unit/test_trade_valuation.py`
  through the registered functions, `tests/performance/test_trade_budgets.py` for the work,
  `tools/excel_smoke.ps1` on a sheet, `host/Goosedove.Host.Tests/CallTests.cs` from the host,
  and the kept workbook's WTI block at the foot of the handles sheet, rows 1695 to 1737, with
  the booking's three states and its two readbacks.
- **Not in this slice.** No roll convention but the calendar's: no second-nearby or
  fixed-contract daily averaging, no two references on one date, no trade-level roll offset,
  as the ticket bounds it; no whole-month-quote conversion; the date-entry UX of the UAT
  notes is separate work; no new signature, instrument, rate model or quote adapter.
