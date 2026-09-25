# _CreateCalendar

Built in #82 over a futures schedule; any schedule since #104.

The calendar of one index: the run of periods the index prices, each with the contract it belongs to, whether it prices and whether it is on the fixed side of the valuation date, built once from the index's schedule and reached by handle. It is the backbone the pricing will run along and the shell the market history and the market fill: no price, no fixing and no publication is read here, so the object is built once and stands while prices move. Since #82 it has been the futures calendar alone, every day from the day after the first contract expires to the day the last expires, the prompt contract on each. From #104 it takes any of the three schedules, and the schedule's kind says which calendar is made: the futures schedule gives the calendar of #82; the [Gas Daily schedule](../index-definitions/gas-daily-schedule.md) gives every flow day from the first month's first day to the last month's last, each day the month it flows in; and the [IFERC schedule](../index-definitions/iferc-schedule.md) gives one row per contract month, dated by the day its index is published. Nothing on the sheet names the market: the handle in the schedule cell already says what it is, `futures_schedule`, `gas_daily_schedule` or `iferc_schedule`, and the library reads the kind off the object the seam hands it, as `util_ReadHandle` does. The three calendars share one record and four columns, so that one [market history](../market/market-history.md) and one [market](../market/market.md) can serve every market, and instruments that combine markets, an index swap over the Gas Daily average against the IFERC index, a swing swap over chosen days, read the same shape from each; the history binds only a futures calendar until its own ticket. The code is `src/goosedove/calendar/calendar.py`, the record and its builder, and `src/goosedove/excel/calendar.py`, the worksheet function.

## Worksheet contract

```python
def _CreateCalendar(
    valuation_date: Handle[ValuationDate],
    schedule: Handle[object],
    holiday_calendar: Handle[HolidayCalendar] | None = None,
) -> Handle[Calendar]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 1 | as_of | 25-May-2026 | contract_code | future_expiry |
| 2 | holiday | 25-May-2026 | m26 | 19-May-2026 |
| 3 | | | n26 | 22-Jun-2026 |
| 4 | | | q26 | 21-Jul-2026 |
| 5 | `=_CreateValuationDate(B1, 0.5)` | shows `valuation_date:3f9a1c:000001` | `=_CreateFuturesSchedule(C2:C4, D2:D4)` | shows `futures_schedule:3f9a1c:000004` |
| 6 | `=_CreateHolidayCalendar(B2)` | shows `holiday_calendar:3f9a1c:000007` | | |
| 7 | `=_CreateCalendar(A5, C5, A6)` | shows `calendar:3f9a1c:000012`, the futures calendar | | |
| 8 | `=_CreateCalendar(A5, B20)` | shows `calendar:3f9a1c:000013`, B20 holding a Gas Daily schedule | | |
| 9 | `=_CreateCalendar(A5, B30)` | shows `calendar:3f9a1c:000014`, B30 holding an IFERC schedule | | |

Two handles required and one that may be left out: the valuation date, the index's schedule, and, for a futures schedule alone, the market's holiday calendar, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say. The schedule is declared `Handle[object]`, the form [inputs.md](../../seam/inputs.md) decision 40 gave `util_ReadHandle`: the seam resolves the handle and hands over whatever object it finds, naming no kind, and the library says whether it is one of the three schedules. The holiday calendar is declared `Handle[HolidayCalendar] | None = None`, the form decision 39 gives an argument that may be left out with nothing in its place, which a handle takes since #103: the function receives `None` only when the argument is left out, and a blank cell in the slot fails as a blank. A cell that is not the right kind's handle fails in the seam's words where the seam names a kind, `holiday_calendar is calendar handle 'calendar:3f9a1c:000012', expected holiday calendar handle`, before the function runs, and in the library's words for the schedule, below. The result is a handle: text in the cell that stands for the calendar the seam keeps, declared `Handle[Calendar]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the calendar, its sources by reference, its kind and its four columns.

`=util_ReadHandle(A7)` on the futures calendar above runs from 20 May to 21 July 2026, 63 days, and shows among its rows:

| date | contract | is_priced | is_fixed |
|---|---|---|---|
| datetime64[D] | str | bool | bool |
| 20-May-2026 | n26 | TRUE | TRUE |
| 22-May-2026 | n26 | TRUE | TRUE |
| 23-May-2026 | n26 | FALSE | TRUE |
| 24-May-2026 | n26 | FALSE | TRUE |
| 25-May-2026 | n26 | FALSE | FALSE |
| 26-May-2026 | n26 | TRUE | FALSE |
| … | … | … | … |
| 22-Jun-2026 | n26 | TRUE | FALSE |
| 23-Jun-2026 | q26 | TRUE | FALSE |
| … | … | … | … |
| 21-Jul-2026 | q26 | TRUE | FALSE |

`=util_ReadHandle(A8)` on the Gas Daily calendar, built from the schedule page's three months, runs from 1 September to 30 November 2026, 91 days, every one priced, the flow day of the valuation date fixed with the days before it:

| date | contract | is_priced | is_fixed |
|---|---|---|---|
| datetime64[D] | str | bool | bool |
| 1-Sep-2026 | U26 | TRUE | FALSE |
| … | … | … | … |
| 30-Sep-2026 | U26 | TRUE | FALSE |
| 1-Oct-2026 | V26 | TRUE | FALSE |
| … | … | … | … |
| 30-Nov-2026 | X26 | TRUE | FALSE |

`=util_ReadHandle(A9)` on the IFERC calendar, built from the schedule page's three months, shows one row per month, dated by the day its index is published, every one priced, a month fixed once its publication day has passed:

| date | contract | is_priced | is_fixed |
|---|---|---|---|
| datetime64[D] | str | bool | bool |
| 1-Oct-2026 | V26 | TRUE | FALSE |
| 2-Nov-2026 | X26 | TRUE | FALSE |
| 1-Dec-2026 | Z26 | TRUE | FALSE |

The four columns, one shape for the three markets: `date`, the day a period's price is dated by, the calendar day itself for a futures or a Gas Daily calendar and the publication day for an IFERC one, as [time.md](../time.md) decided every period would be spelled, day by day; `contract`, the code of the contract the period belongs to, as the desk typed it in the schedule, the prompt future on a futures day and the delivery month otherwise; `is_priced`, whether the period has a price of its own, Monday to Friday and not a listed holiday on a futures calendar, every row on the other two, since Gas Daily prints every flow day and an index is a price for its whole month; and `is_fixed`, whether the period is on the fixed side of the valuation date, the side the history binds a fixing to. That side is decided per market by when its price becomes known: a futures settle prints at the close, so a day is fixed when it is before the valuation date's day; a Gas Daily midpoint prints on the session before the flow day, so a flow day is fixed when it is on or before the valuation date's day; and an Inside FERC index prints during its publication day, so a month is fixed when that day is before the valuation date's day. The valuation date's fraction changes nothing, as before. The columns were `prompt_contract`, `is_business_day` and `is_past` for the futures calendar of #82; the names change here because each now means more than a futures day, and the spill and its readers change with them.

## Excel help

Quoted from the declaration in `src/goosedove/excel/calendar.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the calendar of one index from its schedule, one row per day it prices, or per month for an index published monthly, each with its contract and whether it has fixed, and shows its handle, the text other formulas take as the calendar. |
| `valuation_date` | The valuation-date handle: the cell showing _CreateValuationDate's result, such as B2, or a name for it. |
| `schedule` | The index's schedule handle, futures, IFERC or Gas Daily: the cell showing its creator's result, such as B8, or a name for it; a futures schedule needs two contracts or more. |
| `holiday_calendar` | The market's holiday-calendar handle with a futures schedule: the cell showing _CreateHolidayCalendar's result, such as B12, or a name for it; left out for an IFERC or Gas Daily schedule. |

Registration shows the third as `[holiday_calendar]`, with its line alone: the brackets say it may be left out, and the line is written as if the argument were required, as every line is.

## The library checks

The schedule's kind first, then the holiday calendar against it, then the rules of that kind's calendar, in this order, the first failure being the message. They are the calendar's, not the schedule's, so a schedule of one contract or with a code twice is still a schedule. Rows count as the sheet counts them, the schedule's first row being row 1. The kind is read off the object the seam hands over, the one way the library tells kinds apart, the way `util_ReadHandle` chooses a table for a handle, and no text is parsed.

| Rule | Message |
|---|---|
| the schedule is a futures, IFERC or Gas Daily schedule | `schedule is a holiday calendar, expected a futures, IFERC or Gas Daily schedule` |
| a futures schedule brings the holiday calendar, and the other two leave it out, since nothing reads it there | `holiday_calendar is missing, expected holiday calendar handle with a futures schedule`, or `holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule` |

A futures schedule's four rules stand from #82 word for word but the first, whose message names the argument as it is now:

| Rule | Message |
|---|---|
| the schedule has two contracts or more, the first only bounding the calendar | `schedule has 1 contract, expected at least 2` |
| each code once, spelling and case as typed, the boundary's included | `contract_code row 2 is 'm26', already given at row 1` |
| each future expiring after the one above, in the order given | `future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22` |
| the last future within 1,048,574 days of the first, a sheet's rows less the two heading rows `util_ReadHandle` spills first, the bound the discount curve holds, so whatever is created can be read back | `future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19` |

A Gas Daily schedule's four rules, one month being a calendar:

| Rule | Message |
|---|---|
| each code once, spelling and case as typed | `contract_code row 2 is 'V26', already given at row 1` |
| each month's last day on or after its first | `last_date row 2 is 2026-09-30, expected a date on or after row 2's first_date 2026-10-01` |
| each month's first day the day after the month above's last, so the flow days run without a gap or an overlap | `first_date row 2 is 2026-11-01, expected 2026-10-01, the day after row 1's last_date 2026-09-30` |
| the last month's last day within 1,048,573 days of the first month's first day, both ends being rows, so the calendar fits a sheet's rows less the two heading rows | `last_date row 3 is 4897-07-25, expected within 1048573 days of row 1's first_date 2026-09-01` |

An IFERC schedule's two rules, one month being a calendar:

| Rule | Message |
|---|---|
| each code once, spelling and case as typed | `contract_code row 2 is 'V26', already given at row 1` |
| each month's index published after the month above's, in the order given | `publication_date row 2 is 2026-10-01, expected a date after row 1's 2026-11-02` |

A count of one reads `1 contract`. The codes are labels: `M26` and `m26` are two codes, no code is read for its month, nothing is sorted, and no contract is inferred between two that are given; the Gas Daily days come from the schedule's typed first and last days and the IFERC rows from its publication days, so no calendar here reads a month off a code. Then the four columns are made, once. For a futures schedule as in #82: the days one `np.arange` from the day after the first expiry to the last, the contract on each day one `np.searchsorted` over the expiries, never the first row, the priced flag `np.is_busday` over the days with the holiday calendar's list, and the fixed flag one comparison against the valuation date's day. For a Gas Daily schedule: the days one `np.arange` from the first month's first day to the last month's last, the contract on each day one `np.searchsorted` over the months' last days, the priced flag true throughout, and the fixed flag one comparison, on or before the valuation date's day. For an IFERC schedule: the dates the publication days as given, the contract each month's own row, the priced flag true throughout, and the fixed flag one comparison, before the valuation date's day. The sources are kept by reference, not copied, the record holds which kind it is, and the columns are frozen. Reading the handle shows the columns as they were made and reads each row's code from the schedule the calendar keeps; nothing is rebuilt. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_calendar.py`; the seam's texts and the handle are `tests/unit/test_calendar_creator.py`, which reads the calendar back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, for each of the three kinds, and that reading the handle rebuilds nothing, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market history's and the market's tests read the renamed columns and move with them; their cases are unchanged, and a Gas Daily or IFERC calendar handed to the history is refused until the history's own ticket, `calendar is a Gas Daily calendar, expected a futures calendar`.

| Case | Kind |
|---|---|
| the futures sample above: 63 consecutive days from 20 May to 21 July, the rows the page shows, and the boundary contract never prompt | example |
| four contracts: every interior expiry keeps its contract, the next day switches, and each contract after the boundary holds the days from the expiry before to its own | example |
| two expiries a day apart: one row, the second contract's | example |
| one contract, no contract, the boundary code given again or a third time, a code twice after the boundary, two expiries equal, expiries backwards, a later expiry before the one above: rejected, naming the row; the codes before the expiries, and `M26` and `m26` two codes | example |
| the longest calendar a sheet shows, 1,048,574 days, made and read back in full; one day longer, and a third contract far off, refused naming both expiries | example |
| a month end, a year end, a leap day and a February without one, the first and last days a cell holds, and a short range at the start of the sheet's calendar: every day a row | example |
| weekdays priced and both weekend days not; a holiday on a weekday not priced, on a weekend nothing; consecutive holidays each not priced | example |
| duplicate, unordered and out-of-range holidays change nothing; a holiday on an expiry changes the priced flag alone | example |
| the valuation date before, on the boundary, on the first day, inside, on the last day, after and well after the futures calendar: the days before it fixed and the day itself not; the fraction of the day changing nothing; the two flags independent, a fixed Saturday not priced | example |
| option expiries, added, removed or changed, change nothing | example |
| the Gas Daily sample: 91 consecutive days from 1 September to 30 November, each day its month's code, every day priced, the valuation date's flow day fixed with the days before it and the day after it not | example |
| a Gas Daily schedule of one month; of a month of one day; a month end and a year end between two months: every day a row, each with its month | example |
| a Gas Daily code twice, a month whose last day precedes its first, a gap of a day between two months, an overlap of a day, months out of order, and a span no sheet could show: rejected, naming the row and the day expected; the longest Gas Daily calendar a sheet shows, 1,048,574 days with both ends rows, made, and one day longer refused | example |
| a Gas Daily calendar's flags: a holiday or a weekend among the flow days changes nothing, every day being priced; the valuation date before, inside and after the days | example |
| the IFERC sample: three rows dated by their publication days, each its month's code, every one priced, a month fixed when its publication day is before the valuation date, not on it | example |
| an IFERC schedule of one month; an IFERC code twice and publication days out of order: rejected, naming the row | example |
| a holiday calendar left out with a futures schedule, and given with a Gas Daily or an IFERC schedule: rejected, naming the argument and the kind; a holiday calendar, a valuation date and a futures calendar where the schedule should be: rejected, naming what arrived and the three kinds expected | example |
| for any futures schedule of two to forty contracts with distinct codes and increasing expiries, any holidays and any valuation date: one row per day between the first expiry and the last, consecutive, each day on the one contract whose interval holds it, and the fixed flag one comparison | property |
| for any Gas Daily schedule of one to forty months of any lengths laid end to end, and any valuation date: one row per day from the first day to the last, consecutive, each day on the month whose days hold it, every day priced, the fixed flag one comparison | property |
| for any IFERC schedule of one to forty months with increasing publication days, and any valuation date: one row per month in the order given, every one priced, the fixed flag one comparison | property |
| the sources kept by reference, the columns read-only and refusing writes; making a calendar changes no source, and a second calendar leaves the first; the record says which kind it is | example |
| the handles in and each of the three calendars read back row by row, the flags reaching the sheet as booleans, the codes exactly as typed, one futures row from two expiries a day apart, the valuation date on the first day and its fraction | example, through the seam |
| a schedule of one contract, a code twice, expiries backwards, a span no sheet could show, a gap between two Gas Daily months and IFERC publication days out of order, the library's words; the kind refusals and the holiday calendar rules, the library's words; each argument left out, blank, a number, text naming no live object, or a handle of another kind, the seam's words, the calendar's own handle where the holiday calendar should be included, the holiday calendar left out reaching the function as none | example, through the seam |
| a failed construction publishes no object and no handle; a dead calendar handle cannot be read | example, with handles |
| the spill: four headers, four types, one row per day or per month with the flags' kinds the boolean code, for each of the three kinds | example |
| the creator's handle read back in a real workbook, 156 rows over the six-contract futures schedule, a Gas Daily calendar over the schedule page's three months and an IFERC calendar over its three, a code and both flags read from each, the four futures refusals, a Gas Daily gap, and the holiday calendar given with a Gas Daily schedule | Excel smoke |

## Not here

Binding fixings to a Gas Daily or an IFERC calendar: the [market history](../market/market-history.md)'s next ticket, which reads the kind the record holds and binds each fixings kind to its own calendar, a fixing on a period not yet fixed refused as today; until then the history takes a futures calendar alone. The quote on each period to come, and what a Gas Daily market quotes for the rest of the month in progress: the [market](../market/market.md)'s, since #86 for futures. The day an index prints during its publication day, and the session's close on the valuation day: the valuation date's fraction, which no reader reads yet; here the publication day itself is not fixed, as the valuation day's settle is not. The IFERC schedule's last trading day: the basis future's fact, unread here; the basis future is a futures market of its own, with a futures schedule of those days and its daily settles as futures fixings. Which contract is prompt with a roll lag, a market whose prompt moves before the expiry day: the nearby reader's, when a market states one. Reading codes for their months, and a schedule that lists only some months: [time.md](../time.md) parks both, and no calendar here needs either. Tying the calendar to an index definition, and a market trading on weekends. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any calendar. Pricing and risk.
