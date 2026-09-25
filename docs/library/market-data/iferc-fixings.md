# _CreateIfercFixings

Built in #99.

The IFERC fixings of one index: Inside FERC's index for each contract month whose index has been published, price beside code, as the desk keeps them, kept as given and reached by handle. Inside FERC, IFERC for short, prints one index per location per delivery month, around noon on the publication day its calendar sets for that month, the first business day of the month in most months and later around a holiday, January 2026's index having printed on the 5th, from the fixed-price deals of bidweek; the ICE basis and fixed-price futures on that location settle to it, the basis future to the index minus NYMEX's final settlement for the same month. The number here is Platts' index as printed, the fact the desk has; the subtraction is the instrument's arithmetic, and NYMEX's final settlement already lives in the NG futures fixings on its last trading day. The fixings are keyed by the month, not by the day the index appeared, because the [IFERC schedule](../index-definitions/iferc-schedule.md) holds that day beside each month's code, so the two need not say it twice. It replaces `_CreateMonthlyFixings`, which was dated by publication and checked against the futures schedule's publication column, and which nothing read; that creator, its page and its record go with this build. Nothing reads the IFERC fixings yet but [util_ReadHandle](../utilities/read-handle.md); the history of the IFERC market is the first reader, when it is written, binding each expired month's index to the days of the IFERC calendar. The code is `src/goosedove/market_data/iferc_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreateIfercFixings(
    contract_code: TextColumn,
    price: NumberColumn,
) -> Handle[IfercFixings]: ...
```

Waha IFERC, the first four months of 2026, with the prices illustrative and not published values:

| | A | B |
|---|---|---|
| 1 | contract_code | price |
| 2 | F26 | 1.85 |
| 3 | G26 | 2.10 |
| 4 | H26 | 1.95 |
| 5 | J26 | 1.60 |
| 6 | `=_CreateIfercFixings(A2:A5, B2:B5)` | shows `iferc_fixings:3f9a1c:000053` |
| 7 | `=_CreateIfercFixings(A2, B2)` | shows `iferc_fixings:3f9a1c:000054`, the fixings of one month |

Two columns of one kind each, both required, neither with a default, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the IFERC schedule's, columns paired by position, chosen for the sheet's ergonomics, a handful of months typed by hand rather than a history pasted from a feed, at the cost [inputs.md](../../seam/inputs.md) decision 38 states: two columns can be selected one row out of step, and equal lengths cannot catch it. The code column is `contract_code`, as the schedule's is, because the code labels the month the index is for; the same text names the future on that month. A price is any number a cell holds, zero and below included, and Waha has printed below zero. No schedule and no holiday calendar are taken: what must hold between these months and the schedule's is the history's rule, below under Not here. The seam checks each column alone, text one column wide, numbers one column wide, no blank cells, and hands over a tuple of texts and an array of numbers; nothing here restates that. A single cell is a column of one, so the fixings of one month need no range. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[IfercFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings.

`=util_ReadHandle(A6)` on the fixings above shows the two columns as they went in, the code as text and the price as a number, under the two heading rows:

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
| Function | Creates the IFERC fixings of one index from the contract months whose index has been published and the index printed for each, and shows its handle, the text other formulas take as the fixings. |
| `contract_code` | The column of contract codes, such as A2:A5 holding F26 to J26, one per month published. |
| `price` | The column of published indices beside the codes, such as B2:B5, one per code. |

## The library checks

Two rules, in this order, the first failure being the message. Rows count as the sheet counts them, the first row of the column being row 1.

| Rule | Message |
|---|---|
| the price column has one row per code, since the seam never compares two columns and a series is rows | `price has 3 prices, expected 4, one per contract_code` |
| each code once, spelling and case as typed, since a code given twice is two indices for one month and neither can be the month's | `contract_code row 3 is 'G26', already given at row 2` |

A count of one reads `1 price`. Nothing else is checked. The codes are kept as typed, `f26` and `F26` being two codes, the seam's tuple as it arrived, and the prices as given, in the order given, copied and frozen so that a later change to the input cells changes no fixings. Nothing is sorted, filled or extended: the months may be typed in any order, a month may be missing, and a code the schedule does not list is kept, since whether the months are the schedule's, whether they run without a gap and whether a month's index has printed are the history's rules, written when the history is and checked against the schedule it takes. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_iferc_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, creating and reading back, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the four-month sample above: every code and every price preserved, aligned, as typed | example |
| the fixings of one month accepted, from a one-row range and from two single cells; twelve months kept in their order | example |
| a price below zero and a zero kept as given | example |
| codes in either case, months out of the schedule's order, a month left out and a code no schedule lists kept as given: nothing else is checked | example |
| a price column one row short, one row long, one price for four codes and four prices for one code: rejected, naming the count | example |
| a code given twice, and three times: rejected, naming the row it was already given at; the count checked before the repeat | example |
| for any `N` distinct codes and any column of `N` prices, everything is preserved and aligned | property |
| an input changed after construction leaves the fixings unchanged, the price array refuses writes, and the codes are the tuple that arrived | example |
| two columns read back through their handle, and two single cells the fixings of one month | example, through the seam |
| a price column one row long or short and a code twice, the library's words; a blank among the prices, text where a price should be, a number or empty text among the codes, a row where a column should be, either column left out or blank, the seam's words, the codes named first when both columns are wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short, a code twice and a blank among the prices alike | example, with handles |
| a handle of another kind is not IFERC fixings, the IFERC schedule's included | example, with handles |
| the spill: two headers, two types, then a row per month, the code as text and the price as a number, a zero and a negative in their places | example |
| the creator's handle over four rows and over two single cells, read back through `util_ReadHandle`, a column one row long and one row short, a code twice, a blank among the prices, a number among the codes and the prices left out, in a real workbook | Excel smoke |

## Not here

Reading the fixings for anything: the history of the IFERC market, when it is written, which will take the IFERC calendar and these fixings and decide that every code is one of the schedule's, matched exactly, that every month expired by the valuation date has its index and no live month has one, and which days each index falls on. The day an index printed: the [IFERC schedule](../index-definitions/iferc-schedule.md)'s, beside the month. NYMEX's final settlement for the month and the basis future's settlement, index minus that settlement: the instrument's, with the NG futures fixings beside it. A revised index: a new fixings object, never an edit; the library tells a provisional value from a published one in no way, a value supplied being a value. The monthly fixings of #76 and #81: removed with this build, their page with them; the futures schedule's publication column, which they alone read, went in #102. Sorting a series, filling a missing month. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns. Pricing and risk.
