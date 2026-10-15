# _ListInstruments

Built in #137 as ticket I2 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), beside [_ShowInstrument](show-instrument.md). Its one instrument was named `future` until #174, when [rename-instrument-fixed-float.md](../../engineering-tickets/trade-valuation-pipeline/rename-instrument-fixed-float.md), the first slice of the bilateral arc, renamed it `fixed_float`; the name and its description changed and nothing else.

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
| fixed_float | A fixed-for-floating position on a specified reference contract, with explicit observation and settlement terms. |

This is the first catalog, the one row. Another row comes when that instrument's field contract
is defined and inspectable. Being listed establishes schema availability, not support for
every product or valuation measure. The definitions are `src/goosedove/instruments/definitions.py`,
frozen library data authored and checked there, each name once and nonempty, each description
nonempty; the function is `src/goosedove/excel/instruments.py`, which lays them out as one table
of two text columns through the seam's table builder.

The order is the explicit library declaration order. Every identifier is unique and can be
passed unchanged to `_ShowInstrument`. An empty catalog returns the header alone. Neither
function creates or returns a definition handle. The seam validates the declared result:
[outputs](../../seam/outputs.md). No additional row of implementation types is inserted.

The worksheet prefix follows this repository's convention. `List` and `Show` are the agreed
verbs for catalog and definition inspection, recorded in the
[naming conventions](../conventions.md#verbs). Both are read-only supporting functions for
instrument definitions, before template or trade creation.

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
the earlier phrase "no discounting" is omitted from `fixed_float`. The supported measure and
settlement/valuation treatment are specified at their own boundary.

The `fixed_float` family is organized around contract identity. It can later include a
supported bilateral lookalike while preserving its actual agreement and cash treatment.
The generic description does not make every route/settlement combination constructible;
the [field sketch](../../engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md)
records the distinction between the reference contract and the actual trade's terms.

## Tests

`tests/unit/test_instruments.py` holds the examples, `tests/unit/test_help.py` pins the help,
`tests/performance/test_seam_budgets.py` and `test_seam_allocation.py` the cost, `tools/excel_smoke.ps1`
the rows in Excel and `host/Goosedove.Host.Tests/CallTests.cs` their replay.

| Case | Kind |
|---|---|
| the two headers, the fixed_float's row and its description, every cell text | example |
| every listed name is shown by `_ShowInstrument` | example across the catalog |
| an empty catalog spills the header alone | example |
| three reads publish nothing: the store's live handles as they were | example |
| seven calls across seven functions and the mixed way out's numpy, no trade, market or history among them; a peak of 994 bytes, within twice the slack | budget |
| the header, `fixed_float` and the two counts in a real Excel, and `future`, the name until #174, refused as any other word | Excel smoke |

## Not here

Editing the catalog, creating templates or trades, enumerating product-specific contracts,
or reporting pricing capabilities. Schema availability and supported evaluation measures
must not be conflated. A separate capability surface is not required for this first reader.
