# _CreateTradeTemplate

Whiteboard draft for review. Waiting on the seam: an instrument-selected partial record with typed field values, including static object references. Not implemented.

Creates reusable defaults under a library-owned instrument definition, reducing repeated
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

One field uses the same path as many. Omit a field entirely when the template should not
supply it; a listed field with a blank value is an input error, not an instruction to inherit
something. Start with at least one supplied default; an instrument without defaults can be
selected directly when the trade-construction surface is specified.

The user's CL example, shown conceptually:

| index | quantity_unit |
|---|---|
| CL | LOT |

On the worksheet, `CL` denotes the actual static index reference. For example, a workbook
name `CLIndex` points to the cell containing `_CreateIndex`'s handle, and the value cell below
`index` contains `=CLIndex`. It is not the literal text CL used for an implicit lookup:
existing Index names are display labels and need not be unique.

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

The selected instrument must be a recognized definition. Supplied fields must belong to
that definition, occur once and have valid supplied values. Header matching follows the
existing table convention; the seam owns shape, type and typed-reference resolution.
Static semantic constraints belong to the library. It does not parse Excel handles or
coerce numbers/dates from strings.

A template need not supply all required trade fields. Do not apply complete-trade required
or required_when checks to this partial record. Intrinsic supplied-value rules still apply;
relationships needing ticket values are checked against the final resolved trade. Avoid
an elaborate second validator that tries to anticipate every future ticket.

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
        index: the CL Index object
        quantity_unit: LOT
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

| contract_code | quantity | trade_price |
|---|---:|---:|
| Z26 | 5 | 70.00 |
| F27 | -2 | 71.25 |

Resolved excerpt:

| index | quantity_unit | contract_code | quantity | trade_price |
|---|---|---|---:|---:|
| CL | LOT | Z26 | 5 | 70.00 |
| CL | LOT | F27 | -2 | 71.25 |

Explicit ticket values override template defaults. The completed record is then resolved
and checked against its actual selected definitions, including conditional requirements.
An explicit blank remains an error; it does not silently fall back to the template. Shared
reference/default storage does not merge trade occurrences or introduce netting.

The intended CreateTrades call supplies one template for its array of ticket rows. A shared
template helps keep them alike, but explicit overrides still require checking compatibility
of the resolved collection. A uniform route and one actual index are the recommended first
commodity batch scope, with the index restriction still under discussion. This does not add
field locks or make template identity a valuation-group key. See the
[batch-boundary sketch](../../engineering-tickets/trade-valuation-pipeline/batch-boundaries-and-discounting.md).

Editing a template input produces a new immutable template through normal worksheet
dependencies; dependent trade construction can then rebuild. Market-price, fixing and
valuation-date changes alone do not recreate it. Worksheet headings and names remain an
Excel concern and do not become additional facts inside the library object.

## Seam work to specify before implementation

`fields` already fits `TextRow`. The combined partial record does not fit the current table path:

- Table schemas are fixed at registration and require all declared columns.
- A listed function cannot declare a bare MixedArray input to perform its own parsing.
- Table columns currently support numbers, dates, text and booleans, not typed handles.

Specify a narrow schema-selected partial-record binding at the seam, driven by the approved
instrument definition: align fields and values, refine supplied cells once, and resolve any
declared static-reference fields to their objects. The library should receive a typed partial
record. Do not require all values to be text or insert a new global name registry to bypass
this requirement. Dependency/lifetime handling must cover the references retained by the
template, including when the referenced index creator changes or is released.

See [inputs](../../seam/inputs.md), particularly the table and handle contracts and decision
38, and [handles](../../seam/handles.md). This is the remaining transport specification;
the worksheet ergonomics above are the proposed product contract.

## Tests

Implementation acceptance cases, not tests added by this documentation draft:

| Case | Kind |
|---|---|
| CL reference and LOT create the expected partial template | Example |
| One field and several fields follow the same constructor path | Example |
| Reordering field/value pairs preserves meaning; duplicate fields, width/row-count mismatches and wrong-type values fail | Property and example |
| Missing trade-only requirements are permitted; invalid supplied values are rejected | Example |
| An Excel name references the creator cell and its current handle without a library label field | Excel smoke |
| Typed index reference survives through the template and into resolved trades | Example through the seam and Excel lifetime check |
| Two ticket rows inherit defaults; explicit overrides validate against the completed record | Example in the trade-construction slice |
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
obligations, and separating templates does not introduce field locks.
