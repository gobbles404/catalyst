# _CreatePublishedFixings

The published fixings of one index: the price of each print that has one, price beside the print's publication date, as the desk keeps a series, the newest at the top, and the index they are the fixings of. They are the fixings of a [published index](../index-definitions/published-schedule.md), one whose price is a listed set of dated prints, weekly retail diesel the first; the design and its decisions are [issue #271](https://github.com/gobbles404/catalyst/issues/271). They stand beside the [futures](futures-fixings.md), [IFERC](iferc-fixings.md) and [Gas Daily](gas-daily-fixings.md) fixings. The [market history](../market/market-history.md) binds them to the index's calendar, the [market](../market/market.md) adds the quotes of the prints still to come, and [util_ReadHandle](../utilities/read-handle.md) spills them. The code is `src/catalyst/market_data/published_fixings.py`, the record and its builder, and `src/catalyst/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreatePublishedFixings(
    publication_date: DateColumn,
    price: NumberColumn,
    index: Handle[Index],
) -> Handle[PublishedFixings]: ...
```

Hypothetical diesel prices, over the index of the [schedule page](../index-definitions/published-schedule.md)'s six prints, on Wednesday 16 September 2026:

| | A | B | C |
|---|---|---|---|
| 1 | publication_date | price | |
| 2 | 14-Sep-2026 | 3.20 | |
| 3 | 7-Sep-2026 | 3.00 | |
| 4 | 31-Aug-2026 | 2.95 | |
| 5 | `=_CreatePublishedFixings(A2:A4, B2:B4, D3)` | shows `30512:published_fixings:DOE Diesel:52` | D3 holding the index |

Two columns and a handle, all required, selected without the header row. A row says: the price this index dated this day. The date is the one the publisher puts on the price, the Monday for diesel, so the publisher's history is entered as it arrives and nobody relabels a date before a load. The newest print is the first row, so a new price is a row added at the top. A single cell is a column of one. The result is a handle, declared `Handle[PublishedFixings]`, and its text carries the index's name.

`=util_ReadHandle(A5)` shows the series as it went in, newest first, so the spill given back to the creator makes the same fixings:

| publication_date | price |
|---|---|
| datetime64[D] | float64 |
| 14-Sep-2026 | 3.2 |
| 7-Sep-2026 | 3 |
| 31-Aug-2026 | 2.95 |

Bound to the index's calendar valued that day, `_CreateMarketHistory` shows each fixed print's price and `unfixed` on the three still to come. With a price vector of two quotes, 3.50 for September and 3.65 for October, `_CreateMarket` shows September's quote on each of its two prints still to come and October's on its one:

| date | contract | is_priced | is_fixed | price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 31-Aug-2026 | Q26 | TRUE | TRUE | 2.95 |
| 7-Sep-2026 | U26 | TRUE | TRUE | 3 |
| 14-Sep-2026 | U26 | TRUE | TRUE | 3.2 |
| 21-Sep-2026 | U26 | TRUE | FALSE | 3.5 |
| 28-Sep-2026 | U26 | TRUE | FALSE | 3.5 |
| 5-Oct-2026 | V26 | TRUE | FALSE | 3.65 |

One quote per month, from the month of the first print still to come: a month's quote is the price of each of its prints still to come, however many of its prints have fixed. A whole-month quote already holds the fixed prints, so it is converted on the sheet before it is entered: with N prints in the month, k of them fixed, and a whole-month quote Q, the price to enter is `(N*Q - sum(fixed)) / (N-k)`.

## The stand-in

A print is fixed from the day after its date, and its publisher has not always released it by then. The Energy Information Administration releases Monday's diesel price on Tuesday around 10 a.m. Eastern, and on Wednesday after a Monday federal holiday. From the day after the print's date until the release, the history asks for a price the publisher has not given.

In that gap the desk enters a stand-in as the print's price: the front price of the price vector, the nearest live price. When the published price arrives it replaces the stand-in. A formula keeps the cell honest, the published price where its cell holds one and the front price where it does not:

| | A | B | C |
|---|---|---|---|
| 2 | 14-Sep-2026 | `=IF(ISNUMBER(C2), C2, F2)` | the published price, blank until it is released; F2 holds the front price of the vector |

- The library refuses a fixed print with no price, so the gap is never silent, and it cannot tell a stand-in from a published price: both are a number beside a date.
- The count of prints still to come, and so the sensitivity to the month's quote, is right in the gap: Monday's price reflects Monday, and nothing traded on Tuesday moves it. The value is off by the stand-in's miss on that one print.
- For the last print of a month the front price is the next month's, which is still the nearest live price.
- With a valuation at the end of the day the stand-in is needed only after a Monday federal holiday, five times in 2026. With a valuation in the morning it is needed every Tuesday until the release.

On Tuesday 15 September, before the release, the sample's first row holds the stand-in 3.50 and the market shows it on the print dated the 14th; after it, 3.20. Nothing else on the market moves.

## Excel help

Quoted from the declaration in `src/catalyst/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the published fixings of one index from the dates of its prints that have a price, newest first, and the price of each, checked against the dates of its index's schedule, and shows its handle, the text other formulas take as the fixings. |
| `publication_date` | The column of dates on the prints that have a price, newest first, such as A2:A4 holding 14-Sep-2026 down to 31-Aug-2026, each a date of the index's schedule. |
| `price` | The column of prices beside the dates, such as B2:B4, one per date; a stand-in where a print has fixed and its publisher has not released it. |
| `index` | The index handle: the cell showing _CreateIndex's result, such as D3, or a name for it; a published index, whose schedule the dates are checked against. |

## The library checks

Four rules, in this order, the first failure being the message. Rows count as the sheet counts them, the first row of a column being row 1, and within a rule the first row from the top that breaks it is named.

| Rule | Message |
|---|---|
| the index is a published index | `index is an IFERC index, expected a published index` |
| the price column has one row per date | `price has 2 prices, expected 3, one per publication_date` |
| each date is before the row above, which keeps the newest first and refuses a date given twice | `publication_date row 2 is 2026-09-07, expected a date before row 1's 2026-08-31` |
| each date is the publication date of one of the index's prints | `publication_date row 1 is 2026-09-15, expected the publication date of one of the index's prints` |

A count of one reads `1 price`. Nothing is sorted, so a series pasted oldest first fails at its second row. The last rule keeps the fixings to the schedule's prints: history from before the schedule's first row stays off the sheet, and a price entered under the day it was released, where its date should be, is refused. Any prints of the schedule may be given; the fixings take no valuation date. Which prints have fixed by a given day, and whether every fixed print has its price, are the [market history](../market/market-history.md#the-library-checks)'s rules, checked against the calendar it takes: a fixed print with no price is refused there, and so is a price for a print not yet fixed.

A price is any number a cell holds, zero and below included. Each price's print is found once, here, by one search of the schedule's dates, and kept, so the history searches nothing. The prices are copied and frozen, the series kept oldest first, and the index kept by reference. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and properties are `tests/unit/test_published_fixings.py`; the history's rules are `tests/unit/test_market_history.py` and the market's `tests/unit/test_market.py`; the seam's texts, the handle and the spill are `tests/unit/test_market_data.py`; the history and the market read back through the seam, the stand-in among them, are `tests/unit/test_market_creators.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`: the creator works by column and searches the schedule once; the history searches nothing and copies neither column.

| Case | Kind |
|---|---|
| the sample above: kept oldest first, each price on its print; one price a series; any prints of the schedule taken, with a gap or past any day; a price of zero or below; no rows | example |
| an index of another kind; a price column short or long; a series oldest first, a date given twice, a date after the row above further down; the day a price was released, history from before the schedule, a date after its last print, and two unlisted dates, the first from the top named; the rules in order | example |
| for any schedule and any of its prints given newest first, each price is kept on its print's row; for any date between two prints, the series is refused at that row | property |
| an input changed after construction leaves the fixings unchanged, both arrays refuse writes, and the index is the one given | example |
| the history: the sample's three fixed prints priced and no other; one print, and nothing fixed; a price for the print dated the valuation day refused at any fraction of the day and required the day after; a stand-in makes the history; a price for a print not yet fixed, the earliest named, and a fixed print without a price, newest, between two, oldest and none at all | example |
| the market: the month of the first print still to come quoted first, on a Monday, the Tuesday, a month's last print's own date and the day after it; a month whose prints have all fixed not quoted; a stand-in moves the one print and nothing of the live side | example |
| for any published history, a quote per month from the first unfixed print's, and the market's readback its fixing or its month's quote on every print | property |
| through the seam: the fixings created, read back and fed back to their creator; every refusal above and the seam's own words; the history and the market read back print by print; a fixed print without a price refused and a stand-in accepted; fixings over another index refused | example, through the seam |
| the fixings, the history, the market and the stand-in's formula in a real workbook | Excel smoke |

## Not here

Trades that average a month's prints, date windows and quoting, and the IFERC fixings moving onto this kind, entered by publication date in place of contract code: the later steps of [issue #271](https://github.com/gobbles404/catalyst/issues/271). A release date, and telling a stand-in from a published price: the library holds one date per print, by the owner's decision on the issue. A whole-month quote as a market input: converted on the sheet, as above. A history valued before the schedule's first print has fixed: it needs fixings of no rows, a column the sheet cannot paste, so that calendar has no history until its first print fixes, as an IFERC calendar has none before its first index. Rounding of a month's average, and fetching prices. Pricing and risk.
