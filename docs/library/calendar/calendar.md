# _CreateCalendar

Built in #82.

The calendar of one index: every calendar day from the day after its first contract expires to the day its last expires, with the contract prompt on each day, whether the market is open that day and whether the day is before the valuation date, built once from three objects the sheet already holds and reached by handle. It is the backbone the pricing will run along: a swap's period is a run of these days, each day's prompt contract says which future prices it, the business-day flag says whether a fixing is expected on it, and the past flag says which side of the valuation date it falls, the side that has fixed or the side the curve prices. Today it is the shell, four columns and nothing priced: no price, no fixing and no publication is read, so the object is built once and stands while prices move. The code is `src/goosedove/calendar/calendar.py`, the record and its builder, and `src/goosedove/excel/calendar.py`, the worksheet function.

## Worksheet contract

```python
def _CreateCalendar(
    valuation_date: Handle[ValuationDate],
    expiry_schedule: Handle[ExpirySchedule],
    holiday_calendar: Handle[HolidayCalendar],
) -> Handle[Calendar]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 1 | as_of | 25-May-2026 | future_code | future_expiry |
| 2 | holiday | 25-May-2026 | m26 | 19-May-2026 |
| 3 | | | n26 | 22-Jun-2026 |
| 4 | | | q26 | 21-Jul-2026 |
| 5 | `=_CreateValuationDate(B1, 0.5)` | shows `valuation_date:3f9a1c:000001` | `=_CreateExpirySchedule(C2:C4, D2:D4)` | shows `expiry_schedule:3f9a1c:000004` |
| 6 | `=_CreateHolidayCalendar(B2)` | shows `holiday_calendar:3f9a1c:000007` | | |
| 7 | `=_CreateCalendar(A5, C5, A6)` | shows `calendar:3f9a1c:000012` | | |

Three handles, all required, none with a default: the valuation date, the index's expiry schedule and the market's holiday calendar, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say. The function receives the three objects the seam keeps, never the text, and a cell that is not the right kind's handle fails in the seam's words, `holiday_calendar is calendar handle 'calendar:3f9a1c:000012', expected holiday calendar handle`, before the function runs. The seam resolves the three handles and nothing else; nothing here restates that. The result is a handle: text in the cell that stands for the calendar the seam keeps, declared `Handle[Calendar]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the calendar, its three sources by reference and its four columns.

`=util_ReadHandle(A7)` on the calendar above runs from 20 May to 21 July 2026, 63 days, and shows among its rows:

| date | prompt_contract | is_business_day | is_past |
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

The four columns: `date`, every calendar day from the day after the first expiry to the last, weekends and holidays included, as [time.md](../time.md) decided every period would be; `prompt_contract`, the code of the contract prompt on that day, as the desk typed it in the schedule; `is_business_day`, Monday to Friday and not a day the holiday calendar lists; and `is_past`, whether the day is before the valuation date's day. The first contract of the schedule only bounds the calendar: nothing says when it became prompt, so it is never prompt here, and the calendar starts the day after it expires. Every day after that belongs to the next contract in the schedule up to and including its expiry day, so the expiry day belongs to the contract expiring on it and the day after to the contract after; a weekend or a holiday moves neither an expiry nor the day the prompt changes. The valuation date's day is not past, whatever fraction of it has elapsed, and changing the fraction alone changes nothing; the valuation date need not fall inside the calendar, one before it making no day past and one after it making every day past. A holiday outside the calendar changes nothing, a day listed twice or out of order counts as once, and the list's first and last days bound nothing.

## Excel help

Quoted from the declaration in `src/goosedove/excel/calendar.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the calendar of one index, every day after its first contract's expiry to its last, with the contract prompt on each, whether the market is open and whether the day is past, and shows its handle, the text other formulas take as the calendar. |
| `valuation_date` | The valuation-date handle: the cell showing _CreateValuationDate's result, such as B2, or a name for it. |
| `expiry_schedule` | The index's expiry-schedule handle: the cell showing _CreateExpirySchedule's result, such as B8, or a name for it, two contracts or more. |
| `holiday_calendar` | The market's holiday-calendar handle: the cell showing _CreateHolidayCalendar's result, such as B12, or a name for it. |

## The library checks

Three rules on the schedule, in this order, the first failure being the message; they are the calendar's, not the schedule's, so a schedule of one contract or with a code twice is still a schedule. Rows count as the sheet counts them, the schedule's first row being row 1.

| Rule | Message |
|---|---|
| the schedule has two contracts or more, the first only bounding the calendar | `expiry_schedule has 1 contract, expected at least 2` |
| each code once, spelling and case as typed, the boundary's included | `future_code row 2 is 'm26', already given at row 1` |
| each future expiring after the one above, in the order given | `future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22` |

A count of one reads `1 contract`. The codes are labels: `M26` and `m26` are two codes, no code is read for its month, nothing is sorted, and no contract is inferred between two that are given. The schedule as supplied is the whole prompt sequence, so these rules make the mapping unambiguous and say nothing about whether a market lists more contracts than the sheet does. Then the four columns are made, once: the days are one `np.arange` from the day after the first expiry to the last; the prompt on each day is one `np.searchsorted` over the expiries, each day finding the first expiry on or after it, which is never the first row; the business-day flag is `np.is_busday` over the days with the holiday calendar's list, as [time.md](../time.md) decided business days would be counted; and the past flag is one comparison against the valuation date's day. Reading the handle shows the columns as they were made and reads each day's code from the schedule the calendar keeps; nothing is rebuilt. The three objects are kept by reference, not copied, and the columns are frozen. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_calendar.py`; the seam's texts and the handle are `tests/unit/test_calendar_creator.py`, which reads the calendar back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, and that reading the handle rebuilds nothing, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the sample above: 63 consecutive days from 20 May to 21 July, the rows the page shows, and the boundary contract never prompt | example |
| four contracts: every interior expiry keeps its contract, the next day switches, and each contract after the boundary holds the days from the expiry before to its own | example |
| two expiries a day apart: one row, the second contract's | example |
| one contract, no contract, the boundary code given again or a third time, a code twice after the boundary, two expiries equal, expiries backwards, a later expiry before the one above: rejected, naming the row; the codes before the expiries, and `M26` and `m26` two codes | example |
| a month end, a year end, a leap day and a February without one, the first and last days a cell holds, and a short range at the start of the sheet's calendar: every day a row | example |
| weekdays open and both weekend days closed; a holiday on a weekday closed, on a weekend nothing; consecutive holidays each closed | example |
| duplicate, unordered and out-of-range holidays change nothing; a holiday on an expiry changes the business-day flag alone | example |
| the valuation date before, on the boundary, on the first day, inside, on the last day, after and well after the calendar: the days before it past and the day itself not; the fraction of the day changing nothing; the two flags independent, a past Saturday closed and past | example |
| option expiries and publication dates, added, removed or changed, change nothing | example |
| for any schedule of two to forty contracts with distinct codes and increasing expiries, any holidays and any valuation date: one row per day between the first expiry and the last, consecutive, each day prompt on the one contract whose interval holds it, each contract after the boundary holding exactly the days between its expiry and the one before, and the past flag one comparison | property |
| the three sources kept by reference, the columns read-only and refusing writes; making a calendar changes no source, and a second calendar leaves the first | example |
| three handles in and the calendar read back day by day, the flags reaching the sheet as booleans, the codes exactly as typed, one row from two expiries a day apart, the valuation date on the first day and its fraction | example, through the seam |
| a schedule of one contract, a code twice and expiries backwards, the library's words; each argument left out, blank, a number, text naming no live object, or a handle of another kind, the seam's words, the calendar's own handle where the holiday calendar should be included | example, through the seam |
| a failed construction publishes no object and no handle; a dead calendar handle cannot be read | example, with handles |
| the spill: four headers, four types, one row per day with the flags' kinds the boolean code | example |
| the creator's handle read back in a real workbook, 156 rows over the six-contract schedule, a code and both flags read, and the three refusals | Excel smoke |

## Not here

The price on each day, the fixing on each past business day and whether it has been published, the settle of a period and the pricing of a swap along these days: the work built on top of this shell, one pull request at a time. Which contract is prompt with a roll lag, a market whose prompt moves before the expiry day: the nearby reader's, when a market states one. Whether a fixing exists or has been published on a past day: `is_past` says where the day falls, and no more. Reading codes for their months, and a schedule that lists only some months: [time.md](../time.md) parks both. Tying the calendar to an index definition, and a market trading on weekends. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any calendar. Pricing and risk.
