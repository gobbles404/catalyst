# R3 Calendar month Asian trades in the prototype

[Pipeline overview](README.md) · [Trade creation](create-trade.md) ·
[Dated exposure](dated-exposure.md) · [Last three pricing days](last3day-trades.md)

**Status:** Built in #158 on the prototype stack above #157, the page as a ticket. Engineering
ticket, 7 October 2026. Next prototype slice after PR #157, reviewed at `592a6bc`. Implemented
as one focused PR on the prototype's current head with that work included. This ticket does not
decide how the prototype will reach main. The section at the end records what was built.

**Follow-up, 8 October 2026:** [Calendar driven Asian pricing references](calendar-driven-asian-references.md)
supersedes this initial slice's requirement that each observation reference its booked
month's contract. The general rule takes the nearby reference from the supplied index
schedule/calendar for each pricing day; month-aligned and rolling references share one path.
This page otherwise records the original slice and its acceptance examples. Built in #NN.

## Outcome and scope

Support `schedule_method = asian` through the existing trade pipeline. Each contract
component averages the eligible pricing days of its calendar month, fixes progressively,
and pays once. One trade and many trades use the same path, with aggregate valuation,
a retained vector of risks and the existing scalar reports.

Start with a month-aligned ethane example. Keep one index, one selected quantity
specification and one schedule method per batch. The supported valuation profile is
cleared, financial settlement, with `quantity_per = month`. Use common payment terms
and a common clearing-house label in the example. Preserve existing accepted payment
calendar and lag behavior; do not introduce extra uniformity restrictions on it.

Mixed schedule methods, multiple payment dates for the same contract, oil averages
crossing futures rolls, daily quantity bases, exact date ranges, balance-of-month trades,
bilateral rates and physical delivery remain separate slices. Bilateral construction
retains its existing behavior and evaluation refuses the unsupported route. Physical
Asian fails visibly by `settlement_method`, consistent with the other averaging method.

## Product reference and market input meaning

ICE's **Ethane, OPIS Mt. Belvieu Non-TET Future**, symbol ETE, provides the product
reference: it settles financially against daily OPIS assessments for the contract period,
using the days on which those prices are reported. Its size is 1,000 barrels, or 42,000
gallons, and payment is the second clearing business day after its last trading day.
[ICE product specification](https://www.ice.com/products/6590286), checked 7 October 2026.

The acceptance fixture below uses explicitly supplied calendars and simplified units.
It demonstrates that pricing pattern; its dates are not a verified OPIS or ICE holiday
schedule. A named exchange booking still needs the correct publication calendar,
quantity specification and payment terms. The library does not infer them from ETE,
ethane or a clearing-house label.

**Preserve and document the current kernel's live-input meaning.** A monthly live input
projects that month's remaining unfixed daily observations at a common price. History
supplies the daily underlying prices being averaged, such as OPIS assessments. Those are
different from daily exchange settlement prices of the monthly averaging future.

A raw quote for the entire monthly average is not interchangeable with that remaining
projection after fixing starts. If `N` is the full observation count and `k` have fixed,
the relationship, while `k < N`, is:

```text
remaining_projection = (N * whole_month_quote - sum(fixed_daily_prices)) / (N - k)
```

The current market does not perform that conversion. This slice supplies projection
inputs directly, as the existing averaging examples do; it adds no quote adapter or
new market field. Reported delta is sensitivity to those supplied projection inputs,
not a claim about hedge quantity against a raw whole-month futures quote. Conversion
and risk with respect to that original quote require their own design. This distinction
must appear beside the working example so its market inputs are unambiguous.

## Definition of asian

For each resolved contract component:

1. Use the calendar month represented by its contract code. `Z26` means December 2026;
   a strip expands into its existing monthly components. Reuse the month resolved at
   creation. Do not infer it from the expiry's month or parse the code again downstream.
2. Select every Monday-to-Friday day in that month except the index's pricing holidays,
   in increasing date order. For this product family that calendar represents publication
   days. There is no weekend carry, calendar-day weighting or payment-calendar filtering.
3. Require at least one eligible day. Give each observation weight `1 / N`, where `N`
   is that component's total observation count. Weights sum to one separately for each
   component, including months of different lengths in the same strip.
4. The initial slice required each date-derived reference to equal the component's own
   contract. That restriction is superseded by [Calendar driven Asian pricing references](calendar-driven-asian-references.md).
   Keep calendar coverage checks and the preceding boundary requirement; the Asian now
   consumes each day's calendar reference even when it differs from the booked month.
5. Count payment from the component's **last observation day**, using its existing
   payment lag and payment calendar. Use PR #157's shared anchor derivation. One payment
   per contract group was the compression boundary until #162,
   [multiple-payment-groups.md](multiple-payment-groups.md), made the payment day part of
   the group's key.

The whole month is contractual. `as_of` and `trade_date` do not shorten the schedule.
Preparation distinguishes fixed from live observations; it does not rebuild their dates
or renormalize the surviving weights. A booked monthly quantity of 2,200 with 22 pricing
days contributes 100 units per observation. After one fixes, live exposure is 2,100.

A closed calendar month-end simply contributes no observation. The last eligible day
is the payment anchor. Do not copy an expiry-based rule that requires an observation on
the month's final calendar day. Existing reference and coverage checks still apply to
every generated observation. An NG or WTI schedule that does not price the full booked
month with that component's own reference remains unsupported in this slice.

## Pipeline and implementation boundary

Public signatures and handles stay unchanged:

```text
_CreateTradeTemplate(instrument, fields, values)
_CreateTrades(index, fields, trade_rows, template)
_PrepareTrades(trades, history)
_EvaluateTrades(prepared, market)
_ReportValues(results)
_ReportRisk(results)
```

`CreateTrades` resolves the month and generates observations once, then uses the shared
encoding and payment path. Quantity conversions and the fixed leg are computed once per
component. The encoded `offset` remains minus the signed quantity coefficient times
`fixed_price`; observation expansion must not multiply that amount by the day count.

`PrepareTrades` applies history to the dated slots. An observation is live on its own
date and fixed when its date precedes `as_of`, under the existing cutoff. Its contribution
then joins `floating_leg_set` and leaves `floating_leg_live`. A missing required fixing
still fails. Fully fixed amounts stay in mark until their payment date, then become
cumulative cash under the current model.

`EvaluateTrades` reads each distinct live reference once and projects its live slots.
A tick does no date generation, quantity conversion, fixed-leg construction or fixing
folding. A changed history requires an explicit new preparation; evaluation never
prepares implicitly. Preserve both identity checks and price-vector alignment checks.

Keep the existing stable contract delta vector, dated live contents, scalar value and
risk reports, and `util_ReadHandle` inspection path. Fixed observations have zero live
delta. Readers access saved results without repricing. Cleared mark is undiscounted and
cleared DV01 remains zero under this model.

Expected implementation is the method definition and dispatch, observation construction,
and passing already-resolved months to that construction if needed. PR #157's variable
observation counts and last-observation anchors should make shared payment, preparation
and evaluation reusable. Do not add an Asian-specific evaluator or a new cache.

## Worked acceptance example

Use a synthetic month-aligned ethane index with `VOLUME`, base quantity unit `GAL`,
quote quantity unit `GAL`, quote currency `USD` and settlement currency `USD`. Its quantity
specifications explicitly contain a row named `GAL`, size 1 in unit `GAL`. Thus the ticket's quantities are gallons
and its prices are USD per gallon; the name alone never determines that size.

| Contract | Supplied expiry | Role |
|---|---|---|
| X26 | 2026-11-30 | Preceding boundary |
| Z26 | 2026-12-31 | December component |
| F27 | 2027-01-29 | January component and later live reference |
| G27 | 2027-02-26 | Later reference for lifecycle coverage |

The pricing calendar closes **25 December 2026 and 1 January 2027**, plus weekends.
The payment calendar closes **1 January 2027**, plus weekends. These are the entire
synthetic holiday lists. Use `payment_time_lag = +2bd`.

December has **22 observations**: 1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21,
22, 23, 24, 28, 29, 30 and 31 December. Weight is `1/22`. Payment is **5 January 2027**:
1 January is closed, 4 January is the first payment business day, and 5 January the second.

The template supplies the financial cleared profile, `schedule_method = asian`,
`quantity_unit = GAL`, `quantity_per = month`, `clearing_house = Prototype Clearing`,
the lag and the payment-calendar reference. Both rows have `trade_date = 2026-11-20`:

| trade_id | contract_code | quantity | fixed_price |
|---|---|---:|---:|
| A | Z26 | 4400 | 0.25 |
| B | Z26 | -2200 | 0.26 |

A contributes 200 gallons per date and B contributes -100. Compression produces
**22 slots of 100** and fixed leg amount `-4400 * 0.25 + 2200 * 0.26 = -528 USD`.

Use a Z26 live projection of **0.28**, F27 **0.30**, and G27 **0.32**. After each market
roll, the supplied positional vector starts at the appropriate live contract as it does
today. Later references keep the market valid when these trades have no live exposure.

Supply complete histories, newest first at entry, using this synthetic daily series:

| Pricing dates | Daily underlying fixing |
|---|---:|
| 30 November, preceding boundary date | 0.28 |
| 1 December | 0.24 |
| 2 December | 0.30 |
| Every other December observation except 31 December | 0.28 |
| 31 December | 0.26 |
| January pricing days needed by a lifecycle state | 0.30 |

Each history contains the required prefix before its `as_of`, including the 30 November
entry. That preceding fixing supplies a nonblank Excel range for the 1 December state;
the history ignores it because its calendar starts on 1 December. It contributes to no
Asian observation. For 5 January the prefix includes the 4 January fixing belonging to
F27. There are no fixings for closed days.

Mark and cash below are USD. Delta is USD per (USD/GAL), with respect to the supplied
projection input. The stable reference axis for this batch is Z26.

| as_of | Fixed observations | cleared_mark | cleared_cash | Z26 delta |
|---|---:|---:|---:|---:|
| 2026-12-01 | 0 | 88 | 0 | 2200 |
| 2026-12-02 | 1 | 84 | 0 | 2100 |
| 2026-12-03 | 2 | 86 | 0 | 2000 |
| 2026-12-25 | 18 | 86 | 0 | 400 |
| 2026-12-31 | 21; final observation still live | 86 | 0 | 100 |
| 2027-01-01 | 22; fixed and unpaid | 84 | 0 | 0 |
| 2027-01-04 | 22; still unpaid | 84 | 0 | 0 |
| 2027-01-05 | 22; paid | 0 | 84 | 0 |

For 2 December: `-528 + 100 * 0.24 + 2100 * 0.28 = 84`.
The final payment is `-528 + 100 * (0.24 + 0.30 + 19 * 0.28 + 0.26) = 84`.

- At 2 December, a Z26 projection tick from 0.28 to 0.29 gives mark **105**, using the
  same preparation and delta 2,100. Retain the old result and verify it still reads 84.
- At that date, correcting the 1 December fixing from 0.24 to 0.25, with projection
  unchanged at 0.28, gives mark **85** after explicit preparation against the new history.
  The old preparation refuses a market over that history.
- In a separate batch, also close 4 January on the payment calendar: payment becomes
  **6 January**. Observation dates and weights stay unchanged; on 5 January mark is
  84 and cash is zero, then mark is zero and cash 84 on 6 January.

## Strips and varying observation counts

At 1 December, create a separate `Z26-F27` strip with quantity **2,200 per month** and
fixed price **0.25**, using the same synthetic index and calendars.

| Component | Observation count | Weight per date | Exposure per date | Payment anchor | Payment |
|---|---:|---:|---:|---|---|
| Z26 | 22 | 1/22 | 100 | 2026-12-31 | 2027-01-05 |
| F27 | 20 | 1/20 | 110 | 2027-01-29 | 2027-02-02 |

January's observations are its weekdays from 4 through 29 January; the 1st is closed
and the month ends on a weekend. There are **42 observations**, two component fixed
legs and two payments. Weights must not be normalized over all 42 dates together.

At projections `[0.28, 0.30]`, aggregate mark is
`2200 * (0.28 - 0.25) + 2200 * (0.30 - 0.25) = 176`, cash zero and delta
**[2200, 2200]**, on `[Z26, F27]`. Duplicate the row: mark **352** and delta
**[4400, 4400]**. Exercise actual creation and its payment anchors, not just manually
constructed kernel records.

## Acceptance and delivery

1. **Discovery and booking.** `asian` works in template or ticket under existing strict
   headers and disjoint-source rules. Update instrument help and relevant function/kernel
   pages to specify the calendar month, equal publication-day weights, payment anchor,
   input-price meaning and supported settlement. No public field or signature changes.
2. **Dates and refusals.** Pin the full month, excluded holidays/weekends, varying counts
   and payment dates above. Cover a month with no eligible pricing days and a month that
   crosses into another pricing reference. Refuse visibly, naming the offending contract
   and date or month. Preserve boundary-contract and missing-fixing failures. Do not
   silently accept a partial monthly schedule.
3. **Independent economics.** Pin the lifecycle, tick, correction and strip answers at
   the kernel and registered-function boundaries. Verify the contract delta vector and
   dated exposures as well as the scalar totals. These hand answers precede implementation;
   do not generate the expected answers using the new observation builder.
4. **Cardinality and compression.** Compatible singletons sum to the same batch result
   on aligned reference axes. Row permutation preserves economics, duplicates count and
   zero quantities remain fully validated. Different fixed prices still compress correctly.
5. **Reuse and regressions.** Pin zero observation generation, fixed-leg construction
   and fixing folding during a tick. A history change requires a new preparation. Existing
   `lastday`, `penultimate`, `last3day`, zero-quantity and unit-selection cases retain
   their behavior except for the expanded supported-method list.
6. **Excel and work.** Keep one working example in the existing workbook with sufficient
   spill space, and exercise the public path in existing smoke/host coverage. Measure
   components, observations, compressed slots and distinct live references using the
   existing work/allocation harness. Generate compact observations, not a dense
   trades-by-full-market-calendar matrix. Explain changed creation/preparation counts;
   do not raise ceilings just to pass. Run the full repository gate.

Follow the repository's separate review rule for any existing golden baseline changes.
Keep this PR focused on the method; additional hardening must relate to behavior this
slice introduces or exposes. Completion is an end-to-end Asian booking with independently
checked lifecycle and strip values, preserved tick reuse, and inspectable saved risk.

After this slice, discuss mixed methods and payment groups using the actual implementations.
Broader pricing references and conversion from whole-month quotes remain explicit follow-ups.

## As built, #158

Built as the page says, on the path the other methods take, with these particulars.

- **The month.** The resolution reads each schedule code for its month once, as it did, through
  `schedule_months` in `src/goosedove/trades/resolution.py`, now a public reader, and hands the
  months to `observed` as a fourth argument, one per schedule row as numpy counts months; the
  asian method takes each component's month from them and reads no code again. The three
  one-day and three-day methods ignore the months.
- **The observations.** `observed` in `src/goosedove/trades/observations.py` gives `asian` every
  Monday to Friday of the component's calendar month the index's market is open on, an equal
  share each: one `numpy.busday_count` over the components for the days of each month, and one
  `numpy.busday_offset` over the observations, the month's first day rolled forward and counted
  on, the weights `1 / N` per component. A month with no pricing day is refused by its
  contract, `G27 has no pricing day in 2027-02, expected a Monday to Friday of its month the
  index's market is open on; the asian method averages the pricing days of the contract's
  month`. A closed month-end is simply no observation, and the last eligible day is the payment
  anchor through #157's `_last_days`. A day that another contract prices is the encoding's
  existing refusal, `trade 'A' at row 1 observes Z26 on 2026-12-01, a day F27 prices; an
  observation of a contract other than the day's pricing contract has no settle in a futures
  history, not supported`, and nothing is truncated or substituted. Superseded in #NN: an
  asian day another contract prices takes that contract as its reference, the booked contract
  keeping the fixed leg and the payment,
  [calendar-driven-asian-references.md](calendar-driven-asian-references.md).
- **The settlement and the words.** A physical `asian` is refused by the kernel by
  `settlement_method`: `settlement_method is 'physical', expected 'financial' with the asian
  method; an asian future is cash settled on the average of its month's pricing days`. With all
  four methods of the definition built, the method choice reads `expected lastday, penultimate,
  last3day or asian`, and a word that is none of them, `Asian` among them, is refused by name;
  the `future` definition's rule says the four are built, in words kept short since the Show spill's allocation pin follows the length of its texts, and `_ShowInstrument` shows it.
- **The live input.** As the page says above, a monthly live input projects the month's
  remaining unfixed days at a common price, and the history supplies the daily prices averaged;
  the market performs no conversion from a quote of the whole month's average, and the delta is
  to the projection input. [evaluate-trades.md](../../library/trades/evaluate-trades.md) says the
  same beside the vector's positional limit, and the kept workbook's note beside the example.
- **Nothing else changed.** The encoding, the preparation, the evaluation, the readers and the
  reports are as they were; a component's 22 slots are slots like any other, and a tick runs the
  evaluation alone, as the budgets pin. The NG, penultimate, last3day, zero-quantity and
  quantity-selection examples keep every number, date and refusal, the method list apart.
- **Where it is proved.** The worked example, the tick, the correction, the payment calendar
  closed on the 4th, the strip, its duplicate, the singletons in either order, the row kept
  ready and the three refusals are pinned to the page's numbers in `tests/unit/test_trades.py`
  at the kernel, `tests/unit/test_create_trades.py` through resolution and
  `tests/unit/test_trade_valuation.py` through the registered worksheet functions; the work
  counts and the ledgers in `tests/performance/test_trade_creation_budgets.py` and
  `test_trade_budgets.py`, over an index whose contracts price their whole months; the public
  path on a sheet in `tools/excel_smoke.ps1`, from the host in
  `host/Goosedove.Host.Tests/CallTests.cs`, and in the kept workbook's asian block at the foot
  of the handles sheet.
