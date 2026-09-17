# _CreateMonthlyFixings

Built in #76; dated by publication and checked against the expiry schedule since #81.

The monthly fixings of one index: the price for each contract month, dated by the day the index's settle for that month was published, price beside publication date, as the desk keeps them, for an index published once a month, Inside FERC's monthly gas indices say, where a daily series is not published and would be overkill. It is the daily fixings' sibling, the third market data. Since #81 the creator takes the index's expiry schedule and checks the series against the schedule's publication dates: every fixing falls on a day the schedule publishes, and every publication between the first fixing and the last has one. The months are no longer typed as their first days and no longer kept as [time.md](../time.md)'s month unit: a monthly settle appears on a day of its own, which the schedule states, and that day is what the fixing is dated by. Nothing reads the fixings yet, and nothing binds them to an index yet. The code is `src/goosedove/market_data/monthly_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreateMonthlyFixings(
    publication_date: DateColumn, price: NumberColumn, expiry_schedule: Handle[ExpirySchedule]
) -> Handle[MonthlyFixings]: ...
```

Waha IFERC natural gas, the final monthly index Platts publishes on the first business day of each month, with the prices illustrative and not published values:

| | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| 1 | publication_date | price | | future_code | future_expiry | publication_date |
| 2 | 5-Jan-2026 | 1.85 | | F26 | 31-Dec-2025 | 5-Jan-2026 |
| 3 | 2-Feb-2026 | 2.10 | | G26 | 30-Jan-2026 | 2-Feb-2026 |
| 4 | 2-Mar-2026 | 1.95 | | H26 | 27-Feb-2026 | 2-Mar-2026 |
| 5 | 1-Apr-2026 | 1.60 | | J26 | 31-Mar-2026 | 1-Apr-2026 |
| 6 | `=_CreateMonthlyFixings(A2:A5, B2:B5, D6)` | shows `monthly_fixings:3f9a1c:000011` | | `=_CreateExpirySchedule(D2:D5, E2:E5, , F2:F5)` | shows `expiry_schedule:3f9a1c:000010` | |

January's final indices were published on 5 January 2026, not on the 1st, a holiday, nor on the 2nd, as [Platts announced](https://www.spglobal.com/energy/en/pricing-benchmarks/our-methodology/subscriber-notes/120425-platts-confirms-daily-monthly-north-american-natural-gas-trading-calendar-for-christmas-new-years-day) for the Christmas and New Year calendar; February's and March's on the 2nd, the 1st falling on a Sunday both times. That is why the input is the publication date and not a first-of-month label: the day is a fact of the index's calendar, stated once in its schedule, and a label would have to be turned back into it.

Two columns of one kind each and a handle. The columns are selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The owner chose columns over the daily fixings' table for the sheet's ergonomics, a handful of months typed by hand rather than a history pasted from a source, at the cost the schedule's page states, that two columns can be selected one row out of step. The schedule comes by handle because it is an object the sheet already holds, made once by [_CreateExpirySchedule](../index-definitions/expiry-schedule.md) with its publication dates and named by its cell, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say: the function receives the schedule the seam keeps, never the text, and a cell that is not a schedule's handle fails in the seam's words, `expiry_schedule is number 2.86, expected expiry schedule handle`, before the function runs. All three arguments required, no defaults. The seam checks each column alone, dates one column wide, numbers one column wide, no blank cells, resolves the handle, and hands over an array of days, an array of numbers and the schedule; nothing here restates that. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[MonthlyFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings, their publication dates as days. A single cell is a column of one, so a fixing of one publication needs no range.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the monthly fixings of one index from the days its settles were published and their prices, checked against the publication dates of its expiry schedule, and shows its handle, the text other formulas take as the fixings. |
| `publication_date` | The column of days the index's monthly settles were published, such as A2:A5 holding 5-Jan-2026 to 1-Apr-2026, one per fixing. |
| `price` | The column of prices beside the dates, such as B2:B5, one per date. |
| `expiry_schedule` | The index's expiry-schedule handle, built with its publication dates: the cell showing _CreateExpirySchedule's result, such as D6, or a name for it. |

## The library checks

Five rules, in this order, the first failure being the message. Rows count as the sheet counts them, the first row of the column being row 1.

| Rule | Message |
|---|---|
| the schedule has publication dates | `expiry_schedule has no publication dates, expected a schedule with one per contract` |
| the price column has one row per date | `price has 3 prices, expected 4, one per publication_date` |
| each date after the row above, the owner's no duplicate dates and the dates ascending | `publication_date row 2 is 2026-01-05, expected a date after row 1's 2026-02-02` |
| each date one the schedule publishes on, before its first and after its last as much as between | `publication_date row 1 is 2026-01-01, expected one of the schedule's publication dates` |
| every publication from the first date to the last has a fixing | `publication_date row 2 is 2026-03-02, expected 2026-02-02, the schedule's publication after row 1's 2026-01-05` |

A count of one reads `1 price`. The schedule's publication dates are read as a set, sorted once into a copy of their own, so their order and any repetition in the schedule change nothing, and the schedule is neither written to nor kept: the fixings hold dates and prices only, and read nothing of the codes or the expiries. What the schedule says is authoritative, a Saturday or a holiday included, because whoever wrote it has already moved a publication off a closed day; no holiday calendar is taken and no weekday is looked at. The first and last dates bound the last rule, so publications before the first and after the last impose nothing, a partial history is whole between its own ends, and a single publication is a series. With every date scheduled and the dates increasing, the series is whole exactly when each date is the schedule's next publication after the one above, which is one search over the column and one comparison. Nothing is sorted, filled or extended: a series pasted newest first fails at its second row, and a publication without a fixing is a row to paste. Nothing else is checked. A price is any number a cell holds, zero and below included, as the futures curve's page says, and Waha has printed below zero. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_monthly_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings, the publication dates as days; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the four-row sample above under a schedule that runs from November 2025 to June 2026: every publication date kept as the day it is, beside its price | example |
| one fixing accepted as a series, from a one-row range and from two single cells | example |
| February and March alone: the publications before and after impose nothing | example |
| a price below zero and a zero are kept as given | example |
| the schedule's dates shuffled and one repeated say the same, and the array handed over is neither written to nor kept | example, and through the seam with a schedule whose codes and futures repeat alongside |
| a publication the schedule puts on a Saturday or a holiday is accepted | example |
| a schedule without publication dates, a price column one row short or long, two dates swapped, a date twice, a series newest first, the first of the month in place of the publication day, the day after a publication, a date before the schedule's first or after its last, a publication skipped, and three skipped: rejected, naming the row; the order before the schedule, the schedule before the gaps, and the schedule's dates before the prices | example |
| for any schedule of distinct days in any order and any run of them, the run and its prices are kept; with one publication left out, the row after the gap is refused, naming the day | property |
| an input changed after construction, the schedule's array included, leaves the fixings unchanged, and their arrays refuse writes | example |
| a blank among the prices, a date typed as text, the price column left out, and the schedule left out, a blank cell, a number or a handle of another kind in its place: the seam's words | example, through the seam |
| a failed construction publishes no object and no handle | example, with handles |
| a handle of another kind is not monthly fixings | example, with handles |
| the fixings' spill: `publication_date` over `datetime64[D]` and `price` over `float64`, then one row per fixing, the day as a serial | example |
| the creator's handle read back, a day the schedule does not publish on, the days backwards, a publication skipped, a schedule without publication dates, codes where prices are expected, and the schedule left out, in a real workbook | Excel smoke |

## Not here

Reading a price by publication date or by contract month, which contract month a publication belongs to, and the months a period covers: the first consumer's job, with the schedule beside it, since the fixings keep dates and prices only. Binding the fixings to an index. Whether the schedule's publication dates are right: the schedule's author's, and the calendar's when one is tied to it. Sorting a pasted series, filling a missing fixing. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns. Pricing and risk.
