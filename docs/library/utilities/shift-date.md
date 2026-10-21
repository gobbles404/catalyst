# util_ShiftDate

Built in #171, UAT item 9 of the trade surface; the ticket is [date-offset-utility.md](../../engineering-tickets/trade-valuation-pipeline/date-offset-utility.md). Since #181 an offset is one or more instructions, [compound-date-offsets.md](../../engineering-tickets/trade-valuation-pipeline/compound-date-offsets.md): `+3em+25cd-1bd+1bd`, each applied to the result of the one before, left to right, and the same reading and arithmetic serve a trade's `payment_day` where it holds a rule and not a date, [payment-day-date-or-rule.md](../../engineering-tickets/trade-valuation-pipeline/payment-day-date-or-rule.md), [create-trades.md](../trades/create-trades.md).

Shifts a date by a text offset as the desk writes one: `+1bd` the next business day, `-1bd` the one before, `+7cd` a week of calendar days on, `+0em` the last day of the date's own month and `+1em` the next month's, and a chain of these in turn. One date and one offset in, one date out, no object and no handle; the cell holds a date the sheet formats, as every date the seam sends. Business days are Monday to Friday less the holidays of a calendar the formula may name, the existing [holiday calendar](../index-definitions/holiday-calendar.md)'s handle; left out, they are Monday to Friday and nothing else. It derives a date and reads no object but the calendar it is given, so it is no `util_Read*` function, as [conventions.md](../conventions.md) divides them. The code is `src/goosedove/index_definitions/date_offsets.py`, beside the period grammar, and the wrapper `src/goosedove/excel/utilities.py`.

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
| 7 | 31-Jan-2028 | `=util_ShiftDate(A7,"+1em")` shows `46812`, 29-Feb-2028 | `=util_ShiftDate(A7,"1em")` shows `#ERROR util_ShiftDate: ValueError: offset is '1em', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd` |
| 8 | 25-Dec-2026 | `=_CreateHolidayCalendar(A8)` shows `30512:holiday_calendar:9`, the ticket's calendar H, Christmas Day closed and nothing else | |
| 9 | 12-Aug-2026 | `=util_ShiftDate(A9,"+3em+25cd-1bd+1bd",B8)` shows `46384`, Monday 28-Dec-2026 | `=util_ShiftDate(A9,"+3em+25cd-1bd+1bd")` shows `46381`, Friday 25-Dec-2026, open without H |

Three arguments. The date, required: a date, `DATE(2026,10,9)` or a cell holding one, checked as the seam checks any date scalar, as [inputs.md](../../seam/inputs.md) says, refusing text, a blank, a fraction of a day and a range in its own words, `date is text 'x', expected date`; no text is read as a date and no contract code stands for one. The offset, required, as text, typed in the formula or in a cell, the seam refusing a number, a blank and empty text, `offset is number 1.0, expected text`. The holiday calendar, which may be left out with nothing in its place, decision 39's form, `holiday_calendar: Handle[HolidayCalendar] | None = None`: a holiday-calendar handle, the cell showing `_CreateHolidayCalendar`'s result or a name for it, checked as the seam checks any handle, a blank, a text naming no live object and a handle of another kind refused in its words, `holiday_calendar is blank, expected holiday calendar handle`, `holiday_calendar is valuation date handle '30512:valuation_date:3', expected holiday calendar handle`; a blank is no omission. The calendar is checked whatever the offset, a zero count and a calendar-day one included, and read by the business days alone, every `bd` of a chain on the one calendar. The result is a date, the serial the sheet formats; nothing is published and no handle is made, so a shifted date is a plain cell, recalculated when its date, its offset or its calendar's cell changes and never otherwise. Since #183 the calendar may be a combination of calendars, [combine-holiday-calendars.md](../index-definitions/combine-holiday-calendars.md), closed on every day any of them is closed: on the ticket's combination of A, the 14th, the 12th and the 14th of October 2026, and B, the 13th and the 14th, `+1bd` from Friday the 9th is Thursday the 15th and `+2bd` Friday the 16th, and from the 15th `-1bd` is the 9th; every `bd` instruction of a chain counts on the one calendar given.

## Excel help

Quoted from the declaration in `src/goosedove/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Shifts a date by business days, calendar days or month ends, +1bd the next business day, -1bd the one before, +7cd a week on, +0em the month's last day, a chain such as +3em+25cd-1bd+1bd applied left to right, and shows the date. |
| `date` | The day to shift, such as A2 or DATE(2026,10,9). |
| `offset` | The shift as text: one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd, applied left to right, typed or in a cell such as B2. |
| `[holiday_calendar]` | The holiday-calendar handle whose holidays business days skip, such as C2; left out for Monday to Friday with no holidays. |

## The grammar

One or more instructions, each one sign, `+` or `-`, one whole count in ASCII digits, leading zeros allowed and dropped before the count is read, however many, and one of three suffixes in either case, one after another with nothing before, between or after: `+1bd`, `-1BD`, `+001cD`, `-0em`, `+3em+25cd-1bd+1bd`, `+003EM+025cD-01BD+001bd`. A count of more than seven significant digits is refused by its digits, since the sheet's calendar is 2,958,404 days, 2,113,146 business days and 97,197 month ends end to end and an eighth digit names no day a cell can show; so is anything else, a missing sign, a decimal, a space, a letter that is no suffix or a digit that is no ASCII digit, naming the offset and the form, and past the first instruction the character the reading reached and the text from there, so a chain malformed late fails whole.

| Suffix | Means | From Friday 9-Oct-2026 |
|---|---|---|
| `bd` | business days, Monday to Friday less the calendar's holidays, counted strictly from the date without including it: `+n` the n-th business day after, `-n` the n-th before, `0` the date itself, closed or not | `+1bd` Monday the 12th, or Tuesday the 13th when the Monday is closed; `-1bd` Thursday the 8th |
| `cd` | calendar days, weekends and holidays counted alike; the calendar is read for nothing | `+7cd` the 16th; `-7cd` the 2nd |
| `em` | month ends: the date's month moved by the count, and that month's last calendar day, whatever day of the week it is; `+0em` the date's own month's; the calendar is read for nothing | `+0em` Saturday the 31st; `+1em` 30-Nov-2026; `-1em` 30-Sep-2026 |

A date that is itself closed is counted from, not counted: Saturday `+1bd` is Monday, Sunday `-1bd` is Friday, a closed Monday `+1bd` is the Tuesday and `-1bd` the Friday before it. In numpy's terms a positive count rolls a closed date back before counting forward and a negative one rolls it forward before counting back, so that the first business day after a closed day is the next open day and not the one after it, and a zero count rolls nothing. February's length and the year end fall out of numpy: `+1em` from 31-Jan-2028 is 29-Feb-2028, from 31-Jan-2027 is 28-Feb-2027, and from 15-Dec-2026 is 31-Jan-2027. The business days from an open day round trip, `+n` then `-n` returning the day; from a closed day they do not, since the closed day is never a day counted to.

A chain is its instructions in turn, each applied to the result of the one before, and the order is the rule: nothing is netted, reordered or cancelled, `-1bd+1bd` keeps an open day and moves a closed one to the next open day, `+1cd+0em` from 30-Jan-2026 is the 31st and `+0em+1cd` is 1 February. There is no roll at the end: a chain ending in `cd` or `em` may land on a weekend or a holiday, `+1cd` from Friday the 9th being the Saturday, and a `bd` is written where a roll is wanted. The ticket's chain from 12 August 2026 on H, a calendar closing Christmas Day and nothing else:

| Instruction | Result |
|---|---|
| start | 12-Aug-2026 |
| `+3em` | 30-Nov-2026, the end of the month three ahead |
| `+25cd` | 25-Dec-2026, which H closes |
| `-1bd` | 24-Dec-2026, the business day before |
| `+1bd` | 28-Dec-2026, past the closed Friday and the weekend; 25-Dec-2026 without H, the Friday open |

## The library checks

Four rules, the first failure being the message, after the seam's own checks of the three arguments; the offset is read whole before any instruction is applied, so a chain malformed late makes no date.

| Rule | Message |
|---|---|
| the offset begins with an instruction, a sign, a count and a suffix, as the grammar says | `offset is '1bd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd` |
| past the first instruction, every character on begins another; where none does, the reading names the character it reached and the text from there | `offset is '+1bd+2xd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd; from character 5, '+2xd' begins with no instruction` |
| each count has at most seven significant digits, checked before any arithmetic, so that no count ever runs over the day arithmetic or Python's own conversion; the instruction named when the offset has more than one | `offset has a count of 8 digits, expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31`; `offset has a count of 8 digits in instruction 2, '+99999999cd', expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31` |
| the day each instruction makes lies within the sheet's calendar, 1 March 1900 to 31 December 9999, named with the date and the offset that left it and the instruction when the offset has more than one, whatever a later instruction would have made of it | `date 9999-12-31 shifted by '+1cd' is 10000-01-01, outside the sheet's calendar, 1900-03-01 to 9999-12-31`; `date 9999-12-31 shifted by '+1cd-1cd' is 10000-01-01 at instruction 1, '+1cd', outside the sheet's calendar, 1900-03-01 to 9999-12-31` |

The sheet's two days are the library's in `src/goosedove/index_definitions/sheet_days.py`, the same two a trade's payment rule is held to; `9999-12-31` with `+0em` is its own month's end and stands, since the month after is reached and a day subtracted before the rule is applied to what is made. Nothing is clamped, filled in or rolled to make a result fit.

## The reading

The offset is read once, `read_offset`, one instruction at a time from the start, a sign, digits and two letters where the reading stands; each suffix is looked up among the three; each count's leading zeros are dropped and the count is read as an integer from the digits left, only after they are counted; the instructions come back as a tuple, text, unit and signed count each. They are applied once, `shift_days`, to the one day as an array of one, since the same function applies a trade's rule to every component's anchor at once, [create-trades.md](../trades/create-trades.md): a business-day instruction is one `np.busday_offset` with the sign's roll and the calendar's holidays, or none; a calendar-day instruction one `np.timedelta64` added; a month end two conversions, the days to their months, the months moved by the count and one, to their first days, less one day; after each instruction one look says whether any day left the sheet's calendar, the first such instruction and its day kept per day. No loop runs over the days shifted, so a shift of two million business days costs what a shift of one does, and a chain costs its instructions and nothing more, as the budgets pin.

## Tests

The library's examples and properties are `tests/unit/test_date_offsets.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`, with a fact on a calendar the host makes. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the ticket's sixteen worked answers, the synthetic calendar of one closed Monday where it says, the calendar omitted where it says | example |
| a nonleap February, three business days across the holiday and back, two weekends, every suffix in mixed case, the signed zeros of each suffix on a Sunday, a count with leading zeros | example |
| the sheet's last day keeps its month end; its first and last days reached from each other end to end in calendar days; a day past either end, by a day, a business day or a month, and the largest seven-digit counts of each suffix, refused naming the date and the offset; eight digits and five thousand refused by their digits; seven digits read; five thousand leading zeros dropped, the digits after them read, none as zero and eight refused | example |
| twelve texts that are no offset, a missing sign, a decimal, a space, a letter that is no suffix, an Arabic-Indic digit, refused naming the offset; eleven chains malformed late, a space, a letter, a sign on its own, a second instruction with no unit or a decimal, a bracket, refused whole naming the character reached | example |
| since #181: the requested chain through the holiday instruction by instruction and without the calendar; the compound ticket's nine answers, the zeros and cases as one, the order as the rule, no roll at the end; an offset read whole into its instructions; too many digits in a later instruction named by it; an instruction leaving the sheet refused at that instruction though the next comes back | example |
| from any open day of 2026 to 2080, with the calendar and without, `+n` business days lands on an open day n business days on and `-n` returns; any month end is the last day of the month the count names; calendar days add and subtract whatever the calendar; since #181 any chain of up to six instructions is its instructions applied one by one | property |
| the ticket's table through the seam as serials and a float, since #181 the requested chain on a calendar closing Christmas Day and without it; the library's refusals in its words, a chain malformed late and a chain leaving the sheet among them; the date, the offset and the calendar refused in the seam's, a blank, a dead text and a valuation date where the calendar should be, whatever the offset; two calendars published and nothing of the shifts | example, through the seam |
| the same calls, the calendar's resolution the difference, the offset read once and applied once, and the same numpy for one business day and for two million, a week and the calendar end to end, one month end and ninety thousand, one look per instruction at the sheet's calendar, the requested chain four; within three slacks for each and four for the chain, nothing published | budget |
| the ticket's table on a sheet with the synthetic calendar in PA2 and since #181 the chain on H in PB2, the refusals in both sets of words; the host's rows and its fact on a calendar of its own | Excel smoke, host |
| rows 1884 to 1905 of the kept workbook's handles sheet, the table with its calendar and two refusals; since #181 the chain's block from row 2500 | workbook |

## Not here

No reading of a date from text, a contract code or a period label: a date is a date, and [util_StartDate](start-date.md) and [util_EndDate](end-date.md) turn labels into days. No custom weekend, no time of day, no clamping of a month end to a business day and no month-end business-day adjustment, no named rolling convention: an instruction is one of three, and a roll is written as a `bd`. No valuation date, market or clock: the function is deterministic and nonvolatile, a plain cell of the sheet's dependency graph. The trade's payment rule reads through this grammar since #181, on its required calendar and from its own anchors, [create-trades.md](../trades/create-trades.md); the helper itself is composed in Excel with explicit dates.
