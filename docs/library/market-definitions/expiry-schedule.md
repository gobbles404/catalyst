# CreateExpirySchedule

Open: D26, D27, D33.

The contract months of one index: each contract's code, the day its future expires and, for an index that has options, the day its option expires, retained and reached by handle. Why these choices, and what they cost, is [decisions.md](../decisions.md#market-definitions), D30 to D33. Nothing here reads the schedule yet; the first consumer, the function that says which contract is prompt on a given date, is not specified.

## Worksheet contract

```python
def CreateExpirySchedule(
    future_code: TextColumn,
    futures_expiry: DateColumn,
    options_expiry: DateColumn | None = None,
) -> Handle[ExpirySchedule]: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | future_code | futures_expiry | options_expiry |
| 2 | m26 | 19-May-2026 | 14-May-2026 |
| 3 | n26 | 22-Jun-2026 | 16-Jun-2026 |
| 4 | q26 | 21-Jul-2026 | 16-Jul-2026 |
| 5 | u26 | 20-Aug-2026 | 17-Aug-2026 |
| 6 | V26 | 22-Sep-2026 | 17-Sep-2026 |
| 7 | X26 | 20-Oct-2026 | 15-Oct-2026 |
| 8 | `=CreateExpirySchedule(A2:A7, B2:B7, C2:C7)` | shows `expiry_schedule:3f9a1c:000004` |
| 9 | `=CreateExpirySchedule(A2:A7, B2:B7)` | shows `expiry_schedule:3f9a1c:000005`, an index with no options |

The input is three columns of one kind each (D30), selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The first two are required. The third is left out for an index that has no options, and a formula that leaves it out is what the seam cannot yet declare: an optional argument today takes a default value of its type, and this one takes nothing (D33). The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and arrays of days; nothing here restates that. It never compares two arguments, so whether the columns agree is the library's first check. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[ExpirySchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule. What is still open about handles, release above all, is [handles.md](../../seam/handles.md) and D26.

This is the first function to take columns of one kind without headers, the case [inputs.md](../../seam/inputs.md) decision 38 left to the next few functions. Its cost is D21's: two columns can be selected one row out of step, `A2:A7` beside `B3:B8`, and equal lengths cannot catch it. On most sheets the cell past the table's edge is blank, and a blank fails; the two date columns passed in each other's place fail on the last rule below.

## Excel help

The lines go beside each parameter in the declaration when the function is built, as [conventions.md](../conventions.md#excel-help) says, and `tests/unit/test_help.py` pins them.

| Item | Text |
|---|---|
| Function | Creates an expiry schedule from the contract codes of one index and their expiry dates, and shows its handle, the text other formulas take as the schedule. |
| `future_code` | The column of contract codes, such as A2:A7 holding m26 to X26, one per contract and each once. |
| `futures_expiry` | The column of futures expiry dates beside the codes, such as B2:B7, one per code and each later than the one above. |
| `options_expiry` | The column of options expiry dates beside the codes, such as C2:C7, one per code and each on or before its futures expiry. |

Registration shows the third as `[options_expiry]`. What it adds after that sentence for an argument that takes nothing when left out is the seam's to decide with D33; the line is written as if the argument were required, as every line is.

## The library checks

The checks consume the seam's tuple and arrays; cell kinds, shapes and date conversion are the seam's and are not repeated here. Rows count as the sheet counts them, the first row of a selection being row 1, and each message names the column by its parameter name, because no sheet address crosses. Every rejection raises `ValueError` (D29). The checks run in this order, and the first failure is the message: the counts first, because nothing else can be read row against row until they agree.

| Rule | Message |
|---|---|
| every column has one row per code; the seam never compares two arguments | `futures_expiry has 5 dates, expected 6, one per future_code` |
| the same for the options column, when given | `options_expiry has 7 dates, expected 6, one per future_code` |
| codes are given once each, without regard to case (D31); the row named is the second | `future_code row 4 is 'Q26', already given as 'q26' at row 3` |
| futures expiries strictly increase down the column (D32) | `futures_expiry row 3 is 2026-06-22, expected a date after row 2's 2026-07-21` |
| options expiries strictly increase down the column (D32) | `options_expiry row 3 is 2026-06-16, expected a date after row 2's 2026-07-16` |
| each options expiry is on or before the futures expiry of its own row, the same day allowed (D32) | `options_expiry row 2 is 2026-06-25, expected a date on or before futures_expiry row 2's 2026-06-22` |

Nothing is sorted, trimmed, re-cased or dropped; a code is kept exactly as typed, `m26` and `V26` alike, and `m26` beside `M26` is one code given twice. A one-row schedule is a schedule: a single cell fits a column type as a 1×1 range. A failed call publishes nothing.

## In memory

Received, per [bridge.md](../../seam/bridge.md#the-declared-input-types): `future_code` as the host's tuple of texts, `futures_expiry` and `options_expiry` as flat arrays of numpy days, and `options_expiry` as nothing when the argument was left out, in the form D33 settles. Retained, after the checks pass:

| Field | Representation |
|---|---|
| `codes` | `tuple[str, ...]`, length `N`, as typed; the seam's tuple is immutable already |
| `futures_expiry` | `NDArray[np.datetime64]`, dtype `datetime64[D]`, shape `(N,)`, a copy, read-only |
| `options_expiry` | the same, or `None` for an index with no options |

The three align by position: `codes[i]`, `futures_expiry[i]` and `options_expiry[i]` describe one contract. The date arrays are copied, because a Python caller keeps whatever it passed, and frozen, so a later change to an input never changes a schedule. The date checks are vectorized; the codes are text, so their uniqueness is one pass over the tuple, as the seam's own scan of a text range is. No index from code to row is built: the first consumer that looks a code up decides what it needs. The schedule is held in the seam's store until Excel closes; release is D26.

## Counted work

None. The builder converts nothing, the seam converted the dates, copies two small arrays, and does no numeric work beyond the comparisons above. It takes no `WorkCounter` (D27, deferred by the owner); its work is pinned at the seam as the creators' is: a ledger in `tests/performance/test_seam_budgets.py`, a text column and two date columns in, the builder and one publication out, and a ceiling in `tests/performance/test_seam_allocation.py`, both measured when built.

## Tests

| Case | Kind |
|---|---|
| the six-row sample above: every code and both dates preserved, aligned, as typed | example |
| the same with `options_expiry` left out: the other two preserved, options retained as none | example |
| a one-row schedule accepted | example |
| a futures column one row short, and an options column one row long: rejected, naming both counts | example |
| `q26` given twice, and `q26` beside `Q26`: rejected as one code, naming both rows | example |
| two futures expiries equal, and two reversed: rejected, not sorted | example |
| two options expiries equal, and two reversed: rejected | example |
| an options expiry one day after its futures expiry: rejected; on the same day: accepted | example |
| for any `N` codes and any two strictly increasing date columns with each option on or before its future, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, and its arrays refuse writes | example |
| a failed construction publishes no object and no handle | example, with handles |
| a blank cell in the options column fails in the seam's words, not as an argument left out | example, through the seam |
| the creator's handle with and without options, and its failures, in a real workbook | Excel smoke |

The message texts above are pinned by the examples, and the seam's own texts for a wrong cell or shape are the seam's tests, not these.

## Open

| | |
|---|---|
| An argument that may be left out, with nothing in its place: what the seam needs before this is built | D33 |
| Release of the schedule when its creator is deleted or its workbook closes, and reuse on an unchanged recalculation | D26 |
| How a work counter reaches this code | D27 |

## Not here

Which contract is prompt on a given date, and the roll rule that says whether a contract is still prompt on its own expiry day: the first consumer's job. Business-day adjustment (D1). What a code means: `m26` is text, never read as a month and a year. The index's name, its exchange, its units, tick size, first notice, last delivery, settlement. A temporary reader: the handle path is proven, and a second kind adds no seam code. Market data, pricing.
