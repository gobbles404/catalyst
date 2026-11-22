# _CreateHolidayCalendar

A name and the days one market is closed, listed one by one as the desk keeps them, kept as given and reached by handle. It is a static calendar: the list is the calendar, and no day is generated from a rule. Every reader chooses a calendar by its name, a key, from a collection of calendars: [_CollectHolidayCalendars](collect-holiday-calendars.md) owns the collection and the key, and [holiday-keys.md](../../engineering-tickets/trade-valuation-pipeline/holiday-keys.md) is the decision.

Its readers are an [index](index.md), which holds a futures market's calendar beside its schedule, the payment days of a [batch of trades](../trades/create-trades.md) and of a [quote template](../quoting/quote-template.md), and [util_ShiftDate](../utilities/shift-date.md). Through an index, the [futures fixings](../market-data/futures-fixings.md) are refused on a listed day, or without a fixing on a business day, through numpy's business-day functions over this list, as [time.md](../time.md) decided; the [calendar](../calendar/calendar.md) reads it the same way, flagging whether the market is open on each of its days. The code is `src/catalyst/index_definitions/holiday_calendar.py`, the record and its builder, and `src/catalyst/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateHolidayCalendar(name: str, holiday: DateColumn) -> Handle[HolidayCalendar]: ...
```

| | A | B |
|---|---|---|
| 1 | holiday | |
| 2 | 1-Jan-2026 | |
| 3 | 19-Jan-2026 | |
| 4 | 16-Feb-2026 | |
| 5 | 3-Apr-2026 | |
| 6 | 25-May-2026 | |
| 7 | 19-Jun-2026 | |
| 8 | 3-Jul-2026 | |
| 9 | 7-Sep-2026 | |
| 10 | 26-Nov-2026 | |
| 11 | 25-Dec-2026 | |
| 12 | `=_CreateHolidayCalendar("NYMEX",A2:A11)` | shows `30512:holiday_calendar:NYMEX:6` |
| 13 | `=_CreateHolidayCalendar("NEW_YEAR",A2)` | shows `30512:holiday_calendar:NEW_YEAR:7`, a market closed on one day |

The name first, then one column of dates, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. A single cell is a column of one, so a market closed on one day needs no range. The seam checks the name as text and the column alone, dates one column wide, no blank cells, and hands over an array of days; nothing here restates that. The result is a handle: text in the cell that stands for the calendar the seam keeps, declared `Handle[HolidayCalendar]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. The one consumer of the handle is the collection: no other function takes a calendar's handle.

## Excel help

Quoted from the declaration in `src/catalyst/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a holiday calendar from its name and the days one market is closed, and shows its handle, the text _CollectHolidayCalendars takes as the calendar. |
| `name` | The calendar's name, text such as NYFED, exact and case-sensitive with no whitespace around it and no plus sign: what a holiday key selects it by. |
| `holiday` | The column of dates the market is closed, such as A2:A11, one holiday per row. |

## The name

Required, the first argument. It is kept as typed and shows in two places: in the handle, `30512:holiday_calendar:NYMEX:6`, and beside each day of the readback, a second column `name`, as a curve's readback repeats its name.

| Rule on a name | Refused as |
|---|---|
| Not whitespace alone | `name is ' ', expected a name, not whitespace alone` |
| No whitespace around it | `name is ' NYFED', expected a name with no whitespace around it` |
| No plus sign, which joins names in a key | `name is 'NYFED+LON', expected a name without '+', which joins names in a key` |

The first two are the curve name's rule, [discount-curve.md](../globals/discount-curve.md), since a key matches a name exactly, case and all. A name left out, a blank cell, a number or empty text for the name is the seam's to refuse: `name is missing, expected text`, `name is number 7.0, expected text`. Nothing asks that a name be unique until calendars are collected.

## The library checks

None on the days. A calendar is the days the desk listed. The dates are kept as given, in the order given: a day listed twice is listed twice, a day out of order stays where it was, and a Saturday listed is kept. What a calendar must look like for a reader to use it, whether days repeat, whether they increase, whether a weekend day belongs, is that reader's rule; its readers read the list as numpy does, a day listed twice counting once and a weekend day listed adding nothing, so none needs one. A one-row calendar is a calendar. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and properties of the days are `tests/unit/test_holiday_calendar.py`; the name's are `tests/unit/test_holiday_calendars.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the calendar; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py`, `tests/performance/test_seam_allocation.py` and `tests/performance/test_holiday_calendar_budgets.py`.

| Case | Kind |
|---|---|
| the ten-row sample above: every day preserved, as given, in order | example |
| a one-row calendar accepted | example |
| a day listed twice, days out of order and a Saturday are kept as given: nothing else is checked | example |
| for any column of `N` dates, every day is preserved in order | property |
| an input changed after construction leaves the calendar unchanged, and its array refuses writes | example |
| a name kept as typed, and each name no key could select refused | example |
| a column read back through its handle holds the days that went in beside the name, and a single cell is a calendar of one day | example, through the seam |
| a name left out, a blank, a number or empty text for it; a blank, text or a time in the column, a row of dates, a blank cell or the column left out: the seam's words | example, through the seam |
| a rejected column publishes no object and no handle | example, with handles |
| a handle of another kind is not a calendar | example, with handles |
| the creator's handle over three days and over one cell, read back through `util_ReadHandle`, a blank in the column and a row where a column is expected, in a real workbook | Excel smoke |

## Not here

Whether a day is a business day: the futures fixings' rule and the calendar's priced flag, numpy's business-day functions over this list as [time.md](../time.md) decided. Where a date that falls on a holiday rolls to: [util_ShiftDate](../utilities/shift-date.md)'s and a payment rule's. Weekends: the calendar holds the days the desk listed and knows nothing of Saturdays and Sundays; its readers treat them as closed, Monday to Friday being the week. Holidays from a rule, the third Monday of January say: the list is the calendar. Which market the calendar belongs to, its exchange, its time zone: a name is the word a key selects by and says nothing of a market. A market with no holidays: a range has at least one cell and a blank fails, so the smallest calendar holds one day, and an empty calendar waits for a need. A calendar closed when either of two is: a key of two names, `NYFED+LON`, [collect-holiday-calendars.md](collect-holiday-calendars.md#binding-a-key), and no function of its own. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any calendar.
