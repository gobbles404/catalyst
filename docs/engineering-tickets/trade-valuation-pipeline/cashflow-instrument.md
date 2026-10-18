# Cashflow instrument

[Pipeline overview](README.md) · [UAT item 23](surface-uat-notes.md#23-cashflow-instrument)

**Status:** Built in #200, 17 October 2026, as the first of two PRs from main; the collection through
`_AggregateResults`, the second's, was folded on 18 October into slice 2 of the named-curve arc,
[named-curves-slice-2.md](named-curves-slice-2.md), built in #202, which reworked the collector in
the one place the integration touches; [create-cashflows.md](../../library/cashflows/create-cashflows.md)
and [evaluate-cashflows.md](../../library/cashflows/evaluate-cashflows.md) own the functions.
The review points below were decided on 17 October 2026: USD alone, one currency per batch;
`cashflow_mark` and `cashflow_cash`; `dv01` by day, month and year with `all` the DV01 alone
and the commodity selectors refused by name; the currency in the handle; the batch read back
row by row and the results by payment day with the totals once; the payment arithmetic
extracted in the first commit with the trade results pinned unchanged.

## Outcome

Book one or many known payments, discount the unpaid amounts, and retain their value, cash
and DV01. A row might represent an unwind or termination payment, a fee, or a broker or
exchange rebate. Each row is one payment, with a known signed amount, currency and explicit
payment date.

The instrument is `cashflow`. It has no commodity price dependency and needs no commodity
index, contract, schedule method or lot definition. A future payment has interest-rate risk;
it has no commodity delta or commodity/rate cross-gamma. Linking it to an originating deal
for attribution can be considered separately without making that deal necessary to value it.

## Proposed instrument definition

Add `cashflow` to `_ListInstruments`, described as "A known signed amount in one currency,
payable on one explicit date." `_ShowInstrument("cashflow")` uses the existing layout:
fields across columns, metadata down rows. The table below is written vertically for review.

| Field | Required | Type | Meaning and rule |
|---|---|---|---|
| `amount` | yes | number | Finite signed monetary amount in the stated currency. Positive means receive; negative means pay. Fractions and zero are allowed. This is the complete payment amount, not a price or a quantity. |
| `currency` | yes | text | Settlement currency, for example `USD`. Amounts are in that currency's whole units, so `100` USD means 100 dollars. Currency-code validation is a review point below; no FX conversion is implied. |
| `payment_date` | yes | date | The actual scheduled payment date, past, present or future. Use the date as entered; do not roll it or infer it from a commodity schedule. |
| `trade_date` | yes, proposed | date | Date the obligation was agreed or booked, supplied explicitly. Keep the existing trade-date semantics; do not introduce a rule requiring payment to follow trade date. |
| `trade_id` | no | number | Reuse the existing whole-number identifier policy and bounds. Duplicate IDs do not merge or remove occurrences. |
| `counterparty` | no, proposed | text | The payer or payee. May be a trading counterparty, broker or exchange. This is attribution, not a curve selector or a fee trigger. |
| `description` | no, proposed | text | Short explanation, such as "Swap termination" or "Clearing rebate". No valuation behavior is inferred from the words. |

The last four rows are proposed booking metadata for owner review. The first three are the
economic facts needed to value the payment. Refer to the existing
[instrument definition](../../library/instruments/show-instrument.md) for shared field types
and identifier rules rather than creating a second version of those policies.

Reuse the template and ticket pattern: the template names the instrument and supplies shared
fields; each ticket row completes it. Exact field names, disjoint template/ticket fields,
and the existing missing-versus-blank rules still apply. An optional field may be omitted;
this does not introduce new blank-cell exceptions. A zero amount is still a fully validated
row. Repeated rows count as repeated payments.

For example, a template can supply `currency = USD` and `counterparty = Firm A`, while the
ticket supplies `trade_date`, `trade_id`, `amount`, `payment_date` and `description`.

Do not add `route`, `settlement_method`, `quantity`, `quantity_unit`, `quantity_per`,
`fixed_price`, payment lags, holiday calendars, or reserves to this first definition.
An exchange rebate is still a dated receivable: the identity of the payer does not make it
an undiscounted cleared position. A fee entered as a cashflow affects value and cash;
the existing brokerage, clearing and marketing reserves remain a different concept.

## Agreed worksheet path

Cashflows have their own creation and evaluation functions. Reuse the instrument catalog
and template mechanism, then pass a template and an array of cashflow rows to the creator:

```text
_CreateTradeTemplate("cashflow", fields, values)
    -> template handle

_CreateCashflows(fields, cashflow_rows, template)
    -> cashflow batch handle

_EvaluateCashflows(cashflows, valuation_date, discount_curve)
    -> cashflow results handle
```

All arguments to the two new functions are required. The template remains the last creator
argument and must select `cashflow`; a template for another instrument fails by name.
`fields` is the row of exact column headers, and `cashflow_rows` is one or more rows beneath
it. Creation resolves the rows against the template and instrument, then encodes the batch.
One cashflow uses the same path as many; repeated rows count separately.

Evaluation takes the created cashflow batch directly, an existing valuation-date handle,
and an ordinary discount-curve handle. The valuation date supplies `as_of` explicitly; the
curve is a dynamic input whose start must match that day. There is no cashflow preparation
function and no call to `_PrepareTrades`: all payment amounts are already known at creation.
No index, commodity history or market is required at either boundary.

Keep `_CreateTrades`, `_PrepareTrades` and `_EvaluateTrades` as the commodity trade path.
Do not widen their signatures to accept cashflows, add cashflow branches to their workflow,
or manufacture fixed/float records with empty observations to fit those functions.

Extend the existing readers and collector to accept cashflow results: `_ReportValues`,
`_ReportRisk`, `util_ReadHandle` and `_AggregateResults`. Their display details and the
delivery split are reviewed below. Sharing reports does not require cashflow results to
pretend they have a commodity index, reporting lot or market.

## Valuation and risk

Use an explicit valuation-date input. The booked amount and payment date never move when
`as_of` moves. A discount curve is a changing input supplied to evaluation, not stored in a
template or trade row. The proposed first scope is one currency and one curve per batch.

For each payment, using the existing continuous-zero-rate, ACT/365F DV01 convention:

```text
if payment_date > as_of:
    tau  = calendar_days(payment_date - as_of) / 365
    npv  = amount * DF(payment_date)
    cash = 0
    dv01 = -tau * npv / 10000
else:
    npv  = 0
    cash = amount
    dv01 = 0
```

The curve must start on `as_of`, and every unpaid payment date must be covered. A missing
factor or mismatched curve start fails visibly. Paid amounts use factor 1 and require no
historical curve lookup. No extrapolation, inferred curve, or automatic currency conversion.
Reuse the existing [discount-curve rules](../../library/globals/discount-curve.md) and
[DV01 convention](../../library/trades/evaluate-trades.md), including finite-result checks.

`payment_date <= as_of` means the amount has moved to cumulative cash under the existing
date-based model. This assumes payment on the scheduled day; it does not confirm a bank
transfer. Unpaid overdue balances, settlement confirmation, partial payments and intraday
payment cutoffs require a separate design. The valuation-date handle's intraday fraction
does not change this date-based cutoff.

DV01 is stored by payment date and by payment month/year, with its saved total, in currency
units per basis point. Nominal commodity delta, discounted commodity delta and cross-gamma
are economically zero, and there is no commodity risk axis to construct. Do not invent an
index or reporting lot to label these absences.

## Static state and changing inputs

| Stage | Responsibility |
|---|---|
| Definition and template | Declare valid fields and shared static values. |
| `_CreateCashflows` | Resolve all rows; retain booking metadata; encode monetary amounts and explicit payment dates. |
| `_EvaluateCashflows` | Apply `as_of`, look up unpaid payment factors, calculate NPV/cash/DV01 and save their totals and dated vectors. |
| Readers | Select the saved results. No discounting, rate bumps or risk recalculation in a reader. |

Give cashflows their own library records and natural module ownership. The shared boundary
with fixed/float evaluation is payment valuation: known amounts on payment dates, valued
against `as_of` and the supplied curve. Reuse or extract that arithmetic, its date treatment
and DV01 convention rather than maintaining a second discounting implementation. Shared
payment code must not require commodity records. Keep any extraction separately reviewable
and preserve existing fixed/float results.

Creation can compress amounts sharing the same currency and payment date once; payments
on different dates remain separate even when their nominal amounts net to zero. This is
arithmetic aggregation, not counterparty credit or legal netting. Cashflow results retain the
batch and evaluation context, payment dates, amounts, factors, NPVs, cash and DV01, with the
saved totals and dated risk vectors. Exact internal record names remain engineering choices.

Keep the created batch immutable through curve changes and date rolls. Evaluation work should
follow distinct payment dates rather than the number of input rows. One row and many use the
same path. Count actual creation, factor lookup and reduction work with the existing work
counter. A commodity quote update must not be a dependency of a standalone cashflow result.
Normal handle publication, reuse and release apply. A curve or valuation-date change makes
new results over the same static batch; an older held result remains an unchanged snapshot.

## Worked acceptance

Synthetic valuation date: **4 January 2027**. The supplied curve has factors 0.95 on
4 January 2028 and 0.90 on 3 January 2029, respectively 365 and 730 days away.

| Payment | Amount USD | Payment date | Factor | NPV USD | Cash USD | DV01 USD per bp |
|---|---:|---|---:|---:|---:|---:|
| Receivable | 10,000 | 4-Jan-2028 | 0.95 | 9,500 | 0 | -0.95 |
| Payable | -10,000 | 3-Jan-2029 | 0.90 | -9,000 | 0 | 1.80 |
| Earlier rebate | 250 | 3-Jan-2027 | 1 | 0 | 250 | 0 |
| Total | | | | **500** | **250** | **0.85** |

The two future nominal amounts cancel, but their NPV and DV01 do not: payment dates must
survive compression. Equal and opposite amounts on the same payment date do cancel.

For a separate receipt of 100 on 4 January 2028, the initial result is NPV 95, cash 0 and
DV01 -0.0095. Changing the factor to 0.96 gives NPV 96 and DV01 -0.0096 without changing the
trade. On the payment day, the result is NPV 0, cash 100 and DV01 0; it stays cash afterwards.

Acceptance should also cover a fractional amount, a zero row, duplicate rows, reordered rows,
and a batch equalling the sum of its singleton evaluations. Reject invalid fields and amounts,
missing future factors and nonfinite arithmetic without publishing a partial result. Use a
centered small parallel rate bump as an independent check of the analytic DV01, under the
same rate convention, not as the production calculation.

Drive the example through the agreed template, creation and evaluation calls without any
commodity index, history, market or preparation. Verify a wrong-instrument template is
refused, curve/date changes reuse the created batch, and the existing commodity path retains
its outputs after any shared payment-code extraction. Cover the new handle kinds and their
reader integration through the ordinary seam and lifetime checks.

## Review points before engineering

1. **Booking metadata and currencies.** Confirm required `trade_date`, optional `trade_id`,
   `counterparty` and `description`, and one currency per batch. Decide the accepted currency
   codes explicitly. The current unit tables contain USD and CENT; they are not a general
   currency registry. A cashflow needs no commodity-unit conversion, and its amount must not
   silently be interpreted as cents. A supplied curve currently has no currency metadata, so
   the caller chooses the right curve; do not claim the library verifies its currency.
2. **Reports and collection.** Extend `_ReportValues` and `_ReportRisk` to read the cashflow
   result's saved values and risk. Propose value labels for NPV and cash, and the
   behavior of `all` and explicit commodity-risk selectors without fictitious lot columns.
   The desired collection behavior is to add cashflow DV01 to the existing exact-curve and
   currency group at the same valuation date, with no commodity group. Check cashflow-only
   collections as well as collections with fixed/float results. Review the required result
   type and collector changes before deciding whether that integration is the same PR or
   a follow-up; do not silently broaden this into a universal instrument framework.

## Delivery

After the remaining choices are reviewed, implement the agreed cashflow path from a template
and ticket through `_CreateCashflows` and `_EvaluateCashflows` to readback and reports, with
a kept-workbook example of the lifecycle above. Split independently reviewable work if the
shared payment arithmetic or result integration warrants it.
Use existing seam, publication/release, work-budget and test conventions; run the repository
checks. Give each public function one maintained owner page and link shared rules instead
of copying them. Update this ticket and its UAT entry when built.

Outside this first instrument: recurring schedule generation, floating or contingent amounts,
commodity attribution, FX valuation or FX risk, credit adjustments, multiple curves within
one batch, actual payment reconciliation, and automatic creation of a cashflow from a
termination or reserve. More rows already represent more individual payments; no schedule
instrument is required for that.
