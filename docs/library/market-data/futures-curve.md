# _CreateFuturesCurve

Built in #74.

The futures curve of one index: the price of each contract, code beside price, as the desk keeps it on one day, kept as given and reached by handle. It is the first market data, the prices an index's instruments will be priced and risked off, as opposed to the index definitions that say what the index is; nothing reads the curve yet, and nothing binds it to an index yet. The code is `src/goosedove/market_data/futures_curve.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreateFuturesCurve(future_code: TextColumn, price: NumberColumn) -> Handle[FuturesCurve]: ...
```

| | A | B |
|---|---|---|
| 1 | future_code | price |
| 2 | M26 | 71.25 |
| 3 | N26 | 71.40 |
| 4 | Q26 | 71.10 |
| 5 | U26 | 70.85 |
| 6 | V26 | 70.60 |
| 7 | X26 | 70.40 |
| 8 | `=_CreateFuturesCurve(A2:A7, B2:B7)` | shows `futures_curve:3f9a1c:000009` |

Two columns of one kind each, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The owner chose columns over a table because a curve is hot data, rebuilt whenever prices move, and the seam's own numbers bear that out: a column of numbers crosses on the host's summary of kinds alone, with no look at the cells and no temporary per cell, and a column of text is the host's tuple handed over as it is, while a welded table pays the header binding, one look per column and the gathers that pull each column out of the mixed body ([measuring.md](../../seam/measuring.md), and the two ledgers side by side in `tests/performance/test_seam_budgets.py`). The cost is the one the schedule's page states: two columns can be selected one row out of step, and equal lengths cannot catch it. It is the third function to take columns of one kind without headers, after the schedule and the calendar ([inputs.md](../../seam/inputs.md) decision 38). The seam checks each column alone, text one column wide, numbers one column wide, no blank cell and no text among the numbers, and hands over a tuple of texts and an array of numbers; nothing here restates that. The result is a handle: text in the cell that stands for the curve the seam keeps, declared `Handle[FuturesCurve]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the curve. A single cell is a column of one, so a curve of one contract needs no range.

What a recalculation costs is the seam's open item, not this function's: today every creator call publishes anew, so a curve whose prices tick is rebuilt and republished each time, and reuse of an unchanged creator is the next handle pull request ([handles.md](../../seam/handles.md)).

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a futures curve from the contract codes of one index and their prices, and shows its handle, the text other formulas take as the curve. |
| `future_code` | The column of contract codes, such as A2:A7 holding M26 to X26, one per contract. |
| `price` | The column of prices beside the codes, such as B2:B7, one per code. |

## The library checks

One rule: the columns have one row per code, because the seam never compares two arguments and a curve is rows.

| Rule | Message |
|---|---|
| the price column has one row per code | `price has 5 prices, expected 6, one per future_code` |

A count of one reads `1 price`. Nothing else is checked. The codes are kept as typed, the prices as given, in the order given: a price is any number a cell holds, zero and below included, since WTI's May 2020 contract settled at minus 37.63 dollars, and a cell holds no NaN or infinity to refuse. Whether codes repeat, whether they follow the index's schedule, and what a price may be for a given index are a reader's rules, written when the reader is; what a code means is decided in [time.md](../time.md). A one-contract curve is a curve. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_futures_curve.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the curve; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the six-row sample above: every code and price preserved, aligned, as typed | example |
| a one-contract curve accepted, from a one-row range and from two single cells | example |
| a negative price, a zero, repeated codes and codes out of order are kept as given: nothing else is checked | example |
| a price column one row short, one row long, and one price for six codes: rejected, naming the count | example |
| for any `N` codes and any `N` prices, everything is preserved and aligned | property |
| an input changed after construction leaves the curve unchanged, and its prices refuse writes | example |
| a failed construction publishes no object and no handle | example, with handles |
| a blank, prices typed as text, a row where the price column should be, a number among the codes, and the price column left out: the seam's words | example, through the seam |
| a handle of another kind is not a futures curve | example, with handles |
| the curve's spill: two headers, two types, then one row per contract, the code as text and the price exactly | example |
| the creator's handle read back, a column one row short, a blank among the prices and the price column left out, in a real workbook | Excel smoke |

## Not here

Binding the curve to an index, and reading a contract's price by code, by month or by position: the first consumer's job, with whatever it needs a curve to hold true; the day the prices are for is the valuation date's. A curve as of a date, a history of curves, a settlement curve beside a live one, bid and ask, volume and open interest. What a code means: text here, as on the schedule's page, decided in [time.md](../time.md). Reuse of an unchanged creator on recalculation: the seam's, in [handles.md](../../seam/handles.md). A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any curve as two columns. Pricing and risk off the curve.
