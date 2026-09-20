# _CreateCalendar

Built in #82; takes its fixing mode, daily or monthly, since #87.

The calendar of one index: every calendar day from the day after its first contract expires to the day its last expires, with the contract prompt on each day, whether the market is open that day and whether the day is before the valuation date, built once from three objects the sheet already holds and a word, the fixing mode, and reached by handle. The mode says how the index fixes, daily, a settle on each business day, or monthly, one published price per contract, as IFERC's monthly indices are published beside Gas Daily's daily ones; it is the caller's word, never read off the schedule, and a monthly calendar needs the schedule's publication dates. It is the backbone the pricing will run along: a swap's period is a run of these days, each day's prompt contract says which future prices it, the business-day flag says whether the market is open on it, and the past flag says whether the day is before the valuation date, a comparison of dates and no more: it does not say that a fixing has been received for the day. It is the shell, four columns and nothing priced: no price, no fixing and no publication is read here, so the object is built once and stands while prices move; since #84 the [market history](../market/market-history.md) binds the fixings to its past business days, keeping the calendar as it is. The code is `src/goosedove/calendar/calendar.py`, the record and its builder, and `src/goosedove/excel/calendar.py`, the worksheet function.

## Worksheet contract

```python
def _CreateCalendar(
    valuation_date: Handle[ValuationDate],
    fixing_mode: str,
    expiry_schedule: Handle[ExpirySchedule],
    holiday_calendar: Handle[HolidayCalendar],
) -> Handle[Calendar]: ...
```

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | as_of | 25-May-2026 | future_code | future_expiry | publication_date |
| 2 | holiday | 25-May-2026 | m26 | 19-May-2026 | 20-May-2026 |
| 3 | fixing_mode | daily | n26 | 22-Jun-2026 | 23-Jun-2026 |
| 4 | | | q26 | 21-Jul-2026 | 22-Jul-2026 |
| 5 | `=_CreateValuationDate(B1, 0.5)` | shows `valuation_date:3f9a1c:000001` | `=_CreateExpirySchedule(C2:C4, D2:D4, , E2:E4)` | shows `expiry_schedule:3f9a1c:000004` | |
| 6 | `=_CreateHolidayCalendar(B2)` | shows `holiday_calendar:3f9a1c:000007` | | | |
| 7 | `=_CreateCalendar(A5, B3, C5, A6)` | shows `calendar:3f9a1c:000012` | `=_CreateCalendar(A5, "monthly", C5, A6)` | shows `calendar:3f9a1c:000013` | |

Three handles and a word, all required, none with a default: the valuation date, the fixing mode, the index's expiry schedule and the market's holiday calendar, each handle the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say, and the mode a text cell or the text itself, exactly `daily` or `monthly`. The function receives the three objects the seam keeps, never the text, and a cell that is not the right kind's handle fails in the seam's words, `holiday_calendar is calendar handle 'calendar:3f9a1c:000012', expected holiday calendar handle`, before the function runs; the mode left out, blank, empty text or a number fails in the seam's words too, `fixing_mode is blank, expected text`. The seam resolves the three handles, takes the text and nothing else; nothing here restates that. The three-handle form of #82 to #86 is gone, with no fallback: `=_CreateCalendar(A5, C5, A6)` lands the schedule in the mode's slot, which takes any text, and the holiday calendar in the schedule's, which fails by kind, `expiry_schedule is holiday calendar handle 'holiday_calendar:3f9a1c:000007', expected expiry schedule handle`. The result is a handle: text in the cell that stands for the calendar the seam keeps, declared `Handle[Calendar]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the calendar, its three sources by reference, its mode and its four columns.

`=util_ReadHandle(A7)` on the daily calendar above runs from 20 May to 21 July 2026, 63 days, and shows among its rows; `=util_ReadHandle(C7)` on the monthly one shows the same rows, since the mode is a property of the calendar and not a column:

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

The four columns: `date`, every calendar day from the day after the first expiry to the last, weekends and holidays included, as [time.md](../time.md) decided every period would be; `prompt_contract`, the code of the contract prompt on that day, as the desk typed it in the schedule; `is_business_day`, Monday to Friday and not a day the holiday calendar lists; and `is_past`, whether the day is before the valuation date's day. The first contract of the schedule only bounds the calendar: nothing says when it became prompt, so it is never prompt here, and the calendar starts the day after it expires. Every day after that belongs to the next contract in the schedule up to and including its expiry day, so the expiry day belongs to the contract expiring on it and the day after to the contract after; a weekend or a holiday moves neither an expiry nor the day the prompt changes. The valuation date's day is not past, whatever fraction of it has elapsed, and changing the fraction alone changes nothing; the valuation date need not fall inside the calendar, one before it making no day past and one after it making every day past. A holiday outside the calendar changes nothing, a day listed twice or out of order counts as once, and the list's first and last days bound nothing. The schedule's publication dates, which a monthly calendar requires and a daily one may carry, change nothing either: each stays with its contract's row of the schedule, read through the calendar's reference to it, whether it falls inside the calendar's days or not, and no row of the calendar carries it or a price. In the sample, n26's publication date is 23 June, the day q26 becomes prompt, and the last contract's is 22 July, after the calendar's last day: both are kept as they are, and the calendar ends where it did.

## Excel help

Quoted from the declaration in `src/goosedove/excel/calendar.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the calendar of one index for daily or monthly fixings, each day after its first expiry to its last, its prompt contract, whether the market is open and whether it is past, and shows its handle, the text other formulas take as the calendar. |
| `valuation_date` | The valuation-date handle: the cell showing _CreateValuationDate's result, such as B2, or a name for it. |
| `fixing_mode` | How the index fixes, the text daily or monthly, such as B4: daily for a settle on each business day, monthly for one published price per contract, which needs the schedule's publication dates. |
| `expiry_schedule` | The index's expiry-schedule handle: the cell showing _CreateExpirySchedule's result, such as B8, or a name for it, two contracts or more. |
| `holiday_calendar` | The market's holiday-calendar handle: the cell showing _CreateHolidayCalendar's result, such as B12, or a name for it. |

## The library checks

Two rules on the mode and four on the schedule, in this order, the first failure being the message; they are the calendar's, not the schedule's, so a schedule of one contract or with a code twice is still a schedule. Rows count as the sheet counts them, the schedule's first row being row 1.

| Rule | Message |
|---|---|
| the mode is exactly `daily` or `monthly`: a capital, a space around it or another word is refused, never corrected, and nothing is read off the schedule | `fixing_mode is 'auto', expected 'daily' or 'monthly'` |
| a monthly calendar has the schedule's publication dates, one per contract as the schedule's creator already checked; a daily one may have them or not | `fixing_mode 'monthly' requires publication_date in expiry_schedule` |
| the schedule has two contracts or more, the first only bounding the calendar | `expiry_schedule has 1 contract, expected at least 2` |
| each code once, spelling and case as typed, the boundary's included | `future_code row 2 is 'm26', already given at row 1` |
| each future expiring after the one above, in the order given | `future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22` |
| the last future within 1,048,574 days of the first, a sheet's rows less the two heading rows `util_ReadHandle` spills first, the bound the discount curve holds, so whatever is created can be read back | `future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19` |

A count of one reads `1 contract`. The mode's rules run first, so a wrong word is named on a schedule of one contract, and a monthly calendar without publication dates before the contract count; the mode is then one property of the calendar, held as an enum, and not a column. The codes are labels: `M26` and `m26` are two codes, no code is read for its month, nothing is sorted, and no contract is inferred between two that are given. The schedule as supplied is the whole prompt sequence, so these rules make the mapping unambiguous and say nothing about whether a market lists more contracts than the sheet does. Then the four columns are made, once: the days are one `np.arange` from the day after the first expiry to the last; the prompt on each day is one `np.searchsorted` over the expiries, each day finding the first expiry on or after it, which is never the first row; the business-day flag is `np.is_busday` over the days with the holiday calendar's list, as [time.md](../time.md) decided business days would be counted; and the past flag is one comparison against the valuation date's day. Reading the handle shows the columns as they were made and reads each day's code from the schedule the calendar keeps; nothing is rebuilt, and the columns are the same in either mode. The three objects are kept by reference, not copied, the publication dates among them, and the columns are frozen. Nothing here allocates a price, decides that a fixing has arrived or reads a publication date. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_calendar.py`; the seam's texts and the handle are `tests/unit/test_calendar_creator.py`, which reads the calendar back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, and that reading the handle rebuilds nothing, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the sample above: 63 consecutive days from 20 May to 21 July, the rows the page shows, and the boundary contract never prompt | example |
| four contracts: every interior expiry keeps its contract, the next day switches, and each contract after the boundary holds the days from the expiry before to its own | example |
| two expiries a day apart: one row, the second contract's | example |
| one contract, no contract, the boundary code given again or a third time, a code twice after the boundary, two expiries equal, expiries backwards, a later expiry before the one above: rejected, naming the row; the codes before the expiries, and `M26` and `m26` two codes | example |
| the longest calendar a sheet shows, 1,048,574 days, made and read back in full; one day longer, and a third contract far off, refused naming both expiries | example |
| a month end, a year end, a leap day and a February without one, the first and last days a cell holds, and a short range at the start of the sheet's calendar: every day a row | example |
| weekdays open and both weekend days closed; a holiday on a weekday closed, on a weekend nothing; consecutive holidays each closed | example |
| duplicate, unordered and out-of-range holidays change nothing; a holiday on an expiry changes the business-day flag alone | example |
| the valuation date before, on the boundary, on the first day, inside, on the last day, after and well after the calendar: the days before it past and the day itself not; the fraction of the day changing nothing; the two flags independent, a past Saturday closed and past | example |
| option expiries and publication dates, added, removed or changed, change nothing | example |
| daily and monthly calendars over the schedule with its publication dates have the same days, prompts and flags and differ in mode alone; the page's example, n26's publication date on the day q26 becomes prompt and the last one after the calendar's last day, both kept with their contracts | example |
| the mode capitalized, in capitals, with a space before or after it, another word or empty: refused, naming the text; monthly over a schedule without publication dates, with or without options, refused; daily over either accepted; the mode's rules before the schedule's | example |
| publication dates earlier, later, on either side of the valuation date, before the calendar or after it, repeated or out of order change no column in either mode and are kept as given | example |
| for any schedule of two to forty contracts with distinct codes and increasing expiries, with or without publication dates, any holidays, any valuation date and either mode the schedule allows: one row per day between the first expiry and the last, consecutive, each day prompt on the one contract whose interval holds it, each contract after the boundary holding exactly the days between its expiry and the one before, the past flag one comparison, and the mode as given | property |
| the three sources kept by reference in either mode, the publication dates with them, the columns read-only and refusing writes; making a calendar of either mode changes no source, and a second calendar leaves the first | example |
| three handles and the mode in and the calendar read back day by day, the flags reaching the sheet as booleans, the codes exactly as typed, one row from two expiries a day apart, the valuation date on the first day and its fraction; a monthly calendar spilling the same rows as the daily one | example, through the seam |
| a schedule of one contract, a code twice, expiries backwards and a span no sheet could show, the mode capitalized or with a space and monthly without publication dates, the library's words; each argument left out, blank, a number, text naming no live object, or a handle of another kind, the mode empty or a boolean, the seam's words, the calendar's own handle where the holiday calendar should be included; the three-handle form of #82 failing by kind and making nothing | example, through the seam |
| a failed construction publishes no object and no handle; a dead calendar handle cannot be read | example, with handles |
| the spill: four headers, four types, one row per day with the flags' kinds the boolean code | example |
| the creator's handle read back in a real workbook, 156 rows over the six-contract schedule, a code and both flags read, a monthly calendar of the same rows over the schedule with publication dates, and the refusals, the mode's among them | Excel smoke |

## Not here

The fixing on each past business day: [market-history.md](../market/market-history.md), since #84, which keeps the calendar as it is. The price on each day to come: [market.md](../market/market.md), since #86, the prompt contract's quote. Whether a fixing has been published, the settle of a period and the pricing of a swap along these days: the work built on top of this shell, one pull request at a time. Which contract is prompt with a roll lag, a market whose prompt moves before the expiry day: the nearby reader's, when a market states one. Whether a fixing has been published on a past day: `is_past` says where the day falls, and no more; whether one exists is the history's to say, and for a monthly calendar that history, one published price per contract on its publication date, is not built: [market-history.md](../market/market-history.md) refuses a monthly calendar until it is. Reading a publication date for anything, a provisional price, the days a delivery period covers and a trade's average: the same later work. Inferring the mode from the schedule: never; the caller says it. Reading codes for their months, and a schedule that lists only some months: [time.md](../time.md) parks both. Tying the calendar to an index definition, and a market trading on weekends. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any calendar. Pricing and risk.
