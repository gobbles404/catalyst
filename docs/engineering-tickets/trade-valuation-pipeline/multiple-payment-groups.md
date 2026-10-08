# Multiple payment dates in one trade batch

[Pipeline overview](README.md) · [Trade periods and BAL](trade-periods-and-bal.md)

**Status:** Next prototype slice, 8 October 2026. Implement as one focused PR after
PR #161, reviewed at `3f6c93b`. This is a continuation of the prototype, with no decision
to merge the full stack or rebuild it on main.

## Outcome and reason for this slice

Allow two financial trade components on the same contract to have different payment
dates in one `_CreateTrades` batch. Keep their amounts separate until each payment has
moved from mark to cash, while reporting aggregate values and one delta per contract.

Today creation resolves a payment date for every component, using its last observation,
payment lag and payment holiday calendar. Encoding then groups solely by contract and
refuses differing payment dates. Remove that grouping restriction. The rule that a
payment must follow the group's last observation remains.

This is the foundation for mixed row terms. For example, `lastday` and `penultimate`
on the same contract can produce different payment dates even with the same lag. First
make payment ownership correct, using the methods and row inputs already available;
then allow schedule method, quantity unit and quantity basis to vary within a batch.

## Scope and existing boundaries

Use the existing pipeline and signatures:

```text
_CreateTradeTemplate(instrument, fields, values)
_CreateTrades(index, fields, trade_rows, template)
_PrepareTrades(trades, history)
_EvaluateTrades(prepared, market)
_ReportValues(results)
_ReportRisk(results)
```

`payment_time_lag` and `payment_holiday_calendar` already accept values per ticket row.
Use them to produce different dates. Explicit Asian period ends can also produce
different dates. Add no worksheet field or new function: `payment_date` remains a
resolved fact, rather than a new trade-entry parameter.

Keep one index, instrument, route, settlement method, schedule method, quantity-unit
selection and quantity basis per batch. Keep strict headers, template/ticket disjointness,
and the existing choice of contract-code entry or complete date entry. Clearing-house
labels already vary by row and keep their current meaning.

The valuation example is cleared and financial. Physical futures retain their existing
contract grouping, no payment terms, and loud refusal after expiry. Bilateral creation
continues through its existing path; bilateral evaluation still refuses pending rates.
No discounting, DV01 convention, mixed route, delivery or margining work belongs here.

## Payment groups and compression

For the financial profile, a payment group is identified by:

```text
(resolved contract reference, resolved payment date)
```

Index, currency, route and settlement method are already shared within this batch. Do
not add speculative rate-curve or currency machinery. Revisit the grouping key when
bilateral valuation or those broader batch boundaries are implemented.

Group by the resulting date, not the text of the lag or the identity of its calendar.
Two different payment conventions that produce the same date can share a group. Preserve
the original component terms for inspection. Do not group by trade ID or occurrence:
duplicate rows still contribute, and compatible rows still compress.

Keep these axes distinct:

| Axis | Meaning | Example |
|---|---|---|
| Component | A trade row's monthly component, with its dates, quantity and fixed leg | Two components both reference Z26 |
| Payment group | Components sharing contract and payment date | Z26 paying 7 December; Z26 paying 9 December |
| Dated slot | Observation date within one payment group | 2 December in each of those groups is two slots |
| Market reference and risk | Unique contract reference, shared across groups | One Z26 quote and one Z26 delta |

Build financial groups in deterministic order: schedule contract order, then payment
date. Order slots by group, then observation date. Keep component-to-group,
observation-to-slot and slot-to-market-reference mappings. Preserve the existing rule
that each observation references its component's own contract.

The same contract can occur in multiple groups, but appears once on the stable risk axis.
Audit code that currently treats `encoded.groups` as both a payment-group axis and a
list of unique contracts. Array names are engineering's choice; the distinctions above
must be explicit in their definitions and consumers.

## Work at each pipeline boundary

**Creation and encoding.** Resolve dates and payment terms once through the existing
path. Form the payment groups, sum each component's fixed leg into its own group, and
compress observation exposures by `(payment group, observation date)`. The encoded
`offset` remains the existing representation of the signed fixed leg. Do not add it once
per observation, or net it across different payment dates. Validate payment strictly
after the last observation of each group.

**Preparation.** Apply fixings to slots and sum `floating_leg_set` by payment group
(currently named `set_amount` in the kernel). Determine payment state independently for
each group: all its observations have fixed, and its payment date is on or before
`as_of`. One group may be cash while another on the same contract remains unpaid or
still has live observations. Fixing is not payment.

Retain enough group state to explain that split. Existing aggregate prepared sums can
remain where they support this undiscounted evaluation; per-group valuation result
vectors need not be added just to anticipate discounting.

**Evaluation.** Read each distinct live contract quote once, gather it onto the live
slots, and calculate `floating_leg_live`. Aggregate mark only from unpaid groups and
cash only from paid groups. Keep the existing preparation reuse and history/index
identity checks: a tick never rebuilds payment groups, reads fixings, or silently
prepares again. An `as_of` change or fixing correction needs new preparation over the
same static encoding.

**Results and readers.** Keep the immutable contract delta vector, with all groups'
remaining exposure summed onto the stable unique-contract axis. A fixed but unpaid
group has zero forward delta and can still have mark. `_ReportValues` continues to
spill aggregate `cleared_mark` and `cleared_cash`; `_ReportRisk` continues to spill
aggregate delta and the cleared model's zero DV01. Cash retains its cumulative modeled
meaning. Do not introduce a report per trade or payment group.

For inspection, show `payment_date` alongside financial slots in `util_ReadHandle` for
prepared and result handles. Otherwise two rows with the same contract and observation
date cannot be distinguished. Gather that date from retained state; add no repricing.
Keep the physical readback free of invented dates. Update affected workbook references
and tests when the financial spill gains a column. The debug spill's repeated
`contract_delta` is still the contract total, not an additive slot value; the stored
risk vector contains each contract once.

## Worked acceptance example

Use a synthetic USD-quoted index with one unit per specification quantity and no unit or
currency conversion. Pricing and payment calendars are Monday to Friday, with no
holidays in this fixture. These are test terms, not an exchange product specification.

| Schedule code | Expiry | Purpose |
|---|---|---|
| X26 | 2026-11-30 | Preceding boundary contract |
| Z26 | 2026-12-04 | Traded contract |
| F27 | 2027-01-08 | Keeps the market valid through both payments |

Both rows are booked on 2026-11-30, `cleared`, `financial`, `last3day`, `quantity_per =
month`, with one shared unit-size specification and clearing-house label. The template
supplies those shared fields; the ticket supplies trade ID, contract, quantity, fixed
price and payment lag. The template supplies the common payment calendar.

| Trade | Contract | Signed quantity | Fixed price | Payment lag | Resolved payment date |
|---|---|---:|---:|---|---|
| A | Z26 | 60 | 70 | +1bd | 2026-12-07 |
| B | Z26 | -30 | 72 | +3bd | 2026-12-09 |

Each component observes 2, 3 and 4 December with weight `1/3`. Creation produces:

| Group | Contract | Payment date | Fixed leg | 2 Dec exposure | 3 Dec exposure | 4 Dec exposure |
|---|---|---|---:|---:|---:|---:|
| 0 | Z26 | 7 Dec | -4200 | 20 | 20 | 20 |
| 1 | Z26 | 9 Dec | 2160 | -10 | -10 | -10 |

There are two components, two groups, six observations and six compressed slots, but
only one distinct market reference. Identical dates in different payment groups remain
separate. While all observations are live, contract delta is `60 - 30 = 30`.

Use live Z26 projection 74. Fixings for 2, 3 and 4 December are respectively 71, 75 and
73. An observation remains live on its own day and fixes the next day, as today. Supply
complete history and the later F27 quote/fixings required to keep the market valid;
unrelated days can use 74 and contribute nothing to this batch.

| as_of | cleared_mark | cleared_cash | Z26 delta | Explanation |
|---|---:|---:|---:|---|
| 2026-12-02 | 180 | 0 | 30 | All three observations live |
| 2026-12-03 | 150 | 0 | 20 | First observation fixed at 71 |
| 2026-12-04 | 160 | 0 | 10 | Second fixed at 75; last still live |
| 2026-12-05 | 150 | 0 | 0 | Both final amounts known; neither paid |
| 2026-12-07 | -30 | 180 | 0 | A paid; B still unpaid |
| 2026-12-09 | 0 | 150 | 0 | B paid; cumulative cash is 180 - 30 |

The final average is 73. A pays `60 * (73 - 70) = 180`; B pays
`-30 * (73 - 72) = -30`. These independently explain the mark-to-cash split.

On 3 December, a tick from 74 to 75 increases mark from 150 to 170 over the same
preparation, with delta still 20 and one live price read. Correcting the 2 December
fixing from 71 to 72, with the live projection still 74, requires new preparation and
changes mark from 150 to 160; payment dates, static weights and delta remain unchanged.

## Additional acceptance and regressions

- **Batch equals its singletons.** Every lifecycle state above matches the sum of the
  rows evaluated separately. Include duplicates, reversed ticket order, signs, zero
  quantities under normal validation, and multiple contracts. Compare the aligned
  contract risk vectors as well as scalar totals, with appropriate floating tolerance.
- **Opposite positions cannot disappear across payment dates.** Change B to -60 at 70.
  Before payment aggregate mark and delta are zero, but both groups survive. On 7
  December cash is 180 and mark is -180; on 9 December both are zero. A zero net
  contract exposure must not erase either payment.
- **Matching dates still compress.** Give A and B the same resolved payment date: one
  group and three slots reproduce the existing single-payment answers. Also prove
  different lag/calendar combinations reaching the same date coalesce. For example,
  +1bd with 7 and 8 December closed pays 9 December, as +3bd on the open calendar does.
  Different contracts remain different groups even when they pay on the same date.
- **Partial Asian periods can settle independently.** On the existing month-aligned
  Asian fixture, book two rows on Z26 ending on different pricing days, using the same
  method and lag. With a unit-size specification, no holidays in this window, `month`
  quantities and +2bd, use A covering 1-3 December, +30 at 70, and B covering 1-7
  December, +50 at 70. A pays 7 December; B pays 9 December. All past fixings are 72
  and the live projection is 74. On 7 December, A contributes cash
  `30 * (72 - 70) = 60`; B contributes mark
  `10 * (4 * 72 + 74) - 50 * 70 = 120` and delta 10. Thus aggregate mark is 120,
  cash 60 and Z26 delta 10. This catches retiring a whole contract when only one group
  has paid, which the main example cannot catch because both groups fix together.
  It removes #161's different-end payment refusal without changing its date or quantity
  semantics.
- **One quote serves multiple groups.** Even when a contract contributes live slots in
  several groups, evaluation reads its price once. Check a second contract as well to
  expose accidental confusion between group positions and market-reference positions.
- **Existing refusals retain their meaning.** Payment on or before its group's last
  observation still fails. Missing coverage, wrong index/history, closed observation
  dates, unsupported physical settlement methods and expired physical contracts retain
  their refusals. Bilateral evaluation remains unsupported. Only the refusal of two
  resolved payment dates for one contract is deliberately removed.

Retain the zero entries on the stable contract delta axis after fixing. Keep duplicate
and zero rows' existing behavior, rather than adding a new pruning rule in this slice.

## Implementation map and work budgets

At the reviewed baseline, the change starts in `src/goosedove/trades/encoding.py`:
contract-only grouping and `_one_payment_day_per_group` currently enforce the restriction.
Separate construction of groups from the validation that each group's payment follows
its observations. Review `preparation.py` consumers of the group axis, `evaluation.py`
consumers of the reference axis, and the prepared/result spills in
`src/goosedove/excel/utilities.py`. Resolution already supplies component payment dates.

Track components, payment groups, observations, compressed slots and distinct live
references separately in the relevant work/allocation tests. State changed counts and
explain retained memory. The worked example has six slots where the old same-payment
case has three; that growth represents different payment ownership, not a reason to
expand a dense calendar or copy history per group.

Keep group construction in creation and dated fixing work in preparation. Preserve the
existing vectorized tick path, with no row or group loop and no extra price reads per
group. The current preparation reads fixings per slot; this slice does not require a
separate fixing-deduplication cache. If that read strategy changes, measure and explain it.
Avoid adding optimizations unrelated to the changed grouping boundary.

## Delivery and completion

Deliver one PR for multiple payment groups, stacked after the reviewed prototype unless
the stack has since landed. Add the hand-priced lifecycle through the kernel, public
creators, reports and kept workbook, with an inspectable pair of same-contract groups.
Update the smoke and host assertions and the changed debug spill references. Extend the
lifetime example where needed to prove the same preparation survives ticks and is
replaced on a history change.

Update the pipeline packet and current library pages to distinguish payment groups from
market references and to retire the one-payment-day-per-contract constraint. Leave old
PR history as history; change current guidance. Run `check.ps1`, report work/allocation
changes, and follow the separate-review rule for existing golden updates.

This PR is done when different payment dates on one contract value and move to cash
independently through the existing public pipeline, while the reports remain aggregate
and the stored contract risk vector remains unique and reusable. Mixed schedule methods,
quantity units and quantity bases are the next slice. The inherited #159 quantity-overflow
P3 remains a small separate correction; it is not a payment-group feature requirement.
