# _CreateIfercFixings

Built in #99; the index since #NN.

The IFERC fixings of one index: Inside FERC's index for each contract month whose index has been published, price beside code, as the desk keeps them, kept as given and reached by handle. Inside FERC, IFERC for short, prints one index per location per delivery month, around noon on the publication day its calendar sets for that month, the first business day of the month in most months and later around a holiday, January 2026's index having printed on the 5th, from the fixed-price deals of bidweek; the ICE basis and fixed-price futures on that location settle to it, the basis future to the index minus NYMEX's final settlement for the same month. The number here is Platts' index as printed, the fact the desk has; the subtraction is the instrument's arithmetic, and NYMEX's final settlement already lives in the NG futures fixings on its last trading day. The fixings are keyed by the month, not by the day the index appeared, because the [IFERC schedule](../index-definitions/iferc-schedule.md) holds that day beside each month's code, so the two need not say it twice. It replaced `_CreateMonthlyFixings`, which was dated by publication and checked against the futures schedule's publication column, and which nothing read; that creator, its page and its record went with #99. Since #105 the [market history](../market/market-history.md) reads them, binding each published month's index to its row of the IFERC calendar; before that only [util_ReadHandle](../utilities/read-handle.md) did. From #NN the creator takes the [index](../index-definitions/index.md), as the [futures fixings](futures-fixings.md) do since #108: it keeps the index by reference, so that the fixings say whose they are and the history can check that they and its calendar are one index's; it refuses an index of another kind; and it reads the index's schedule for its months, refusing a code that is none of them, the rule the history held since #105 moving to where the codes are typed and checked once. The code is `src/goosedove/market_data/iferc_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreateIfercFixings(
    contract_code: TextColumn,
    price: NumberColumn,
    index: Handle[Index],
) -> Handle[IfercFixings]: ...
```

Waha IFERC, the first four months of 2026, with the prices illustrative and not published values, and the schedule's dates ICE's last trading days and Platts' publication days:

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | contract_code | price | last_trading_date | publication_date | |
| 2 | F26 | 1.85 | 31-Dec-2025 | 5-Jan-2026 | `=_CreateIfercSchedule(A2:A5, C2:C5, D2:D5)` shows `iferc_schedule:3f9a1c:000051` |
| 3 | G26 | 2.10 | 30-Jan-2026 | 2-Feb-2026 | `=_CreateIndex("Waha IFERC", E2, B10, B11)` shows `index:3f9a1c:000052`, B10 and B11 holding the conventions and the specifications |
| 4 | H26 | 1.95 | 27-Feb-2026 | 2-Mar-2026 | |
| 5 | J26 | 1.60 | 31-Mar-2026 | 1-Apr-2026 | |
| 6 | `=_CreateIfercFixings(A2:A5, B2:B5, E3)` | shows `iferc_fixings:3f9a1c:000053` | | | |
| 7 | `=_CreateIfercFixings(A2, B2, E3)` | shows `iferc_fixings:3f9a1c:000054`, the fixings of one month | | | |

Two columns of one kind each and a handle, all three required, none with a default, the columns selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the IFERC schedule's, columns paired by position, chosen for the sheet's ergonomics, a handful of months typed by hand rather than a history pasted from a feed, at the cost [inputs.md](../../seam/inputs.md) decision 38 states: two columns can be selected one row out of step, and equal lengths cannot catch it. The code column is `contract_code`, as the schedule's is, because the code labels the month the index is for; the same text names the future on that month, and in the sample the schedule and the fixings share the column, the months published being months of the schedule. A price is any number a cell holds, zero and below included, and Waha has printed below zero. The index comes by handle because it is an object the sheet already holds, made once by [_CreateIndex](../index-definitions/index.md) and named by its cell, as decisions 34 to 37 say: the function receives the index the seam keeps, never the text, and reads its schedule's months through it; a cell that is not an index's handle fails in the seam's words, `index is number 1.85, expected index handle`, before the function runs, and an index of another kind in the library's words, below. No holiday calendar is taken: an IFERC index has none, since the month prints on a day the schedule already holds. The seam checks each column alone, text one column wide, numbers one column wide, no blank cells, resolves the handle, and hands over a tuple of texts, an array of numbers and the index; nothing here restates that. A single cell is a column of one, so the fixings of one month need no range. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[IfercFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings, their index by reference and their two columns. The index is one object: the fixings and the calendar of their market refer to the same `_CreateIndex` cell, or a name for it, and are remade together when the index is.

`=util_ReadHandle(A6)` on the fixings above shows the two columns as they went in, the code as text and the price as a number, under the two heading rows, as it did before: the spill does not change.

| contract_code | price |
|---|---|
| str | float64 |
| F26 | 1.85 |
| G26 | 2.1 |
| H26 | 1.95 |
| J26 | 1.6 |

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the IFERC fixings of one index from the contract months whose index has been published and the index printed for each, checked against the months of its index, and shows its handle, the text other formulas take as the fixings. |
| `contract_code` | The column of contract codes, such as A2:A5 holding F26 to J26, one per month published. |
| `price` | The column of published indices beside the codes, such as B2:B5, one per code. |
| `index` | The index handle: the cell showing _CreateIndex's result, such as E3, or a name for it; an IFERC index, whose months the codes are checked against. |

## The library checks

Four rules, in this order, the first failure being the message. The first is the index's kind: the codes are checked against the months of an IFERC schedule, and only an IFERC index has one, so a futures or a Gas Daily index is refused naming its kind, as the calendar names kinds. The second comes with the columns: the price column has one row per code, since the seam never compares two columns and a series is rows. The third and fourth are read in one pass over the codes in row order, each row asked whether it names a month of the index and then whether it was given already, so the earliest offending row is named: each code is one of the index's months, matched exactly, spelling and case as typed, since an index for a month the schedule does not hold names nothing; and each code once, since a code given twice is two indices for one month and neither can be the month's. Rows count as the sheet counts them, the first row of the column being row 1.

| Rule | Message |
|---|---|
| the index is an IFERC index, whose months the codes are checked against | `index is a futures index, expected an IFERC index` |
| the price column has one row per code | `price has 3 prices, expected 4, one per contract_code` |
| each code one of the index's months, spelling and case as typed | `contract_code row 2 is 'K26', expected one of the index's months` |
| each code once | `contract_code row 3 is 'G26', already given at row 2` |

A count of one reads `1 price`. Nothing else is checked. The codes are kept as typed, the seam's tuple as it arrived, `f26` being no month of a schedule that spells it `F26`, and the prices as given, in the order given, copied and frozen so that a later change to the input cells changes no fixings; the index is kept by reference, the one the desk paired the series with. Nothing is sorted, filled or extended: the months may be typed in any order and a month may be missing, since whether a month's index has printed by a given day and whether every published month has its index are the history's rules, checked against the calendar it takes. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_iferc_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, creating and reading back, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market history's tests build their IFERC fixings through this creator and move with it.

| Case | Kind |
|---|---|
| the four-month sample above, over the index of those four months: every code and every price preserved, aligned, as typed, and the index kept | example |
| the fixings of one month accepted, from a one-row range and from two single cells; twelve months kept in their order | example |
| a price below zero and a zero kept as given | example |
| months out of the schedule's order and a month left out kept as given: nothing else is checked | example |
| a futures index and a Gas Daily index: rejected, naming the kind, before the columns are looked at | example |
| a price column one row short, one row long, one price for four codes and four prices for one code: rejected, naming the count; the count checked before the codes | example |
| a code the index does not hold, first, last and between, and a code in another case than the schedule's: rejected, naming the row and the code | example |
| a code given twice, and three times: rejected, naming the row it was already given at; when one row is unknown and another repeated, the earlier row is named | example |
| for any `N` distinct codes of an index's schedule and any column of `N` prices, everything is preserved and aligned | property |
| an input changed after construction leaves the fixings unchanged, the price array refuses writes, and the codes are the tuple that arrived | example |
| two columns and an index read back through their handle, and two single cells the fixings of one month | example, through the seam |
| a futures index where the IFERC index should be, a price column one row long or short, a code the index does not hold and a code twice, the library's words; a blank among the prices, text where a price should be, a number or empty text among the codes, a row where a column should be, either column left out or blank, and a number, a blank, a missing argument, text naming no live object, a creator's failure or a schedule's handle where the index should be, the seam's words, the codes named first when both columns are wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short, a code twice, a code the index does not hold and a blank among the prices alike | example, with handles |
| a handle of another kind is not IFERC fixings, the IFERC schedule's included, and is not an index | example, with handles |
| the spill: two headers, two types, then a row per month, the code as text and the price as a number, a zero and a negative in their places | example |
| the creator's handle over four rows and over two single cells, read back through `util_ReadHandle`, a column one row long and one row short, a code twice, a code the index does not hold, a blank among the prices, a number among the codes, and the index left out or a schedule in its place, in a real workbook | Excel smoke |

## Not here

Reading the fixings against a calendar: the [market history](../market/market-history.md)'s since #105, which takes the IFERC calendar and these fixings, from #NN requires the two to be one index's, the same `_CreateIndex` cell and not merely the same name, and requires that every month published before the valuation date has its index and no other month has one, each index landing on its month's row; that every code is a month of the index is checked here from #NN, once, where the codes are typed. The day an index printed: the [IFERC schedule](../index-definitions/iferc-schedule.md)'s, beside the month. NYMEX's final settlement for the month and the basis future's settlement, index minus that settlement: the instrument's, with the NG futures fixings beside it. A revised index: a new fixings object, never an edit; the library tells a provisional value from a published one in no way, a value supplied being a value. The monthly fixings of #76 and #81: removed in #99, their page with them; the futures schedule's publication column, which they alone read, went in #102. A holiday calendar: an IFERC index has none. Sorting a series, filling a missing month. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns. Pricing and risk.
