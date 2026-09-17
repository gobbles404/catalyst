# _CreateDailyFixings

Built in #75.

The daily fixings of one index: the settlement price on each day it fixed, date beside settle, as the desk keeps them, kept as given and reached by handle. It is the second market data, beside the futures curve: a history that instruments will settle against, as opposed to the curve that prices them. Nothing reads the fixings yet, and nothing binds them to an index yet. The code is `src/goosedove/market_data/daily_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
class DailyFixingsTable(Table):
    date: DateColumn
    settle: NumberColumn


def _CreateDailyFixings(header_row: TextRow, table: DailyFixingsTable) -> Handle[DailyFixings]: ...
```

| | A | B |
|---|---|---|
| 1 | date | settle |
| 2 | 1-May-2026 | 101.94 |
| 3 | 4-May-2026 | 106.42 |
| 4 | 5-May-2026 | 102.27 |
| 5 | 6-May-2026 | 95.08 |
| 6 | `=_CreateDailyFixings(A1:B1, A2:B5)` | shows `daily_fixings:3f9a1c:000010` |

The input is a table: a header row, then a body with one row per fixing, the date and its settle, dates increasing with any gaps between them, a weekend or a holiday. The owner chose a table over columns, the shape the futures curve takes, for two reasons its page states the other side of: a fixings series is closer to static data than to a ticking curve, so the table path's cost is paid rarely, and a body selected as one range cannot put a date beside the wrong settle, where two columns selected one row out of step could. The headers bind in either order and capital letters do not matter; the spelling must match, and `price` is not a header. Both arguments required, no defaults. The seam binds the headers, checks the columns and converts the dates, at the cost its ledgers state, one look per column and the gathers that pull each column out of the body; nothing here restates that. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[DailyFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the daily fixings of one index from the days it fixed and their settles, and shows its handle, the text other formulas take as the fixings. |
| `header_row` | The header cells of your fixings table, such as A1:B1, reading date and settle in either order. |
| `table` | The rows under the headers, such as A2:B5: one fixing per row, its date and settle, dates increasing. |

## The library checks

One rule, the curve's: each date is after the row above. It keeps one fixing per day, since a date twice would be two settles for one day, and the order a reader finds a day by. Rows count as the sheet counts them, the first row of the body being row 1, and the message names the column by its header, because the headers bind in either order.

| Rule | Message |
|---|---|
| each date after the row above; a gap of any length is expected | `date row 2 is 2026-05-01, expected a date after row 1's 2026-05-04` |

Nothing is sorted: a series pasted newest first fails at its second row, and the desk sorts it, because nothing in the library sorts anything. Nothing else is checked. A settle is any number a cell holds, zero and below included, as the futures curve's page says, and a cell holds no NaN or infinity to refuse. What a settle may be for a given index, and which days an index should have fixed on, are a reader's rules, written when the reader is. One fixing is a series. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_daily_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the four-row sample above: every date and settle preserved, aligned | example |
| one fixing accepted as a series | example |
| a settle below zero, a zero, and gaps of any length between the days are kept as given: nothing else is checked | example |
| two dates swapped, a date twice, and a series newest first: rejected, naming the row | example |
| for any `N` increasing dates and any `N` settles, everything is preserved and aligned | property |
| an input changed after construction leaves the fixings unchanged, and their arrays refuse writes | example |
| the headers bind in either order and any case | example, through the seam |
| an unknown header, text in the settle column, a body wider than its headers, a blank or a missing body, and headers down a column: the seam's words | example, through the seam |
| a failed construction publishes no object and no handle | example, with handles |
| a handle of another kind is not daily fixings | example, with handles |
| the fixings' spill: two headers, two types, then one row per day, the date as a serial and the settle exactly | example |
| the creator's handle read back, the days newest first, the headers where the body should be, and a header the table does not have, in a real workbook | Excel smoke |

## Not here

Reading a settle by date, the days a period covers and their average, which is how a swap settles, and whether a day with no fixing is a holiday, a missing row or an error: the first consumer's job, with whatever it needs a series to hold true, and the holiday calendar beside it. Binding the fixings to an index. A series as of a date, revisions to a published settle, bid and ask, volume. Sorting a pasted series. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns. Pricing and risk.
