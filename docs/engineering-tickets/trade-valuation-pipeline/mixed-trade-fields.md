# Mixed fields in one trade batch

[Pipeline overview](README.md) · [Multiple payment groups](multiple-payment-groups.md)

**Status:** Built in #NN on the prototype stack above #162, the page as a ticket; the
[As built](#as-built-nn) section at the end says what was built and what was not. Written
8 October 2026 as the next prototype slice after PR #162, reviewed at `fa7cb93`, a
continuation of the prototype that does not decide how the full stack will land or what
will be rebuilt on main.

**Suggested PR title:** `feat(trades): allow mixed methods and quantity terms in a batch`

## Outcome

Allow `schedule_method`, `quantity_unit` and `quantity_per` to vary by row in one
`_CreateTrades` call. Resolve every row into dated exposures in the index's common
quote units, then compress and value the batch through the existing pipeline.

#162 supplies the necessary payment ownership: components on one contract can belong
to different payment groups. This slice removes three remaining batch-wide choices.
It does not implement separate evaluations by method and add their answers together.

## Entry and retained boundaries

Keep the existing functions and signatures:

```text
_CreateTradeTemplate(instrument, fields, values)
_CreateTrades(index, fields, trade_rows, template)
_PrepareTrades(trades, history)
_EvaluateTrades(prepared, market)
_ReportValues(results)
_ReportRisk(results)
```

The template remains required and carries the instrument; the supplied index belongs
to the batch. Any of the three fields can be supplied once by the template or as a
complete ticket column. A varying field belongs in the ticket. Template/ticket
overlap still fails even when values agree; blanks do not inherit template values.
Keep exact headers and the existing field types and choice spellings.

| Field | Behavior in this PR |
|---|---|
| `schedule_method` | Per row: `lastday`, `penultimate`, `last3day`, `asian` |
| `quantity_unit` | Per row: an exact specification name from the supplied index |
| `quantity_per` | Per row: `month` or `calday` |
| `payment_time_lag`, `payment_holiday_calendar` | Already per row; preserve and exercise with mixed methods |
| `clearing_house` | Already per row; preserve and demonstrate in the mixed ticket |
| Index, instrument, `route`, `settlement_method` | One of each per batch, unchanged |

`clearing_house` remains attribution. It selects no product, schedule, settlement
method, calendar or conversion, and compression makes no legal netting claim. Add no
`exchange` field. `payment_date` remains a resolved component date, not a new input.

Keep one period-entry form per batch: `contract_code`, or complete `start_date` and
`end_date` fields. Different rows may cover different periods. Partial components are
supported by `asian`; the other methods still require whole months. Explicit dates
can therefore describe a partial Asian row beside a whole-month `lastday` row. Do not
introduce blank-based switching between codes and dates, a new `exact` enum, or moving
BAL periods.

Physical batches retain `lastday` only, no payment terms, and the existing refusal
after expiry. Bilateral creation retains its existing behavior; evaluation still
refuses until rates are implemented. Keep the single history, own-contract observation
rule and market identity checks. This PR adds no discounting, DV01 convention, physical
delivery, margining or new instrument.

## Resolution and static encoding

Retain each occurrence's resolved method, specification selection and quantity basis.
An occurrence is one ticket row; a component is one of its contract months. Every
component of a strip inherits the choices of its owning occurrence. Use typed,
immutable selections and the existing occurrence mapping. Replace the current scalar
batch assumptions rather than maintain parallel uniform and mixed implementations.
The exact record layout is engineering's choice.

Resolve distinct field values once during creation and gather the results onto rows
and components. `quantity_unit` is still an exact specification name, not arbitrary
text accepted merely because a unit-conversion table knows it. Do not infer a
specification from a clearing-house label or select the first specification as a
fallback. Specification fees remain reserves and do not affect valuation.

For each component, form its quantity once:

```text
component_quantity = entered_quantity                         # month
component_quantity = entered_quantity * covered_calendar_days # calday

quote_quantity = component_quantity * selected_lot_size * conversion_to_quote_unit
coefficient = quote_quantity * conversion_to_settlement_currency
fixed_leg = -coefficient * fixed_price
```

`covered_calendar_days` includes both endpoints, weekends and holidays. `month` gives
the full entered quantity to each monthly component, including a partial month; it
neither prorates nor distributes one total over a strip. Observation counts and
averaging weights never determine this quantity multiplier. Apply the day multiplier
only to `calday` components; an unused multiplication must not overflow a `month` row.

Input quantities remain signed whole counts, including zero, of the selected
specification. Conversion can produce fractional quote quantities. `fixed_price`
remains in the index's quote units for every row; changing `quantity_unit` does not
change the meaning of the price. Preserve the existing finite expanded-quantity
refusal and sign handling.

Compute conversion factors for the distinct selections needed by the batch, then
apply them as arrays. There is no unit lookup, basis expansion or fixed-leg rebuild
during preparation or on a price tick.

## Observation rules and common compression

Apply each component's method using the existing observation rules. Dispatching over
the finite set of methods during creation is appropriate; invoking the entire
creation/evaluation pipeline separately for each row or method is not.

Each component's weights sum to one over its own observations. After any method
partitioning, restore original global component IDs and component/date order before
deriving payment anchors. The existing last-observation lookup depends on that order.
Keep error provenance attached to the original ticket row, including strip components.

Derive payment from each component's own last observation and its owning row's lag and
calendar. Then use #162's financial grouping and slot rules unchanged:

```text
payment group = (contract reference, resolved payment date)
dated slot    = (payment group, observation date)
slot exposure = sum(coefficient * observation weight)
group fixed leg = sum(component fixed leg)
```

Different methods, specifications, quantity bases and clearing-house labels are not
additional grouping keys. Once converted, compatible exposures can share a slot. Two
rows observing the same date but paying on different dates remain separate slots.
Keep the stable risk axis as distinct contract references, not payment groups or
method groups.

Preparation applies fixings and payment state to these arrays. Evaluation gathers
distinct live quotes, multiplies exposures and aggregates. It needs no new dispatch
on method, specification or quantity basis, and a tick does no preparation work.

## Saved state and readers

`util_ReadHandle(trades)` must show the actual method, quantity-unit name and quantity
basis for each component's owning row in its existing columns. A strip must not show
row 1's choices on another row's components. Keep entered quantities distinguishable
from expanded component quantities through the existing readback.

Prepared/result debug spills already expose observation dates and financial payment
dates. Their layout needs no expansion for these three fields. Keep
`_ReportValues`' aggregate mark/cash and `_ReportRisk`'s aggregate delta/cleared zero
DV01. Retain the immutable contract delta vector for reuse; no per-trade valuation
report is part of this slice.

## Hand-priced mixed example

Use a synthetic month-aligned futures index quoted and settled in USD, with quote
quantity unit GAL. This fixture is not an exchange contract specification. Its two
specifications are `GAL` (size 1, unit GAL) and `BBL` (size 1, unit BBL); the conversion
is 42 GAL per BBL.

The schedule has X26 expiring 30 November 2026 as its preceding boundary, Z26 expiring
31 December 2026, and F27 expiring 29 January 2027 to keep the market valid through
payment. Pricing days are Monday-Friday excluding 25 December. Payment days are
Monday-Friday excluding 1 January 2027. December has 31 calendar days and 22 pricing
days; Z26 prices every observation used below.

Create the template with instrument `future`. Its shared fields are `route = cleared`,
`settlement_method = financial`, `trade_date = 2026-11-30`, `fixed_price = 10`,
`payment_time_lag = +1bd` and the payment-calendar handle. Supply the following ticket
fields in one call. The two clearing-house labels are deliberately just labels in
this fixture.

| trade_id | contract_code | quantity | quantity_unit | quantity_per | schedule_method | clearing_house |
|---|---|---:|---|---|---|---|
| A | Z26 | 1 | BBL | month | lastday | Clearer A |
| B | Z26 | -2 | GAL | calday | penultimate | Clearer B |
| C | Z26 | 3 | BBL | month | last3day | Clearer A |
| D | Z26 | 22 | GAL | month | asian | Clearer B |

Creation gives:

| Trade | Quantity in GAL | Observation exposure in GAL | Fixed leg in USD | Payment date |
|---|---:|---|---:|---|
| A | 42 | 42 on 31 Dec | -420 | 4 Jan 2027 |
| B | -62 | -62 on 30 Dec | 620 | 31 Dec 2026 |
| C | 126 | 42 on each of 29, 30, 31 Dec | -1260 | 4 Jan 2027 |
| D | 22 | 1 on each of December's 22 pricing days | -220 | 4 Jan 2027 |

The compressed exposure table, with repeated equal slots abbreviated for display:

| Payment date | Observation dates | Number of slots | Exposure per slot |
|---|---|---:|---:|
| 31 Dec | 30 Dec | 1 | -62 |
| 4 Jan | Pricing days from 1 through 28 Dec | 19 | 1 |
| 4 Jan | 29 Dec | 1 | 43 |
| 4 Jan | 30 Dec | 1 | 43 |
| 4 Jan | 31 Dec | 1 | 85 |

There are four occurrences/components, 27 uncompressed observations, two payment
groups, 23 compressed slots and one market reference. Group fixed legs are +620
for 31 December and -1900 for 4 January. Group exposures total -62 and 190, giving
initial Z26 delta 128. This exercises compression across methods and quantity units,
while keeping the two 30 December slots separate by payment ownership.

Use a live Z26 projection of 12 and a fixing of 11 on every past observation day.
An observation stays live on its own date and fixes the following day. Supply complete
history and the later F27 market inputs required by the existing market; the whole
calendar has not ended.

| as_of | cleared_mark | cleared_cash | Z26 delta | Reason |
|---|---:|---:|---:|---|
| 2026-12-01 | 256 | 0 | 128 | Everything live: -1280 + 128 x 12 |
| 2026-12-30 | 194 | 0 | 66 | 29 Dec and earlier fixed; penultimate still live |
| 2026-12-31 | 275 | -62 | 85 | Penultimate paid; the other group still has live exposure |
| 2027-01-01 | 190 | -62 | 0 | Remaining amount fixed, but unpaid |
| 2027-01-04 | 0 | 128 | 0 | Both payments in cumulative cash |

The final amounts are A = 42, B = -62, C = 126 and D = 22: each normalized quantity
times `11 - 10`. Delta rises from 66 to 85 when the negative penultimate exposure fixes,
despite other exposure also fixing. Signed delta need not decrease monotonically.

On 30 December, a tick from 12 to 13 changes mark from 194 to 260 over the same
preparation; delta stays 66 and only one live reference is read. With live price still
12, correcting 29 December's fixing from 11 to 12 requires new preparation and changes
mark to 237: the correction affects C's 42 and D's 1, a total exposure of 43.

## Acceptance beyond the example

- **One path and correct aggregation.** At each lifecycle state, the mixed batch equals
  the sum of singletons, including aligned contract risk vectors. Test reordered rows,
  duplicates, opposite signs, zero quantities, multiple contracts and strips spanning
  months of different lengths. Use the independent hand amounts above as the financial
  oracle; batch/singleton agreement alone cannot establish correctness.
- **Equivalent quantities compress.** Re-express A as 42 GAL/month and obtain identical
  values, slots and risk. Also include a selected specification with lot size greater
  than one and a cent-quoted example settling in dollars, so conversion is not tested
  solely through unit-size USD specifications. Choosing a quantity unit must not change
  how fixed prices or market prices are interpreted.
- **Payment conventions combine correctly.** Retain #162's different-lag and
  different-calendar cases with mixed methods. Equal resulting payment dates coalesce;
  different dates remain separate. Verify that shared clearing-house labels neither
  force grouping nor prevent it when labels differ.
- **Explicit periods and row ownership.** Mix a partial Asian row with whole-month
  rows using other methods, all through the date-entry form. Check `month` and `calday`
  quantities separately. Reject a partial non-Asian component at its original row.
  Include interleaved methods and a multi-month row so subgroup-local component IDs or
  quantities cannot accidentally line up and pass.
- **Template and ticket agree.** A uniform field supplied by the template and the same
  field repeated in a separate valid ticket give the same economics. The uniform case
  uses the mixed-capable path, including one row. Supplying the field in both still
  refuses; unknown headers, invalid choices, unknown specification names and blanks
  keep their strict behavior.
- **Refusals preserve provenance.** Within each validation stage, reject the first
  offending original row/component rather than the first enum or specification bucket
  processed. Preserve the existing stage order and name the field and row where
  applicable. An invalid zero-quantity row still fails; failure publishes no trade
  handle. Keep physical/method incompatibility and route/settlement uniformity explicit.
- **No hidden tick work.** A tick uses the same preparation, reads each distinct live
  reference once and rebuilds no observations, payment dates, unit factors or fixed
  legs. Fixing corrections and as_of changes require new preparation over the same
  static encoding. Existing identity and live-price coverage failures remain loud.

## Implementation and delivery

The main changes are in `trades/resolution.py` and `trades/terms.py` (scalar batch
choices become row selections), `trades/observations.py` (method dispatch and assembly),
`trades/encoding.py` (component conversion factors) and `excel/utilities.py` (accurate
trade readback). The common payment grouping, preparation and evaluation remain the
consumers of normalized arrays. Adapt consumers as necessary without creating another
pricing path or imposing method-based payment groups.

Report meaningful work counts for distinct selections, components, observations,
groups, slots and live references. Extend the existing work/allocation tests to a
repeated large mixed ticket: repeated rows should add economics without multiplying
distinct-value resolution or conversion lookups. Avoid a dense trade-by-day matrix,
per-row numerical loops and persistent caches introduced solely for this slice.
Report changed retained memory and before/after counts; wall-clock timings are not gates.

Deliver one focused PR stacked above the reviewed #162 head, or its successor if the
stack has moved. Include the mixed example through public creators and reports in the
kept workbook, with trade readback and both payment groups inspectable. Update relevant
host/smoke assertions and current instrument, creation, kernel and packet documentation
to remove only the three obsolete uniformity restrictions. Existing golden changes
follow the repository's separate-review rule. Run `check.ps1`.

Completion means one mixed ticket produces the hand-priced lifecycle, preserves every
row's meaning in readback, and reaches the same compressed evaluation path as one
trade. The next step is realistic mixed-batch Excel UAT and a review of the prototype's
shape before adding bilateral rates or deciding what to rebuild on main.

## As built, #NN

Engineering's record of what landed, in the ticket's terms.
[create-trades.md](../../library/trades/create-trades.md) and
[kernel.md](../../library/trades/kernel.md) are the pages.

- **The selections.** The kernel's `ResolvedTrades` keeps `specification`, `schedule_method` and
  `quantity_per` per occurrence, each an array of positions among the members, `METHODS` and
  `BASES` in the definition's order and the index's specification rows, so that the kernel gathers
  and compares positions and never texts and a reader turns a position back into its name;
  `one_choice` gives a batch whose rows all chose alike its arrays, and the tests use it. The
  resolution reads each distinct text of the three fields once, through the one distinct-text
  reader the codes and the lags already use, in the order its first row comes, so that the first
  offending row is the one named, and gathers the rows; the route and the settlement stay one
  across the batch, and `one_text` serves them alone. The `a batch has one quantity_unit` refusal
  is gone; a selection not one per occurrence or out of range is refused by its row in the kernel.
- **The observations.** `observed` takes each component's method. The whole-month rule is looked
  at over the expiry-based components in their order and the open-expiry rule over the penultimate
  and last3day ones, so the first component at fault is named with its own method; each method
  present makes its components' observations once, the finite set dispatched over and never the
  rows; when the batch mixes methods the observations are put back in component order and by day,
  one lexsort, since the payment anchors are found by that order, and a batch of one method is in
  order as made. The index's holiday calendar is typed once per batch for the methods that read it,
  lastday batches now included.
- **The encoding and the readback.** The lot size and the unit factor are formed once per distinct
  specification the batch selects and gathered onto the components; the payment grouping, the
  slots, the preparation and the tick are untouched, a mixed batch valuing through the one path.
  The trades spill shows each row's own method, unit and basis, a strip's components their owning
  row's. The prepared and results spills are as #162 left them.
- **The numbers pinned.** The ticket's example on the MIXED index, USD per GAL with GAL and BBL of
  one unit each, X26, Z26, F27 and G27, the market closed on 25 December and the payment calendar
  on New Year's Day: 42, -62, 126 and 22 gallons of quote quantity, the fixed legs -420, 620,
  -1,260 and -220, two groups of Z26, B paying the 31st and the rest 4 January, 27 observations
  into 23 slots, a gallon on each of nineteen days, 43 on the 29th and the 30th and 85 on the 31st
  beside B's -62 on the 30th, one reference; 256 and 128 on 1 December, 194 and 66 on the 30th,
  275 of mark with -62 of cash and 85 on the 31st, 190 unpaid on 1 January, 128 of cash on the 4th;
  a tick to 260 on the same preparation, the 29th corrected to 12 taking a new history and 237.
  The singletons summed in every state and order, with a duplicate, a row kept ready and a strip of
  a gallon a day over January and February, 93 + 112 of mark and 31 and 28 of delta on two more
  contracts; A as 42 gallons a month identical in encoding and value; a lot of ten thousand beside
  ten thousand units on a cent-quoted index, one slot of 200 and 2,000 dollars ten cents up, the
  price in cents for both rows; the clearing labels swapped changing nothing, B at +2bd coalescing
  into one group of 22 slots, A on a payment calendar closed on 4 January a third group; a partial
  asian row beside a whole lastday month, 84 of mark beside 15 of cash and 42 of delta on
  16 December, a partial penultimate row refused by its contract, its days and its own method;
  interleaved methods with a strip keeping component order and anchors, S's F27 paying 1 February;
  a physical batch with a penultimate row refused by that method, one of lastday rows mixing units
  and bases standing; a method not one per component refused. The same through the creator and the
  seam, the readback row by row with a strip showing its own row's choices, a uniform field from
  the template or the ticket alike and both refused, the refusals naming the first offending row;
  and on the host, in the smoke and in the kept workbook.
- **The work.** The resolution's ledger: `_each_distinct` five times for two, `_Fields.one_text`
  twice for five, `_the_selections` for `_the_batch`, `_frozen_rows` five for two, `_the_days` and
  `with_holiday_calendar` once; its numpy six more looks, six more sorts and three more conversions
  for the three distinct reads, three more frozen copies, numpy's unique over the methods present,
  nine more arrays and seventeen more `asanyarray`s, measured and pinned with the reasons. The
  mixed ticket's ledger reads two units, four methods and two bases once each, makes the four
  methods once each and nothing per row, the same at eight rows and at two thousand. The mixed
  batch of two thousand trades over twenty-four contracts: 48 groups, 13,071 observations, 543
  slots, four methods dispatched once each, two conversions, the preparation and the tick as any
  batch's; peaks 45,298 and 11,440 bytes, within 90 and 24 a slot. The 2,500-row batch's creation
  peak 569,243 to 668,580 bytes, the three selections 24 bytes a row retained and their distinct
  reads' temporaries, the pin 232 to 272 a row.
- **Not in this slice.** No mixed route or settlement in one batch; no discounting, DV01
  convention, delivery or margining; bilateral evaluation still refused; no `exact` method, no
  blank-based switching between codes and dates, no moving BAL periods; the lifetime example not
  extended, the smoke, the host and the kept workbook carrying the mixed example.
