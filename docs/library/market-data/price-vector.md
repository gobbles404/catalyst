# _CreatePriceVector

Built in #85; named for its index since #112. Unchanged by #NN, which lets the market take a vector that stops before the schedule's last contract.

An ordered snapshot of futures prices from one numeric column, stored as a vector and reached by handle: the hot market data, a column a vendor's feed rewrites about once a second, taken as it stands each time the sheet recalculates and kept as given. From #112 the vector also carries the name of the index it prices, ordinary text typed once, so that the [market](../market/market.md) can refuse a vector labelled for another index whatever its length: a name is a label the sheet keeps, compared by the market with the name its index was created with, and no index object is looked up or held here, so the vector depends on its prices and its name cell and never on the index cell. It uses the existing `NumberColumn` seam and host transport; the typed Excel-DNA transport considered during design is deferred, with the decision recorded below. The code is `src/goosedove/market_data/price_vector.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreatePriceVector(index_name: str, prices: NumberColumn) -> Handle[PriceVector]: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | WTI NYMEX | 74.25 | `=_CreatePriceVector(A1, B1:B4)` |
| 2 | | 0 | shows a handle such as `30512:price_vector:WTI NYMEX:12` |
| 3 | | -0.50 | |
| 4 | | 74.25 | `=_CreatePriceVector("WTI NYMEX", B1:B4)` shows a second handle, the name typed |

The name first, then the prices, both required, neither with a default. The name is ordinary text, one cell: the cell `_CreateIndex` was given the name from, a defined name referring to it, or a literal typed in the formula; it is not the index's handle, and the function receives the text and nothing else. Pointing at the cell the index was created from is the way to type the name once, A1 above being the cell `_CreateIndex("WTI NYMEX", ...)` reads too; a literal serves a quick sheet. Select the prices only, without a header. One numeric cell is a valid vector of length one. The supplied column determines its length on each call; there is no required contract count or length carried over from a previous call, and since #NN the [market](../market/market.md) takes any length from one price to one per contract its schedule has left.

The seam checks type and shape, the name against the text rule and the column against the existing `NumberColumn` rules in [inputs.md](../../seam/inputs.md). Empty text, a blank, a number, a boolean or a one-cell range where the name should be fails in the seam's words, `index_name is blank, expected text`, `index_name is number 74.25, expected text`; a horizontal range with several cells, a range with several columns, a text header, numeric text, a boolean, a blank cell or a missing argument among the prices fails as before, `prices is 1x3 array, expected column of numbers`, `prices cell (1, 1) is text 'price', expected number`, `prices cell (2, 1) is blank, expected number`, `prices is missing, expected column of numbers`. Excel error cells follow the host's existing error propagation. The library does not repeat these checks, and a failed call publishes nothing.

A successful call publishes a vector. A recalculation with the same name and prices, or a second cell with the same arguments, shares the live vector and its handle; changed prices publish a new vector, and the old one is released when Excel disconnects its last creator, as [handles.md](../../seam/handles.md#publication-and-release) says. The vector recalculates when a price moves or the name cell changes, and not when the index is remade, since it refers to no index cell. Consumers refer to the creator cell or a defined name referring to it. A market made over an earlier vector keeps that snapshot by reference, since a release takes the store's entry and not the object.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a price vector of one index from the index's name and one column of prices, and shows its handle, the text other formulas take as the price vector. |
| `index_name` | The name the index was created with, such as A1 or "WTI NYMEX", typed as _CreateIndex was given it; the market checks it against its history's index. |
| `prices` | The column of futures prices, such as B2:B101, without a header. |

## The library checks

No rule of meaning here. The name is kept as typed, never trimmed or re-cased, `WTI NYMEX` and `wti nymex` being two names; whether it is the name of the history's index is the [market](../market/market.md)'s rule, since #112, checked as text when the market is made. Every value and its position is preserved, including zero, negative prices and repeated values. Nothing is sorted, rounded, deduplicated, padded, truncated or bounded. A vector contains a name and prices only; validating what each position means belongs to its eventual consumer.

## The snapshot

`PriceVector` is a record with two fields: `index_name`, the text as typed, and `prices`, an owned, read-only, one-dimensional NumPy `float64` array, following the existing immutable record pattern. The builder makes one ownership copy of the typed column and marks it read-only; modifying the caller's array afterwards cannot change a published snapshot. Nothing converts to a smaller dtype, and no index object is held: the record has no reference to keep the index alive or to remake the vector when the index is remade.

`util_ReadHandle` shows the vector as one numeric column, as it did before; the name is not spilled, since the sheet holds it beside the creator:

| price |
|---|
| float64 |
| 74.25 |
| 0 |
| -0.50 |
| 74.25 |

The input is headerless; the inspection output has a header. Readback preserves order and numeric values.

The creator's work budget is one library ownership copy, one freeze and one publication; the name costs the seam its text rule, one call, and the library nothing. Its retained numeric storage is `8 * N` bytes for `N` prices, plus fixed object overhead and the name's own. The existing host and seam have their own transport costs; this is not a claim of one copy across the complete Excel-to-Python path: the host copies the cells into its buffers, the seam owns the range with a copy of its own before the column reaches the builder, and the builder's copy is the second on the Python side. The counts and allocations are pinned in the existing performance tests, without a timing gate or a new work-counter argument.

## Tests

The record and its builder are `src/goosedove/market_data/price_vector.py`, the creator is registered in `src/goosedove/excel/market_data.py`, and the handle reader shows the kind in `src/goosedove/excel/utilities.py`, following the [worksheet-function build process](../../seam/working.md#2-adding-a-worksheet-function). The examples and the property below are `tests/unit/test_price_vector.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`; the ledger and the ceiling are `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market's tests build their vectors through this creator and move with it, naming each vector for its history's index.

| Case | Kind |
|---|---|
| One price and several prices produce a one-dimensional `float64` vector with the supplied length, and the name is kept as typed | example |
| Values and order survive creation and readback, including zero, negatives and repeats | example and property |
| For any text and any column of numbers, the name and the prices are kept as given | property |
| A name in another case, with a space, or that no index bears: kept as typed, since nothing here checks it | example |
| Changing the source array after creation leaves the snapshot unchanged; the record and stored array reject ordinary mutation | example |
| A later call through the seam's prepared path, including one with equal values or a different length, publishes a fresh handle without changing the earlier object, nothing being released there | example |
| In Excel, through the production registration: an unchanged full calculation publishes nothing; a changed price publishes a new vector and releases the old one with its market; an identical vector in another cell shows the same handle and publishes nothing, and deleting it releases nothing while the first cell lives; a vector with other prices is its own publication, released when its last owner goes | the lifetime script's `core` group |
| A literal name and a cell holding the same text make the same vector; empty text, a blank, a number, a boolean, a one-cell range and a missing name fail through the existing text rule; wrong shape, header text, numeric text, booleans, blanks and a missing column fail through the existing column rules; no handle is published, and the name is named first when both are wrong | seam integration |
| Excel errors retain the existing host behavior | host replay and Excel smoke |
| `util_ReadHandle` returns the `price` header, `float64` row and the exact numeric column, and no name | example |
| Registration and help match this page; the saved workbook demonstrates creation and readback, each vector named for its index | help, host replay and Excel smoke |
| The builder makes one ownership copy and freezes it; publication occurs once; the name adds the seam's text rule and nothing to the library; retained storage scales with the input length | work and allocation budget |

## Not here

Whether the vector is this index's: the [market](../market/market.md)'s check since #112, by name and as text, which catches a vector labelled for another index and cannot catch two indices of one name or a vendor column labelled wrongly; the vector holds the label and knows nothing of the index, and no index object is held, looked up or kept alive here. No contract codes, dates, layout handle, calendar work, fixings, market construction or matching positions to contracts. No in-place updates, no comparison of one snapshot's prices with another's, and no float32 conversion. The sharing of a live vector by equal calls and its release: the seam's, since #114, the same for every creator, and nothing of it here. The correspondence between prices and contracts is [market.md](../market/market.md)'s, since #86 and, for any calendar, #106: one price per contract from the first unfixed period's contract on, in the schedule's order, through the schedule's last or, since #NN, stopping before it.

### Deferred: a contract code on the vector

The vector is positional. It carries no contract code and no starting contract, so the market reads the first price as the first required contract's, the contract of the first period not yet fixed, and cannot tell a vector the sheet moved on from one it left as it was. When the first contract rolls, a vector left unchanged is read one contract later than the desk meant it: `70, 71` quoted for Z26 and F27 is read as F27 and G27 once Z26's last period has fixed. Until #NN the market's count caught that case when the vector reached the schedule's end, one price too many; a vector that stops before the end is taken as it stands. Keeping the first price on the first required contract is the sheet's to do. [market.md](../market/market.md#when-the-first-contract-rolls) has the example; contract labels and the alignment checks they would allow belong to a later discussion.

### Deferred: Excel-DNA `double[,]` transport

Decision, 19 September 2026: keep the existing transport for this creator. A separate numeric route would add registration choices, buffer-lifetime handling, tests and another path for maintainers to understand. The measured benefit does not currently justify that cost for the intended column of roughly 50-150 prices updating about once a second. This is a recorded alternative, not a requirement or dependency of this ticket. The name argument of #112 leaves it as it was: Excel registers each argument with its own type, so the name stays text as every argument is today and the column could still take the typed route on its own.

The numeric-input experiment, whose results the owner keeps at `tools/performance/numeric_input/RESULTS.md` outside this repository, measured a warm saving of about 3.5-5.4 microseconds per call and 1.2-3.6 KB of managed allocation for those sizes. A small sample with one-second pauses showed no detectable latency improvement. Its consumer copied and summed prices; it excluded handle publication, calendar work, valuation and live-feed scheduling. These are experimental transport results, not measurements of `_CreatePriceVector`.

The implementation considered would explicitly register this argument as C# `double[,]`, bulk-copy its temporarily pinned numeric buffer into owned NumPy storage, and reuse the prepared Python validation and publication path. It would retain the two dimensions until the one-column check. The straightforward adapter still makes a transport copy followed by the creator's ownership copy; reducing that requires an explicit ownership design, and no Python view may outlive the managed pin. The experiment remains outside production code.

It also changes the input contract: Excel's typed conversion can turn blanks into zero, booleans into numbers and numeric text into numbers before our code sees them. The original cell kinds cannot then be recovered. It cannot silently replace the strict `NumberColumn` behavior promised above. See the [Excel-DNA marshalling reference](https://excel-dna.net/reference-data-type-marshalling/) for supported CLR input types.

Revisit only if profiling a representative workbook shows input transport materially limits the required workload. Any proposal must weigh measured end-to-end benefit against maintenance cost and explicitly resolve the coercion and ownership contracts. It would be a separate seam/host change, not part of building this creator.
