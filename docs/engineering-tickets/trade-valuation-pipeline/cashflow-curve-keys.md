# A named discount curve for each cashflow

**Status:** Built in #260, stacked on #259, agreed with the owner on 20 November 2026 for
[issue #254](https://github.com/gobbles404/catalyst/issues/254), this page in its first
commit. A batch of cashflows discounts each payment on the curve its row names, where the
whole batch took one curve. It extends the cashflow instrument of
[cashflow-instrument.md](cashflow-instrument.md) by the rules bilateral trades follow since
[named-curves-slice-3.md](named-curves-slice-3.md), and binds its keys by the shared step of
[shared-curve-binding.md](shared-curve-binding.md). No creator, evaluator or collection is
added. [create-cashflows.md](../../library/cashflows/create-cashflows.md),
[evaluate-cashflows.md](../../library/cashflows/evaluate-cashflows.md),
[report-risk.md](../../library/trades/report-risk.md),
[read-handle.md](../../library/utilities/read-handle.md) and
[collect-discount-curves.md](../../library/globals/collect-discount-curves.md) are the owners
it updates.

## The issue

A batch of cashflows can hold payments that discount on different curves, SOFR and FFOIS
say. `_EvaluateCashflows` takes one curve for the whole batch, and creation sums amounts by
payment day alone, so 10,000 received on SOFR and 10,000 paid on FFOIS on one day book as
nothing at all.

## Decisions of 20 November 2026

| Decision | Agreed |
|---|---|
| The field | `discount_curve_key` on the `cashflow` instrument, required on every row: the template's one value for the batch, or a ticket column, a key a row. Never both, as any field. |
| The key | The curve's exact name, case and all, read by the curve's own name rule. Nothing trimmed, changed or inferred, a collection of one included. Only the text is booked; the curve is found at evaluation. |
| The evaluator | `_EvaluateCashflows(cashflows, valuation_date, discount_curve_set)`: the third argument is the collection `_CollectDiscountCurves` makes, where it was one curve. All three required. A batch on one curve passes a collection too. No direct-curve form is kept. |
| Payment groups | A payment day and a key. Only rows of one group net before discounting. A group that nets to zero is kept, with its key. |
| Binding | The shared step: each distinct key bound once to the curve of that name; a key naming none refused with its first row. The order of the collection changes nothing. |
| Dates | Each selected curve starts on the valuation day and covers its own unpaid payment days. A curve nobody selects is held to nothing. A batch paid in full still binds its keys and checks each selected curve's start. |
| Value | Unchanged per group: `npv = amount * factor`, `dv01 = -(days / 365) * npv / 10000`; a payment day on or before the valuation day is cash at its full amount, reading no factor. |
| Saved risk | One rate contribution per selected curve, its DV01 by payment day, month and year on the batch's shared axes. The batch's mark, cash and DV01 are the sums. |

Chosen by the build where the issue left it open:

| Choice | Why |
|---|---|
| `discount_curve_key` is the last field of the instrument and the last column of both readbacks | No existing readback column moves. A sheet on one curve needs the two edits below and its readback formulas read what they read. |
| One key column, no curve-name column beside it | The key is the curve's name, by the binding rule. |
| Groups are ordered by payment day, then by key in the order the rows first name them | The readback stays in date order, and a batch on one key reads row for row as it did. |

## Worksheet contract

```excel
B3  = _CreateTradeTemplate("cashflow", A1:B1, A2:B2)        currency and discount_curve_key
B10 = _CreateCashflows(A4:D4, A5:D9, B3)
D2  = _CollectDiscountCurves(B12:B13)
D3  = _EvaluateCashflows(B10, B1, D2)
```

`_CreateTradeTemplate` and `_CreateCashflows` keep their arguments. `_EvaluateCashflows`
takes the collection's handle and never a range of curve handles.

**What every existing cashflow sheet changes.** Two edits, and each fails by name until it
is made:

1. Add `discount_curve_key` to the template, or as a ticket column.
2. Point the third argument of `_EvaluateCashflows` at a `_CollectDiscountCurves` cell.

## Booking

The rows are kept as booked, each with its key. The distinct keys are kept in the order the
rows first name them. A payment group is a payment day and a key; the groups are in day
order and, within a day, in key order; each group's amount is its rows' amounts summed, one
bincount, finite or refused by its day and key. The batch's distinct payment days, and the
months and years they fall in, stay the batch's axes, shared by every key, so that every
curve's DV01 stands on one date axis.

## Evaluation

In this order, the first failure being the message:

1. Each distinct key, in key order, is bound to the collection's curve of that name by the
   shared step; a key naming none is refused with the first row booking it and the
   collection's names.
2. Each selected curve, in key order, starts on the valuation day and covers its own unpaid
   payment days.

Then, per group: a group on or before the valuation day is cash, at factor 1; an unpaid
group reads its key's curve for its day, one factor a group. The mark, the cash and the DV01
are the groups' sums, each finite. Per curve: its groups' DV01 summed onto the batch's days,
months and years, one rate contribution a curve.

A changed curve makes a new evaluation over the same booked cashflows. A result already held
is the snapshot it was.

## Reports and readback

- `_ReportValues` reads `cashflow_mark`, `cashflow_cash`, the currency and the valuation day,
  as before.
- `_ReportRisk(results, "dv01", bucket)`, and `"all"`, read one DV01 column per curve used,
  on one date axis, with the Total row and the day, month and year rules as they are. A batch
  of cashflows has no commodity risk.
- `_AggregateResults` takes every contribution of a batch of cashflows and groups each with
  the trades' and other cashflows' on the same curve object and currency, as it groups any.
- `util_ReadHandle` on the booked cashflows shows each row's key, the last column.
- `util_ReadHandle` on the results shows one row per payment day and key, where it showed one
  per payment day, with the key the last column and the batch's three totals once. A payment
  day on two keys is two rows.

## The refusals

In the words the build pins:

| Entered | Refused as |
|---|---|
| No key, in template or ticket | `discount_curve_key is missing, expected a value in the template or a column in the ticket` |
| A key in both | `discount_curve_key is supplied by the template and by the ticket, expected by one of them` |
| A key with a space around it | the curve's name rule, by the field or by the field and its row |
| One curve where the collection goes | the seam's words for a handle of another kind |
| A key the collection lacks | `discount_curve_key 'SONIA' of trade 1002 at row 2 names no curve of the collection, which holds 'SOFR' and 'FFOIS'; expected a curve of that name` |
| A selected curve starting on another day | `discount curve 'SOFR' starts on 2027-01-05, expected 2027-01-04, the valuation date; a curve is never rebased` |
| An unpaid day past its curve | `the payment on 2029-01-04 on SOFR is past the discount curve 'SOFR', which runs from 2027-01-04 to 2028-01-04; expected every unpaid payment day covered` |
| A group's amounts summing past the largest number | `the payments on 2028-01-04 on SOFR sum to inf, expected a finite amount of USD; the rows' amounts, each finite, sum past the largest number` |

## Hand-priced acceptance

Valued 4 January 2027, paying 4 January 2028, 365 days on. Both curves start on the
valuation day.

| Amount, USD | discount_curve_key | Factor | Mark | DV01, USD per basis point |
|---:|---|---:|---:|---:|
| 10,000 | SOFR | 0.95 | 9,500 | -0.95 |
| -10,000 | FFOIS | 0.90 | -9,000 | 0.90 |
| **Total** | | | **500** | **-0.05** |

The amounts net to nothing before discounting and are worth 500: two groups, never one. The
risk report has a SOFR column and an FFOIS column. With SOFR's factor at 0.96 the mark is
600 and the DV01 -0.06, FFOIS's column is as it was and the booked cashflows are the same
handle.

Also pin: two rows on one key and one day netting to one group; two days on one curve; a
repeated row; a negative and a zero amount, a group netting to zero kept with its key; the
key from the template and from a ticket column; a mixed batch equal to its one-curve batches
summed, mark, cash, DV01 and each curve's risk, alone and collected with bilateral trades;
the ticket's rows and the collection's curves in any order; the standalone report against a
collection of that result alone; every refusal above; a short or differently dated curve
nobody selects failing nothing; paid today, paid before and a mix of paid and unpaid, a paid
group reading no factor; and the finiteness of the group amounts, the values, the risk
vectors and the totals.

## Engineering boundaries and delivery

One pull request stacked on #259, this page and its index row in the first commit, the build
in the next. The definition, the key last; the booking, the key per row, the keys and the
groups; the valuation, the binding by the shared step, the per-curve rules and the
contributions; the worksheet function's third argument; the two readbacks; then every
existing cashflow formula in the tests, the host's facts, the smoke, the lifetime group and
the kept workbook cut over, and a mixed-curve block added to the kept workbook; the owning
pages, a history row and a UAT item.

Measure before and after. Booking scales with the rows and with the groups of day and key;
evaluation binds the distinct keys and reads one factor per unpaid group; a reader values
nothing again. The pull request states the counts it measured.

## Outside this ticket

Another currency, FX, payment reconciliation, overdue payments, another rate method,
commodity risk on a cashflow, quoting, and any change to a trade's economics.
