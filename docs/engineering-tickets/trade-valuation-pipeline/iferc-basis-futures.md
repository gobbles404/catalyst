# IFERC basis futures through the trade pipeline

[Pipeline overview](README.md) · [UAT item 10](surface-uat-notes.md#10-iferc-market-accepted-but-trade-creation-refused)

**Status:** Built in #167 on the prototype stack above #166, the page as a ticket, `lastday` kept
as proposed; the [As built](#as-built-167) section at the end says what was built and what was
not. Engineering ticket, 9 October 2026. Product direction agreed during Excel UAT;
the proposed `lastday` meaning below is an explicit recommendation for this slice.
Inspected prototype: PR #166, `df2bec9`. Implement against its current successor as one
focused PR. This ticket does not decide how the prototype lands or is later rebuilt.

## Outcome

Book and value a cleared, financially settled `fixed_float` on an IFERC index through the
existing template, trade, preparation, evaluation and reporting functions. The first
examples are ICE Waha and Houston Ship Channel basis futures.

The supplied index represents the traded basis. Its live quotes, monthly fixings and
the ticket's `fixed_price` are all basis prices in the index's quote units. A trade
does not need two legs merely because the exchange defines its final basis by subtraction.
Supplying an outright location fixing where a basis fixing is expected is incorrect input;
the current numerical data cannot detect that semantic mismatch.

Keep two dates distinct: **publication determines when the monthly price fixes;
last trading determines the payment anchor.** The existing IFERC schedule already
contains both. No new instrument, schedule field or public function is needed.

*Superseded on the anchor by [iferc-publication-payment-anchor.md](iferc-publication-payment-anchor.md): the payment counts from the publication day, and the schedule holds no last trading date.*

## Product evidence

ICE's [Waha Basis Future (WAH)](https://www.ice.com/products/6590171/Waha-Basis-Future)
and [HSC Basis Future (HXS)](https://www.ice.com/products/6590137) specify the same structure:

| Fact | Published product terms |
|---|---|
| Contract size and quote | 2,500 MMBtu; USD per MMBtu |
| Final basis | Location's monthly Inside FERC index minus the same delivery month's NYMEX Henry Hub final settlement |
| Location pricing date | First publication date of the contract period |
| Last trading day | Last business day before the first calendar day of the contract period |
| Final payment | Third clearing-organization business day following last trading day |

Use the supplied schedule and payment holiday calendar for those dates. Do not infer
exchange rules from the index name or clearing-house label. In particular, `+3bd` is
counted on the clearing payment calendar, not assumed to be three calendar days.

This slice consumes the completed basis series. Constructing that series from location
and Henry Hub data is separate market-data work. The examples are basis futures, not
the separately listed outright fixed-price or Gas Daily-versus-IFERC products.

## Surface and supported terms

Keep these signatures and the normal handle dependencies:

```text
_CreateTradeTemplate(instrument, fields, values)
_CreateTrades(index, fields, trade_rows, template)
_PrepareTrades(trades, history)
_EvaluateTrades(prepared, market)
_ReportValues(results)
_ReportRisk(results)
_ReportDelta(results, [bucket = "day"])
```

Example shared template values, under instrument `fixed_float`:

| Field | Value |
|---|---|
| `route` | `cleared` |
| `settlement_method` | `financial` |
| `schedule_method` | `lastday` — proposed meaning below |
| `quantity_unit` | `LOT`, an exact specification name on the supplied index |
| `quantity_per` | `month` |
| `clearing_house` | `ICE Clear Europe`, retained descriptive text |
| `payment_time_lag` | `+3bd` |
| `payment_holiday_calendar` | Supplied clearing-payment calendar handle |

Example ticket:

| trade_id | trade_date | contract_code | quantity | fixed_price |
|---|---|---|---:|---:|
| WAH001 | 30-Nov-2026 | Z26 | 1 | -0.50 |

The index is supplied to `_CreateTrades`, not stored in the reusable template. Normal
strict headers, disjoint template/ticket fields and quantity specification validation apply.

**Proposed method contract:** retain required `schedule_method = lastday` for a single
final-price observation. On a futures index this remains its expiry-day settle. On an
IFERC index it means the contract month's published final index, observed on
`publication_date`, with weight 1. It does not mean a daily price on `last_trading_date`.
Make this kind-specific meaning explicit in the instrument help and trade pages; if
engineering recommends a different public name, resolve that before implementation.

Support full monthly bullets and strips through existing period resolution, including
explicit dates that cover whole months. Keep `quantity_per = month` and `calday` semantics:
the latter scales quantity by the component's calendar-day count once; it does not create
daily price observations. Selected entry units and the index's designated reporting lot
retain their current roles. Signed and zero quantities follow normal validation.

The IFERC path in this slice accepts cleared financial `lastday` trades only. Refuse
physical settlement, unsupported routes and `asian`, `penultimate` or `last3day` with
the offending row and field. Partial-month periods remain unsupported under `lastday`.
Preserve all existing futures-index behavior and mixed-field support; a batch still has
one index. Gas Daily trade support, bilateral rates and new period-entry UX are separate.

## Mapping through the pipeline

| Stage | IFERC responsibility |
|---|---|
| Resolution | Map each monthly component to its IFERC schedule row once; retain the actual index and its static specifications. |
| Observations | One observation per component, on that row's `publication_date`, with weight 1. The pricing reference is the same monthly contract. |
| Payment terms | Count the component's `payment_time_lag` from its `last_trading_date`, on its supplied payment holiday calendar. Superseded: from its publication day, [iferc-publication-payment-anchor.md](iferc-publication-payment-anchor.md). |
| Encoding | Convert quantity once, retain the fixed leg and dated exposure, and group by booked contract and resolved payment date. |
| Preparation | Bind observation slots to the monthly calendar/history rows; apply published fixings, calculate live exposure and separate unpaid amounts from cash. |
| Evaluation | Read each distinct live monthly reference once and use the existing aggregate arithmetic and results. |
| Readers | Read saved values and risk without recalculation. |

Current code deliberately refuses IFERC in `trades.terms.futures_schedule_of`. Removing
that guard alone is insufficient: `ResolvedTrades` and observation generation assume a
futures schedule, reference resolution uses daily pricing windows, preparation uses day
offsets into a daily calendar, and creation anchors payment on the last observation.
Extend those assumptions at their owning boundaries. Reuse the common numerical kernel;
do not build a second IFERC evaluator or masquerade as a daily futures index.

An IFERC index has no pricing holiday calendar today. Use its explicit publication
dates without introducing a futures open-day check or requiring a dummy pricing calendar.
Its first schedule contract is usable; it is not a preceding boundary contract. Retain a
direct monthly-row mapping rather than expanding months into a dense daily calendar.

Preserve the existing IFERC cutoff: an observation is live on publication day and fixed
when `publication_date < as_of`. Missing required monthly fixings fail through history;
never substitute a quote or zero. History must belong to the batch's exact index, and
evaluation's market must retain the exact prepared history. Evaluation never prepares again.

Payment must remain strictly after the final observation under the current day-based
cutoff. A schedule/lag combination violating that constraint fails with contract, dates
and row context; do not silently delay payment or invent a fixing. WAH/HXS `+3bd` is
counted from last trading even though publication occurs later.

For multiple trades on one month, equal payment dates may compress together. Different
payment dates remain separate groups for mark and cash. Their live contract delta and
observation-date delta may still sum. On this IFERC path, the delta by day, `_ReportDelta`
then and `_ReportRisk(results, "nominal_delta", "day")` since #178,
puts the live lots on publication day, then retains a zero when fixed. Month/year reports
bucket that observation date, not payment date or an invented daily delivery exposure.

Readback must make the dates inspectable: the retained IFERC schedule supplies last
trading and publication dates, the trades spill supplies resolved payment dates, and
prepared/results slots supply the observation date and monthly pricing reference.
No extra duplicate date array or report column is required merely to repeat those facts.

## Independent worked acceptance

Use this **synthetic** Waha-like fixture, not a claim about ICE's actual holiday or
publication schedule. Quote and settlement units are USD/MMBtu and USD. The index has
`LOT = 2500 MMBtu` and `MMBtu = 1 MMBtu` specifications, with LOT selected for reporting.
The payment calendar closes weekends and 1 January 2027.

| Contract | Last trading | Publication | Payment with `+3bd` |
|---|---|---|---|
| X26 | 30-Oct-2026 | 2-Nov-2026 | 4-Nov-2026 |
| Z26 | 30-Nov-2026 | 1-Dec-2026 | 3-Dec-2026 |
| F27 | 31-Dec-2026 | 4-Jan-2027 | 6-Jan-2027 |

Provide the earlier X26 fixing at each illustrated history and the Z26 fixing only once
required. X26 supplies the nonempty fixing range required by today's worksheet surface;
it is a usable month, not a dummy boundary. F27 remains an unfixed, unused month during
the December lifecycle, so a fully
fixed trade batch uses today's valid market without widening the entirely-ended-calendar
boundary. Quote vectors must roll with the existing market's prompt-first convention.

For WAH001 above, signed exposure is 2,500 MMBtu and the fixed leg is +$1,250:

```text
amount = 2500 * (basis_price - (-0.50))
       = 1250 + 2500 * basis_price
```

| As-of/state | Price used for Z26 | cleared_mark USD | cleared_cash USD | Live delta LOT |
|---|---:|---:|---:|---:|
| 30-Nov, after booking | live -0.30 | 500 | 0 | 1 |
| 1-Dec, publication day | live -0.30 | 500 | 0 | 1 |
| Same history, price tick | live -0.25 | 625 | 0 | 1 |
| 2-Dec, fixed but unpaid | fixing -0.20 | 750 | 0 | 0 |
| 3-Dec, payment day | fixing -0.20 | 0 | 750 | 0 |
| 2-Dec, independent corrected-history case | fixing -0.10 | 1000 | 0 | 0 |

The day axis is 1 December throughout, containing 1 lot before fixing and zero after.
Contract delta remains on Z26. Cleared DV01 remains zero. Mark and cash follow the
prototype's modeled payment lifecycle; this is not margin accounting.

Pin the following additional cases without replacing these hand answers with snapshots:

- `1 LOT/month` and `2500 MMBtu/month` give identical values and 1 reporting lot. A
  `1 MMBtu/calday` December component is 31 MMBtu, one observation, delta `31/2500`,
  mark $6.20 at -0.30 and $9.30 after a -0.20 fixing, before payment.
- Two identical WAH001 occurrences double the answers. Reordering and batching equal
  the sum of the same separately evaluated occurrences; zero rows still validate normally.
- Long 1 LOT and short 1 LOT at -0.50 on Z26, with `+3bd` and `+4bd` respectively:
  after fixing at -0.20, 3 December has cash +$750 and mark -$750; 4 December has
  both net zero. The groups must not disappear when live contract risk nets to zero.
- A `Z26-F27` strip at 1 LOT/month has one component and one fixing per month. At
  2 December, Z26 fixed -0.20 and F27 live -0.10 against -0.50 give mark $1,750,
  cash zero and contract delta `[0, 1]`. F27's holiday-adjusted payment is 6 January.
- The first schedule month is a valid trade reference without a dummy boundary month.
  Book X26 with an appropriate earlier trade date and prepare on 3 November: it is
  fixed and unpaid, with payment on 4 November. Cover missing fixing, wrong identity and
  insufficient live-price coverage through their existing refusals.
- A payment calendar that also closes 2 December moves Z26's `+3bd` payment to
  4 December while leaving publication/fixing unchanged. Conversely `+1bd` puts
  payment on publication day and must fail the existing payment-after-observation rule.

## Delivery and proof

Add a kept worksheet block showing live, fixed-unpaid and paid states, plus a price tick
reusing preparation. Python acceptance covers every state above, corrected history,
different payment dates and strips. Exercise the public functions and the normal host
and handle lifetime path, not only manually constructed kernel records.

Keep work measurable: creation resolves static months, conversions, observations and
payment dates once; preparation reads monthly fixings and builds saved risk vectors;
a price tick performs no schedule, payment-date or fixing work. Read only distinct live
monthly references. Report work counts and retained memory before/after using the existing
budget tests; a monthly IFERC observation must not create one slot per delivery day.

Update instrument help, trade/kernel documentation, smoke and host expectations where
their existing futures-only descriptions change. Keep source and golden baseline updates
in separate PRs under the repository rule. Run the full gate, preserving futures, pens,
last-three-day and Asian acceptance examples. No new reserve behavior, discounting,
two-index risk decomposition or date-offset utility is included in this ticket.

## As built, #167

Engineering's record of what landed, in the ticket's terms.
[kernel.md](../../library/trades/kernel.md),
[create-trades.md](../../library/trades/create-trades.md),
[prepare-trades.md](../../library/trades/prepare-trades.md) and
[show-instrument.md](../../library/instruments/show-instrument.md) are the pages.

- **The guard.** `trade_schedule_of` in `src/goosedove/trades/terms.py` replaces
  `futures_schedule_of`: a futures index gives its futures schedule, an IFERC index its IFERC
  schedule, and a Gas Daily index is refused, `index is a Gas Daily index, expected a futures or
  an IFERC index for a future`. `ResolvedTrades.schedule` is one or the other, and the four steps
  that read a day off the schedule dispatch on which it is, one `match` each: no second evaluator,
  no dense daily calendar and no futures mask over an IFERC index.
- **The method.** `lastday` kept as proposed. On an IFERC index `observed` makes one observation
  per component on its month's `publication_date` with weight 1, no pricing calendar read, an
  IFERC index having none; the whole month is required as under the expiry-based methods, `Z26 of trade 'WAH001' at row 1 is covered from 2026-12-01 to 2026-12-15, part of its month, expected the whole month under lastday; an IFERC month's index is one price for the whole month`;
  any other method is refused by its row, `schedule_method of trade 'WAH001' at row 1 is 'asian', expected 'lastday' on an IFERC index; an IFERC month has one index, published once`, in the resolution and in the kernel alike; a
  physical settlement is refused, `settlement_method is 'physical', expected 'financial' on an IFERC index; an IFERC basis future is cash settled on its month's published index`. The instrument help says so: `all four are built on a
  futures index, asian averaging the month's pricing days; lastday alone on an IFERC index, its
  published month`.
- **Payment.** Superseded by [iferc-publication-payment-anchor.md](iferc-publication-payment-anchor.md), which anchors every component on its last observation day. As built here, the resolution anchored each component's lag on the schedule's `last_trading_date`
  on an IFERC index and on its last observation day on a futures one, counted on the row's payment
  calendar as before: WAH001's `+3bd` from 30 November is 3 December, F27's 6 January with New
  Year's Day closed, X26's 4 November; a calendar closing 2 December gives 4 December and moves no
  observation; `+1bd` lands on the publication day and fails the existing payment-after-observation
  rule, `Z26 pays on 2026-12-01, expected a day after its last observation, 2026-12-01, when its
  final price exists`.
- **Encoding and preparation.** An IFERC observation's reference is its component's own month,
  checked against that month's publication day, `trade 'WAH001' at row 1 observes 2026-12-02, expected 2026-12-01, the day Z26's index publishes; an IFERC month prices once, on that day`; the preparation finds each slot's
  calendar row by one search over the publication days, `_the_slot_rows`, the first month a month
  like any other, the futures path's offset and boundary refusal unchanged. Fixings, live exposure,
  cash, lot delta, the day, month and year vectors, evaluation and the readers are the common
  kernel's, untouched; `_ReportDelta` by day puts the lot on the publication day and keeps a zero
  there once fixed.
- **Pinned by hand.** The ticket's six states, 500, 500, 625, 750, 750 of cash and 1,000, the
  lot on Z26 and on 1 December while live and zero after; a LOT and its 2,500 MMBtu alike;
  `1 MMBtu/calday` over December 31 MMBtu, 6.20 then 9.30, delta 31/2500; two identical rows
  doubling, reorderings and singletons summing, a zero row kept; long and short at +3bd and +4bd,
  two groups, mark zero while live, 3 December +750 of cash and -750 of mark, 4 December net zero;
  the Z26-F27 strip 1,750 of mark on 2 December with delta `[0, 1]` and F27 paying 6 January;
  X26 fixed and unpaid on 3 November and cash on the 4th; the missing-month, identity and coverage
  refusals the history's and the market's. At the kernel, through the resolution, through the
  registered functions, on the host, in the smoke and in the kept workbook, rows 1818 to 1845.
- **Counts.** An IFERC batch's observations run `observed`, `trade_schedule_of`, `_whole_months`
  and `observations` alone; its encoding the futures ledger less `with_holiday_calendar`,
  `open_days` and `contract_on`; its preparation the futures functions and `_the_slot_rows`, the
  helper every preparation now runs, with one `ndarray.any` fewer and one `ndarray.searchsorted`
  more; its tick the futures tick's. The resolution of an IFERC ticket runs the futures ledger less
  `_the_days`, `with_holiday_calendar` and `_last_days`. One observation and one slot per
  component month, never one per delivery day: 2,000 trades over 24 months make 24 slots, and the
  preparation allocates by month and not by trade.
- **Not built.** No Gas Daily trades, no bilateral rates, no partial month on an IFERC index, no
  new field, function or signature, no reserve, discounting or two-index decomposition, as the
  ticket bounds it; no lifetime group, the handle machinery being the same whatever the index's
  kind. The smoke's earlier IFERC refusal, an index made without a reporting lot, now shows that
  refusal.
