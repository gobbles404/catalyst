# _CollectPaymentCalendars

Named holiday calendars gathered into one collection, the calendars a trade's or a quote's `payment_calendar_key` selects from by name. [payment-calendar-keys.md](../../engineering-tickets/trade-valuation-pipeline/payment-calendar-keys.md) is the ticket. A calendar gets its name where it is made, the optional second argument of [_CreateHolidayCalendar](holiday-calendar.md); this page is the collection and the key that selects from it.

It follows [_CollectDiscountCurves](../globals/collect-discount-curves.md), which gathers named curves the same way.

## Worksheet contract

```python
def _CollectPaymentCalendars(
    calendar_handles: Handles[HolidayCalendar],
) -> Handle[PaymentCalendars]: ...
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

## Binding a key

A financially settled row of a batch, and a quote template, names its payment calendar by a key, the field `payment_calendar_key`: one calendar's name, or several joined by `+`. The key is bound once, when the batch or the quote template is made, by the creator that was given the collection: [_CreateTrades](../trades/create-trades.md) for each distinct key of its rows, [_CreateQuoteTemplate](../quoting/quote-template.md) for its one. Preparation, evaluation and the quote functions look nothing up.

| Key | Means |
|---|---|
| `NYFED` | the collection's calendar of that name, taken as it is, by reference |
| `NYFED+LON` | the calendar closed on every day either is closed, the union [_CombineHolidayCalendars](combine-holiday-calendars.md) makes |
| `LON+NYFED` | the same calendar: the order of the names does not matter |

The step is one for every caller, `payment_calendar` in `src/catalyst/index_definitions/payment_calendars.py`. The key's own form is read first, by `calendar_key`, which a [trade template](../trades/trade-template.md) also reads its key by. Then each name is looked up exactly, case and all, with nothing trimmed or guessed, no fallback and no choice made for a collection of one. A key of several names is combined once for each distinct set of names in a batch, so `NYFED+LON` on two thousand rows, or beside `LON+NYFED`, is one calendar.

| Rule | Refused as |
|---|---|
| No name is missing | `payment_calendar_key row 1 is 'PAY_A+', expected a calendar's name, or several joined by '+'; a name is missing` |
| No name has whitespace around it | `payment_calendar_key is 'NYFED + LON', expected a calendar's name, or several joined by '+', each with no whitespace around it` |
| Each name once, since a name twice says nothing | `payment_calendar_key is 'NYFED+NYFED', expected a calendar's name, or several joined by '+', each once; 'NYFED' is given twice` |
| Every name is a calendar of the collection | `payment_calendar_key row 2 is 'PAY_A+PAY_C', expected names of the collection's calendars, 'PAY_A' and 'PAY_B'; it holds no 'PAY_C'` |
| A key has a collection to select from | `payment_calendars is missing, expected a _CollectPaymentCalendars collection, which a financially settled batch selects its payment calendar from`; from a quote template, `which payment_calendar_key selects its payment calendar from` |

A key the ticket supplies is named with its row, the first row holding that text; a template's key is named alone.

The calendar is what a payment rule's business days are counted on, Monday to Friday less its holidays. It never stops a payment falling on a holiday: a row that pays on a stated date pays on that date as entered, and its key is still required and still looked up, though the calendar is read for nothing.

## Work

`calendars_collected`, one per calendar given. A refusal counts nothing. `tests/performance/test_payment_calendar_budgets.py` pins the calls, which grow with the handles alone and run no numpy, and the peak, which follows the calendars and nothing of their days.

Binding counts `payment_keys_bound`, one per distinct key text a batch or a quote template binds, however many rows hold it. A key of several names adds the combination's own counts, `calendars_combined`, `holidays_read` and `holidays_kept`, once per distinct set of names.

## Not here

- Cleaning a key: no trimming, no case folding. Keys are cleaned to one format in the sheet.
- A second name for one calendar. A calendar wanted under two names is made twice.
- A name on a combination.
- Rolling a stated payment date onto a business day.
