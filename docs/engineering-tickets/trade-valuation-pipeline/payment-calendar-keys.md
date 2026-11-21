# A payment calendar is chosen by key

**Status:** The first of two pull requests built in #NNN, agreed with the owner on 21 November
2026 for [issue #255](https://github.com/gobbles404/catalyst/issues/255), this page in its first
commit; on `feat/payment-calendar-names`, stacked on `feat/fractional-quantities`, the branch of
[fractional-quantities.md](fractional-quantities.md), #267. The second pull request, the cutover
of the field, is stacked on the first. It follows
[multiple-discount-curves.md](multiple-discount-curves.md), #201 to #203, which chose a discount
curve by name, and [combine-holiday-calendars.md](combine-holiday-calendars.md), #183.
[holiday-calendar.md](../../library/index-definitions/holiday-calendar.md) and
[collect-payment-calendars.md](../../library/index-definitions/collect-payment-calendars.md) own
the name and the collection.

## The issue

Trades in one batch pay on different holiday calendars, and the trading system of record, the
CTRM, supplies each trade's calendar as a text name. One calendar on the template for the whole
batch worked for energy. With metals, counterparties bring a mix of preferred holiday schedules,
often two centres together.

A ticket column of `payment_holiday_calendar` already gives each row its own calendar, but each
cell must hold a calendar handle, text that changes every session, so a row pulled from the CTRM
cannot be used as it arrives. `payment_holiday_calendar` is the only field of any instrument that
takes a handle.

So the payment calendar is chosen by name, as a discount curve is: `payment_calendar_key` holds
`NYFED`, `LON` or `NYFED+LON`.

## Decisions of 21 November 2026

| Decision | Agreed |
|---|---|
| A key is one calendar name, or several joined by `+` | `NYFED+LON` is the calendar closed on every day either is closed, the union `_CombineHolidayCalendars` makes, built when the batch or the quote template is made. The order of the names does not matter, and no combination needs a row of its own anywhere. |
| A calendar carries its name from its creator, as a curve does | `_CreateHolidayCalendar` takes an optional name; the collection takes handles alone. |
| Names are matched exactly, case and all | The rule of `discount_curve_key`: no trimming, no case folding, no fallback, no implicit choice from a collection of one. Keys are cleaned to one format in the sheet. |
| Every financially settled row has a key, and every key names calendars the collection holds | A row that pays on a stated date included. A blank is refused and a name the collection lacks is refused. The calendar is what a rule's business days are counted on; it never stops a payment falling on a holiday, and a stated date is used as entered. |

## The two pull requests

| | What | State |
|---|---|---|
| 1 | The name and the collection: the optional name on `_CreateHolidayCalendar`, `_CollectPaymentCalendars`, their readbacks. No field changes and nothing reads a collection yet. | #NNN |
| 2 | The cutover, trades and quotes together: `payment_calendar_key` replaces `payment_holiday_calendar`; the key's rule and its binding in `_CreateTrades` and `_CreateQuoteTemplate`; the holiday-calendar field type deleted. | stacked on the first |

The field is one definition shared by trades and quotes, so it cannot change for one without
the other; that is why the second is one pull request and not two.

## The first pull request

```text
_CreateHolidayCalendar(holiday, [name]) -> handle
_CollectPaymentCalendars(calendar_handles) -> handle
```

**The name.** Optional, since an index's pricing calendar and a date utility's calendar need
none: left out, a calendar and every formula that makes one are as they were. Given, it follows
the curve name's rule, text with no whitespace around it and not whitespace alone, and holds no
`+`, which joins names in a key. It is kept as typed and shows in the handle,
`30512:holiday_calendar:NYFED:8`, and beside each day of the calendar's readback. A combination
from `_CombineHolidayCalendars` has no name.

**The collection.** Calendars held by reference, as the curve collection holds curves: nothing
combined, no day read. Every member has a name and each name once; the same calendar given twice
is a repeat too. Its readback is one row per calendar, the name and how many days it lists.

| What | Words |
|---|---|
| A name with whitespace around it | `name is ' NYFED', expected a name with no whitespace around it` |
| A name holding a plus sign | `name is 'NYFED+LON', expected a name without '+', which joins names in a key` |
| A member with no name | `calendar_handles cell 2 is a calendar with no name, expected one made with a name, the word a payment calendar key selects it by` |
| A name twice | `calendar_handles cell 1 and cell 3 are both named 'NYFED', expected each name once` |
| A number for a name, a blank or a wrong kind of handle among the members | the seam's, by the argument or the cell |

## Ownership

| Fact | Owner |
|---|---|
| A calendar's name and its rule | `HolidayCalendar.name` and `calendar_name` in `index_definitions/holiday_calendar.py`; the two text rules it shares with a curve's name are `curve_name`'s |
| The collection | `PaymentCalendars` and `collect_payment_calendars` in `index_definitions/payment_calendars.py` |
| The handle that shows a name | `_NAMED` and `_publish` in `excel/bridge.py`: a holiday calendar is the one kind whose objects may or may not carry a name |
| The readbacks | `holiday_calendar_table` and `payment_calendars_table` in `excel/utilities.py` |

## Also pin

- A calendar made without a name is unchanged in every way: its handle, its readback, its days.
- A name changes nothing of the days.
- The collection keeps the order given and the objects themselves.
- The work: `calendars_collected`, one per calendar given, nothing on a refusal; a name is one
  rule read once and nothing of the days; a collection runs no numpy whatever its calendars'
  lengths.
- The creator's second argument is optional, so a direct call states that the name is missing,
  as Excel does for a formula that leaves it out.

## The second pull request, as agreed

The key, each name looked up exactly:

| Key | Means |
|---|---|
| `NYFED` | the collection's calendar of that name, taken as it is |
| `NYFED+LON` | closed on every day either is closed |
| `LON+NYFED` | the same calendar |
| `NYFED+NYFED` | refused: a name twice says nothing |
| `NYFED+`, `+LON`, `NYFED++LON` | refused: a name is missing |
| `NYFED + LON` | refused: a name has whitespace around it |
| `nyfed` | refused, unless a calendar is named `nyfed` |

A trade template can supply the key for the batch, or the ticket a key on each row.
`_CreateTrades(indexes, fields, trade_rows, template, [payment_calendars])` binds each distinct
key once and holds the calendars by reference; preparation and evaluation look nothing up.
`_CreateQuoteTemplate(instrument, fields, values, [payment_calendars])` binds a supplied key and
holds the calendar, which serves the direct quotes and `_CreateRFQ` without a calendar argument
on any pricing function. Payment semantics do not change: the anchors, the offsets, a stated
date used as entered and never rolled, and the payment groups all stand.

The hand-worked example, each trade's last observation Wednesday 25 November 2026 and its
`payment_day` `+2bd`, on `PAY_A`, closed 26 November, and `PAY_B`, closed 27 and 30 November:

| `payment_calendar_key` | Business days counted | `payment_date` |
|---|---|---|
| `PAY_A` | Friday 27, Monday 30 | 30 November 2026 |
| `PAY_B` | Thursday 26, Tuesday 1 | 1 December 2026 |
| `PAY_A+PAY_B` | Tuesday 1, Wednesday 2 | 2 December 2026 |

## Outside this ticket

- Case folding, trimming or any other cleaning of a key by the library.
- A second name for one calendar. A calendar wanted under two names is made twice.
- A name on a combined calendar.
- Relaxing the key on a row that pays on a stated date.
- Index pricing and observation calendars, holiday sourcing, settlement conventions, rolling a
  stated date, names unique beyond one collection, and new instruments.
