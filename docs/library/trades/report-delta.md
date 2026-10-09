# _ReportDelta

Built in #NN as the ticket [daily-risk-vector.md](../../engineering-tickets/trade-valuation-pipeline/daily-risk-vector.md) of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), beside [_ReportRisk](report-risk.md) and [_ReportValues](report-values.md); the design is [readers](../../engineering-tickets/trade-valuation-pipeline/06-readers.md).

The batch's delta by observation time, from its results: the lots still to price on each day the batch observes, in the index's reporting specification, summed across its trades, methods and payment groups, or the same lots summed by the calendar month those days fall in, or by the calendar year, in chronological order, with the lot unit and the valuation day beside each row. The three vectors are the preparation's, summed once from each slot's live lots and shared by every result over it; the reader selects one and sums, sorts and converts nothing. A day's lots fall to zero once it has fixed and its row stays; a bucket is a day, a month or a year the batch observes in, never a calendar day without an observation, and a payment day moves nothing.

## Worksheet contract

```python
def _ReportDelta(results: Handle[TradeResults], bucket: str = "day") -> MixedArray: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 21 | `=_ReportDelta(A12)` | | | |
| | bucket_start | delta | delta_unit | as_of |
| | datetime64[D] | float64 | str | datetime64[D] |
| | 1-Dec-2026 | 1 | lots of LOT (1000 BBL) | 1-Dec-2026 |
| | 2-Dec-2026 | 1 | lots of LOT (1000 BBL) | 1-Dec-2026 |
| | ... | | | |
| | 30-Dec-2026 | 4 | lots of LOT (1000 BBL) | 1-Dec-2026 |
| | 31-Dec-2026 | 1 | lots of LOT (1000 BBL) | 1-Dec-2026 |

One handle, required: the results, the cell showing `_EvaluateTrades`'s result or a name for it. One text, optional and last: `bucket`, exactly `day`, `month` or `year`; left out, `day`. The spill is a header row, a type row and one row per bucket, four columns: `bucket_start`, an Excel date, the observation day under `day`, the first day of the calendar month under `month` and 1 January of the calendar year under `year`, a label of the bucket and not an observation; `delta`, the lots still to price in it, signed, fractional where the weights are, zero once fixed or netted; `delta_unit`, the index's reporting lot's words; `as_of`, the valuation day the results were made on. `=_ReportDelta(A12, "month")` on the example above spills one row from 1 December 2026 of 25, `=_ReportDelta(A12, "year")` one row from 1 January 2026 of 25, the batch has no observation on either day.

The example is the ticket's: 22 LOT of a December asian and 3 LOT of a Z26 penultimate on a month-aligned index, both at 70 and +1bd, every settle 75. The asian is a lot on each of December's 22 pricing days and the pen 3 lots on the 30th, 4 that day and 25 in all; on 31 December the 30th reads zero and the 31st one, the month one, and on 4 January, paid, every row zero and every row kept. The sum of the day rows is `_ReportRisk`'s `delta_total`, the month rows sum to it and the year rows to the months.

## Excel help

| Item | Text |
|---|---|
| Function | Reports the batch's delta by observation time from its results: one row per day, calendar month or calendar year the batch observes in, the lots still to price summed into it, with the lot unit and the valuation day, as the preparation stored them. |
| results | The results handle: the cell showing _EvaluateTrades's result, such as A12, or a name for it. |
| bucket | What to sum the delta by: day, month or year, exactly so; day when left out. |

## The library checks

| Rule | Refused as |
|---|---|
| The bucket is one of the three words, exactly, case and all; a blank, empty text and a number are the seam's refusals, and only an omitted argument takes `day` | `bucket is 'quarter', expected day, month or year`; `bucket is 'Day', expected day, month or year` |

Nothing else: the three vectors are complete when the preparation publishes, each checked finite there, [kernel.md](kernel.md).

## What it reads

The encoding's time axes, static for the batch: the distinct observation days, increasing, each slot's day and each day's pricing contract; the first day of each calendar month those days fall in and each day's month; the first day of each calendar year and each month's year, three uniques over the slots when the batch is made. The preparation's three vectors: the live lots summed onto the days, then onto the months, then onto the years, one bincount each, checked finite, frozen, the same objects under every result made over that preparation and so under every tick. `util_ReadHandle` on the preparation and the results keeps its slot layout, each slot's pricing and booked contract, day and lots; the day's contract is retained on the axis and spilled by no reader here.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_trades.py` | the asian and the pen through the ticket's five states, by day, month and year, the rows reversed the same, the pen at +2bd coalescing the slots to 22 and changing no view; the WTI-like boundary case, two calendar-day asians and a month one over a year end, 1, 1, 2.5, 2.5, 1.5 and 1.5 by day off G27 then H27, 2, 5 and 3 by month, 2 and 8 by year, 7 and 3 by contract, through 1 January and 5 January; a lastday F27 counted in December, its observation's month, not January, its booked one; the six-day asian at 0.2 a day; same-day opposites netting to a kept zero and two-day opposites netting by month; two Decembers two months in two years; a day's and a month's lots summing past the largest number refused by their bucket |
| `tests/unit/test_create_trades.py` | the asian and the pen's axes from the ticket: 23 slots, 22 days, one month and one year, the rows reversed the same, the pen at +2bd one group of 22 slots on the same axes |
| `tests/unit/test_trade_valuation.py` | the ticket's table on the sheet through the five states, the selector left out the day view, the month and the year one row each, the day rows summing to `_ReportRisk`'s total; the refusals, a quarter, a case, a blank, empty text, a number, a blank results and a prepared handle; the six-day asian's three views, a tick spilling the same, the roll zeroing the first two days |
| `tests/performance/test_trade_budgets.py` | the encoding's ledger one function more, `_the_buckets`, three uniques; the preparation's three more bincounts, looks and freezes, `ndarray.any` 3 to 6, `ufunc.reduce` 7 to 10, `ndarray.setflags` 10 to 13; the pins by slot unchanged |
| `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `workbooks/handles.xlsx` | the WTI block's six days at 0.2, the month 1.2 and the year 1.2, the roll zeroing two days, the ethane asian's day and month, the refusals, on a sheet; the asian and the pen from the host on 1 December and the 31st; the kept workbook's block in rows 1741 to 1814, three states and the three views side by side |

## Not here

No DV01 by day, no discounting, no quarter or week, no hourly bucket, no second index, no two references on one day, no attribution to a trade or a method, no roll-off forecast and no display name: the ticket's boundaries. The contract pricing each day is retained on the axis and reconciles the days to the contract risk in the tests; no reader spills it yet.
