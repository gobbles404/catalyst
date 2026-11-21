# A payment calendar is chosen by key

**Status:** Built in two pull requests, #268 and #NNN, agreed with the owner on 21 November
2026 for [issue #255](https://github.com/gobbles404/catalyst/issues/255). The first is on
`feat/payment-calendar-names`, stacked on `feat/fractional-quantities`, the branch of
[fractional-quantities.md](fractional-quantities.md), #267; the second, the cutover of the
field, on `feat/payment-calendar-keys`, stacked on the first. It follows
[multiple-discount-curves.md](multiple-discount-curves.md), #201 to #203, which chose a discount
curve by name, and [combine-holiday-calendars.md](combine-holiday-calendars.md), #183.
[holiday-calendar.md](../../library/index-definitions/holiday-calendar.md) and
[collect-payment-calendars.md](../../library/index-definitions/collect-payment-calendars.md) own
the name, the collection and the key.

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
| 1 | The name and the collection: the optional name on `_CreateHolidayCalendar`, `_CollectPaymentCalendars`, their readbacks. No field changes and nothing reads a collection yet. | #268 |
| 2 | The cutover, trades and quotes together: `payment_calendar_key` replaces `payment_holiday_calendar`; the key's rule and its binding in `_CreateTrades` and `_CreateQuoteTemplate`; the holiday-calendar field type deleted. | #NNN |

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

## The second pull request

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

```text
_CreateTrades(indexes, fields, trade_rows, template, [payment_calendars]) -> handle
_CreateQuoteTemplate(instrument, fields, values, [payment_calendars]) -> handle
```

**The field.** `payment_calendar_key`, text, stands where `payment_holiday_calendar` stood in
the `fixed_float` and the `float_float`: required with a financial settlement, refused with a
physical one, and a field a quote template may hold. No field of any instrument takes a handle
now, so the holiday-calendar field type, the seam's column of handle texts and their readers
are deleted.

**A batch.** A trade template supplies the key for the batch, or the ticket a key on each row.
`_CreateTrades` binds each distinct key once, in the order its first row comes, and holds the
calendars by reference; preparation and evaluation look nothing up. Keys naming one set of
calendars share one calendar, and a combination is made once per set of names, so `NYFED+LON`
on two thousand rows is one calendar. Every financially settled row binds its key, a row paying
on a stated date included. Each row's key is kept as entered and read back as the batch's last
column, so no column a sheet already reads has moved. A physical batch names no collection.

**A quote template.** `_CreateQuoteTemplate` binds the key its row holds and holds the
calendar, which serves the direct quotes and `_CreateRFQ` with no calendar argument on any
pricing function. A template that holds no key needs no collection.

**A trade template** is given no collection: it reads the key's form and keeps the text. So a
changed calendar remakes its collection and every batch and quote template that names the
collection, and leaves a trade template as it is.

Payment semantics do not change: the anchors, the offsets, a stated date used as entered and
never rolled, and the payment groups all stand. Every batch on the kept workbook pays on the
day it paid.

The hand-worked example, each trade's last observation Wednesday 25 November 2026 and its
`payment_day` `+2bd`, on `PAY_A`, closed 26 November, and `PAY_B`, closed 27 and 30 November:

| `payment_calendar_key` | Business days counted | `payment_date` |
|---|---|---|
| `PAY_A` | Friday 27, Monday 30 | 30 November 2026 |
| `PAY_B` | Thursday 26, Tuesday 1 | 1 December 2026 |
| `PAY_A+PAY_B` | Tuesday 1, Wednesday 2 | 2 December 2026 |

| What | Words |
|---|---|
| A name missing | `payment_calendar_key row 1 is 'PAY_A+', expected a calendar's name, or several joined by '+'; a name is missing` |
| A name with whitespace around it | `payment_calendar_key row 1 is 'NYFED + LON', expected a calendar's name, or several joined by '+', each with no whitespace around it` |
| A name twice | `payment_calendar_key row 1 is 'NYFED+NYFED', expected a calendar's name, or several joined by '+', each once; 'NYFED' is given twice` |
| A name the collection lacks | `payment_calendar_key row 2 is 'PAY_A+PAY_C', expected names of the collection's calendars, 'PAY_A' and 'PAY_B'; it holds no 'PAY_C'` |
| A financial batch given no collection | `payment_calendars is missing, expected a _CollectPaymentCalendars collection, which a financially settled batch selects its payment calendar from` |
| A quote template holding a key and given no collection | `payment_calendars is missing, expected a _CollectPaymentCalendars collection, which payment_calendar_key selects its payment calendar from` |
| A financial row with no key | `payment_calendar_key is missing, expected it when settlement_method = financial` |
| A key on a physical batch | `payment_calendar_key is 'NYFED', expected none unless settlement_method = financial` |
| A blank key cell, a number for a key | the seam's, by the cell: `trade_rows cell (1, 6) is blank, expected text` |

A key the ticket supplies is named with its row, the first that holds that text; a template's
key is named alone.

### What a sheet changes

A sheet made before this pull request fails by name until it changes four things:

1. Name each payment calendar where it is made: `=_CreateHolidayCalendar(B2:B9, "NYFED")`.
2. Collect them, once: `=_CollectPaymentCalendars(D2:D4)`.
3. Rename the header `payment_holiday_calendar` to `payment_calendar_key`, and type the
   calendar's name where its cell was referred to.
4. Give `_CreateTrades` and `_CreateQuoteTemplate` the collection's cell as their last argument.

A `_CombineHolidayCalendars` cell made for a payment calendar is no longer needed: its key is
the names joined by `+`.

### Ownership

| Fact | Owner |
|---|---|
| The field | `payment_calendar_key` in `instruments/definitions.py` |
| The key's form | `calendar_key` in `index_definitions/payment_calendars.py`, the field's reader in `trades/template.py` |
| The binding, and its refusals | `payment_calendar` and `no_collection` in the same module, called by `_the_calendars` in `trades/resolution.py` and by `quote_template` in `quoting/template.py`; [collect-payment-calendars.md](../../library/index-definitions/collect-payment-calendars.md#binding-a-key) is the page |
| The key kept to show | `ResolvedTrades.payment_calendar_key` in `trades/terms.py`, read back last by `trades_table` in `excel/utilities.py` |

### Also pin

- The work: `payment_keys_bound`, one per distinct key text a batch or a quote template binds;
  a key of several names adds one combination per distinct set of names. Binding one key adds a
  fixed number of calls to a batch's resolution, the same at five rows and at two thousand.
- Rows that share a calendar are counted together, as rows that shared a handle were.
- A key is no payment group: two keys that pay on one day are one group.
- A collection of no calendars, which the library can make and the sheet cannot, says `none`
  in the refusal's list of names.

## Outside this ticket

- Case folding, trimming or any other cleaning of a key by the library.
- A second name for one calendar. A calendar wanted under two names is made twice.
- A name on a combined calendar.
- Relaxing the key on a row that pays on a stated date.
- Index pricing and observation calendars, holiday sourcing, settlement conventions, rolling a
  stated date, names unique beyond one collection, and new instruments.
