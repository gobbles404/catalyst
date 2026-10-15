# R2 Last three pricing days in the trade prototype

[Pipeline overview](README.md) · [Trade creation](create-trade.md) ·
[Dated exposure](dated-exposure.md) · [Penultimate futures](penultimate-trades.md)

**Status:** Built in #157 on the prototype stack above #156, the page as a ticket. Agreed
direction, 7 October 2026. Next prototype slice after the hardening stack, reviewed through PR
#156 at `1971c8c`. Implemented as one focused PR on the prototype branch. This ticket does not
prescribe merging the prototype into main or the later rebuild. The section at the end records
what was built.

## Outcome and scope

Support `schedule_method = last3day` through the existing Excel pipeline. A contract
component contributes three equally weighted observations, fixes progressively, and pays
once. One trade and many trades use the same path and return aggregate values and risk.

This is the first public averaging method. The dated kernel already accepts multiple
observations in its toy tests; the public creators currently generate one observation per
component for `lastday` and `penultimate`. Extend that path and preserve those methods'
answers, rather than adding a separate averaging evaluator.

The supported valuation profile for this slice is **cleared, financial settlement**. Keep
one index, one selected quantity specification and one schedule method per batch. Use a
shared payment lag, payment calendar and clearing-house label in the worked example.
Preserve existing payment-calendar support and compatibility checks; this slice neither
widens them nor adds a new requirement that every ticket use the example's uniform terms.

Asian, mixed schedule methods, several payment dates for the same contract, bilateral rates,
physical delivery, daily quantity bases and new readers are separate slices. Bilateral
construction keeps its existing behavior and evaluation still refuses that unsupported
route. A physical `last3day` booking fails by `settlement_method`, as physical penultimate
does today. A clearing-house label and quantity specification do not select these rules.

## Definition of last3day

For each contract component:

1. Take its expiry from the supplied index's existing, unshifted futures schedule.
2. Require that expiry to be an eligible pricing day. Do not silently roll a closed expiry.
3. Select that day and the two preceding eligible pricing days, in increasing date order.
   Eligible means Monday to Friday excluding the index's pricing holidays, using the
   existing calendar rules.
4. Give each observation weight `1/3`. This is an arithmetic average of three daily
   settlement prices, including the final pricing day. It is not the final three calendar
   days or the final three business days of the delivery month.
5. Retain the existing reference rule: each selected day must price this component's own
   contract. Refuse an observation crossing into another contract's pricing window, or
   outside supported schedule coverage. Do not substitute the other contract's fixing.

Each component's total quantity is shared across the three dates. A quantity of 60 gives
20 units of exposure per date, not 60 on each date. For a strip, the entered monthly quantity
applies separately to each constituent month, as it does today.

The acceptance contracts below are deliberately synthetic, with explicit dates and terms.
They define this library method without claiming to reproduce a particular listed product.
Before using a named exchange product as an additional example, verify that its pricing
window, weighting and payment terms match the rule against that product's official specification.

## Pipeline and implementation boundary

The worksheet signatures stay unchanged:

```text
_CreateTradeTemplate(instrument, fields, values)
_CreateTrades(index, fields, trade_rows, template)
_PrepareTrades(trades, history)
_EvaluateTrades(prepared, market)
_ReportValues(results)
_ReportRisk(results)
```

`CreateTrades` resolves the contract components and builds their observations once. The
fixed leg amount is also determined once: the existing encoded `offset` is the signed
quantity coefficient multiplied by minus the entered `fixed_price`. Do not distribute
that whole amount three times when expanding the floating observations.

**Remove the one-observation assumption from payment construction.** At the reviewed head,
`resolution.py` passes `observations.date` directly to `_the_payment_terms`. That works only
because each public method currently produces one observation per component. Instead,
derive **one last observation date per component**, preserving component order, and supply
those dates as the payment anchors:

```text
components = resolve ticket contracts and strips
observations = build observations(method, index, components)
payment_anchors = last observation date for each component
payments = apply each component's lag and payment calendar to its anchor
encoded = encode terms, observations and payments
```

Use the same anchor derivation for all supported methods. `lastday` and `penultimate` each
have a single observation, so their payment dates remain unchanged. The anchor can be
derived during creation; it does not require a new worksheet field or permanently stored
array. Internal representation is engineering's choice.

`PrepareTrades` applies the supplied history to each observation date. Under the existing
date cutoff, an observation is live on its own date and fixed when that date is before
`as_of`. Known observations contribute to `floating_leg_set`; remaining observations
contribute to `floating_leg_live`. Fixed amounts remain mark until their payment group
pays, then become cumulative cash. Preserve the current missing-fixing refusals.

`EvaluateTrades` continues to read distinct live contract prices once, gather them onto
live dated slots and evaluate the compressed batch. All unfixed observations of a component
use its contract's current quote under the existing projection model. Ticks do not generate
dates, convert quantities, recompute the fixed leg or apply fixings again. No hidden
preparation or new history cache is introduced.

Keep the existing stable contract delta vector, zero delta for fixed observations, dated
result contents and scalar reports. Readers inspect the saved result without pricing.
Cleared mark remains undiscounted; cleared DV01 remains zero under that model.

Principal implementation areas are the instrument's supported choices/help, schedule-method
parsing and terms, `observations.py`, and payment-anchor resolution. Reuse existing encoding,
preparation and evaluation wherever their multi-observation behavior already suffices.

## Worked acceptance example

Use a synthetic index quoted in USD per MMBTU and settling in USD. Its specifications
explicitly contain `UNIT`, size 1 MMBTU. The label alone does not imply size one. Mark and
cash below are USD; delta is USD per (USD/MMBTU). No currency or quantity conversion
obscures this example.

| Contract | Synthetic expiry | Role |
|---|---|---|
| X26 | 2026-11-30 | Preceding boundary contract |
| Z26 | 2026-12-07 | Traded component |
| F27 | 2027-01-07 | Later live contract for complete lifecycle markets |

The pricing calendar closes **4 December 2026**, in addition to weekends. The payment
calendar has weekdays open with no additional holidays. With `payment_time_lag = +2bd`,
Z26 observes **2 December, 3 December and 7 December**, and pays **9 December**.

The template supplies `quantity_unit = UNIT`, `quantity_per = month`,
`schedule_method = last3day`, `route = cleared`, `settlement_method = financial`,
`clearing_house = Prototype Clearing`, and the lag/payment-calendar reference. The ticket
supplies these rows; both have `trade_date = 2026-11-20`:

| trade_id | contract_code | quantity | fixed_price |
|---|---|---:|---:|
| A | Z26 | 60 | 70 |
| B | Z26 | -30 | 72 |

Before compression A contributes 20 units per observation and B contributes -10. The
compressed batch has three slots of 10 units each and fixed leg amount
`-60 * 70 + 30 * 72 = -2040`.

| Observation date | Reference | Compressed exposure | Fixing when available |
|---|---|---:|---:|
| 2026-12-02 | Z26 | 10 | 71 |
| 2026-12-03 | Z26 | 10 | 75 |
| 2026-12-07 | Z26 | 10 | 73 |

While Z26 is live, quote it at 74 and F27 at 80. After Z26 rolls, the price vector begins
with F27 at 80. Its presence keeps the market valid even when the trade batch has no live
exposure; an entirely ended market remains outside this slice.

Supply complete history for each state, not just the three observations. The daily series
through 8 December is: 1 December = 70, 2 December = 71, 3 December = 75, 7 December = 73,
8 December = 80. The last value belongs to F27; 4–6 December are closed. Each history
contains the required prefix before its valuation date.

| as_of | Fixed observations | cleared_mark | cleared_cash | Z26 delta |
|---|---|---:|---:|---:|
| 2026-12-02 | None; first observation is still live | 180 | 0 | 30 |
| 2026-12-03 | 2 December | 150 | 0 | 20 |
| 2026-12-04 | 2 and 3 December | 160 | 0 | 10 |
| 2026-12-07 | Same; final observation is still live | 160 | 0 | 10 |
| 2026-12-08 | All three; unpaid | 150 | 0 | 0 |
| 2026-12-09 | All three; paid | 0 | 150 | 0 |

For example, 3 December's mark is `-2040 + 10 * 71 + 20 * 74 = 150`.
The final amount is `-2040 + 10 * (71 + 75 + 73) = 150`.

Two additional changes have independent expected answers:

- At 3 December, a quote tick from 74 to 75 changes mark from 150 to **170**, with the
  same preparation and delta 20.
- At the same valuation date, correcting 2 December's fixing from 71 to 72 changes mark
  from 150 to **160**, with the quote still 74. The old preparation must reject a market
  over the new history; explicit preparation against that history gives the corrected answer.

## Acceptance and verification

1. **Entry and discovery.** `last3day` works through template or ticket under existing
   strict field and disjoint-source rules. Show/help describe the rule and supported
   settlement. Physical last3day fails visibly; other unimplemented methods remain refused.
2. **Dates and payments.** Pin the worked dates, equal weights and one payment per component.
   In a separate uniform batch, close 8 December on the payment calendar: payment moves
   to **10 December**, while observations and their weights remain unchanged. Cover a
   closed expiry and an observation crossing the preceding contract's pricing window.
3. **Economic lifecycle.** Pin the table at the kernel and through the registered worksheet
   functions, including contract-level delta and dated live exposure, not just total delta.
   Do not replace these expected answers with outputs generated by the implementation.
4. **One and many.** Batch equals compatible singletons summed on aligned contract axes;
   row order does not change economics; duplicating a row counts twice. Zero quantities
   remain validated rows and contribute zero, without dropping required dates or identities.
5. **Strip and anchor cardinality.** At 2 December, a separate `Z26-F27` strip with quantity
   3 per month and fixed price 70 has mark **42** and contract delta **[3, 3]** at quotes
   [74, 80]. Its six observations are 2/3/7 December and 5/6/7 January. Its two payment
   anchors are 7 December and 7 January; payments are **9 December and 11 January**.
   Duplicate that row: mark **84**, delta **[6, 6]**. This must exercise actual creation,
   not only a test constructing resolved payment dates by hand.
6. **Reuse and identity.** Exercise the tick and correction above. Preserve both index and
   history identity checks, live-price coverage, and the existing positional-vector boundary.
   Retain an old result across the tick and confirm its original values stay unchanged.
7. **Existing behavior.** The NG, penultimate, zero-quantity and quantity-selection examples
   retain their numbers, dates and errors except where a supported-method list gains
   `last3day`. Keep the shape and meaning of existing reports/readbacks.

Update the relevant function pages and keep one working last3day block in the existing
workbook, with room for its spills. Exercise the public path in the existing smoke/host
coverage without adding another parallel test framework.

Measure components, observations, compressed slots and distinct live references explicitly.
Three observations per component should increase creation/preparation work where necessary,
but a tick must still perform zero schedule generation, fixed-leg construction and fixing
folding. Use the existing work/allocation harness, explain changed counts, and do not raise
ceilings merely to obtain a pass. Run the repository's complete gate on the implementation.
Keep changes to existing golden baselines separately reviewed under the repository rule.

## Completion and next slice

Done means the method works from ticket entry to both reports, the independent lifecycle
and strip examples pass, and tick reuse is demonstrated. Review this as one product slice
before broadening the prototype.

Next, specify a month-aligned Asian using a concrete ethane example, then address mixed
methods and payment groups. The last3day anchor derivation should already accept a varying
number of observations per component; it must not hard-code a stride of three into shared
payment machinery. Oil averages crossing a futures roll require a separate decision about
market references and history coverage.

## As built, #157

Built as the page says, on the path the two one-observation methods take, with these
particulars.

- **The observations.** `observed` in `src/goosedove/trades/observations.py` gives `last3day`
  three observations per component: the expiry and the two business days before it on the
  index's holiday calendar, one `numpy.busday_offset` over the components and the three offsets
  `-2, -1, 0` at once, a third of the quantity each, the three days of a component increasing.
  The check that every expiry is a day the market prices is the pen's, shared, and the refusal
  names the contract and the method's rule: `Z26 expires on 2026-12-04, a day the index's
  market is closed; the last3day method takes an expiry the market prices and the two business
  days before it`. A day among the three that another contract prices is the encoding's
  existing refusal, `trade 'A' at row 1 observes Z26 on 2026-12-02, a day X26 prices; an
  observation of a contract other than the day's pricing contract has no settle in a futures
  history, not supported`, and nothing is substituted.
- **The payment anchor.** Resolution no longer hands the observations' dates to the payment
  terms. `_last_days` finds each component's last observation, the one just before the next
  component's first, by one `numpy.searchsorted` over the observations in component order,
  however many a method gives; `lastday` and `penultimate` pay as before, and `last3day` pays
  from the expiry. The anchor is derived at creation and stored nowhere.
- **The settlement.** A physical `last3day` is refused by the kernel's `_the_method` as the
  physical pen is, by `settlement_method`: `settlement_method is 'physical', expected
  'financial' with the last3day method; a last3day future is cash settled on the average of its
  last three pricing days`. The template and the ticket read the method through the one
  `choice` reader, whose words are now `expected lastday, penultimate or last3day, the three
  methods built`; `asian` is refused by name as before. The `future` definition's rule for
  `schedule_method` says the three are built, and `_ShowInstrument` shows it.
- **Nothing else changed.** The encoding, the preparation, the evaluation, the readers and
  the reports are as they were; the three slots of a component are slots like any other, and
  a tick runs the evaluation alone, as the budgets pin. The NG, penultimate, zero-quantity and
  quantity-selection examples keep every number, date and refusal, the method list apart.
- **Where it is proved.** The worked example, the tick, the correction, the strip, its
  duplicate, the singletons in either order, the row kept ready, the closed payment day and
  the three refusals are pinned to the page's numbers in `tests/unit/test_trades.py` at the
  kernel, `tests/unit/test_create_trades.py` through resolution and
  `tests/unit/test_trade_valuation.py` through the registered worksheet functions; the work
  counts and the ledgers in `tests/performance/test_trade_creation_budgets.py` and
  `test_trade_budgets.py`; the public path on a sheet in `tools/excel_smoke.ps1`, from the
  host in `host/Goosedove.Host.Tests/CallTests.cs`, and in the kept workbook's last3day block
  at the foot of the handles sheet.
