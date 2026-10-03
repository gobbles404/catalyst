# _ListInstruments

Draft for owner and engineering review. Not implemented; the catalog contents and seam declaration have not passed the function-page review gate.

Lists the library-defined instrument schemas that can be inspected with
[_ShowInstrument](show-instrument.md). This is the first read-only surface for the
[instrument-definition stage](../../engineering-tickets/trade-valuation-pipeline/00-instrument-definitions.md).

## Worksheet contract

```python
def _ListInstruments() -> MixedArray: ...
```

Excel formula:

```excel
=_ListInstruments()
```

It spills a header and one row per inspectable definition, with exactly these two columns:

| instrument | description |
|---|---|
| future | A position tied to a specified reference contract, with explicit settlement terms. |

This is the proposed first catalog, not a claim that this function currently exists. Start
with the future schema; add another row when that instrument's field contract is defined and
inspectable. Catalog inspection can precede construction and evaluation implementation.
Being listed establishes schema availability, not support for every product or valuation measure.

The order is the explicit library declaration order. Every identifier is unique and can be
passed unchanged to `_ShowInstrument`. An empty catalog returns the header alone. Neither
function creates or returns a definition handle. The seam validates the declared result:
[outputs](../../seam/outputs.md). No additional row of implementation types is inserted.

The worksheet prefix follows this repository's convention. `List` and `Show` are the user's
proposed verbs for this surface; their adoption is a deliberate extension of the current
Create/Read vocabulary, to be recorded in the conventions page when this design is accepted.

## Excel help

| Item | Text |
|---|---|
| Function | Lists the library-defined instruments and their descriptions. |

## The library checks

There are no worksheet arguments to check. The shared library definitions must have unique,
nonempty identifiers and descriptions. Validate definition integrity where the definitions
are authored/loaded, rather than scanning for it on every reader call.

## The catalog

Read the same library-owned definitions used by `_ShowInstrument` and, when implemented,
trade construction. Do not maintain an independent hand-written list for this spill.
The definitions are immutable within the running library. Reading them depends on no trade,
index, history, valuation date, price vector or active workbook selection.

Candidate future additions remain in the design discussion until their schemas are defined:
single-index `swap`, a known dated cash flow, and the explicitly agreed meaning of static
cash. `basis_swap` and `option` remain out of the first scope. The older names
`cashflow_event`, `cashflow_schedule` and `settled_position` are examples to review, not
aliases to silently accept alongside the eventual identifiers.

Descriptions explain the economic record. They do not set universal evaluation policy:
the earlier phrase "no discounting" is omitted from `future`. The supported measure and
settlement/valuation treatment are specified at their own boundary.

The proposed future family is organized around contract identity. It can later include a
supported bilateral lookalike while preserving its actual agreement and cash treatment.
The generic description does not make every route/settlement combination constructible;
the [field sketch](../../engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md)
records the distinction between the reference contract and the actual trade's terms.

## Tests

These are implementation acceptance cases, not new tests added by this documentation change.

| Case | Kind |
|---|---|
| Exact two headers, catalog order, descriptions and row count | Example |
| Every listed identifier is inspectable by `_ShowInstrument` | Property across the shipped catalog |
| Empty definition collection produces a header-only spill | Example |
| Repeated reads return equal cells and create no handles or trade/market work | Example and work budget |
| Real Excel spill preserves headers and text; no implicit type row | Excel smoke |

Formatting/publication has a cost; count its work under the existing measurement policy.
There must be zero trade resolution, encoding, binding, fixing gathering or evaluation work.

## Not here

Editing the catalog, creating templates or trades, enumerating product-specific contracts,
or reporting pricing capabilities. Schema availability and supported evaluation measures
must not be conflated. A separate capability surface is not required for this first reader.
