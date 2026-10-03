# 1. Resolution and trade representation

[Pipeline overview](README.md) · [Previous: instrument definitions](00-instrument-definitions.md) · [Next: static encoding](02-static-encoding.md)

Resolution is the first private child of [CreateTrades](create-trade.md). Static encoding is
its second child. The wrapper returns one handle retaining both resolved terms and encoding.

The first constructor whiteboard is [_CreateTradeTemplate](../../library/trades/trade-template.md):
instrument, field names and one aligned values row. Excel names identify the template cells;
the library object has no label field. Its CL/LOT
example shows shared defaults flowing into ticket rows. It creates a partial template, which
`_CreateTrades(index, fields, trade_rows, template)` takes last, required.

## Responsibility

Describe the deal that was consummated under an approved library instrument definition.
Resolve permitted template defaults and explicit ticket fields against that schema and the
referenced product definitions once. Preserve the accepted economics independently of current
prices, fixing arrivals and valuation dates. Approved cash records use their own defined
payment/balance meaning rather than pretending every record is a consummated commodity deal.

The entry point takes its instrument from the required template and its index as the first
argument of `_CreateTrades(index, fields, trade_rows, template)`.
fields is the column-header row. There is no labels argument; aliasing is deferred as a
separate future use case. trade_id remains optional attribution within the trade fields.
The result preserves every row occurrence, including duplicates.
One and N rows use the same constructor and downstream batch path; mixed instrument schemas
in a single batch are not an initial requirement.

## Inputs and output

Inputs are the approved instrument definition, applicable product/reference definitions,
typed rows with named fields and optional shared template values. Specifications define
product facts; templates cannot silently override them. Template fields and ticket columns
must be disjoint. Any overlap fails before combining values, even when the values match.
Duplicate headers within either input also fail. A blank is an error, not a fallback.
Every header must exactly match a field identifier in the selected instrument definition,
with no case folding, trimming, aliases or arbitrary extra columns. Order may vary. The
[CreateTrades contract](create-trade.md) defines this boundary for both templates and tickets.
Conflicts with authoritative specifications fail; the caller must explicitly select different
supported terms or a different product before trying again.

This child's output is immutable resolved terms with occurrence identity, displayed trade
identifiers, executed facts and retained static definitions. Encoding consumes that output
without reinterpreting the ticket. CreateTrades retains both as `TradeBatch.resolved` and
`TradeBatch.encoded`; the resolved terms are not a separate public handle. History-dependent
preparation is created later, outside this static object.

Required fields are instrument-specific. A supported future/swap schema identifies trade date,
contract/period, signed quantity and its unit, agreed price and its unit, currency, reference
and product/settlement treatment. A known cash flow instead needs signed money, currency,
payment date and settlement state; static cash needs its defined balance/snapshot context.
Payment terms belong here or in authoritative definitions when the instrument needs them.
Broker can be retained as optional attribution, as in the user's example below; its name
alone supplies no fees or other pricing inputs. Book, account and further metadata can be
added when their meanings and uses are established.

## Template plus ticket, then resolution

The user's next example separates templates by intended product/venue, using worksheet names
such as `ICE_Futs` and `NYMEX_Futs`. Each name points to a template creator cell. A separate
sheet holds ticket rows and refers to the selected template by that cell/name.

The conceptual flow is:

```text
template defaults + explicit ticket row
    -> CreateTrades:
         resolve: merge, select and validate static trade terms
         encode: derive numerical contributions and market input descriptors
         retain: TradeBatch(resolved, encoded)
    -> one trade-batch handle
```

Assembly is part of resolution. Resolution and encoding are distinct private children of
CreateTrades, coordinated in that order; neither needs a separate worksheet function or handle.
Encoding materializes schedules and numerical contributions from already selected contractual
rules. No history or current prices are needed for either child. One row is a batch of one.

The creation shape is settled:

```text
_CreateTrades(index, fields, trade_rows, template) -> trade_batch_handle
```

The template is required and selects the instrument; the index is the argument and appears in
no template field or ticket column. Selecting a taller trade body supplies more occurrences
through the same path.

The original ticket excerpt, preserved as whiteboard notation:

| future_month | quantity | clearing_house | broker | trade_price |
|---|---:|---|---|---:|
| u26 | -6 | ICE | ION | 105 |

`future_month` and `trade_price` are the earlier whiteboard spellings. The current schema
draft uses `contract_code` and `fixed_price`; this historical excerpt does not create aliases.
The code `u26` must resolve under the selected schedule's explicit spelling rules. `ION` is
the supplied broker label, not an instruction to infer a clearing firm or apply fees.

If the template already supplies the intended clearing selection, the ticket must omit it:

| contract_code | quantity | broker | fixed_price |
|---|---:|---|---:|
| u26 | -6 | ION | 105 |

This remains an excerpt. The template or ticket must also establish the actual index/product,
specification selection, units, executed date and remaining required contractual facts.
Here the template can supply the product context, LOT and compatible clearing/settlement
facts; the ticket supplies month, signed lots, broker and agreed price.

If the template supplies clearing_house, the ticket must omit that column. Repeating the
same clearing choice fails just as a different choice does. To vary a field between rows,
leave it out of the template and supply it in the tickets, subject to batch compatibility.
The completed trade must match its selected product; never silently select a different
product to make conflicting terms fit. This is one uniform no-duplication rule, with no
per-field permission flag. Duplicate trade occurrences are preserved and contribute separately.

### Product, venue and clearing identity

The shorthand ICE/NYMEX expresses the user's intended distinction. Before fixing the schema,
distinguish traded product, exchange/venue and actual clearing organization. For example,
ICE's WTI Crude Futures specification identifies ICE Clear Europe and cash final settlement;
NYMEX WTI describes physical settlement. These are properties of the particular products,
not a universal rule derived from an exchange label. See the
[ICE WTI specification](https://www.ice.com/products/213/WTI-Crude-Futures) and
[CME WTI product page](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.html).

Separate templates should therefore select unambiguous product/specification references
and compatible clearing and settlement facts. A field named clearing_house should identify
the actual clearing organization. If the desk instead wants an ICE/NYMEX product/venue
selector, define that field accordingly. An index label such as CL, the template's worksheet
name, or the clearing-house field alone cannot supply all of this identity. Current index
and specification objects do not yet establish every such relationship automatically.

## Worked payload

The [shared fixture](worked-example.md) is a fictional bilateral average, not a listed future:

```python
index = approved_toy_average_index  # the first argument of the call
template = create_template(instrument=approved_single_index_swap_definition, defaults={})
fields = ["Trade", "TradeDate", "Contract", "Quantity", "AgreedPrice", "PaymentDate"]
trade_rows = [
    ["T1", "2026-12-10", "Z26", 100, 70, "2027-01-05"],
    ["T2", "2026-12-10", "Z26", -40, 72, "2027-02-05"],
]
```

Dates above are readable notation for typed date values. The approved test-only toy definition
fixes quantity units, price units, currency, two observation dates and equal weights; the
user template cannot invent or override those facts. A contract code is interpreted within that
definition; it does not independently identify an index or imply a strip.

## Dependencies and acceptance

- A ticket, used default or referenced definition change creates a new resolved and encoded batch.
  A commodity tick, fixing or as-of change does not mutate an existing trade.
- Duplicate IDs are labels, not deduplication keys. Preserve the distinction between row
  occurrence and external trade identifier.
- Exact repeated rows remain two trades. A strip retains its deal identity and defined
  constituents; one monthly averaging contract is not automatically a strip.
- One trade alone must match its facts as an occurrence in a larger batch.
- Missing required fields, ambiguous codes and incompatible units fail visibly. The seam
  validates types/shapes once; the library checks product meaning without repeating seam checks.
- Resolution establishes meaning and compatibility once; encoding consumes that result.
  A failure in either child publishes no new trade handle.

Open before shipping: definition/version references. The NG field set is the
[Show page](../../library/instruments/show-instrument.md)'s, the instrument comes from the
template, and the seam's typed partial input is the agreed extension. A universal template
language is not required to establish the trade contract.
