# _CollectPaymentCalendars

Named holiday calendars gathered into one collection, the calendars a trade's payment calendar key will select from by name. [payment-calendar-keys.md](../../engineering-tickets/trade-valuation-pipeline/payment-calendar-keys.md) is the ticket. A calendar gets its name where it is made, the optional second argument of [_CreateHolidayCalendar](holiday-calendar.md); this page is the collection alone. No field reads a collection yet: the field `payment_calendar_key` and its binding are the ticket's second pull request.

It follows [_CollectDiscountCurves](../globals/collect-discount-curves.md), which gathers named curves the same way.

## Worksheet contract

```python
def _CollectPaymentCalendars(calendar_handles: Handles[HolidayCalendar]) -> Handle[PaymentCalendars]: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | NYFED | LON | |
| 2 | 26-Nov-2026 | 27-Nov-2026 | |
| 3 | | 30-Nov-2026 | |
| 4 | `=_CreateHolidayCalendar(A2,"NYFED")` | `=_CreateHolidayCalendar(B2:B3,"LON")` | shows `30512:holiday_calendar:NYFED:6` and `30512:holiday_calendar:LON:7` |
| 5 | `=_CollectPaymentCalendars(A4:B4)` | | shows `30512:payment_calendars:8` |
| 6 | `=util_ReadHandle(A5)` | | spills the table below |

The calendars in a cell, a row or a column of cells, each showing a calendar's handle: the form `_CombineHolidayCalendars` takes, [combine-holiday-calendars.md](combine-holiday-calendars.md). One calendar follows the same path as many. The days in the sample are synthetic and claim no market's convention.

`util_ReadHandle` on the collection spills one row per calendar in the order given, its name and how many days it lists. The days themselves are each calendar's own handle's to spill.

| name | holidays |
|---|---|
| str | int64 |
| NYFED | 1 |
| LON | 2 |

## Excel help

Quoted from the declaration in `src/catalyst/excel/index_definitions.py`, which `tests/unit/test_help.py` pins.

| Item | Text |
|---|---|
| Function | Collects named holiday calendars into one collection, each name once, the calendars as they are and nothing of their days combined, and shows its handle, the text other formulas take as the collection. |
| `calendar_handles` | The calendars to collect: a cell, a row or a column of cells showing _CreateHolidayCalendar's results, such as B2:B3, each made with a name and each name once. |

## The library checks

Two, by `collect_payment_calendars` in `src/catalyst/index_definitions/payment_calendars.py`, the one way to make a `PaymentCalendars`. The cells are counted from one in the order the sheet gave them.

| Rule | Refused as |
|---|---|
| Every member has a name, since a key could never select one without | `calendar_handles cell 2 is a calendar with no name, expected one made with a name, the word a payment calendar key selects it by` |
| Each name once, the same calendar given twice a repeat too | `calendar_handles cell 1 and cell 3 are both named 'NYFED', expected each name once` |

Names are compared exactly, case and all, so `NYFED` and `nyfed` are two names. A combination from `_CombineHolidayCalendars` has no name and is no member.

Nothing else is checked. No day is read, copied or combined, and the calendars are held by reference, so a collection is remade when one of its calendars is and a held one keeps its old members. A calendar nobody selects costs nothing.

The seam's refusals are its own: a cell that is blank, a number or a handle of another kind is named by its cell, `calendar_handles cell (2, 1) is blank, expected holiday calendar handle`; no argument at all reads `calendar_handles is missing, expected holiday calendar handles in a cell, a row or a column`.

## Work

`calendars_collected`, one per calendar given. A refusal counts nothing. `tests/performance/test_payment_calendar_budgets.py` pins the calls, which grow with the handles alone and run no numpy, and the peak, which follows the calendars and nothing of their days.

## Not here

- The key: one name, or several joined by `+`, and its binding when a batch or a quote template is made. That is the ticket's second pull request.
- A second name for one calendar. A calendar wanted under two names is made twice.
- A name on a combination.
