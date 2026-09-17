# _CreateMonthlyFixings

Built in #76.

The monthly fixings of one index: the price for each month it fixed, month beside price, as the desk keeps them, for an index that fixes once a month, Inside FERC's monthly gas indices say, where a daily series is not published and would be overkill. It is the daily fixings' sibling, the third market data, and the first function to hold a contract month as a unit of its own, as [time.md](../time.md) decides. Nothing reads the fixings yet, and nothing binds them to an index yet. The code is `src/goosedove/market_data/monthly_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreateMonthlyFixings(month: DateColumn, price: NumberColumn) -> Handle[MonthlyFixings]: ...
```

| | A | B |
|---|---|---|
| 1 | month | price |
| 2 | 1-May-2026 | 2.86 |
| 3 | 1-Jun-2026 | 3.01 |
| 4 | 1-Jul-2026 | 3.24 |
| 5 | 1-Aug-2026 | 3.19 |
| 6 | `=_CreateMonthlyFixings(A2:A5, B2:B5)` | shows `monthly_fixings:3f9a1c:000011` |

Two columns of one kind each, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The owner chose columns over the daily fixings' table for the sheet's ergonomics, a handful of months typed by hand rather than a history pasted from a source, at the cost the schedule's page states, that two columns can be selected one row out of step. A month is typed as its first day, `1-May-2026`, because a cell holds a date and not a month: typing `May-26` stores the 26th of May this year, the trap [inputs.md](../../seam/inputs.md) records against the seam's wanted `ContractMonth` type, and the library refuses any day but the first rather than read it as its month. The seam checks each column alone, dates one column wide, numbers one column wide, no blank cells, and hands over an array of days and an array of numbers; nothing here restates that. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[MonthlyFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings, their months as numpy months. A single cell is a column of one, so a fixing of one month needs no range.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the monthly fixings of one index from the months it fixed and their prices, and shows its handle, the text other formulas take as the fixings. |
| `month` | The column of months, each typed as its first day, such as A2:A5 holding 1-May-2026 to 1-Aug-2026. |
| `price` | The column of prices beside the months, such as B2:B5, one per month. |

## The library checks

Three rules, in this order, the first failure being the message. Rows count as the sheet counts them.

| Rule | Message |
|---|---|
| the price column has one row per month | `price has 3 prices, expected 4, one per month` |
| each date is the first day of its month | `month row 2 is 2026-05-26, expected the first day of a month` |
| each month after the row above, the owner's no duplicate dates and the dates ascending | `month row 3 is 2026-06, expected a month after row 2's 2026-06` |

A count of one reads `1 price`. The first-day rule runs before the order, since a day that is not the first has no month to order. The months are kept as months, `datetime64[M]`, never as first-of-month dates standing in for months; the builder makes them from the days it is handed, and copies the prices. Nothing is sorted: a series pasted newest first fails at its second row. Nothing else is checked. A price is any number a cell holds, zero and below included, as the futures curve's page says. What a price may be for a given index, and which months an index should have fixed for, are a reader's rules, written when the reader is. One fixing is a series. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_monthly_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings, the months as months; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the four-row sample above: every month kept as a month, beside its price | example |
| one fixing accepted as a series, from a one-row range and from two single cells | example |
| a price below zero, a zero, and gaps of any length between the months are kept as given: nothing else is checked | example |
| a price column one row short or long, a day that is not the first, two months swapped, a month twice, and a series newest first: rejected, naming the row, the first-day rule before the order | example |
| for any `N` increasing months typed as first days and any `N` prices, the months and prices are kept | property |
| an input changed after construction leaves the fixings unchanged, and their arrays refuse writes | example |
| a blank among the prices, a month typed as text, and the price column left out: the seam's words | example, through the seam |
| a failed construction publishes no object and no handle | example, with handles |
| a handle of another kind is not monthly fixings | example, with handles |
| the fixings' spill: `month` over `datetime64[M]` and `price` over `float64`, then one row per month, the month as its first day's serial | example |
| the creator's handle read back, a day that is not the first, months backwards, and codes where prices are expected, in a real workbook | Excel smoke |

## Not here

Reading a price by month, the months a period covers, and whether a month with no fixing is a gap or an error: the first consumer's job, with whatever it needs a series to hold true. Binding the fixings to an index. A month typed any other way than its first day, `May-26` above all, until the seam's `ContractMonth` type is built and takes the trap on itself. Sorting a pasted series. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns, a month as its first day under the month type, since a month cannot cross the seam as a month. Pricing and risk.
