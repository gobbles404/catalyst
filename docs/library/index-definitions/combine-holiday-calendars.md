# _CombineHolidayCalendars

Built in #183 as the ticket [combine-holiday-calendars.md](../../engineering-tickets/trade-valuation-pipeline/combine-holiday-calendars.md), UAT item 16.

One holiday calendar closed on every day any of the given calendars is closed. Two desks' calendars, a clearing house's and a bank's, combined this way give the days a payment can move on when it must be open on all of them: a holiday in any of the calendars is a holiday in the result, and a weekday none of them lists stays open. The result is an ordinary [holiday calendar](holiday-calendar.md), reached by handle, for an index, for [util_ShiftDate](../utilities/shift-date.md) or for another combination. A payment calendar of several centres needs no cell of this function since [payment-calendar-keys.md](../../engineering-tickets/trade-valuation-pipeline/payment-calendar-keys.md): a key of several names, `NYFED+LON`, makes the same union when a batch or a quote template is made, [collect-payment-calendars.md](collect-payment-calendars.md#binding-a-key), and a combination, having no name, is no member of a collection.

## Worksheet contract

```python
def _CombineHolidayCalendars(
    calendar_handles: Handles[HolidayCalendar],
) -> Handle[HolidayCalendar]: ...
```

The ticket's synthetic calendars, which claim no exchange's rules: A lists Wednesday 14 October 2026 twice around Monday the 12th, B the 13th and the 14th.

| | A | B | D |
|---|---|---|---|
| 1 | 14-Oct-2026 | 13-Oct-2026 | `=_CreateHolidayCalendar(A1:A3)` shows `30512:holiday_calendar:7`, calendar A as listed |
| 2 | 12-Oct-2026 | 14-Oct-2026 | `=_CreateHolidayCalendar(B1:B2)` shows `30512:holiday_calendar:8`, calendar B |
| 3 | 14-Oct-2026 | | `=_CombineHolidayCalendars(D1:D2)` shows `30512:holiday_calendar:9`, closed on the 12th, the 13th and the 14th |
| 4 | | | `=util_ReadHandle(D3)` spills `holiday`, `datetime64[D]`, then 12-Oct-2026, 13-Oct-2026 and 14-Oct-2026, once each, in order |
| 9 | 9-Oct-2026 | | `=util_ShiftDate(A9,"+1bd",D3)` shows `46310`, Thursday 15 October: the weekend and the three listed weekdays are closed |
| 10 | | | `=util_ShiftDate(A9,"+2bd",D3)` shows `46311`, Friday 16 October |
| 11 | 15-Oct-2026 | | `=util_ShiftDate(A11,"-1bd",D3)` shows `46304`, Friday 9 October |
| 12 | | | `=_CombineHolidayCalendars(D1)` shows `30512:holiday_calendar:10`, one calendar combined: its own distinct days, the 12th and the 14th, in order |
| 13 | 10-Oct-2026 | | `=_CreateHolidayCalendar(A13)` shows `30512:holiday_calendar:11`, a Saturday listed; E13 holds `=D3`, the combination's handle beside it |
| 14 | | | `=_CombineHolidayCalendars(D13:E13)` shows `30512:holiday_calendar:12`, closed on the 10th, the 12th, the 13th and the 14th: a combination is an ordinary input, so combining nests without a special case |

One argument, required and without a default: a cell, a row or a column of cells each showing `_CreateHolidayCalendar`'s result, this function's or a name for one, `Handles[HolidayCalendar]`, [inputs.md](../../seam/inputs.md) decision 44. The seam holds the range to one cell, one row or one column before any cell is read, a wider and taller block refused by its shape; then each cell is resolved once, in sheet order, left to right along a row and down a column, a repeat read again, and the function receives the calendars and never the texts. A blank cell, a number, an empty text, a text naming no live object, a handle of another kind and a creator's failure are each refused at their cell, the failure carried whole so that a consumer of the failed combination shows the creator's text once. One cell is one calendar combined, so at least one calendar is always given; the argument left out or a blank cell in its place is refused in the seam's words.

A payment on the combined calendar: a cleared, financially settled trade whose component stops trading on Friday 9 October 2026 under a rule of `+1bd` pays Thursday 15 October, as it does on a calendar the desk listed as the union itself; on A alone it pays Tuesday the 13th, on B alone Monday the 12th. Nothing of [create-trades.md](../trades/create-trades.md) changes: the template holds a calendar handle, and a combination is one.

## The rule

The union of closed days, in the ticket's words: a holiday in any input calendar is a holiday in the result. Business days stay Monday to Friday less the calendar's holidays, as every reader of a calendar counts them, so a weekend day a calendar lists is kept in the result and changes no business day.

| Calendar A | Calendar B | Combined business day |
|---|---|---|
| Open | Open | Open |
| Closed | Open | Closed |
| Open | Closed | Closed |
| Closed | Closed | Closed |

The listed days of every calendar are taken together and the distinct days kept in chronological order, once each: a day two calendars list or one lists twice is kept once. This is the one place a calendar's list is sorted and deduplicated; `_CreateHolidayCalendar` keeps the desk's list as given, repeats and order and all, as [holiday-calendar.md](holiday-calendar.md) says, and a single calendar combined comes out as its distinct days in order. The sources are read and left as they are. The result owns its days, frozen, through the same builder every calendar comes from, so a combination is an ordinary calendar and an ordinary input to another combination; the order of the inputs and a repeated input change nothing of the days.

## Excel help

Quoted from the declaration in `src/catalyst/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Combines holiday calendars into one closed on every day any of them is closed, the days in order, once each, and shows its handle, an ordinary calendar for an index, util_ShiftDate or another combination. |
| `calendar_handles` | The calendars to combine: a cell, a row or a column of cells showing _CreateHolidayCalendar's or this function's results, such as B2:B3, every one read and a repeat read again. |

## The library checks

None of its own: any calendars combine, and the seam's checks on the handles are the whole of it. Nothing is published by a refusal.

| Refused | As |
|---|---|
| a block wider and taller than one | `calendar_handles is 2x2 array, expected one cell, one row or one column of holiday calendar handles` |
| a blank cell among the handles | `calendar_handles cell (2, 1) is blank, expected holiday calendar handle` |
| a number, a date among them | `calendar_handles cell (1, 2) is number 46307.0, expected holiday calendar handle` |
| an empty text | `calendar_handles cell (2, 1) is empty text, expected holiday calendar handle` |
| text naming no live object | `calendar_handles cell (2, 1) is text 'x' naming no live object, expected holiday calendar handle` |
| a handle of another kind | `calendar_handles cell (2, 1) is futures schedule handle '30512:futures_schedule:3', expected holiday calendar handle` |
| a creator's failure in a cell | `calendar_handles cell (2, 1) is the creator's failure, expected holiday calendar handle: #ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date`, and a consumer of the combination shows that creator's text once |
| the argument left out, or a blank cell in its place | `calendar_handles is missing, expected holiday calendar handles in a cell, a row or a column`; `calendar_handles is blank, expected holiday calendar handles in a cell, a row or a column` |

## The record

A `HolidayCalendar`, as [holiday-calendar.md](holiday-calendar.md) describes it: one column of days, here the distinct days of every source in chronological order, frozen and owned. Its readback through `util_ReadHandle` is the calendar's, one `holiday` column, so a combination of one calendar reads back as that calendar's distinct days.

## Work

`combine_holiday_calendars` in `src/catalyst/index_definitions/holiday_calendar.py` counts what it did on the `WorkCounter` it is given: `calendars_combined`, the calendars taken; `holidays_read`, the listed days read from them; `holidays_kept`, the distinct days kept. The ticket's two calendars count 2, 5 and 3.

The numpy, the same at two calendars and at twenty-four, pinned in `tests/performance/test_seam_budgets.py`: one concatenation of the sources, which runs in C unseen by the ledger, one `unique`, which the ledger sees as its flatten, sort and hash over two `asanyarray` views, then the builder's one copy and its freeze. The seam's calls grow with the handles and nothing else does: the vector's shape checked once, the cells decoded in one pass, each resolved once, one publication. A combination keeps its distinct days and nothing of its sources, 800 bytes for a hundred distinct days, freed on release, `tests/performance/test_seam_allocation.py`. A trade paying on a combined calendar does the plain calendar's work, call for call, at creation, preparation, evaluation and reporting, `tests/performance/test_trade_valuation_budgets.py`: the union ran once, when the combination was made, and no step after it reads a calendar again.

## Tests

The examples and property are `tests/unit/test_holiday_calendar.py`; the seam's texts and handles `tests/unit/test_index_definitions.py`; the shifted dates `tests/unit/test_utilities.py`; the payment `tests/unit/test_create_trades.py`; the help lines `tests/unit/test_help.py`; the smoke rows `tools/excel_smoke.ps1`, the TA block; the lifetime group `calendars` in `tools/excel_lifetime.ps1`; the host's fact `host/Catalyst.Host.Tests/CallTests.cs`; the kept workbook from row 2624 of the handles sheet.

| Case | Kind |
|---|---|
| the ticket's A and B combine into the 12th, the 13th and the 14th in order, counting 2 calendars, 5 days read and 3 kept; the same days as a calendar listing the union | example |
| one calendar combines into its own distinct days in order | example |
| the inputs reversed, repeated and overlapping change nothing of the days; a calendar combined with itself; a combination combined with a Saturday calendar is the combination of all three, the Saturday kept | example |
| the sources are left as listed; the result refuses writes and shares no memory with a source | example |
| for any calendars, the combination is the distinct days of all of them in order, whatever the order of the inputs, and the counts say how many were read and kept | property |
| a column and a row of handles give the same calendar, one cell its own distinct days, a repeat is read again, a combination combines again, the sources stand; the readback once each in order; every refusal above in the seam's words, a consumer of a failed combination showing the creator's text once, nothing published by a refusal | example, through the seam |
| from Friday 9 October 2026 `+1bd` is the 15th, `+2bd` the 16th and from the 15th `-1bd` the 9th on the combination, as on the union listed; the 13th on A alone; `+1bd+1bd` the 16th; `+7cd` reads the calendar for nothing | example, through the seam |
| a cleared financial trade anchored on the 9th pays the 15th under `+1bd` on the combination as on the union, the 16th under `+2bd`, the 13th on A, the 12th on B and the 12th with no holidays | example |
| the seam's calls grow with the handles, the numpy does not; the bytes kept and freed; a combined payment calendar adds no work after creation | budget |
| the TA block: A, B and a Saturday calendar, their combination in a column, in a row, alone and nested, read back; the shifted dates; a trade anchored on the 9th paying the 15th; a block, a blank cell, a date, text naming nothing and the argument left out refused | Excel smoke |
| the `calendars` group: a source's day moves and the combination, the shift and the readback follow, the old publications released; a source cleared fails the combination at its cell and the shift relays it; the source typed back rebuilds both | Excel lifetime |
| the same calendars on the host: the readback, the row form, one alone, the shifts, the trade's payment day, the refusals and a failed source carried whole | host |

## Not here

Which calendars a payment should be open on: the desk's choice, made in the template. No exchange, clearing or currency calendar is chosen, downloaded or generated, no coverage horizon is added and no custom weekend is introduced; a calendar carries no horizon today, so combining cannot detect a holiday a source never listed. Counting business days on one calendar and rolling the result on another is a different payment convention, for its own specification. `_CreateHolidayCalendar` is unchanged and keeps the list as given.
