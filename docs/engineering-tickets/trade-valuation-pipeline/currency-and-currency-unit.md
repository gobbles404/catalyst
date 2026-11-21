# A result's currency and the unit of it

**Status:** The first of two pull requests, built in #NNN, stacked on #264, agreed with the
owner on 21 November 2026 for
[issue #263](https://github.com/gobbles404/catalyst/issues/263), this page in its first
commit. A result carries two facts where one word stood for both: its currency, and the unit
of that currency its amounts are in. No unit code is renamed here, and no number moves. The
second pull request, stacked on this one, renames the unit code `USD` to `DOLLAR`.
[report-values.md](../../library/trades/report-values.md),
[report-reserves.md](../../library/trades/report-reserves.md),
[report-risk.md](../../library/trades/report-risk.md),
[aggregate-results.md](../../library/trades/aggregate-results.md),
[evaluate-cashflows.md](../../library/cashflows/evaluate-cashflows.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the owners it updates.

## The issue

The desk reads `USD` as a currency. The library also used it as a unit, the whole dollar
beside `CENT`, so a field that asks for a unit took a word that reads as a currency. Worse,
a result's `currency` was not a currency at all: it was the unit its index settles in, `USD`
or `CENT`. An index settled in cents showed `CENT` under `currency`, and its DV01 stood
under `SOFR CENT dv01 [CENT per basis point]`, which calls the cent a currency.

## The two facts

| Fact | What it is | A trade's | A cashflow's |
|---|---|---|---|
| Currency | Which money: `USD` | The group of money units its index's settlement unit belongs to in the unit tables | The `currency` its row enters |
| Currency unit | The scale an amount is in | The unit its index settles in, the conventions' `currency_unit` | Its currency's base unit in the unit tables: whole dollars, never cents |

The unit tables own both words. The currency is the name of the tables' group of money
units, and a cashflow's unit is read from that group by the currency's name, so neither is
typed a second time.

A small example. Ten barrels bought at 70 and quoted at 80, paid a year out at a discount
factor of 0.95:

| The index settles in | Mark | `currency` | `currency_unit` |
|---|---:|---|---|
| dollars | 95 | `USD` | `USD` here, `DOLLAR` after the second pull request |
| cents | 9,500 | `USD` | `CENT` |

## What shows

| Surface | Before | This pull request | After the rename |
|---|---|---|---|
| DV01 heading, settled in dollars | `SOFR USD dv01 [USD per basis point]` | the same | `SOFR USD dv01 [DOLLAR per basis point]` |
| DV01 heading, settled in cents | `SOFR CENT dv01 [CENT per basis point]` | `SOFR USD dv01 [CENT per basis point]` | the same |
| DV01 heading, no curve | `cleared USD dv01 [USD per basis point]` | the same | `cleared USD dv01 [DOLLAR per basis point]` |
| `currency` column of a result | `USD` or `CENT` | `USD` | `USD` |
| `currency_unit` column of a result | none | `USD` or `CENT`, the last column | `DOLLAR` or `CENT` |
| A refusal naming an amount's unit | `expected a finite amount of USD` | the same | `expected a finite amount of DOLLAR` |

The new column is appended to:

- `_ReportValues` and `_ReportReserves`;
- `util_ReadHandle` on a batch of trades' results, once on the first row as the reserves'
  `currency` is, and a dash below;
- `util_ReadHandle` on a batch of cashflows' results, on every row as the `currency` is;
- `util_ReadHandle` on a collection, on every row.

The readback of booked cashflows shows the fields as entered and gains nothing.

## Decisions of 21 November 2026

| Decision | Agreed |
|---|---|
| Two facts | A result keeps its settlement unit under its true name, `currency_unit`, and its `currency` is the money that unit belongs to. The alternative, one word, the unit, everywhere, was set aside: `DOLLAR` alone would not say which currency once a second one arrives. |
| Grouping | DV01 is grouped by curve and currency unit, which is the grouping it had under its true name. Nothing merges and nothing splits. |
| A trade and a cashflow | A trade settled in dollars and a cashflow on the same curve share a DV01 column, since a cashflow's unit is the whole dollar. |
| Cents | A result settled in cents on the same curve is a column of its own beside the dollar column, told apart by the unit in the brackets, and is never added to it. |
| The new column | `currency_unit`, always last, so that no column a sheet already reads moves. |
| The refusals | Each keeps its sentence. A sentence that names an amount's unit takes the unit's code; a sentence that names a DV01 group names it as the heading does, the curve and the currency. |
| Names | `quote_currency_unit`, `currency_unit` and `spread_price_currency_unit` keep their names, which already say unit. A cashflow's `currency` and the handles named for it stay `USD`. |
| Order | Two pull requests: the two facts apart first, the rename second. Renaming first would label a trade's results `DOLLAR` while a cashflow's stayed `USD`, and their DV01 on one curve would split for the length of a pull request. |

## What every existing sheet changes

Nothing a sheet already reads moves or changes for an index settled in dollars. Each spill
named above is one column wider, so the cell to its right must be free: a spill that meets
an occupied cell shows `#SPILL!` until the neighbour is moved. A formula that reads a
readback by a column's place from the left reads what it read. A formula that counts from
the last column, `TAKE` with a negative count say, reads one column further on.

A sheet with an index settled in cents sees two cells change: the `currency` of its results
reads `USD` where it read `CENT`, and its DV01 heading reads
`SOFR USD dv01 [CENT per basis point]`. Its numbers are as they were, still in cents, and
`currency_unit` says so.

## The refusals

No sentence is reworded. In this pull request each reads as it did for an index settled in
dollars. For an index settled in cents, a sentence naming a DV01 group now names the
currency where it named the unit:

| Refused | Before | Now |
|---|---|---|
| A cent-settled collection's DV01 past the largest number | `the DV01 of SOFR CENT on 2028-01-04 is inf, expected a finite amount of CENT per basis point; ...` | `the DV01 of SOFR USD on 2028-01-04 is inf, expected a finite amount of CENT per basis point; ...` |

## Acceptance

- A result settled in dollars reads as it did in every existing cell, with `USD` in the new
  last column.
- A result settled in cents shows `USD` under `currency` and `CENT` under `currency_unit`,
  on both reports and the readback, and its DV01 under
  `SOFR USD dv01 [CENT per basis point]`.
- A trade settled in dollars and a cashflow on one curve collect into one DV01 column; a
  trade settled in cents on the same curve is a second column, in either order of
  collection.
- A cashflow's unit follows the unit tables: under tables that spell the dollar `DOLLAR`
  the same ticket books in `DOLLAR`, and its heading and its refusals say so.
- No mark, cash, reserve or risk number moves, and no existing column moves.
- The counters, the function ledgers and the numpy ledgers are as they were. The reports
  and readbacks that gain the column allocate a word more a row, measured and stated in the
  pull request.

## Engineering boundaries and delivery

This pull request, on #264: `currency_unit` beside `currency` on the trades' results and
reserves, the cashflows and their results, each rate contribution and each rate group; the
heading's one spelling, `dv01_label`, taking both; the collector's key the curve, the
currency and the unit; the booking of cashflows taking the unit tables, as the booking of
trades does; the new column on the two reports and the three readbacks; then the tests, the
host's facts, the smoke, the kept workbook, the owning pages, a history row and a UAT item.
Inside the library every local that held the settlement unit under the name `currency` is
renamed `currency_unit`, so that the name `currency` holds a currency wherever it stands.

The second pull request, on this one: the unit tables' dollar spelled `DOLLAR`, the three
unit inputs, every unit label, the help, the refusals, the owning pages, the tests, the
tools and the kept workbook. No alias: `USD` under a unit field is refused by the existing
sentence, which lists the codes.

## Outside this ticket

FX conversion, a second currency, any change to curve selection, a wider redesign of the
reports, and fractional quantities, issue #262. The earlier ticket pages describe the
headings and columns as they were when they were built.
