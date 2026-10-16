# _ShowInstrument

Built in #137 as ticket I2 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), beside [_ListInstruments](list-instruments.md). The table below is written from the definitions by hand, and a test keeps the two equal, cell for cell; there is no generator. The instrument was named `future` until #174, when [rename-instrument-fixed-float.md](../../engineering-tickets/trade-valuation-pipeline/rename-instrument-fixed-float.md) renamed it `fixed_float`, its fields and rules unchanged. Two fields joined in #175, `counterparty` and `marketing_reserve`, [booking-fields-and-marketing-reserve.md](../../engineering-tickets/trade-valuation-pipeline/booking-fields-and-marketing-reserve.md), the first booking slice of the bilateral arc.

Shows one library-defined instrument schema with fields across columns and metadata down
rows, including descriptions, requirements and defined options. This is the read-only counterpart of
[_ListInstruments](list-instruments.md). Both use the same private library definitions that
`_CreateTradeTemplate` and `_CreateTrades` consume.

## Worksheet contract

```python
def _ShowInstrument(
    instrument: Annotated[str, "One instrument name from _ListInstruments, such as fixed_float."],
) -> MixedArray: ...
```

Excel formula:

```excel
=_ShowInstrument("fixed_float")
```

`instrument` is the exact catalog identifier as text, or a reference to its cell in the list.
No instrument handle, index, template or market argument is required. The seam checks the
declared text input and mixed-table output: [inputs](../../seam/inputs.md) and
[outputs](../../seam/outputs.md).

Fields run across columns to align with trade-table headers. The first column contains the
seven row labels `field`, `description`, `required`, `required_when`, `type`, `options`,
`rule`, in that order. Each subsequent column describes one field in the definition's
declared order. For N fields, the spill has seven rows and N + 1 columns. In the first row,
field identifiers begin in column two; those cells match the names used as trade headers.
The `required` row contains Excel booleans after its text label; all other cells are
nonempty text. There are no spacer rows, blank placeholders, object handles or additional
implementation-type row. This is the default layout; no transpose argument is introduced.

The `fixed_float` schema as the sheet sees it, `src/goosedove/instruments/definitions.py` laid out by
`src/goosedove/excel/instruments.py`. A template supplies defaults for
recognized trade fields; the selected traded product/agreement constrains the resolved values.
The index is not among the fields: `_CreateTrades(index, fields, trade_rows, template)` takes
it as its first argument, once for the whole batch.

| field | trade_id | trade_date | contract_code | start_date | end_date | schedule_method | route | settlement_method | clearing_house | counterparty | broker | quantity | quantity_unit | quantity_per | fixed_price | payment_time_lag | payment_holiday_calendar | marketing_reserve |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| description | External numeric identifier of the executed deal | Date the deal was executed | One monthly contract or a strip of monthly contracts, the row's period when it supplies no dates | First day of a booked period; with end_date it takes precedence over a code | Last day of a booked period, inclusive | How observations determine the floating price | The route the trade clears or settles by, cleared or bilateral | How the trade finally settles, by physical delivery or a financial payment | The clearing organization a cleared trade clears through | The counterparty to a bilateral trade | The broker named for the deal, or none for a screen trade | Signed size of the position, a count of the quantity unit | The desk's word for a quantity of the index, one of its contract specifications | Whether quantity is per month or per calendar day | The fixed price agreed when the deal was executed | Date offset from the payment anchor defined by the supported product, one instruction or a chain applied left to right | Calendar supplying holidays for payment-day counting | A marketing cost booked once with the trade |
| required | FALSE | TRUE | FALSE | FALSE | FALSE | TRUE | TRUE | TRUE | FALSE | FALSE | FALSE | TRUE | TRUE | TRUE | TRUE | FALSE | FALSE | FALSE |
| required_when | none | none | no start_date and end_date on the row | no contract_code on the row, or with end_date | no contract_code on the row, or with start_date | none | none | none | route = cleared | route = bilateral | none | none | none | none | none | settlement_method = financial | settlement_method = financial | none |
| type | number | date | text | date | date | code | code | code | text | text | text | number | text | code | number | text | holiday calendar handle | number |
| options | a whole number of at most 15 digits | no fixed list | a contract or strip, F26, 1Q27, 1H27, CAL27, Z27-X28 | no fixed list | no fixed list | asian, lastday, penultimate, last3day | cleared, bilateral | physical, financial | no fixed list | no fixed list | no fixed list | a signed whole count, zero included | the index's specification names | month, calday | no fixed list | +1bd, +3cd, +0em or a chain such as +3em+25cd-1bd+1bd, each a sign, a whole count and bd, cd or em | a _CreateHolidayCalendar handle | a finite amount of zero or more |
| rule | The source system's deal number, whole, -999999999999999 to 999999999999999, never text; duplicates keep separate occurrences | The day the deal was struck, never inferred from the valuation date or today | Typed in either case and resolved by month against the index's schedule when the row supplies no dates, every schedule code read; CAL27 is F27 through Z27, 1H27 F27 through M27, Z27-X28 December 2027 through November 2028; beside both dates it is kept as entered text and not read; a blank or empty cell is not supplied | With end_date the inclusive days the deal covers, split at month ends, whatever the row's code; one date without the other fails; a blank or empty cell is not supplied; util_StartDate gives it from a label | On or after start_date; the two dates book the row's period together, so one without the other fails; a blank or empty cell is not supplied; a part of a month prices under asian alone | A library rule selected by the trade; all four are built on a futures index, asian averaging the month's pricing days; lastday alone on an IFERC index, its published month | Decides the clearing reserve: a cleared trade incurs the selected specification's clearing rate and a bilateral one none; a cleared batch values undiscounted and takes no discount curve, a bilateral one is valued on the curve _EvaluateTrades requires | Selects behavior, validation and payment terms, not a label: a financial batch requires payment_time_lag and payment_holiday_calendar and pays on its payment day; a physical one pays on no day, takes lastday rows alone, is refused past its expiry and refused on the bilateral route; the delivery itself is outside the model | Identifies the organization, kept as typed: required with route = cleared and refused with bilateral; it selects no rate and exempts no fee, the route alone deciding the clearing reserve | A label kept as typed, each row its own; nothing is inferred from it, no netting, credit treatment or curve | A named broker enables the brokerage reserve for that trade at the selected specification's rate; omit the field, or enter none in any case, for no brokerage; a ticket column may mix names and none; the name selects no rate | A whole count of the selected quantity definition, positive, negative or zero; a zero row is kept, has no exposure and no quantity-based reserve, keeps a marketing reserve it entered and can be filled in later | Selects the lot size and unit from the index given to _CreateTrades, exactly as named there; the template may supply it, and the index owns what it means | The quantity per contract month, or per calendar day of it, weekends and holidays included | A finite number in the index's quote units; the same for every month of a strip | Applied in order from the component's anchor, business days on the payment calendar: on a futures index its last observation day, the expiry under lastday; on an IFERC index the month's last_trading_date; the final payment date must be strictly after the last observation date, publication for IFERC; +1bd for PHH, +3bd for Waha | Monday to Friday less its holidays; separate from the pricing calendar | In the index's settlement currency, counted once per ticket row whatever its months, quantity or days; left out of the template and the ticket, zero; static, never a contribution to value |

`fixed_float`, `future` until #174, is the one instrument defined: a fixed-for-floating position on a monthly contract or strip of a futures or, since #167, an IFERC index, built in
#139 through #144 as [create-trades.md](../trades/create-trades.md) and
[trade-template.md](../trades/trade-template.md) describe. The index is no field: it is the first
argument of `_CreateTrades`, once for the batch, and every other fact arrives as a template default
or a ticket column, each from one source, a field supplied by both refused even to the same value.

`quantity` is a signed whole count of `quantity_unit`, zero included since #146, a row kept
ready for a deal, no exposure and no quantity-based reserve but, since #175, any marketing reserve it
entered, and `quantity_unit` names one of the
index's contract specifications exactly as the index spells it, the desk's word for a quantity of
the index: `NYMEX NG` for the 10,000 MMBtu lot, `ICE PHH` for the 2,500 MMBtu lot, `MMBTU` where
the index defines a specification of that name with a size of one. Since #145 there is no separate
specification field and `LOT` has no meaning of its own; the Show cannot list an index's names,
since it takes no index, and `_CreateTrades` refuses a name the index does not spell,
`quantity_unit is 'ICE NG', expected one of the index's specifications: 'NYMEX NG'`. The
selected row's size and unit make the quote quantity, the index's conventions the coefficient,
and nothing later looks the name up again.

`contract_code` is one month or a monthly strip in the period grammar behind `util_StartDate`,
`Z26`, `z26`, `CAL27`, `Z27-X28`, resolved by month against the index's schedule when the row
supplies no dates, every code of the schedule read. Since #161 `start_date` and `end_date` are the
other period form, and since #172 the three stand together on one ticket, each row choosing,
[contract-codes-and-dates.md](../../engineering-tickets/trade-valuation-pipeline/contract-codes-and-dates.md): both dates book
the days between them, whatever code stands beside them, the code kept as entered text and not
read; neither books the code; a blank cell or a formula's `""` in the three supplies nothing, and
one date without the other is refused by its row. The dates are the first and the last day the
deal covers, split at month ends into components, a whole month by dates the code's own
components; a part of a month prices under `asian` alone, and [util_StartDate](../utilities/start-date.md) and
[util_EndDate](../utilities/end-date.md) give both days from a label, `BALZ26` with the valuation-date
handle since #173. `schedule_method` is `lastday`, `penultimate`, `last3day` or `asian`, the four
built on a futures index, any other word refused by name, and on an IFERC index since #167
`lastday` alone, the month's index on its publication day,
[iferc-basis-futures.md](../../engineering-tickets/trade-valuation-pipeline/iferc-basis-futures.md). `route` is `cleared` or `bilateral`: a cleared batch values undiscounted, takes no curve and
incurs the clearing reserve, a bilateral one is valued on the discount curve `_EvaluateTrades`
requires since #177 and incurs none, since #NN,
[reserve-fee-applicability.md](../../engineering-tickets/trade-valuation-pipeline/reserve-fee-applicability.md). `settlement_method` is
`physical`, which pays on no day and supplies no payment field, or `financial`, which requires
`payment_time_lag` and `payment_holiday_calendar`, the lag counted strictly after each
component's anchor on that calendar: on a futures index its last observation day, and on an
IFERC index since #167 the month's last trading date, the index printing later. `clearing_house` is required with a cleared route
and refused with a bilateral one, the organization's name kept as typed, selecting no rate and
exempting no fee; `counterparty` since #175 the reverse, required with a bilateral
route and refused with a cleared one, a label kept per row; and `broker` names the broker whose
presence charges the brokerage reserve since #NN, `none` in any case naming none for a screen
trade. The labels are read for nothing else but the readback. Since #NN the descriptions of these
four fields say what each controls, which the sheet reads in the grid above. `fixed_price` is the agreed price in the
index's quote units, `trade_id` the source system's deal number since #168, a whole number of at
most 15 digits read back as a number, duplicates kept as separate trades,
[numeric-trade-ids.md](../../engineering-tickets/trade-valuation-pipeline/numeric-trade-ids.md),
`trade_date` the day the deal was struck.

`marketing_reserve`, since #175, is an optional amount in the index's settlement currency, a marketing
cost booked once per ticket row whatever its months, quantity, days or sign: the template's one value
booked once by every row or the ticket's column, finite and zero or more, a negative amount, NaN and
the infinities refused naming the field and the first such row, a blank cell refused as any number's;
left out of both, zero. The amounts are summed once when the batch is made, over the rows and never
the components, into the marketing reserve [_ReportReserves](../trades/report-reserves.md) shows, and
enter no mark, cash, delta or DV01; the trades readback shows the row's amount on each of its
components, the one amount and no allocation, so the column is never summed down a strip.

## Excel help

| Item | Text |
|---|---|
| Function | Shows an instrument's fields, requirements, types and rules. |
| instrument | One instrument name from _ListInstruments, such as fixed_float. |

## The library checks

The identifier must be present in the same catalog `_ListInstruments` reads. Matching is
exact: no trimming, case folding, aliases or guessing. An unknown identifier fails with
the choices in catalog order. For the one-instrument catalog:

```text
instrument is 'Future', expected one of: 'fixed_float'
```

An empty catalog gives:

```text
instrument is 'fixed_float', expected a listed instrument; none are defined
```

The seam's existing blank/missing/type errors apply before lookup. A failure publishes no
partial spill and creates no object. Optionality of trade fields is unrelated to the required
`instrument` argument of this reader.

## The metadata rows

- `field`: canonical field identifiers, unique and in the definition's declared display order.
- `description`: the field's economic or recording meaning in plain language.
- `required`: whether the fact must always be present after defaults and static
  references have been resolved. TRUE does not require another cell on every ticket. FALSE
  does not by itself allow omission: `required_when` can still make the field mandatory.
- `required_when`: an additional condition making a field mandatory; `none` when absent.
  Conditions apply to the resolved values, including defaults. A supplied zero is
  present. Displayed conditions describe library-owned rules, not user-authored expressions.
- `type`: the semantic type of the eventual resolved input, in the seam's words, not the
  storage dtype of the metadata cell: `text`, `number`, `date`, `code` for a choice from a
  defined list, and `holiday calendar handle` for that reference, which this reader neither
  looks up nor publishes. A contract code follows a grammar, stated in its rule, not a list.
- `options`: the fixed allowed choices or the source of contextual choices. `no fixed list`
  and similar display phrases are explanatory text, not valid ticket values. A generic
  instrument reader cannot enumerate a selected index's contract codes without that index.
- `rule`: meaning and constraints beyond field type/options, including restrictions imposed
  by a selected traded product/agreement. Independently valid values can form an invalid pair.

A fact is mandatory when `required` is TRUE or its `required_when` condition holds. Validate
supplied values even when optional; do not replace missing facts with zero or empty text.
Trade construction combines disjoint template fields and ticket columns. Any overlap fails,
including equal values; there is no override or per-field permission policy. The resolved
trade satisfies the same rules regardless of which values came from a template or ticket.
Product constraints still apply; a template does not change what a selected product means.

The field row is the complete set of permitted identifiers for that instrument. Template
and trade headers must match it exactly: case-sensitive, with no trimming, aliases or fuzzy
matching. Column order may vary. Unknown columns fail instead of being ignored or carried
as arbitrary metadata; optional fields remain subject to the same names, types and rules.

The reader projects metadata from the shared instrument definition. Validation remains with
the appropriate owner: schema rules at construction, reference-data integrity in definition
constructors, relationship checks during static resolution, and market coverage at binding.
Descriptions must reference those rules; parsing prose from this spill is not a validation
mechanism. Editing or copying the spill does not alter the library definition.

`util_ReadHandle` shows a template's defaults, [trade-template.md](../trades/trade-template.md); a fuller reference inspector, if one is specified, could show selected defaults,
resolved units and remaining ticket inputs. Keep those contextual operations separate from
this generic schema reader for now.

## Treatment of the earlier field list

| Earlier field | What was decided |
|---|---|
| trade_id | Keep optional attribution; occurrence identity always preserves every row |
| index | The `_CreateTrades` argument, not a field; no market snapshot dependency |
| future_month | Use contract_code with explicitly supported syntax |
| quantity, quantity_unit, fixed_price | Use fixed_price for the agreed price; quantity basis is explicit and applies per monthly component |
| broker | Retain optional attribution as in the user's ticket; no pricing effect inferred |
| counterparty, marketer | `counterparty` built in #175: required with a bilateral route, refused with a cleared one, a label kept per row and read for nothing else; marketer is no field |
| clearing_house | Distinguish the clearing house from a clearing firm/account; agree whether selected specifications supply or constrain it |
| marketing_reserve | Built in #175: an amount in the settlement currency per ticket row, zero or more, counted once whatever the strip, quantity or days, reporting-only through `_ReportReserves`; omitted, zero |
| trade_date, contract_specification | Add the missing executed date and unambiguous specification selection; since #145 the selection is `quantity_unit`'s, a name among the index's specifications, and there is no separate field |
| schedule_method, quantity_per | Retain these field names; library-defined methods, all four built, and the month and calday quantity bases, both built since #159; exact and cfd outside v1 |
| settlement_method | Retain physical/financial identification; physical-delivery handling is outside v1 and does not set payment dates |

Omitted candidates are not silently supported or discarded at ingestion. The creators
reject a field absent from the schema, `fields cell (1, 1) is text 'contract_specification', expected a field of fixed_float: trade_id, trade_date, contract_code, ...`. Final settlement belongs
to the actual traded product/agreement; price/quantity units come from the applicable static
definitions. This generic reader describes the domains without choosing or overriding facts.

The newer legacy template also supplies floating/curve sources, observation and payment
scheduling, spreads and conversion controls. Their proposed ownership and unresolved meaning
are recorded in the [field sketch](../../engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md).
They are not all new inputs to the fixed_float schema above.

## Tests

`tests/unit/test_instruments.py` holds the examples, `tests/unit/test_help.py` pins the help,
`tests/performance/test_seam_budgets.py` and `test_seam_allocation.py` the cost, `tools/excel_smoke.ps1`
the rows in Excel and `host/Goosedove.Host.Tests/CallTests.cs` their replay.

| Case | Kind |
|---|---|
| the fixed_float's eighteen fields in order, `counterparty` and `marketing_reserve` since #175, which are required, the conditions, the period fields' three among them since #161 and their words since #172, the three alone letting a cell go unsupplied, the types and the codes | example |
| a definition that cannot be authored says why: an empty name or description, a name or a field twice, an empty cell | example |
| the name matched exactly, `Future`, ` fixed_float` and `future`, the name until #174, refused naming `fixed_float`, an empty catalog saying so, two instruments both named | example |
| seven rows and nineteen columns since #175, the labels down column one, the fields across row one, booleans in the required row and text in every other cell, none blank | example |
| the page's table equals the spill, cell for cell | example against the page |
| through the seam, the spill's shape and booleans, and the errors for another case, a blank, empty text, a number and a left-out name | example through the seam |
| every listed name is shown; a one-field definition shows seven rows and two columns | example |
| three reads publish nothing | example |
| the cell-wise builder: kinds and texts in sheet order; a ragged grid, a cell holding nothing and a whole number beyond what a cell holds exactly, 2^53 either side, refused, the edge itself taken | example |
| twelve functions, the classification once per cell, 133 for the fixed_float since #175, and the mixed way out's numpy; a peak of 12,869 bytes since #161's two period fields, 103 cells of text, about 108 a cell, and 15,041 since #172 lengthened the three period fields' texts, about 126 a cell, and two columns more since #175, 115 cells of text, within 130 a cell and the slack, what a text cell costs, where 110 a cell covered the texts before and a hundred a cell and the slack covered fifteen columns; nothing published | budget |
| the labels, the fields, two booleans, a condition and a type in a real Excel, the two new fields' names, condition and rule since #175; another case and a blank refused | Excel smoke |

The shape has a text label column and field columns holding text with one boolean each, which
the mixed way out carries and the seam's table builder, columns of one kind, could not build:
`MixedArray.cells` lays a small grid out one cell at a time, the way in's classification of a
cell used once per cell, for grids of a few hundred cells and never for data; a whole number
beyond what a cell holds exactly is refused before it becomes a float, as the number and table
results refuse one.

## Not here

Template construction, ticket ingestion, static encoding, product-specific choice expansion,
market binding and valuation. The schema spill is descriptive metadata, not an executable
template table to pass back verbatim as trade rows. No caller-supplied schema changes which
instrument definitions the library accepts.
