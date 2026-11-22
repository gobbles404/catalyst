# Every holiday calendar is named and chosen by key

**Status:** Built in #NNN, agreed with the owner on 21 November 2026 from their acceptance
testing of #268 and #269, one pull request on `feat/holiday-keys`, stacked on
`feat/payment-calendar-keys`, the branch of [payment-calendar-keys.md](payment-calendar-keys.md),
#269. [holiday-calendar.md](../../library/index-definitions/holiday-calendar.md) and
[collect-holiday-calendars.md](../../library/index-definitions/collect-holiday-calendars.md) own
the name, the collection and the key.

## The issue

#269 chose a payment calendar by key, so a calendar closed when either of two centres is closed
became the text `NYFED+LON`. An index's own calendar and `util_ShiftDate`'s still took a handle,
so the same calendar for them was still a `_CombineHolidayCalendars` cell. The owner, moving
their workbook onto the stack, found two ways to say one thing, and three smaller things beside
it:

- A calendar's name came second and was optional, where a curve's and an index's come first.
- The instrument's field read `payment_calendar_key`, where the desk says holiday.
- The collection was called payment calendars, which an index's calendar is not.

## Decisions of 21 November 2026

| Decision | Agreed |
|---|---|
| A calendar's name comes first and is required | `_CreateHolidayCalendar(name, holiday)`. Every calendar has a name, an index's own included. |
| The instrument's field | `payment_holiday_key`, where it read `payment_calendar_key`. |
| An index and a date shift choose their calendar by key | `holiday_key` on `_CreateIndex` and `util_ShiftDate`, one name or several joined by `+`, the rule the payment key already has. |
| `_CombineHolidayCalendars` | Removed. A key of several names is the one way to say a union. |
| The collection says holiday calendars | `_CollectHolidayCalendars`, and the argument `holiday_calendars` on the four functions that select from it. |
| Where the collection goes | Last, as on `_CreateTrades`. On `_CreateIndex` the key stands where the handle stood and no argument moves. |

## The functions

```text
_CreateHolidayCalendar(name, holiday) -> handle
_CollectHolidayCalendars(calendar_handles) -> handle
_CreateIndex(name, display_name, schedule, index_conventions, contract_specifications,
             [holiday_key], [reporting_lot], [holiday_calendars]) -> handle
util_ShiftDate(date, offset, [holiday_key], [holiday_calendars]) -> date
_CreateTrades(indexes, fields, trade_rows, template, [holiday_calendars]) -> handle
_CreateQuoteTemplate(instrument, fields, values, [holiday_calendars]) -> handle
```

**The name.** Required and first. Its rule is unchanged: the curve name's rule, and no `+`,
which joins names in a key. Every calendar's handle shows it, `30512:holiday_calendar:NYFED:8`,
and every calendar's readback repeats it beside each day.

**The collection.** As it was under its new name: calendars held by reference, each name once.
The refusal of a member with no name is gone, since no calendar is without one.

**The key.** One rule and one binding step for every reader: a name of the collection, or
several joined by `+`, matched exactly. `NYFED+LON` is the calendar closed on every day either
is closed, and `LON+NYFED` is the same calendar. A reader that holds a key must be given the
collection. A collection given where no key selects from it is read for nothing, as on a
physically settled batch.

| Reader | Its key | Bound |
|---|---|---|
| A batch of trades | `payment_holiday_key`, each row's | once per distinct key, when the batch is made |
| A quote template | `payment_holiday_key`, its one | when the template is made |
| An index | `holiday_key` | when the index is made |
| `util_ShiftDate` | `holiday_key` | on each call |

**The index.** A futures index requires `holiday_key` and an IFERC or a Gas Daily index
refuses one, the rule the handle had. The index holds the calendar the key selected and nothing
later looks a name up.

**The date shift.** `holiday_key` left out is Monday to Friday with no holidays, as the handle
left out was. The offset is read before the key.

The hand-worked example, on `NYFED`, closed Thursday 26 November 2026, and `LON`, closed Friday
27 and Monday 30 November, one business day on from Wednesday 25 November:

| `holiday_key` | `util_ShiftDate(DATE(2026,11,25), "+1bd", key, collection)` |
|---|---|
| left out | Thursday 26 November 2026 |
| `NYFED` | Friday 27 November 2026 |
| `LON` | Thursday 26 November 2026 |
| `NYFED+LON` | Tuesday 1 December 2026 |
| `LON+NYFED` | Tuesday 1 December 2026 |

No trade, quote, payment day or price moves: every index prices on the days it priced on and
every batch pays on the day it paid.

| What | Words |
|---|---|
| A calendar made with no name | the seam's: `name is missing, expected text` |
| A futures index with no key | `holiday_key is missing, expected a holiday calendar's key with a futures schedule` |
| A key on an IFERC or a Gas Daily index | `holiday_key is 'NYMEX', expected none with an IFERC schedule` |
| A key with no collection | `holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which holiday_key selects a calendar from` |
| A financial batch given no collection | `holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which a financially settled batch selects a calendar from` |
| A name the collection lacks | `holiday_key is 'NYMX', expected names of the collection's calendars, 'NYMEX' and 'ICE'; it holds no 'NYMX'` |
| A key's form | as #269 worded them, under the reader's own word: `payment_holiday_key row 1 is 'NYFED + LON', expected a calendar's name, or several joined by '+', each with no whitespace around it` |
| A calendar's handle where a key is expected | the seam's: text is expected, and a handle is text, so it is read as a name the collection lacks |

## What a sheet changes

A sheet made on #269 fails by name until it changes six things:

1. Put each calendar's name first: `=_CreateHolidayCalendar("NYFED", B2:B9)`. A calendar that
   had no name, an index's own, gets one.
2. Rename `_CollectPaymentCalendars` to `_CollectHolidayCalendars`, and add to its range every
   calendar an index or a date shift uses.
3. Rename the header `payment_calendar_key` to `payment_holiday_key`.
4. On each futures `_CreateIndex`, type the calendar's name where its handle's cell was referred
   to, and add the collection's cell as the last argument.
5. On each `util_ShiftDate` that named a calendar, do the same.
6. Delete each `_CombineHolidayCalendars` cell, and type its calendars' names joined by `+`
   where it was referred to.

## Ownership

| Fact | Owner |
|---|---|
| A calendar's name and its rule | `HolidayCalendar.name` and `calendar_name` in `index_definitions/holiday_calendar.py` |
| The union of calendars | `combine_holiday_calendars` in the same module, called by the binding step alone |
| The collection, the key's form, the binding and its refusals | `HolidayCalendars`, `collect_holiday_calendars`, `calendar_key`, `keyed_calendar`, `calendar_of` and `no_collection` in `index_definitions/holiday_calendars.py`; [collect-holiday-calendars.md](../../library/index-definitions/collect-holiday-calendars.md#binding-a-key) is the page |
| Which index takes a key | `index` in `index_definitions/index.py` |
| The date shift's key | `shift_date` in `index_definitions/date_offsets.py` |
| The field | `payment_holiday_key` in `instruments/definitions.py` |

## Also pin

- The union a key makes is named by its names in sorted order joined by `+`, `LON+NYFED`, so no
  calendar is without a name. The sheet cannot make one under a name of its own.
- The work: `holiday_keys_bound`, where it read `payment_keys_bound`, one per distinct key text
  a batch binds and one for a quote template, an index or a date shift that holds a key. A key
  of several names adds the union's own counts on each binding, so a date shift on `NYFED+LON`
  combines on every call, where a `_CombineHolidayCalendars` cell combined once.
- An index's readback still says whether it has a calendar, `has_holiday_calendar`, and nothing
  of the key.

## Outside this ticket

- A short name for a union, `USUK` for `NYFED+LON`. A calendar wanted under one name is made
  over its days.
- Keeping a union between calls of the date shift.
- Case folding, trimming or any other cleaning of a key by the library.
- The key on the index's readback.
