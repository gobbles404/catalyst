# _CreateTradeTemplate

Agreed contract. The seam's part is built in #NN, `FieldRow[str]` and the `FieldValues` it hands over, [inputs.md](../../seam/inputs.md) decision 42; the creator itself comes in ticket I4. Not implemented.

Creates shared trade fields under a library-owned instrument definition, reducing repeated
ticket entry. The template is allowed to be incomplete. It has no market-state dependency.

## Worksheet contract

Proposed worksheet shape, not a currently registerable Python declaration:

```text
_CreateTradeTemplate(instrument, fields, values) -> Handle[TradeTemplate]
```

| Argument | Proposed meaning |
|---|---|
| instrument | One exact instrument identifier from _ListInstruments, such as future |
| fields | One horizontal row of recognized field names, in any order |
| values | Exactly one aligned row of values for those fields |

instrument is the first, required argument. The template retains the selected definition;
`_CreateTrades(index, fields, trade_rows, template)` takes the template last, required, and
uses that definition when completing it with ticket fields. The template retains no index:
the index is the first argument of that call, so one template serves any compatible index.

One field uses the same path as many. Omit a field entirely when the template should not
supply it; a listed field with a blank value is an input error, not an instruction to inherit
something. A template carries at least one field. The template is required on `_CreateTrades`,
so there is no direct instrument selection and no path without one: a batch that shares
nothing still names one shared fact in its template.

The user's example, shown conceptually:

| quantity_unit | schedule_method |
|---|---|
| LOT | lastday |

The index is not a template field. `_CreateTrades` takes it as its first argument, a workbook
name such as `CLIndex` pointing at the cell holding `_CreateIndex`'s handle, and the same
template serves a CL index and an NG index alike. Existing Index names are display labels and
need not be unique; nothing is looked up by name.

With headers in A1:B1 and their values in A2:B2:

```excel
=_CreateTradeTemplate("future", A1:B1, A2:B2)
```

The result cell contains the template handle. Other formulas refer to that cell. Use a
worksheet heading or Excel name such as `ICE_Futs` or `NYMEX_Futs` to identify its purpose.
There is no label argument or label field in the template object. The exact handle text
follows the seam's existing publication contract. An Excel name refers to the creator cell;
it does not establish product identity or settlement treatment.

## Excel help

Proposed lines for the eventual declaration:

| Item | Text |
|---|---|
| Function | Creates shared defaults for an instrument and shows their handle, the text other formulas take as the trade template. |
| instrument | One instrument name from _ListInstruments, such as future. |
| fields | The field-name cells in one row, such as A1:B1, using names shown by _ShowInstrument. |
| values | The values in one row beneath those fields, such as A2:B2. |

## The library checks

The selected instrument must be a recognized definition. Every supplied field must exactly
match a field identifier in that definition, occur once and have a valid supplied value.
Matching is case-sensitive, without trimming, aliases or fuzzy matching. The identifiers
shown in _ShowInstrument's field row are the accepted names; descriptions are not headers.
Unknown fields fail even if their values are blank or they are intended only as notes.
No extra columns are silently ignored or retained as arbitrary metadata. Field order may vary.

This exact matching is part of the proposed trade-input binding; today's general Table
binder ignores case. The [binding page](../../engineering-tickets/trade-valuation-pipeline/excel-trade-input-binding.md)
records that difference explicitly. The seam owns shape, type and typed-reference resolution.
Static semantic constraints belong to the library. It does not parse Excel handles or
coerce numbers/dates from strings.

A template need not supply all required trade fields. Do not apply complete-trade required
or required_when checks to this partial record. Intrinsic supplied-value rules still apply;
relationships needing ticket values are checked against the final resolved trade. Avoid
an elaborate second validator that tries to anticipate every future ticket.

The accepted payment_time_lag field is a string such as "+1bd". Like every other field,
it is supplied by either the template or the trade row, never both. The same applies to
payment_holiday_calendar. The supported product establishes the payment anchor;
CreateTrades generates each component's payment_date. Broader bilateral rules are deferred.

The first seam review must pin error ownership and exact messages for unknown/duplicate
fields, width mismatch, more than one values row, unsupported types and wrong/dead reference
handles. This page records their required behavior without inventing a new declaration type
or duplicating current seam messages.

## What it retains

Logical payload, not a commitment to a dictionary implementation:

```text
TradeTemplate
    instrument_definition: the library's future definition
    defaults:
        quantity_unit: LOT
        schedule_method: lastday
```

Retain the definition/reference objects and own the supplied default values in an immutable
record. No duplicate instrument schema is authored by the workbook. No per-field template
permission list is needed: the final trade follows the normal instrument and contractual
rules, regardless of a value's source. No trade encoding, history binding or evaluation is
performed here.

The same template can supply defaults to one or many ticket rows. In the following toy
example only the fields relevant to this merge are shown; actual construction still needs
the agreed executed date, specification selection and settlement/clearing facts required by
the future definition. Prices are illustrative agreed trade prices, not market observations.

Ticket excerpt:

| contract_code | quantity | fixed_price |
|---|---:|---:|
| Z26 | 5 | 70.00 |
| F27 | -2 | 71.25 |

Resolved excerpt, the index, CL, being the argument of the call and applying to both rows:

| quantity_unit | schedule_method | contract_code | quantity | fixed_price |
|---|---|---|---:|---:|
| LOT | lastday | Z26 | 5 | 70.00 |
| LOT | lastday | F27 | -2 | 71.25 |

Template fields and ticket columns must be disjoint. Before combining their values,
CreateTrades rejects every overlapping field, even when its two values are identical.
For example, a template supplying quantity_unit=LOT and a ticket containing a quantity_unit
column fails with a field-specific error. Remove that column from the ticket or remove the
field from the template. No override, equality exception or fallback is supported.

Duplicate field names within either input also fail under the exact matching rule.
The completed record must then satisfy its selected definition, including conditional
requirements. An explicit blank remains an error. Duplicate trade rows remain distinct
economic occurrences; rejecting duplicate field sources does not deduplicate trades.

The CreateTrades call supplies one template, required, for its array of ticket rows.
Template-supplied fields are shared; ticket-only fields can vary. Resolution still checks
compatibility of the completed collection. One index per batch is a fact of the call, since the
index is its argument; a uniform route is the recommended first commodity batch scope. This
does not add per-field permission flags or make template identity a valuation-group key. See the
[batch-boundary sketch](../../engineering-tickets/trade-valuation-pipeline/batch-boundaries-and-discounting.md).

Editing a template input produces a new immutable template through normal worksheet
dependencies; dependent trade construction can then rebuild. Market-price, fixing and
valuation-date changes alone do not recreate it. Worksheet headings and names remain an
Excel concern and do not become additional facts inside the library object.

## Seam work before implementation

`fields` already fits `TextRow`. The combined partial record does not fit the current table path:

- Table schemas are fixed at registration and require all declared columns.
- A listed function cannot declare a bare MixedArray input to perform its own parsing.
- Table columns currently support numbers, dates, text and booleans, not typed handles.

The [Excel trade-input binding page](../../engineering-tickets/trade-valuation-pipeline/excel-trade-input-binding.md)
specifies a narrow schema-selected partial-record binding at the seam, driven by the approved
instrument definition: align fields and values, refine supplied cells once, and resolve any
declared static-reference fields to their objects. The library should receive a typed partial
record. Do not require all values to be text or insert a new global name registry to bypass
this requirement. Dependency/lifetime handling must cover the references retained by the
template, including when a referenced holiday calendar's creator changes or is released.

See [inputs](../../seam/inputs.md), particularly the table and handle contracts and decision
38, and [handles](../../seam/handles.md). The proposed transport extension still needs
engineering review and implementation; the current seam cannot register this signature as-is.

## Tests

Implementation acceptance cases, not tests added by this documentation draft:

| Case | Kind |
|---|---|
| LOT and lastday create the expected partial template | Example |
| One field and several fields follow the same constructor path | Example |
| Reordering field/value pairs preserves meaning; duplicate fields, width/row-count mismatches and wrong-type values fail | Property and example |
| Unknown, case-changed, whitespace-padded or aliased headers fail; no extra fields survive construction | Example through the seam |
| Missing trade-only requirements are permitted; invalid supplied values are rejected | Example |
| An Excel name references the creator cell and its current handle without a library label field | Excel smoke |
| A typed holiday calendar reference survives through the template and into resolved trades | Example through the seam and Excel lifetime check |
| Disjoint template/ticket fields complete one or many trades; overlapping fields fail for equal and unequal values | Example in the trade-construction slice |
| Duplicate field names fail; identical trade occurrences each contribute once | Example in the trade-construction slice |
| No market reads, trade encoding or evaluation occur during template creation | Work budget |

Inspection should expose the instrument and stored defaults using the
existing inspection surface when the object kind is implemented. If references are displayed
as human-readable names, the spill is not automatically a round-trip input table.

## Not here

Trade construction, complete-trade validation, static numerical encoding, market binding,
valuation, template inheritance or a permission system. Finalizing the trade constructor's
argument list follows this template contract; this sketch does not add another public function.

The [CreateTrades wrapper](../../engineering-tickets/trade-valuation-pipeline/create-trade.md)
consumes templates and tickets through two private children: resolution followed by static
encoding. Its returned handle retains both outputs; template creation performs neither job.

The [trade-representation sketch](../../engineering-tickets/trade-valuation-pipeline/01-trade-representation.md)
adds the user's ICE/NYMEX example: different product defaults, a separate ticket sheet and
static resolution of the assembled facts. Clearing defaults alone do not identify delivery
obligations; all templates follow the same disjoint-field rule.
