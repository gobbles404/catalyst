# _CreatePriceVector

Built in #85.

An ordered snapshot of futures prices from one numeric column, stored as a vector and reached by handle: the hot market data, a column a vendor's feed rewrites about once a second, taken as it stands each time the sheet recalculates and kept as given. It uses the existing `NumberColumn` seam and host transport; the typed Excel-DNA transport considered during design is deferred, with the decision recorded below. The code is `src/goosedove/market_data/price_vector.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreatePriceVector(prices: NumberColumn) -> Handle[PriceVector]: ...
```

| | B | C |
|---|---|---|
| 2 | 74.25 | `=_CreatePriceVector(B2:B5)` |
| 3 | 0 | shows a handle such as `price_vector:3f9a1c:000012` |
| 4 | -0.50 | |
| 5 | 74.25 | |

Select the prices only, without a header. One numeric cell is a valid vector of length one. The argument is required, and the supplied column determines its length on each call; there is no required contract count or length carried over from a previous call.

The seam checks type and shape using the existing `NumberColumn` rules in [inputs.md](../../seam/inputs.md). A horizontal range with several cells, a range with several columns, a text header, numeric text, a boolean, a blank cell or a missing argument fails under those rules, in the seam's words: `prices is 1x3 array, expected column of numbers`, `prices cell (1, 1) is text 'price', expected number`, `prices cell (2, 1) is blank, expected number`, `prices is missing, expected column of numbers`. Excel error cells follow the host's existing error propagation. The library does not repeat these checks, and a failed call publishes nothing.

Each successful call publishes a new handle, including a call with unchanged prices. Consumers refer to the creator cell or a defined name referring to it. Earlier handles continue to refer to their original snapshots under the existing [handle contract](../../seam/handles.md).

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a price vector from one column of prices and shows its handle, the text other formulas take as the price vector. |
| `prices` | The column of futures prices, such as B2:B101, without a header. |

## The library checks

No additional business rules. Every value and its position is preserved, including zero, negative prices and repeated values. Nothing is sorted, rounded, deduplicated, padded, truncated or bounded. A vector contains prices only; validating what each position means belongs to its eventual consumer.

## The snapshot

`PriceVector` is a record with one field, `prices`: an owned, read-only, one-dimensional NumPy `float64` array, following the existing immutable record pattern. The builder makes one ownership copy of the typed column and marks it read-only; modifying the caller's array afterwards cannot change a published snapshot. Nothing converts to a smaller dtype.

`util_ReadHandle` shows the vector as one numeric column, following the existing header and dtype-row convention:

| price |
|---|
| float64 |
| 74.25 |
| 0 |
| -0.50 |
| 74.25 |

The input is headerless; the inspection output has a header. Readback preserves order and numeric values.

The creator's work budget is one library ownership copy, one freeze and one publication. Its retained numeric storage is `8 * N` bytes for `N` prices, plus fixed object overhead. The existing host and seam have their own transport costs; this is not a claim of one copy across the complete Excel-to-Python path: the host copies the cells into its buffers, the seam owns the range with a copy of its own before the column reaches the builder, and the builder's copy is the second on the Python side. The counts and allocations are pinned in the existing performance tests, without a timing gate or a new work-counter argument.

## Tests

The record and its builder are `src/goosedove/market_data/price_vector.py`, the creator is registered in `src/goosedove/excel/market_data.py`, and the handle reader shows the kind in `src/goosedove/excel/utilities.py`, following the [worksheet-function build process](../../seam/working.md#2-adding-a-worksheet-function). The examples and the property below are `tests/unit/test_price_vector.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`; the ledger and the ceiling are `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| One price and several prices produce a one-dimensional `float64` vector with the supplied length | example |
| Values and order survive creation and readback, including zero, negatives and repeats | example and property |
| Changing the source array after creation leaves the snapshot unchanged; the record and stored array reject ordinary mutation | example |
| A later call, including one with equal values or a different length, publishes a fresh handle without changing the earlier object | example |
| Wrong shape, header text, numeric text, booleans, blanks and a missing argument fail through the existing seam; no handle is published | seam integration |
| Excel errors retain the existing host behavior | host replay and Excel smoke |
| `util_ReadHandle` returns the `price` header, `float64` row and the exact numeric column | example |
| Registration and help match this page; the saved workbook demonstrates creation and readback | help, host replay and Excel smoke |
| The builder makes one ownership copy and freezes it; publication occurs once; retained storage scales with the input length | work and allocation budget |

## Not here

No contract codes, dates, index identity, layout handle, calendar work, fixings, market construction or matching positions to contracts. No in-place updates, deduplication of equal snapshots, subscription machinery, handle-lifetime changes or float32 conversion. The market consumer will specify the correspondence between prices and contracts in its own ticket.

### Deferred: Excel-DNA `double[,]` transport

Decision, 19 September 2026: keep the existing transport for this creator. A separate numeric route would add registration choices, buffer-lifetime handling, tests and another path for maintainers to understand. The measured benefit does not currently justify that cost for the intended column of roughly 50-150 prices updating about once a second. This is a recorded alternative, not a requirement or dependency of this ticket.

The numeric-input experiment, whose results the owner keeps at `tools/performance/numeric_input/RESULTS.md` outside this repository, measured a warm saving of about 3.5-5.4 microseconds per call and 1.2-3.6 KB of managed allocation for those sizes. A small sample with one-second pauses showed no detectable latency improvement. Its consumer copied and summed prices; it excluded handle publication, calendar work, valuation and live-feed scheduling. These are experimental transport results, not measurements of `_CreatePriceVector`.

The implementation considered would explicitly register this argument as C# `double[,]`, bulk-copy its temporarily pinned numeric buffer into owned NumPy storage, and reuse the prepared Python validation and publication path. It would retain the two dimensions until the one-column check. The straightforward adapter still makes a transport copy followed by the creator's ownership copy; reducing that requires an explicit ownership design, and no Python view may outlive the managed pin. The experiment remains outside production code.

It also changes the input contract: Excel's typed conversion can turn blanks into zero, booleans into numbers and numeric text into numbers before our code sees them. The original cell kinds cannot then be recovered. It cannot silently replace the strict `NumberColumn` behavior promised above. See the [Excel-DNA marshalling reference](https://excel-dna.net/reference-data-type-marshalling/) for supported CLR input types.

Revisit only if profiling a representative workbook shows input transport materially limits the required workload. Any proposal must weigh measured end-to-end benefit against maintenance cost and explicitly resolve the coercion and ownership contracts. It would be a separate seam/host change, not part of building this creator.
