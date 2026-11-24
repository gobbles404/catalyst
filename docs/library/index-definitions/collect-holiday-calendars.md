# _CollectHolidayCalendars

Holiday calendars gathered into one collection, the calendars a key selects from by name: a trade's or a quote's `payment_holiday_key`, and the `holiday_key` of an [index](index.md) and of [util_ShiftDate](../utilities/shift-date.md). [holiday-keys.md](../../engineering-tickets/trade-valuation-pipeline/holiday-keys.md) is the decision, after [payment-calendar-keys.md](../../engineering-tickets/trade-valuation-pipeline/payment-calendar-keys.md). A calendar gets its name where it is made, the first argument of [_CreateHolidayCalendar](holiday-calendar.md); this page is the collection and the key that selects from it.

It follows [_CollectDiscountCurves](../globals/collect-discount-curves.md), which gathers named curves the same way.

## Worksheet contract

```python
def _CollectHolidayCalendars(
    calendar_handles: Handles[HolidayCalendar],
) -> Handle[HolidayCalendars]: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | NYFED | LON | |
| 2 | 26-Nov-2026 | 27-Nov-2026 | |
| 3 | | 30-Nov-2026 | |
| 4 | `=_CreateHolidayCalendar(A1,A2)` | `=_CreateHolidayCalendar(B1,B2:B3)` | shows `30512:holiday_calendar:NYFED:6` and `30512:holiday_calendar:LON:7` |
| 5 | `=_CollectHolidayCalendars(A4:B4)` | | shows `30512:holiday_calendars:8` |
| 6 | `=util_ReadHandle(A5)` | | spills the table below |

The calendars in a cell, a row or a column of cells, each showing a calendar's handle. One calendar follows the same path as many. The days in the sample are synthetic and claim no market's convention.

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
| Function | Collects holiday calendars into one collection, each name once, the calendars as they are and nothing of their days combined, and shows its handle, the text other formulas take as the collection a holiday key selects from. |
| `calendar_handles` | The calendars to collect: a cell, a row or a column of cells showing _CreateHolidayCalendar's results, such as B2:B3, each name once. |

## The library checks

One, by `collect_holiday_calendars` in `src/catalyst/index_definitions/holiday_calendars.py`, the one way to make a `HolidayCalendars`. The cells are counted from one in the order the sheet gave them.

| Rule | Refused as |
|---|---|
| Each name once, the same calendar given twice a repeat too | `calendar_handles cell 1 and cell 3 are both named 'NYFED', expected each name once` |

Names are compared exactly, case and all, so `NYFED` and `nyfed` are two names.

Nothing else is checked. No day is read, copied or combined, and the calendars are held by reference, so a collection is remade when one of its calendars is and a held one keeps its old members. A calendar nobody selects costs nothing.

The seam's refusals are its own: a cell that is blank, a number or a handle of another kind is named by its cell, `calendar_handles cell (2, 1) is blank, expected holiday calendar handle`; a range that is neither one row nor one column reads `calendar_handles is 2x2 array, expected one cell, one row or one column of holiday calendar handles`; no argument at all reads `calendar_handles is missing, expected holiday calendar handles in a cell, a row or a column`.

## Binding a key

A key is one calendar's name, or several joined by `+`. It is the one way a calendar is chosen, and the one way to say a calendar closed when any of several is.

| Key | Means |
|---|---|
| `NYFED` | the collection's calendar of that name, taken as it is, by reference |
| `NYFED+LON` | the calendar closed on every day either is closed, their union |
| `LON+NYFED` | the same calendar: the order of the names does not matter |

On the sample, one business day on from Wednesday 25 November 2026 is Friday the 27th on `NYFED`, Thursday the 26th on `LON`, and Tuesday 1 December on `NYFED+LON`.

Each reader binds its key once, when its object is made, and nothing later looks a name up:

| Reader | Its key | Bound by |
|---|---|---|
| A batch of trades | `payment_holiday_key`, each financially settled row's | [_CreateTrades](../trades/create-trades.md), once per distinct key |
| A quote template | `payment_holiday_key`, its one | [_CreateQuoteTemplate](../quoting/quote-template.md) |
| A futures index | `holiday_key` | [_CreateIndex](index.md) |
| A date shift | `holiday_key` | [util_ShiftDate](../utilities/shift-date.md), on each call |

Each of the four takes the collection as its last argument. A reader that holds a key must be given it. A collection given where no key selects from it, a physically settled batch or a published index, is read for nothing.

The step is one for every reader, `keyed_calendar` in `src/catalyst/index_definitions/holiday_calendars.py`, with `calendar_of` in front of it for the readers that hold at most one key. The key's own form is read first, by `calendar_key`, which a [trade template](../trades/trade-template.md) also reads its key by. Then each name is looked up exactly, case and all, with nothing trimmed or guessed, no fallback and no choice made for a collection of one. A key of several names is united once for each distinct set of names in a batch, so `NYFED+LON` on two thousand rows, or beside `LON+NYFED`, is one calendar.

The union, `combine_holiday_calendars` in `src/catalyst/index_definitions/holiday_calendar.py`: the listed days of the named calendars taken together and the distinct days kept in order, once each; a weekend day listed is kept as any other. The calendars it reads stand as they were. It is named by its names in sorted order joined by `+`, `LON+NYFED`, and the sheet cannot make one under a name of its own.

| Rule | Refused as |
|---|---|
| No name is missing | `payment_holiday_key row 1 is 'PAY_A+', expected a calendar's name, or several joined by '+'; a name is missing` |
| No name has whitespace around it | `holiday_key is 'NYFED + LON', expected a calendar's name, or several joined by '+', each with no whitespace around it` |
| Each name once, since a name twice says nothing | `holiday_key is 'NYFED+NYFED', expected a calendar's name, or several joined by '+', each once; 'NYFED' is given twice` |
| Every name is a calendar of the collection | `payment_holiday_key row 2 is 'PAY_A+PAY_C', expected names of the collection's calendars, 'PAY_A' and 'PAY_B'; it holds no 'PAY_C'` |
| A key has a collection to select from | `holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which a financially settled batch selects a calendar from`; from the other three readers, `which payment_holiday_key selects a calendar from` or `which holiday_key selects a calendar from` |

A key the ticket supplies is named with its row, the first row holding that text; any other key is named by its argument or field alone. A calendar's handle typed where a key goes is text, so it is read as a name the collection lacks.

For a payment, the calendar is what a payment rule's business days are counted on, Monday to Friday less its holidays. It never stops a payment falling on a holiday: a row that pays on a stated date pays on that date as entered, and its key is still required and still looked up, though the calendar is read for nothing.

## Work

`calendars_collected`, one per calendar given. A refusal counts nothing. `tests/performance/test_holiday_calendar_budgets.py` pins the calls, which grow with the handles alone and run no numpy, and the peak, which follows the calendars and nothing of their days.

Binding counts `holiday_keys_bound`, one per distinct key text a batch binds, however many rows hold it, and one for a quote template, an index or a date shift that holds a key. A key of several names adds the union's own counts, `calendars_combined`, `holidays_read` and `holidays_kept`, once per distinct set of names in a batch and on every call of a date shift.

## Not here

- Cleaning a key: no trimming, no case folding. Keys are cleaned to one format in the sheet.
- A second name for one calendar, or a short name for a union. A calendar wanted under another name is made again over its days.
- Keeping a union between calls of the date shift.
- Rolling a stated payment date onto a business day.
