# Excel trade inputs and fully fixed trades

[Pipeline overview](README.md) · [CreateTrades](create-trade.md) ·
[Preparation](03-market-binding.md) · [Seam inputs](../../seam/inputs.md)

Agreed integration contract, 3 October 2026, carrying the review's decisions 9 to 14. This
specifies the integration work needed by the agreed pipeline; it does not describe implemented
generic trade functions.

## Agreed surface and remaining choices

```text
_CreateTradeTemplate(instrument, fields, values)   -> template_handle
_CreateTrades(index, fields, trade_rows, template) -> trades_handle
_PrepareTrades(trades, history)                    -> prepared_trades_handle
_EvaluateTrades(prepared, market)                  -> results_handle
_ReportValues(results), _ReportRisk(results)       -> tables
```

The template binds the instrument, identified by the first argument, and supplies a typed
partial set of its fields. `fields` is the column-header row, not labels for trade rows.
`values` contains one template row; `trade_rows` contains one or many occurrences. The
template argument of creation is required and last; the index is the first argument.
Aliases remain deferred.

Both product decisions are made: there is no call without a template, so the instrument
always comes from the template; and `index` is exclusively the explicit argument, never a
template field or ticket column, so no two places can disagree.

Template fields and ticket fields are disjoint. If a ticket includes any field already
supplied by its template, creation fails even when the two values are equal. Duplicate
headers within either input also fail. Omitting an entire field permits the other source to
provide it; a blank cell is a supplied invalid value, not omission or permission to inherit.
There are no per-field `template_allowed` flags.

Only fields declared by the selected instrument definition are accepted, in templates and
trade rows alike. Match the exact field identifiers exposed by _ShowInstrument: case-sensitive,
with no whitespace trimming, aliases, fuzzy matching or silently ignored extra columns.
An extra field does not become valid because its value is blank or it contains only notes.
Column order may vary; a new field requires a library-definition change.
The allowed set belongs to the selected instrument, not the union of every instrument's
fields. Unrelated worksheet columns stay outside the supplied ranges. Exact field names
do not change a field value's own documented grammar, such as contract-code case handling.

## What the existing seam supplies

| Capability | Current implementation and boundary |
|---|---|
| Headers bound to typed columns | `Table`, `Schema`, `_bind` and `_refine` in [bridge.py](../../../src/goosedove/excel/bridge.py) bind a `TextRow` to a declared table. Header width must match body width; order may vary. |
| Canonical header matching | `_bind` uses `casefold()` without trimming. `quantity` and `QUANTITY` are the same field; `quantity ` is not silently repaired. Unknown and repeated headers fail. |
| One type check at the boundary | `Registered.run` hands the library typed values. Dates arrive as dates, quantities as numbers, and handles as objects. The library validates their economic meaning. |
| Scalar typed references | `Handle[Kind]` resolves a live stored object of the declared kind. An optional scalar handle can be omitted with `None` as its declaration default. A blank cell still fails. |
| Publication and lifetime | [Lifetime.cs](../../../host/Goosedove.Host/Lifetime.cs) uses Excel-DNA observation for handle-returning creators. Equal live calls share a publication; changed inputs create a new immutable object; final disconnection releases the store's reference. |

The current `Table` does **not** implement the proposed template inputs. Its schema is
chosen at registration, requires every declared column, and supports number, date, text
and boolean columns. It has no instrument-selected partial-column schema or typed handle
column. Generic `CreateTrades` and its partial-input binding are not yet implemented.

The general binder's case-insensitive matching differs from the exact trade-field contract
above, and that is decided: the new path matches exactly, decision 29 stays for the
registered tables, and inputs.md records the two rules in the decision that records this
extension. This document does not change existing table functions.

## Bounded seam extension, agreed

One extension for library-defined, typed partial tables, agreed in the review of 3 October
2026 as its decisions 9 to 12. Keep the raw mixed-cell
transport private to the seam. Do not pass a `MixedArray` to the trade library and ask it to
interpret Excel cell kinds, serial dates, handle strings or positions.

The proposed prepared boundary performs these steps once per changed creator input:

1. Establish the instrument context from the `instrument` text of `_CreateTradeTemplate` or
   the resolved template of `_CreateTrades`, which the seam resolves before it binds the
   ticket's columns.
   Instrument identifier meaning belongs to the library-owned definition registry. It
   provides an immutable field/type descriptor; the seam adapter compiles the corresponding
   column validators once per definition, not once per trade or tick. This is an explicit
   extension of today's registration-fixed table selection, not an existing facility.
2. Bind the header row to that descriptor using exact field identifiers, without casefold
   or trimming, allowing any supported subset of columns in any order. Reject unknown and
   repeated headers with the offending header, column and allowed names identified; publish
   no partial object. Validate shape and headers before cell contents.
   A template body must have exactly one row; a ticket body must have at least one row.
3. Validate each supplied column and resolve reference-valued cells to their declared object
   kind. Emit canonical field identifiers and typed columns with explicit field presence.
   A reference column needs a declared expected kind, such as `HolidayCalendar`; it is not
   an arbitrary string or a globally looked-up name.
4. Hand the library the typed partial input. The library rejects template/ticket overlap,
   combines disjoint fields, checks completed requirements and valid combinations, resolves
   conventions, then encodes. It does not check Excel cell types again.

The order of failures is: each argument alone, in signature order where possible; the
template resolved before the instrument-dependent schema is bound; the header row's width
against the body; unknown or repeated headers in input order; the cells column by column,
left to right; then the library's meaning, overlap between template and ticket, a required
field missing, an unsupported choice, incompatibility with the index. One failure is reported
at a time and no handle is published on any. An omitted optional field is absence; a supplied
blank reference cell is a failure naming the cell. The `type` row of `_ShowInstrument` uses
the seam's words: `holiday calendar handle` for that reference, `code` for a choice from a
defined list, `text`, `date` and `number`; a contract code follows a grammar, stated in its
rule, not a list.

Use the same library-owned field definitions for reader metadata, the seam's type
descriptors and construction's semantic validation. The library must not import the Excel
bridge. The adapter maps library field types to seam validators. This keeps economic
rules in the library while making the new cross-argument schema selection visible and
reviewable in the seam contract.

An internal typed payload can be as small as:

```text
PartialTradeFields
    instrument_definition
    row_count
    present_fields              # canonical field identifiers
    typed_columns               # arrays/tuples, or typed object references
```

This is a logical payload, not a requirement to allocate Python dictionaries per trade.
Template scalar fields can remain shared until encoding needs a numerical broadcast.
Primitive type validation occurs once on each creator's changed input. Economic meanings
such as `payment_time_lag = "+1bd"` are resolved once into static terms during creation;
preparation and evaluation consume those terms without reparsing the string.

For example, the template's selected columns could be:

| quantity_unit | quantity_per | payment_time_lag | payment_holiday_calendar |
|---|---|---|---|
| LOT | month | +1bd | reference to the calendar creator's cell |

And the ticket columns could be:

| trade_date | contract_code | quantity | fixed_price |
|---|---|---|---|
| 1-Oct-2026 | Z26 | 2 | 3.50 |
| 1-Oct-2026 | F27 | -1 | 3.70 |

This shows a partial input boundary for a financial product, not a complete future
specification; the physical NG template supplies no payment fields. Other required fields
must be supplied from their single agreed source. Adding `quantity_unit` to the ticket is an
overlap error, including when every row says `LOT`.

The calendar cell contains a formula reference to the creator or an Excel name referring
to that cell. The new reference-column validator resolves its handle once and passes the
actual calendar into the template; construction must not retain handle text for later
resolution. Excel follows the input-cell dependencies. The immutable template retains
the typed calendar reference it needs. Direct handle columns are new seam work; declaring
these cells as ordinary text would bypass type checking and is not an acceptable shortcut.

## Dependency graph and retained objects

```text
static definitions + template + ticket rows -> trades
as-of + calendar + fixings                  -> history
trades + history                           -> prepared
index label + changing prices              -> price_vector
history + price_vector                     -> market
prepared + market                          -> results
results                                    -> readers
```

Excel already owns these worksheet dependencies. No private address registry or mutable
history cache is needed. A new prepared object retains strong references to the original
trade batch and history; it does not borrow their handle strings. A result retains the
dependencies needed to explain its own immutable snapshot. Removing an old publication
from the seam store does not invalidate objects retained by another object.

The existing observed-creator path can reuse an unchanged live creator without another
Python call. This reuse belongs to the host, not `Registered.run`: calling the seam
directly twice publishes twice. Tests must distinguish those two execution paths.

| Event | Required work |
|---|---|
| Price tick, same history and layout | New price vector/market/results; zero ticket decoding, resolution, encoding or fixing-fold work |
| Corrected fixing or as-of change | New history and full preparation; reuse static trade encoding |
| Changed ticket, template or used static definition | Recreate trades and prepare their new encoding |
| Unchanged observed creator recalculation | Reuse the live publication; no construction |
| Invalid new input | Visible failure; publish no partial object or previous successful result as the new answer |
| Creator removed or workbook closed | Release publication ownership; retain only dependencies still owned by another live object |

At evaluation, compare the prepared history with the market's history as retained objects,
and validate the live layout/projection contract. Reject incompatibility; never silently
reprepare in evaluation. Two histories with the same displayed index name are not thereby
interchangeable. See [handle ownership](../../seam/handles.md) for existing supported
reference use and lifecycle guarantees.

## Price-vector identity limitation

[PriceVector](../../../src/goosedove/market_data/price_vector.py) retains an index-name
string and ordered prices, without contract identifiers. [Market](../../../src/goosedove/market/market.py)
checks the name and permissible vector length, then interprets positions from the first
unfixed contract in the history's schedule. It cannot identify a same-length permutation,
a column mislabeled with the expected name, or an unrolled price column that still fits.

Preparation should retain its ordered input identities and mapping to those schedule
positions. This makes the consumer contract explicit but does not manufacture missing
provider identities. The initial workbook must visibly align source contract codes with
the schedule order and refresh that alignment on a history roll. Fixtures must show both
the codes and prices used. If detecting incorrectly ordered supplied prices becomes a
requirement, a future input contract must carry source identities; that is an additional
design change, not a check the present positional vector can perform.

## Entirely ended calendar: deferred

Two cases are kept separate:

| Case | Current market support | Decided trade-evaluation behavior |
|---|---|---|
| All observations for this trade batch are fixed, while the broader market still has unfixed periods | A normal market is constructed with its valid live vector | Supported: prepare zero commodity live inputs; evaluate the retained amounts and payment states, reading zero live prices |
| Every period of the supplied history is fixed | History can exist, but `market()` rejects it and requires at least one quoted period | Deferred; the Market is unchanged for this first implementation |

The zero-live numerical dot product is not the blocker. Excel has no ordinary zero-row range
to supply to the price-vector creator, and the market builder rejects both an entirely fixed
history and an empty vector. A fake zero quote, a fabricated schedule month or an earlier
as-of is not a valid representation, and no code inserts a contract or a price to reach one:
where a fixture needs a later contract so that every state has a valid market, the fixture
supplies it, as the [NG example](ng-creation-preparation-example.md) does with G27.

Preparation still owns the fixing fold and payment-state classification under the history's
as-of. A completely fixed unpaid amount can remain in mark until its modeled payment date;
fixed is not paid. Commodity delta is zero when there are no remaining commodity inputs.
Future bilateral rate exposure is a separate measure and must not be declared zero merely
because commodity fixings are complete. Discounting remains outside this amount path.

## Acceptance cases

These are proposed implementation acceptance tests, not new snapshots generated from a
prototype. Independent worked amounts establish expected economics.

| Case | Observable expectation |
|---|---|
| Header order permuted with matching body columns | Same resolved terms and encoded economics |
| `quantity` supplied twice | Duplicate-header error; no publication |
| `QUANTITY`, `quantity ` or an undeclared shorthand supplied | Unknown-field error under exact matching; no publication |
| An extra notes column, including one containing only blanks | Unknown-field error; never ignored or retained as arbitrary metadata |
| A field declared only by another instrument | Unknown-field error for the selected definition |
| Template has `quantity_unit`, ticket has it too | Overlap error for equal or different values; no override |
| Field omitted from ticket but supplied by template | Its typed template value completes the trade |
| Blank, empty text or wrong type under a present header | Cell-specific seam error; no inheritance or coercion |
| Unknown header or column count mismatch | Existing precise header/shape failure |
| Required field absent from both sources | Library error naming the missing completed-trade field |
| Reference field contains an unknown or wrong-kind handle | Seam error before construction; typed references only inside library |
| One row and duplicate identical rows | Same batch path; duplicate occurrences contribute twice |
| Only current prices change | Zero decode/resolve/encode/fixing-fold work; only applicable evaluation work |
| History changes but a stale prepared handle is supplied | Visible incompatibility error, no implicit preparation |
| Entire trade batch fixed within a live broader market | Correct retained amounts; zero live-price reads |
| Entire calendar ended | Deferred: refused as today, and no dummy quote or inserted contract stands in |
| Vector omitted for a live history | Visible failure, as today |
| Fixing correction with zero live inputs | New prepared amount equals the independently recomputed amount |
| Repeated price ticks, failed inputs and recovery, then last workbook closed | No stale results or abandoned ownership; retained memory returns to the live graph's baseline |

Instrument-selected partial tables and typed reference columns are a separately reviewable
seam change, ticket I3 of the [README](README.md). Generic construction and preparation
consume that contract. This scope does not require per-row creator handles, a general rule
language, incremental fixing updates or a new cache.
