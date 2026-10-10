# _CreateCalendar

Built in #82 over a futures schedule, any schedule since #104, the row of its first unfixed period since #106 and the index since #108; the code of that period's contract read by `util_ReadPrompt` since #129.

The calendar of one index: the run of periods the index prices, each with the contract it belongs to, whether it prices and whether it is on the fixed side of the valuation date, built once from the index and reached by handle. It is the backbone the pricing will run along and the shell the market history and the market fill: no price, no fixing and no publication is read here, so the object is built once and stands while prices move. Since #82 it has been the futures calendar alone, every day from the day after the first contract expires to the day the last expires, the prompt contract on each. From #104 it takes any of the three schedules, and the schedule's kind says which calendar is made: the futures schedule gives the calendar of #82; the [Gas Daily schedule](../index-definitions/gas-daily-schedule.md) gives every flow day from the first month's first day to the last month's last, each day the month it flows in; and the [IFERC schedule](../index-definitions/iferc-schedule.md) gives one row per contract month, dated by the day its index is published. From #108 it takes the [index](../index-definitions/index.md) in place of the schedule and the holiday calendar: the index, since #107, holds the schedule, the holiday calendar a futures index needs, the conventions and the specifications, and the kind it read off the schedule when it was made, so the calendar reads the kind the index holds, takes the holiday calendar through it, and names no kind and no holiday calendar itself. The three calendars share one record and four columns, so that one [market history](../market/market-history.md) and one [market](../market/market.md) can serve every market, and instruments that combine markets, an index swap over the Gas Daily average against the IFERC index, a swing swap over chosen days, read the same shape from each; since #105 the history binds each of the three to the fixings of its market. The code is `src/goosedove/calendar/calendar.py`, the record and its builder, `src/goosedove/index_definitions/kind.py`, the kinds and the holiday rules the index and the calendar share, and `src/goosedove/excel/calendar.py`, the worksheet function. The [futures fixings](../market-data/futures-fixings.md) take their holiday calendar through the index in the same build, so that nothing downstream of the index takes a schedule or a holiday calendar by itself.

## Worksheet contract

```python
def _CreateCalendar(
    valuation_date: Handle[ValuationDate],
    index: Handle[Index],
) -> Handle[Calendar]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 1 | as_of | 25-May-2026 | contract_code | future_expiry |
| 2 | holiday | 25-May-2026 | m26 | 19-May-2026 |
| 3 | | | n26 | 22-Jun-2026 |
| 4 | | | q26 | 21-Jul-2026 |
| 5 | `=_CreateValuationDate(B1, 0.5)` | shows `30512:valuation_date:1` | `=_CreateFuturesSchedule(C2:C4, D2:D4)` | shows `30512:futures_schedule:4` |
| 6 | `=_CreateHolidayCalendar(B2)` | shows `30512:holiday_calendar:7` | `=_CreateIndex("WTI NYMEX", "West Texas Intermediate crude oil - NYMEX", D5, B15, B16, A6)` | shows `30512:index:WTI NYMEX:10`, B15 and B16 holding the conventions and the specifications |
| 7 | `=_CreateCalendar(A5, D6)` | shows `30512:calendar:WTI NYMEX:12`, the futures calendar | | |
| 8 | `=_CreateCalendar(A5, B20)` | shows `30512:calendar:Henry Hub Gas Daily:13`, B20 holding a Gas Daily index | | |
| 9 | `=_CreateCalendar(A5, B30)` | shows `30512:calendar:Henry Hub IFERC:14`, B30 holding an IFERC index | | |

Two handles, both required, neither with a default: the valuation date and the index, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say. The index is declared `Handle[Index]`, one kind, and a cell that is not an index's handle fails in the seam's words, `index is futures schedule handle '30512:futures_schedule:4', expected index handle`, before the function runs: the schedule, the holiday calendar and the kind reach the calendar through the index, which read the kind off its schedule and checked the holiday calendar against it when it was made, so nothing here names a kind, resolves an object of any kind or takes a holiday calendar. The `Handle[object]` schedule of #104 and the holiday calendar that could be left out since #103 went from this creator in #108; the forms stay in the seam, and the index uses both. The result is a handle: text in the cell that stands for the calendar the seam keeps, declared `Handle[Calendar]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the calendar, its valuation date and its index by reference, and its four columns. The index is one object: the calendar and the fixings of its market refer to the same `_CreateIndex` cell, or a name for it, and are remade together when the index is. Two `_CreateIndex` cells with the same arguments share one index while both are live, as [handles.md](../../seam/handles.md#shared-objects-and-shared-dependencies) says, but a change to either's inputs makes it another index, so the rule the desk keeps is one index cell used throughout a market's construction.

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

`=util_ReadHandle(A8)` on the Gas Daily calendar, built from the index of the schedule page's three months, runs from 1 September to 30 November 2026, 91 days, every one priced, the flow day of the valuation date fixed with the days before it:

| date | contract | is_priced | is_fixed |
|---|---|---|---|
| datetime64[D] | str | bool | bool |
| 1-Sep-2026 | U26 | TRUE | FALSE |
| … | … | … | … |
| 30-Sep-2026 | U26 | TRUE | FALSE |
| 1-Oct-2026 | V26 | TRUE | FALSE |
| … | … | … | … |
| 30-Nov-2026 | X26 | TRUE | FALSE |

`=util_ReadHandle(A9)` on the IFERC calendar, built from the index of the schedule page's three months, shows one row per month, dated by the day its index is published, every one priced, a month fixed once its publication day has passed:

| date | contract | is_priced | is_fixed |
|---|---|---|---|
| datetime64[D] | str | bool | bool |
| 1-Oct-2026 | V26 | TRUE | FALSE |
| 2-Nov-2026 | X26 | TRUE | FALSE |
| 1-Dec-2026 | Z26 | TRUE | FALSE |

The four columns, one shape for the three markets: `date`, the day a period's price is dated by, the calendar day itself for a futures or a Gas Daily calendar and the publication day for an IFERC one, as [time.md](../time.md) decided every period would be spelled, day by day; `contract`, the code of the contract the period belongs to, as the desk typed it in the schedule, the prompt future on a futures day and the delivery month otherwise; `is_priced`, whether the period has a price of its own, Monday to Friday and not a listed holiday on a futures calendar, every row on the other two, since Gas Daily prints every flow day and an index is a price for its whole month; and `is_fixed`, whether the period is on the fixed side of the valuation date, the side the history binds a fixing to. That side is decided per market by when its price becomes known: a futures settle prints at the close, so a day is fixed when it is before the valuation date's day; a Gas Daily midpoint prints on the session before the flow day, so a flow day is fixed when it is on or before the valuation date's day; and an Inside FERC index prints during its publication day, so a month is fixed when that day is before the valuation date's day. The valuation date's fraction changes nothing, as before. The columns were `prompt_contract`, `is_business_day` and `is_past` for the futures calendar of #82; the names change here because each now means more than a futures day, and the spill and its readers change with them. Beside the columns, since #106, one number, `first_unfixed`: the row of the first period not yet fixed, which is the count of the fixed periods, since the periods are in date order and the fixed side is the earlier one, and the calendar's length when every period has fixed. It is counted once, here, so that the [market](../market/market.md) reads it and looks along no column when it is made. The record holds the valuation date and the index, by reference; the kind, the schedule and the holiday calendar are the index's, read through it and held nowhere else, so the record's own `kind`, `schedule` and `holiday_calendar` fields go with this build, and the history, the market and the spill read them through the index.

## Excel help

Quoted from the declaration in `src/goosedove/excel/calendar.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the calendar of one index, one row per day it prices, or per month for an index published monthly, each with its contract and whether it has fixed, and shows its handle, the text other formulas take as the calendar. |
| `valuation_date` | The valuation-date handle: the cell showing _CreateValuationDate's result, such as B2, or a name for it. |
| `index` | The index handle: the cell showing _CreateIndex's result, such as B10, or a name for it; a futures index needs two contracts or more. |

## The library checks

The rules of the index's kind's calendar, the kind read off the index, in this order, the first failure being the message. They are the calendar's, not the schedule's or the index's, so an index whose schedule has one contract or a code twice is still an index. Rows count as the sheet counts them, the schedule's first row being row 1. The kind was read off the schedule when the index was made and the holiday calendar checked against it then, so neither is checked here: an object that is not an index never reaches the function, the seam naming the kind it expected, and a futures index always brings its holiday calendar. The kind rule and the two holiday rules of #104 leave this page for the [index](../index-definitions/index.md)'s, where since #107 they have stood in the same words; nothing about them changes but the cell that says them.

A futures index's four rules stand from #82 word for word but the first, whose message names the argument as it is now:

| Rule | Message |
|---|---|
| the index's schedule has two contracts or more, the first only bounding the calendar | `index has 1 contract, expected at least 2` |
| each code once, spelling and case as typed, the boundary's included | `contract_code row 2 is 'm26', already given at row 1` |
| the last future within 1,048,574 days of the first, a sheet's rows less the two heading rows `util_ReadHandle` spills first, the bound the discount curve holds, so whatever is created can be read back; checked before the order since #140, the guard against an unreadable calendar coming first | `future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19` |
| each future expiring after the one above, in the order given | `future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22` |

A Gas Daily index's four rules, one month being a calendar:

| Rule | Message |
|---|---|
| each code once, spelling and case as typed | `contract_code row 2 is 'V26', already given at row 1` |
| each month's last day on or after its first | `last_date row 2 is 2026-09-30, expected a date on or after row 2's first_date 2026-10-01` |
| each month's first day the day after the month above's last, so the flow days run without a gap or an overlap | `first_date row 2 is 2026-11-01, expected 2026-10-01, the day after row 1's last_date 2026-09-30` |
| the last month's last day within 1,048,573 days of the first month's first day, both ends being rows, so the calendar fits a sheet's rows less the two heading rows | `last_date row 3 is 4897-07-25, expected within 1048573 days of row 1's first_date 2026-09-01` |

An IFERC index's two rules, one month being a calendar:

| Rule | Message |
|---|---|
| each code once, spelling and case as typed | `contract_code row 2 is 'V26', already given at row 1` |
| each month's index published after the month above's, in the order given | `publication_date row 2 is 2026-10-01, expected a date after row 1's 2026-11-02` |

A count of one reads `1 contract`. The messages name the schedule's columns, since the row to fix is in the schedule's cells, and `index` where the rule is about the index's contracts as a whole. The codes are labels: `M26` and `m26` are two codes, no code is read for its month, nothing is sorted, and no contract is inferred between two that are given; the Gas Daily days come from the schedule's typed first and last days and the IFERC rows from its publication days, so no calendar here reads a month off a code. Then the four columns are made, once. For a futures index as in #82: the days one `np.arange` from the day after the first expiry to the last, the contract on each day one `np.searchsorted` over the expiries, never the first row, the priced flag `np.is_busday` over the days with the index's holiday calendar's list, and the fixed flag one comparison against the valuation date's day. For a Gas Daily index: the days one `np.arange` from the first month's first day to the last month's last, the contract on each day one `np.searchsorted` over the months' last days, the priced flag true throughout, and the fixed flag one comparison, on or before the valuation date's day. For an IFERC index: the dates the publication days as given, the contract each month's own row, the priced flag true throughout, and the fixed flag one comparison, before the valuation date's day. The valuation date and the index are kept by reference, not copied, and the columns are frozen. Reading the handle shows the columns as they were made and reads each row's code from the schedule the index keeps; nothing is rebuilt. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_calendar.py`; the seam's texts and the handle are `tests/unit/test_calendar_creator.py`, which reads the calendar back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, for each of the three kinds, and that reading the handle rebuilds nothing, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market history's and the market's tests build their calendars through the index and read the kind, the schedule and the holiday calendar through it; their cases are unchanged, and so are the futures fixings', which take the index the same way.

| Case | Kind |
|---|---|
| the futures sample above: 63 consecutive days from 20 May to 21 July, the rows the page shows, and the boundary contract never prompt | example |
| four contracts: every interior expiry keeps its contract, the next day switches, and each contract after the boundary holds the days from the expiry before to its own | example |
| two expiries a day apart: one row, the second contract's | example |
| one contract, the boundary code given again or a third time, a code twice after the boundary, two expiries equal, expiries backwards, a later expiry before the one above: rejected, naming the row; the codes before the expiries, and `M26` and `m26` two codes | example |
| the longest calendar a sheet shows, 1,048,574 days, made and read back in full; one day longer, and a third contract far off, refused naming both expiries | example |
| a month end, a year end, a leap day and a February without one, the first and last days a cell holds, and a short range at the start of the sheet's calendar: every day a row | example |
| weekdays priced and both weekend days not; a holiday on a weekday not priced, on a weekend nothing; consecutive holidays each not priced; the holidays read through the index | example |
| duplicate, unordered and out-of-range holidays change nothing; a holiday on an expiry changes the priced flag alone | example |
| the valuation date before, on the boundary, on the first day, inside, on the last day, after and well after the futures calendar: the days before it fixed and the day itself not; the fraction of the day changing nothing; the two flags independent, a fixed Saturday not priced | example |
| option expiries, added, removed or changed, change nothing; the conventions and the specifications the index holds change nothing | example |
| the Gas Daily sample: 91 consecutive days from 1 September to 30 November, each day its month's code, every day priced, the valuation date's flow day fixed with the days before it and the day after it not | example |
| a Gas Daily index of one month; of a month of one day; a month end and a year end between two months: every day a row, each with its month | example |
| a Gas Daily code twice, a month whose last day precedes its first, a gap of a day between two months, an overlap of a day, months out of order, and a span no sheet could show: rejected, naming the row and the day expected; the longest Gas Daily calendar a sheet shows, 1,048,574 days with both ends rows, made, and one day longer refused | example |
| a Gas Daily calendar's flags: a holiday or a weekend among the flow days changes nothing, every day being priced; the valuation date before, inside and after the days | example |
| the IFERC sample: three rows dated by their publication days, each its month's code, every one priced, a month fixed when its publication day is before the valuation date, not on it | example |
| an IFERC index of one month; an IFERC code twice and publication days out of order: rejected, naming the row | example |
| for any futures index of two to forty contracts with distinct codes and increasing expiries, any holidays and any valuation date: one row per day between the first expiry and the last, consecutive, each day on the one contract whose interval holds it, and the fixed flag one comparison | property |
| for any Gas Daily index of one to forty months of any lengths laid end to end, and any valuation date: one row per day from the first day to the last, consecutive, each day on the month whose days hold it, every day priced, the fixed flag one comparison | property |
| for any IFERC index of one to forty months with increasing publication days, and any valuation date: one row per month in the order given, every one priced, the fixed flag one comparison | property |
| the valuation date and the index kept by reference, the kind, the schedule and the holiday calendar read through the index, the columns read-only and refusing writes; making a calendar changes no source, and a second calendar leaves the first | example |
| the handles in and each of the three calendars read back row by row, the flags reaching the sheet as booleans, the codes exactly as typed, one futures row from two expiries a day apart, the valuation date on the first day and its fraction | example, through the seam |
| an index of one contract, a code twice, expiries backwards, a span no sheet could show, a gap between two Gas Daily months and IFERC publication days out of order, the library's words; each argument left out, blank, a number, text naming no live object, or a handle of another kind, a schedule and a holiday calendar where the index should be among them, the seam's words, the calendar's own handle included | example, through the seam |
| a failed construction publishes no object and no handle; a dead calendar handle cannot be read | example, with handles |
| the spill: four headers, four types, one row per day or per month with the flags' kinds the boolean code, for each of the three kinds | example |
| the creator's handle read back in a real workbook, 156 rows over the index of the six-contract futures schedule, a Gas Daily calendar over the index of the schedule page's three months and an IFERC calendar over its three, a code and both flags read from each, the four futures refusals, a Gas Daily gap, and a schedule where the index should be | Excel smoke |

## Not here

Binding fixings to a calendar of any kind: the [market history](../market/market-history.md)'s since #105, which reads the kind through the calendar's index and binds each fixings kind to its own calendar, a fixing on a period not yet fixed refused. Checking that the fixings are this calendar's index's, the same object and not merely the same name: the [market history](../market/market-history.md)'s since #109, one reference comparison when the history is made and nothing on the live path, which catches WTI fixings bound to a gas calendar, an index of the same name made from other inputs, and a calendar or fixings left standing on an index since remade, as manual calculation can leave them; two `_CreateIndex` cells with the same arguments, live at once, are one index and pass; every fixings creator takes its index, the futures fixings since #108 and the IFERC and Gas Daily fixings since #109. The schedule's rules moving from here to the index: parked, since the rule that a futures schedule has two contracts is this calendar's construction's, the first contract only bounding it, and not a fact of every index; the IFERC fixings, the market history and the market read a schedule's codes too, through the index, and none has needed a rule of its own on the schedule, so what is general to a schedule and what is this calendar's own waits for a reader that does. The quote on each period to come, and what a Gas Daily market quotes for the rest of the month in progress: the [market](../market/market.md)'s, since #86 for futures and #106 for any history. The day an index prints during its publication day, and the session's close on the valuation day: the valuation date's fraction, which no reader reads yet; here the publication day itself is not fixed, as the valuation day's settle is not. The IFERC schedule's last trading day: the basis future's fact, unread here; the basis future is a futures market of its own, with a futures schedule of those days and its daily settles as futures fixings. Which contract is prompt with a roll lag, a market whose prompt moves before the expiry day: the nearby reader's, when a market states one. Reading codes for their months, and a schedule that lists only some months: [time.md](../time.md) parks both, and no calendar here needs either. A market trading on weekends. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any calendar. Pricing and risk.
