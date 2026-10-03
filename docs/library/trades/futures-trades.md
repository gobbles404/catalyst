# _CreateFuturesTrades

Built locally; first trade-ingestion iteration.

One immutable record of one or many consummated futures trades. The index and a named
contract specification are shared; each row supplies the deal's remaining terms. The agreed
trade price is static. No current market prices enter this record.

## Worksheet contract

```python
def _CreateFuturesTrades(
    index: Handle[Index],
    contract_specification: str,
    header_row: TextRow,
    table: FuturesTradesTable,
) -> Handle[FuturesTrades]: ...
```

The [example workbook](../../../outputs/ng-trade-ingestion/ng-futures.xlsx) has a trade sheet
and a shared contract sheet. Open it with the current add-in and rebuild its handles:

```powershell
.\tools\excel_dev.ps1 outputs\ng-trade-ingestion\ng-futures.xlsx
```

On **NG Trades**, C6 references the Henry Hub NYMEX index; C7 selects its `NYMEX NG`
specification. That specification holds 10,000 MMBTU per lot. The index conventions hold
USD/MMBTU for prices. The workbook's trade prices and zero fees are illustrative.

| trade_id | trade_date | contract_code | signed_lots | trade_price |
|---|---|---|---:|---:|
| NG-001 | 24-Sep-2026 | Z26 | 10 | 3.100 |
| NG-002 | 24-Sep-2026 | Z26 | -4 | 3.150 |
| NG-003 | 25-Sep-2026 | F27 | 7 | 3.400 |
| NG-004 | 25-Sep-2026 | F27 | -12 | 3.350 |

The headers occupy B11:F11, the rows B12:F15. Both formulas call the same function:

```excel
=_CreateFuturesTrades(C6,C7,B11:F11,B12:F12)
=_CreateFuturesTrades(C6,C7,B11:F11,B12:F15)
```

Each shows `futures_trades:Henry Hub NYMEX:<count>`, a session handle whose trailing count is
the publication number, **not the number of trades**. C19 holds the single-row handle; C27
holds the four-row handle. `=util_ReadHandle(C19)` and `=util_ReadHandle(C27)` show their
contents at B21 and B29. The reader adds `contract_position`, the zero-based position in the
shared schedule: Z26 is 0, F27 is 1. It is not a position in a market price vector.

The seam checks the declared types and aligned table shape using the existing
[input rules](../../seam/inputs.md). Headers bind by name, in any order and case. Dates must
be Excel date cells, numbers numeric cells, and all five fields filled. Body text is kept
exactly as entered, including the case of contract codes.

| Field | Stored type | Meaning |
|---|---|---|
| `trade_id` | tuple of text | Label identifying the deal for review; duplicates are retained, not used as a deduplication key |
| `trade_date` | `datetime64[D]` array | Date the deal was consummated |
| `contract_code` | tuple of text | Exact code in the supplied index's futures schedule |
| `signed_lots` | `float64` array | Whole nonzero lots: positive buy, negative sell |
| `trade_price` | `float64` array | Agreed deal price in the index's quote units |

## Excel help

Quoted from `src/goosedove/excel/trades.py`:

| Item | Text |
|---|---|
| Function | Creates static futures trades from one or many rows of agreed deal terms and shows their handle, the text other formulas take as the trades. |
| `index` | The index handle from _CreateIndex, such as B3, shared by all trades in this table. |
| `contract_specification` | The specification name within that index, such as NYMEX NG, shared by all trades. |
| `header_row` | The header cells, such as A7:E7, reading trade_id, trade_date, contract_code, signed_lots and trade_price in any order. |
| `table` | The rows under the headers, such as A8:E11, one deal per row with positive lots for buys and negative lots for sells. |

## The library checks

In order: a futures index, a specification belonging to it, unambiguous schedule codes,
membership of each traded code, whole lots, then nonzero lots. Examples of the messages:

```text
index is 'IFERC', expected a futures index
contract_specification is 'ICE NG', expected a name in the index's specifications
index schedule has duplicate contract codes, expected each code once
contract_code row 2 is 'G27', expected a code in the index's schedule
signed_lots row 2 is -0.5, expected a whole number
signed_lots row 2 is 0.0, expected nonzero lots
```

Row numbers count from the first row of the supplied body. A failure publishes no object.
Prices may be zero or negative and are never rounded to a tick. No rule compares trade dates
with today, expiry or a valuation date in this iteration.

## The NumPy representation

```text
index                   -> existing immutable Index
specification_position  -> 0 (NYMEX NG in that index's specifications)
trade_ids               -> ("NG-001", "NG-002", "NG-003", "NG-004")
contract_codes          -> ("Z26", "Z26", "F27", "F27")
trade_dates             -> [2026-09-24, 2026-09-24, 2026-09-25, 2026-09-25]  datetime64[D]
contract_positions      -> [0, 0, 1, 1]                                  intp
signed_lots             -> [10, -4, 7, -12]                              float64
trade_prices            -> [3.100, 3.150, 3.400, 3.350]                   float64
```

Every array has shape `(N,)`, including `(1,)`. These are aligned columns, not one Python
object per trade and not a mixed object-dtype matrix. The numeric/date columns own read-only
storage; the index and text tuples are retained by reference. Editing the worksheet creates
new trade contents and cannot mutate an already retained object through a reused input buffer.

Code binding is one static text lookup per occurrence. Numerical consumers can later use
the resulting integer positions. Reading the handle does not bind codes again. No trade is
sorted, merged or netted; input order and repeated occurrences survive.

The four retained arrays use 32 bytes per trade on the required 64-bit runtime, excluding
text, shared objects, array headers and Excel input/output buffers. The budget tests compare
one and 10,000 rows, count creator/publication/reader work, and bound peak temporary memory.
This establishes ingestion behavior; it does not establish pricing speed.

## Tests

| Evidence | Where |
|---|---|
| Worked four-deal example, signs, contract binding, input ownership, errors | `tests/unit/test_futures_trades.py` |
| Property: any row alone equals that row within its batch, with the same dtypes and rank | `tests/unit/test_futures_trades.py` |
| Full Excel seam roundtrip, reordered headers, duplicate rows, blank/type failures | `tests/unit/test_excel_trades.py` |
| One and 10,000 rows: same batch path, one binding pass, linear memory | `tests/performance/test_futures_trades_budgets.py` |
| Actual Excel formulas for single/batch equality, readback and semantic errors | `tools/excel_smoke.ps1` |

## Not here

Market lookup, valuation, Greeks, settlement cash and margin, rates, aggregation, strips,
averaging and mixed-index batches. There is no new template engine: the existing index and
named specification supply the shared fields for this experiment. A schedule of kind
`futures` is this creator's current boundary; it is not yet a classification of every listed
futures product. Physical settlement behavior and clearing-firm details await the next
iteration that uses them.
