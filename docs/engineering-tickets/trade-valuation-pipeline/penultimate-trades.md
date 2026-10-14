# R1 Penultimate futures and payment dates

[Pipeline overview](README.md) · [Trade creation](create-trade.md) ·
[Dated exposure](dated-exposure.md) · [Fixing and payment state](fixing-and-payment-state.md)

**Status:** Agreed implementation ticket, 4 October 2026, reviewed the same day. Build on the
reviewed pipeline through #142, stacked on it. This replaces R1's earlier research-only scope
and adjusted-lag proposal. This page specifies the work; penultimate booking is not
implemented yet.

## Outcome

Book, prepare, evaluate and report cleared financial penultimate futures through the existing
pipeline. Start with ICE Henry Penultimate Fixed Price Future (PHH) and ICE WTI Crude Futures
(T). Derive the pen expiry from the underlying NYMEX futures expiry, then count the payment
lag from the pen expiry. Resolve these dates once during `_CreateTrades`.

```text
futures_expiry = index.schedule.future_expiry[contract]
pen_expiry    = previous_business_day(futures_expiry, index.holiday_calendar)
payment_date  = add_business_days_strictly_after(
    pen_expiry, payment_time_lag, payment_holiday_calendar
)
```

For these supported pen products, the derived pen expiry is the observation date and payment
anchor. The underlying schedule keeps the NYMEX expiry. Its calendar represents the NYMEX
pricing days; the supplied payment calendar represents the product's payment days.
The penultimate rule consumes an **unshifted underlying expiry**, so an already shifted ICE
expiry must not be supplied as the reference schedule in these examples.

For `lastday`, the observation and payment anchor remain the underlying expiry. An added
`penultimate` branch changes the resolved date, not the meaning of `payment_time_lag`.
For PHH, `+1bd` means one clearing business day after the pen expiry. Do not subtract one
from the entered lag or compensate with `0bd`; different calendars make that shortcut unsafe.

## Product evidence and booking inputs

Sources checked 4 October 2026. ICE's published expiry dates are independent checks of the
derived dates, rather than another schedule users must maintain.

| Product | Reference and size | Pricing and payment convention |
|---|---|---|
| ICE PHH | Corresponding NYMEX NG month; 2,500 MMBtu per ICE lot | Price on the NYMEX business day before NG expiry. ICE separately describes its last trading day as four business days before the contract month. Payment is the first clearing-organization business day after that last trading day. |
| ICE WTI T, product 213 | Corresponding NYMEX CL month; 1,000 barrels per ICE lot | NYMEX penultimate settlement; ICE publishes the cash settlement price on its final trading day. Payment is due no later than the following Trading Day. |

Sources: [PHH specification](https://www.ice.com/products/6590264/Henry-Penultimate-Fixed-Price-Future),
[WTI specification](https://www.ice.com/products/213/WTI-Crude-Futures),
[WTI rules Q.2, Q.6 and Q.7(c)](https://www.ice.com/publicdocs/contractregs/25_SECTION_Q.pdf).

**WTI modeling convention for this ticket:** use the next Trading Day deadline as the
modeled payment date, expressed as `+1bd` on the corresponding supplied calendar. This is
an explicit date-based settlement convention, not evidence of the actual time money moves.
PHH uses clearing-organization days. The two calendar meanings must remain identified.
The existing cleared cash bucket remains modeled cumulative settled P&L; margining and bank
reconciliation stay outside this work.

Use the existing `future` definition and exact field names:

| Template field | PHH example | WTI example |
|---|---|---|
| `contract_specification` | A supplied specification named `ICE PHH`, with 2,500 MMBtu per lot | A supplied specification named `ICE WTI T`, with 1,000 BBL per lot |
| `schedule_method` | `penultimate` | `penultimate` |
| `route` | `cleared` | `cleared` |
| `settlement_method` | `financial` | `financial` |
| `quantity_unit` | `LOT` | `LOT` |
| `quantity_per` | `month` | `month` |
| `clearing_house` | `ICE Clear Europe` | `ICE Clear Europe` |
| `payment_time_lag` | `+1bd` | `+1bd`, modeled at the rule deadline |
| `payment_holiday_calendar` | Clearing-organization calendar handle | Calendar handle for the rule's Trading Days |

Specification names above are example data, not magic strings that dispatch code. Select the
actual traded product's lot size from the index's supplied specifications. PHH must not inherit
the 10,000 MMBtu size of its NYMEX reference. Clearing-house text remains a retained label.
The index argument supplies the underlying NG or CL schedule and history. The live projection
uses that underlying market's quote, consistent with the dated-reference model; a separate
ICE quote curve or exchange-basis model is outside R1.

All six existing pipeline signatures stay unchanged:

```text
_CreateTradeTemplate(instrument, fields, values)
_CreateTrades(index, fields, trade_rows, template)
_PrepareTrades(trades, history)
_EvaluateTrades(prepared, market)
_ReportValues(results)
_ReportRisk(results)
```

## Implementation boundaries

1. **Accept the method.** Add `penultimate` to the supported schedule-method enum and semantic
   reader, retaining strict headers, duplicate-field refusal and required financial payment
   terms. R1 supports cleared financial pens; reject physical penultimate combinations by
   name during creation. Existing bilateral evaluation remains unsupported. Preserve the
   current one-index, one-specification and one-method batch restrictions.
2. **Resolve the observations first, then the payments.** Resolve the schedule method's
   observations once during creation, and count `payment_time_lag` from each component's
   last observation day on its payment calendar: the expiry for `lastday`, the pen date for
   `penultimate`. The current payment resolver reads `schedule.future_expiry` directly and
   changes to read the observations. A pen produces one observation of weight 1 for each
   monthly component. Its referenced NYMEX contract and month stay unchanged. Strips resolve
   each month separately. This is the payment rule for the two methods built; a later method,
   Asian or bilateral, states its own payment convention on its own page and inherits nothing
   from this one.
3. **Retain the explanation without a copy.** The underlying schedule by reference, the
   observations the encoding already retains, and the lag, payment calendar and payment date
   `PaymentTerms` already holds are the facts; the observation day is the payment anchor, so
   no anchor array is kept beside the observations. No new worksheet field, schedule column,
   anchor selector or constructor is required. Keep `ContractSpecifications` focused on lot,
   unit and fee data.
4. **Reuse dated slots.** Feed the resolved observation into the I4a observation/encoding path.
   Keep its checks that the day is priced, lies within history coverage and maps to the
   intended underlying contract. Do not overwrite the index's expiry or let a lookup silently
   substitute a different contract. Identical compatible slots compress; duplicate trade
   occurrences still contribute fully. The existing same-contract payment-date mismatch
   refusal remains in force; broader payment grouping is not part of R1.
5. **Reuse preparation and evaluation.** A pen stays live on its observation date under the
   existing date cutoff, then takes the history's fixing for that day. Its commodity delta
   becomes zero once fixed, even while the underlying future is still trading. A fixed amount
   remains in mark until its payment date, then moves into cash. The underlying's later final
   settlement must not replace the pen fixing. Price ticks rebuild neither dates nor fixed
   amounts; evaluation still rejects a different history instead of preparing implicitly.
6. **Expose the facts as the spills already do.** The trades spill shows each component's
   `payment_date`, and the prepared spill each slot's `observation_date` with its reference
   `contract_code`; a pen's dates read back there without re-resolving, and no column is added.
   Preserve the two scalar reports and the distinct dated `live_exposure` and `contract_delta`
   meanings. Update help, current library pages, smoke examples and the kept workbook with
   the implementation. `_ShowInstrument` keeps its agreed layout and no capability row.

The likely code changes are in `trades/template.py`, `terms.py`, `resolution.py` and
`observations.py`, with encoding/readback adjustments needed to consume the retained facts.
Use a small shared private date calculation. Preparation and evaluation should consume the
same records and arithmetic as before; a product-specific evaluator is unnecessary.

For an eligible expiry, a NumPy business-day offset of `-1` on the pricing calendar gives
the pen date. Reuse the current positive-lag, strict-after payment arithmetic on the payment
calendar, including when that calendar closes the anchor. Reject an inconsistent pricing
expiry/calendar rather than silently changing the supplied underlying expiry.

## Date acceptance examples

The NYMEX dates below are derived from the exchange rules; the ICE pen dates are also listed
in the exchange expiry tables. The indicated following payment days are assumed open on the
applicable payment calendars. Pin those calendar inputs and their source/version with the
fixtures, including holidays; an expiry table's final-settlement-date column is not a payment
date source.

| Product and month | Underlying NYMEX expiry | Pen expiry and observation | Modeled payment date |
|---|---|---|---|
| PHH Z26 | Wed 25 Nov 2026 | Tue 24 Nov 2026 | Wed 25 Nov 2026 |
| PHH M27 | Wed 26 May 2027, Memorial Day closing Mon 31 May | Tue 25 May 2027 | Wed 26 May 2027 |
| PHH N27 | Mon 28 Jun 2027 | Fri 25 Jun 2027 | Mon 28 Jun 2027 |
| ICE WTI T F27 | Mon 21 Dec 2026 | Fri 18 Dec 2026 | Mon 21 Dec 2026, at the rule deadline |

Sources: [NYMEX NG rule 220102.F](https://www.cmegroup.com/content/dam/cmegroup/rulebook/NYMEX/2/220.pdf),
[NYMEX CL rule 200102.F](https://www.cmegroup.com/content/dam/cmegroup/rulebook/NYMEX/2/200.pdf),
[CME 2026 holiday notice](https://www.cmegroup.com/content/dam/cmegroup/notices/market-regulation/2026/01/msn01-09-2026revisedholidayprocessinglargetrader2026.pdf),
[PHH expiry table](https://www.ice.com/products/6590264/Henry-Penultimate-Fixed-Price-Future/expiry),
[WTI expiry table](https://www.ice.com/products/213/WTI-Crude-Futures/expiry).

M27 is the real holiday-crossing case: a US holiday closes the last business day of the month
before the contract month, so ICE's four-business-day description and the NYMEX derivation
could have parted, and ICE's table gives 25 May 2027, the derivation's date. Every PHH and WTI
month checked on 4 October 2026, Z26 through N27, agrees with the derivation.

Also pin two **synthetic calendar tests**, separate from the exchange examples: with a Monday
underlying expiry and Friday closed on the pricing calendar, the pen date is Thursday; with
a Friday pen date and Monday closed only on the payment calendar, `+1bd` pays Tuesday. These
prove that pricing and payment calendars are used for their own operations. Include an anchor
closed on the payment calendar to catch double rolling, and a `lastday` regression using the
same underlying expiry to catch an unintended change to existing payment dates.

## Worked valuation and acceptance

Use PHH N27 above, two long lots at a fictional fixed price of 3.00 USD/MMBtu. Quantity is
5,000 MMBtu and entry-price offset is -15,000 USD. Use a live NYMEX N27 quote of 3.10 and a
25 June fixing of 3.20. The following are independent hand answers:

| As of | State | Cleared mark USD | Cleared cash USD | Delta USD per USD/MMBtu |
|---|---|---:|---:|---:|
| 25 Jun 2027 | Pen observation remains live on its own day | 500 | 0 | 5,000 |
| 26 Jun 2027 | Friday's observation has fixed; Monday payment is still ahead | 1,000 | 0 | 0 |
| 28 Jun 2027 | Payment date reached | 0 | 1,000 | 0 |

A move from 3.10 to 3.11 before fixing raises mark from 500 to 550 using the same preparation.
Changing the pen fixing from 3.20 to 3.21 requires new history and preparation and raises the
fixed amount to 1,050. Changing the later NYMEX expiry-day fixing must leave that amount at
1,050. The short trade has the opposite signs. Cleared DV01 remains zero under this model.
Include a preceding boundary contract and a later unused contract so the market is valid
throughout; do not make an entirely ended market part of this test.

Acceptance requires:

- Both products through the public template-to-reports path, with the date expectations above
  and a WTI amount/risk example that checks its 1,000-barrel lot size.
- A single trade, many signed trades, duplicate occurrences and a monthly strip through one
  path; a batch equals its singletons and is invariant to ticket order within tolerances.
- Missing pen fixings fail visibly. A supplied history with the later expiry fixing cannot
  stand in for a missing pen fixing. Preserve index/history identity and live-coverage checks.
- A fully fixed pen batch reads no live quote even though its underlying remains tradable;
  changing that quote changes neither mark nor delta. Corrected history replaces preparation
  and results. Keep the Excel ownership/release checks.
- Work budgets at one and many trades: dates resolved only during creation; no schedule
  expansion, payment-date arithmetic or fixing reads on ticks; readers use retained results.
  Report allocation by component/slot/reference and the work-count changes from I5.
- Existing `lastday` values, cash, risk and expired-physical refusals continue to pass. Existing
  goldens remain untouched in the code-change PR; new hand cases precede new snapshots.

Deliver R1 as one focused implementation PR stacked on #142, with its tests, its documentation
and its own worksheet example: the PHH lifecycle above in the kept workbook, live on the pen
day, fixed and unpaid, then cash on the payment day, with the price tick and the corrected
fixing, beside the toy lifecycle I6 built under `lastday` in #142. Asian and last3day booking,
physical penultimate delivery, bilateral rates, alternate fixing sources, differing payment
dates within one contract group and general payment-rule machinery remain later work.
