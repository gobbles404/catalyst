# util_ShiftDate

Built in #NN, UAT item 9 of the trade surface; the ticket is [date-offset-utility.md](../../engineering-tickets/trade-valuation-pipeline/date-offset-utility.md).

Shifts a date by a text offset as the desk writes one: `+1bd` the next business day, `-1bd` the one before, `+7cd` a week of calendar days on, `+0em` the last day of the date's own month and `+1em` the next month's. One date and one instruction in, one date out, no object and no handle; the cell holds a date the sheet formats, as every date the seam sends. Business days are Monday to Friday less the holidays of a calendar the formula may name, the existing [holiday calendar](../index-definitions/holiday-calendar.md)'s handle; left out, they are Monday to Friday and nothing else. It derives a date and reads no object but the calendar it is given, so it is no `util_Read*` function, as [conventions.md](../conventions.md) divides them. The code is `src/goosedove/index_definitions/date_offsets.py`, beside the period grammar, and the wrapper `src/goosedove/excel/utilities.py`.

## Worksheet contract

```python
def util_ShiftDate(
    date: Date, offset: str, holiday_calendar: Handle[HolidayCalendar] | None = None
) -> Date: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | 12-Oct-2026 | `=_CreateHolidayCalendar(A1)` shows `30512:holiday_calendar:7`, a calendar closed on Monday 12 October and nothing else | |
| 2 | 9-Oct-2026, a Friday | `=util_ShiftDate(A2,"+1bd")` shows `46307`, Monday 12-Oct-2026 once formatted | `=util_ShiftDate(A2,"+1bd",B1)` shows `46308`, Tuesday the 13th, the Monday closed |
| 3 | 10-Oct-2026, a Saturday | `=util_ShiftDate(A3,"+1bd")` shows `46307`, the Monday | `=util_ShiftDate(A3,"+0bd",B1)` shows `46305`, the Saturday itself |
| 4 | 11-Oct-2026, a Sunday | `=util_ShiftDate(A4,"-1bd")` shows `46304`, the Friday | |
| 5 | 9-Oct-2026 | `=util_ShiftDate(A5,"+7cd",B1)` shows `46311`, 16-Oct-2026, the calendar read for nothing | `=util_ShiftDate(A5,"-7cd")` shows `46297`, 2-Oct-2026 |
| 6 | 9-Oct-2026 | `=util_ShiftDate(A6,"+0em")` shows `46326`, Saturday 31-Oct-2026 | `=util_ShiftDate(A6,"+1em")` shows `46356`, 30-Nov-2026 |
| 7 | 31-Jan-2028 | `=util_ShiftDate(A7,"+1em")` shows `46812`, 29-Feb-2028 | `=util_ShiftDate(A7,"1em")` shows `#ERROR util_ShiftDate: ValueError: offset is '1em', expected a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd or +0em` |

Three arguments. The date, required: a date, `DATE(2026,10,9)` or a cell holding one, checked as the seam checks any date scalar, as [inputs.md](../../seam/inputs.md) says, refusing text, a blank, a fraction of a day and a range in its own words, `date is text 'x', expected date`; no text is read as a date and no contract code stands for one. The offset, required, as text, typed in the formula or in a cell, the seam refusing a number, a blank and empty text, `offset is number 1.0, expected text`. The holiday calendar, which may be left out with nothing in its place, decision 39's form, `holiday_calendar: Handle[HolidayCalendar] | None = None`: a holiday-calendar handle, the cell showing `_CreateHolidayCalendar`'s result or a name for it, checked as the seam checks any handle, a blank, a text naming no live object and a handle of another kind refused in its words, `holiday_calendar is blank, expected holiday calendar handle`, `holiday_calendar is valuation date handle '30512:valuation_date:3', expected holiday calendar handle`; a blank is no omission. The calendar is checked whatever the offset, a zero count and a calendar-day one included, and read by the business days alone. The result is a date, the serial the sheet formats; nothing is published and no handle is made, so a shifted date is a plain cell, recalculated when its date, its offset or its calendar's cell changes and never otherwise.

## Excel help

Quoted from the declaration in `src/goosedove/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Shifts a date by business days, calendar days or month ends, +1bd the next business day, -1bd the one before, +7cd a week on, +0em the month's last day, and shows the date. |
| `date` | The day to shift, such as A2 or DATE(2026,10,9). |
| `offset` | The shift as text: a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd or +0em, typed or in a cell such as B2. |
| `[holiday_calendar]` | The holiday-calendar handle whose holidays business days skip, such as C2; left out for Monday to Friday with no holidays. |

## The grammar

One sign, `+` or `-`, one whole count in ASCII digits, leading zeros allowed, and one of three suffixes in either case, nothing before, between or after: `+1bd`, `-1BD`, `+001cD`, `-0em`. A count of more than seven significant digits is refused by its digits, since the sheet's calendar is 2,958,404 days, 2,113,146 business days and 97,197 month ends end to end and an eighth digit names no day a cell can show; so is anything else, a missing sign, a decimal, a space, a second instruction, a letter that is no suffix or a digit that is no ASCII digit, naming the offset and the form.

| Suffix | Means | From Friday 9-Oct-2026 |
|---|---|---|
| `bd` | business days, Monday to Friday less the calendar's holidays, counted strictly from the date without including it: `+n` the n-th business day after, `-n` the n-th before, `0` the date itself, closed or not | `+1bd` Monday the 12th, or Tuesday the 13th when the Monday is closed; `-1bd` Thursday the 8th |
| `cd` | calendar days, weekends and holidays counted alike; the calendar is read for nothing | `+7cd` the 16th; `-7cd` the 2nd |
| `em` | month ends: the date's month moved by the count, and that month's last calendar day, whatever day of the week it is; `+0em` the date's own month's; the calendar is read for nothing | `+0em` Saturday the 31st; `+1em` 30-Nov-2026; `-1em` 30-Sep-2026 |

A date that is itself closed is counted from, not counted: Saturday `+1bd` is Monday, Sunday `-1bd` is Friday, a closed Monday `+1bd` is the Tuesday and `-1bd` the Friday before it. In numpy's terms a positive count rolls a closed date back before counting forward and a negative one rolls it forward before counting back, so that the first business day after a closed day is the next open day and not the one after it, and a zero count rolls nothing. February's length and the year end fall out of numpy: `+1em` from 31-Jan-2028 is 29-Feb-2028, from 31-Jan-2027 is 28-Feb-2027, and from 15-Dec-2026 is 31-Jan-2027. The business days from an open day round trip, `+n` then `-n` returning the day; from a closed day they do not, since the closed day is never a day counted to.

## The library checks

Three rules, the first failure being the message, after the seam's own checks of the three arguments.

| Rule | Message |
|---|---|
| the offset is one sign, one count and one suffix, as the grammar says | `offset is '1bd', expected a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd or +0em` |
| the count has at most seven significant digits, checked before any arithmetic, so that no count ever runs over the day arithmetic or Python's own conversion | `offset has a count of 8 digits, expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31` |
| the day made lies within the sheet's calendar, 1 March 1900 to 31 December 9999, named with the date and the offset that left it | `date 9999-12-31 shifted by '+1cd' is 10000-01-01, outside the sheet's calendar, 1900-03-01 to 9999-12-31` |

The sheet's two days are the library's in `src/goosedove/index_definitions/sheet_days.py`, the same two the trade template holds a payment lag to and the resolution a payment day; `9999-12-31` with `+0em` is its own month's end and stands, since the month after is reached and a day subtracted before the rule is applied to what is made. Nothing is clamped, filled in or rolled to make a result fit.

## The reading

The offset is read once by one full match of a sign, digits and two letters; the suffix is looked up among the three; the count is read as an integer only after its digits are counted. A business-day shift is one `np.busday_offset` with the sign's roll and the calendar's holidays, or none; a calendar-day shift one `np.timedelta64` added; a month end two conversions, the date to its month, the month moved by the count and one, to its first day, less one day. No loop runs over the days shifted, so a shift of two million business days costs what a shift of one does, as the budgets pin.

## Tests

The library's examples and properties are `tests/unit/test_date_offsets.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`, with a fact on a calendar the host makes. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the ticket's sixteen worked answers, the synthetic calendar of one closed Monday where it says, the calendar omitted where it says | example |
| a nonleap February, three business days across the holiday and back, two weekends, every suffix in mixed case, the signed zeros of each suffix on a Sunday, a count with leading zeros | example |
| the sheet's last day keeps its month end; its first and last days reached from each other end to end in calendar days; a day past either end, by a day, a business day or a month, and the largest seven-digit counts of each suffix, refused naming the date and the offset; eight digits and five thousand refused by their digits; seven digits read | example |
| nineteen texts that are no offset, a missing sign, a decimal, a space anywhere, two instructions, a letter that is no suffix, an Arabic-Indic digit, refused naming the offset | example |
| from any open day of 2026 to 2080, with the calendar and without, `+n` business days lands on an open day n business days on and `-n` returns; any month end is the last day of the month the count names; calendar days add and subtract whatever the calendar | property |
| the ticket's table through the seam as serials and a float; the library's three refusals in its words; the date, the offset and the calendar refused in the seam's, a blank, a dead text and a valuation date where the calendar should be, whatever the offset; one calendar published and nothing of the shifts | example, through the seam |
| the same thirteen or fifteen calls, the calendar's resolution the difference, and the same numpy for one business day and for two million, a week and the calendar end to end, one month end and ninety thousand; within twice the slack for each, nothing published | budget |
| the ticket's table on a sheet with the synthetic calendar in PA2, the refusals in both sets of words; the host's rows and its fact on a calendar of its own | Excel smoke, host |
| rows 1884 to 1905 of the kept workbook's handles sheet, the table with its calendar and two refusals | workbook |

## Not here

No reading of a date from text, a contract code or a period label: a date is a date, and [util_StartDate](start-date.md) and [util_EndDate](end-date.md) turn labels into days. No compound instruction, `+1bd+2cd`, no custom weekend, no time of day, no clamping of a month end to a business day and no month-end business-day adjustment: one instruction, one rule. No valuation date, market or clock: the function is deterministic and nonvolatile, a plain cell of the sheet's dependency graph. No change to how a trade obtains its booked dates: the template's `+2bd` payment lag keeps its own grammar, positive and on a required calendar, as [create-trades.md](../trades/create-trades.md) says; the helper is composed in Excel with explicit dates.
