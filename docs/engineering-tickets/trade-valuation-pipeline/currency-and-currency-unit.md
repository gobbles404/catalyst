# A result's currency and the unit of it

**Status:** Built in two pull requests, #265 and, stacked on it, #NNN, agreed with the owner
on 21 November 2026 for
[issue #263](https://github.com/gobbles404/catalyst/issues/263), this page in the first
commit of each. #265: a result carries two facts where one word stood for both, its currency
and the unit of that currency its amounts are in. #NNN: the dollar's unit is spelled `DOLLAR`,
where it was spelled `USD` as the currency is. No number moves in either.
[unit-conversions.md](../../library/globals/unit-conversions.md),
[index-conventions.md](../../library/index-definitions/index-conventions.md),
[report-values.md](../../library/trades/report-values.md),
[report-reserves.md](../../library/trades/report-reserves.md),
[report-risk.md](../../library/trades/report-risk.md),
[aggregate-results.md](../../library/trades/aggregate-results.md),
[evaluate-cashflows.md](../../library/cashflows/evaluate-cashflows.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the owners they update.

## The issue

The desk reads `USD` as a currency. The library also used it as a unit, the whole dollar
beside `CENT`, so a field that asks for a unit took a word that reads as a currency. Worse,
a result's `currency` was not a currency at all: it was the unit its index settles in, `USD`
or `CENT`. An index settled in cents showed `CENT` under `currency`, and its DV01 stood
under `SOFR CENT dv01 [CENT per basis point]`, which calls the cent a currency.

## The two words

| Word | What it is | Where it is typed |
|---|---|---|
| `USD` | The currency: which money | A cashflow's `currency` |
| `DOLLAR`, `CENT` | The units of that currency: the scale a price or an amount is in. 1 `DOLLAR` is 100 `CENT`. | `quote_currency_unit` and `currency_unit` of `_CreateIndexConventions`, and a `float_float`'s `spread_price_currency_unit` |

So 1.05 `DOLLAR` per `GAL` and 105 `CENT` per `GAL` are the same price.

## The two facts on a result

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
| dollars | 95 | `USD` | `DOLLAR` |
| cents | 9,500 | `USD` | `CENT` |

## What shows

| Surface | Before | After #265 | After #NNN |
|---|---|---|---|
| DV01 heading, settled in dollars | `SOFR USD dv01 [USD per basis point]` | the same | `SOFR USD dv01 [DOLLAR per basis point]` |
| DV01 heading, settled in cents | `SOFR CENT dv01 [CENT per basis point]` | `SOFR USD dv01 [CENT per basis point]` | the same |
| DV01 heading, no curve | `cleared USD dv01 [USD per basis point]` | the same | `cleared USD dv01 [DOLLAR per basis point]` |
| `currency` column of a result | `USD` or `CENT` | `USD` | `USD` |
| `currency_unit` column of a result | none | `USD` or `CENT`, the last column | `DOLLAR` or `CENT` |
| A refusal naming an amount's unit | `expected a finite amount of USD` | the same | `expected a finite amount of DOLLAR` |
| `sensitivity_unit` of a readback | `USD per USD/MMBTU` | the same | `DOLLAR per DOLLAR/MMBTU` |
| `price_unit` of a readback, a quote's unit | `USD/MMBTU`, `USD per BBL` | the same | `DOLLAR/MMBTU`, `DOLLAR per BBL` |
| The conventions' readback | `USD` | the same | `DOLLAR` |
| A cashflow's `currency` and its handle | `USD`, `cashflows:USD:3` | the same | the same |

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
| No alias | `USD` is retired as a unit and kept as the currency. A stale sheet fails by name. |
| Order | Two pull requests: the two facts apart first, the rename second. Renaming first would label a trade's results `DOLLAR` while a cashflow's stayed `USD`, and their DV01 on one curve would split for the length of a pull request. |

## What every existing sheet changes

**After #265**, nothing a sheet already reads moves or changes for an index settled in
dollars. Each spill named above is one column wider, so the cell to its right must be free:
a spill that meets an occupied cell shows `#SPILL!` until the neighbour is moved. A formula
that reads a readback by a column's place from the left reads what it read. A formula that
counts from the last column, `TAKE` with a negative count say, reads one column further on.
A sheet with an index settled in cents sees two cells change: the `currency` of its results
reads `USD` where it read `CENT`, and its DV01 heading reads
`SOFR USD dv01 [CENT per basis point]`.

**After #NNN**, every sheet makes these edits, and each fails by name until it is made:

| Where | Was | Is |
|---|---|---|
| `_CreateIndexConventions`, the first argument, the unit a price is quoted in | `USD` | `DOLLAR` |
| `_CreateIndexConventions`, the third argument, the unit the index settles in | `USD` | `DOLLAR` |
| A `float_float` template's or ticket's `spread_price_currency_unit` | `USD` | `DOLLAR` |

`CENT` stays `CENT`, and a cashflow's `currency` stays `USD`. A formula that looks for a
unit's text, a heading in brackets or a `sensitivity_unit` say, looks for `DOLLAR`.

## The refusals

No sentence is reworded in either pull request.

| Refused | In the words |
|---|---|
| `USD` where the unit a price is quoted in goes | `quote_currency_unit is 'USD', expected DOLLAR or CENT` |
| `USD` where the unit the index settles in goes | `currency_unit is 'USD', expected DOLLAR or CENT` |
| `USD` as a spread price's unit | `spread_price_currency_unit is 'USD', expected DOLLAR or CENT` |
| `DOLLAR` as a cashflow's currency | `currency is 'DOLLAR', expected USD, the one currency this version books` |
| An amount past the largest number | `... expected a finite amount of DOLLAR; ...`, and `of CENT` on an index settled in cents |
| A collection's DV01 past the largest number, on an index settled in cents | `the DV01 of SOFR USD on 2028-01-04 is inf, expected a finite amount of CENT per basis point; ...`, where it began `the DV01 of SOFR CENT` |

## Acceptance

- `DOLLAR` and `CENT` are the unit codes of the three unit fields; `USD` in any of them is
  refused by the sentence that lists the codes, and a test pins each.
- `USD` remains a cashflow's `currency`, and `DOLLAR` there is refused.
- A price quoted in cents and one quoted in dollars give the same economics when settled in
  the same unit: a lot is one lot in every quote and settlement unit.
- A result settled in cents shows `USD` under `currency` and `CENT` under `currency_unit`,
  on both reports and the readback, and its DV01 under
  `SOFR USD dv01 [CENT per basis point]`.
- A trade settled in dollars and a cashflow on one curve collect into one DV01 column,
  `SOFR USD dv01 [DOLLAR per basis point]`; a trade settled in cents on the same curve is a
  second column, in either order of collection.
- A cashflow's unit follows the unit tables: under tables that spell the dollar another way
  the same ticket books in that spelling, and its heading and its refusals say so.
- No mark, cash, reserve or risk number moves, and no existing column moves.
- The counters, the function ledgers and the numpy ledgers are as they were in both pull
  requests. In #265 the reports and readbacks that gain the column allocate a word more a
  row, measured and stated there.

## Engineering boundaries and delivery

#265, on #264: `currency_unit` beside `currency` on the trades' results and reserves, the
cashflows and their results, each rate contribution and each rate group; the heading's one
spelling, `dv01_label`, taking both; the collector's key the curve, the currency and the
unit; the booking of cashflows taking the unit tables, as the booking of trades does; the
new column on the two reports and the three readbacks. Inside the library every local that
held the settlement unit under the name `currency` is renamed `currency_unit`, so that the
name `currency` holds a currency wherever it stands.

#NNN, on #265: the unit tables' group `USD` keeps its name and takes `DOLLAR` as its base
unit beside `CENT`, three lines of the tables; the help of the two unit arguments and the
choices of `spread_price_currency_unit`; the two reserve fields' descriptions, which say
the unit the index settles in where they said its currency. Everything else is the cut-over
of callers: the tests, the host's facts, the smoke, the lifetime checks, the owning pages
and the kept workbook. Each `USD` was sorted by hand into the currency, which stays, and
the unit, which is renamed, and a unit phrase such as `USD per USD/BBL` changes in both
places.

## Outside this ticket

FX conversion, a second currency, any change to curve selection, a wider redesign of the
reports, and fractional quantities, issue #262. The earlier ticket pages, the dated notes
of the kept workbook and the chronology describe the unit as it was spelled when they were
written.
