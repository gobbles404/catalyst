# CreateExpirySchedule

Open: D30.

The contract months of one index: each contract's code, the day its future expires and, for an index that has options, the day its option expires, kept as given and reached by handle. It waits on one seam item, D30. Nothing reads the schedule yet; the first consumer, the function that says which contract is prompt on a given date, is not specified.

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

Three columns of one kind each, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The owner chose columns over a table to put the typed columns through a real function, and the third column can be left out, which a table cannot do; the cost, as D21 recorded it, is that two columns can be selected one row out of step and equal lengths cannot catch it. This is the first function to take columns of one kind without headers, the case [inputs.md](../../seam/inputs.md) decision 38 left to the next few functions. The third argument is left out for an index that has no options, and that is what the seam cannot yet declare: an optional argument today takes a default value of its type, and this one takes nothing (D30). The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and arrays of days; nothing here restates that. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[ExpirySchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule.

## Excel help

The lines go beside each parameter in the declaration when the function is built, as [conventions.md](../conventions.md#excel-help) says, and `tests/unit/test_help.py` pins them.

| Item | Text |
|---|---|
| Function | Creates an expiry schedule from the contract codes of one index and their expiry dates, and shows its handle, the text other formulas take as the schedule. |
| `future_code` | The column of contract codes, such as A2:A7 holding m26 to X26, one per contract. |
| `futures_expiry` | The column of futures expiry dates beside the codes, such as B2:B7, one per code. |
| `options_expiry` | The column of options expiry dates beside the codes, such as C2:C7, one per code. |

Registration shows the third as `[options_expiry]`. What it adds after that sentence for an argument that takes nothing when left out is the seam's to decide with D30; the line is written as if the argument were required, as every line is.

## The library checks

One rule: the columns have one row per code, because the seam never compares two arguments and a schedule is rows. Every rejection raises `ValueError`.

| Rule | Message |
|---|---|
| every column given has one row per code | `futures_expiry has 5 dates, expected 6, one per future_code` |

Nothing else is checked. The codes are kept as typed, `m26` and `V26` alike, the dates as given, in the order given. What a schedule must look like for a reader to use it, whether codes repeat, whether dates increase, how an option's expiry sits against its future's, is that reader's rule, written when the reader is. A one-row schedule is a schedule. A failed call publishes nothing.

## In memory

Received, per [bridge.md](../../seam/bridge.md#the-declared-input-types): `future_code` as the host's tuple of texts, `futures_expiry` and `options_expiry` as flat arrays of numpy days, and `options_expiry` as nothing when the argument was left out, in the form D30 settles. Retained:

| Field | Representation |
|---|---|
| `codes` | `tuple[str, ...]`, length `N`, as typed |
| `futures_expiry` | `NDArray[np.datetime64]`, dtype `datetime64[D]`, shape `(N,)`, a copy, read-only |
| `options_expiry` | the same, or `None` for an index with no options |

The three align by position: `codes[i]`, `futures_expiry[i]` and `options_expiry[i]` describe one contract. The date arrays are copied, because a Python caller keeps whatever it passed, and frozen, so a later change to an input never changes a schedule. The schedule is held in the seam's store until Excel closes.

## Counted work

None. The builder converts nothing and copies two small arrays. It takes no `WorkCounter` (D27); its work is pinned at the seam as the creators' is, a ledger in `tests/performance/test_seam_budgets.py` and a ceiling in `tests/performance/test_seam_allocation.py`, both measured when built.

## Tests

| Case | Kind |
|---|---|
| the six-row sample above: every code and both dates preserved, aligned, as typed | example |
| the same with `options_expiry` left out: the other two preserved, options retained as none | example |
| a one-row schedule accepted | example |
| a futures column one row short, and an options column one row long: rejected, naming the count | example |
| for any `N` codes and any two columns of `N` dates, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, and its arrays refuse writes | example |
| a failed construction publishes no object and no handle | example, with handles |
| a blank cell in the options column fails in the seam's words, not as an argument left out | example, through the seam |
| the creator's handle with and without options, and a column one row short, in a real workbook | Excel smoke |

## Open

| | |
|---|---|
| An argument that may be left out, with nothing in its place: what the seam needs before this is built | D30 |

## Not here

Which contract is prompt on a given date, and the roll rule that says whether a contract is still prompt on its own expiry day: the first consumer's job, with whatever it needs a schedule to hold true. Business-day adjustment: every date in the library is a calendar day. What a code means: `m26` is text, never read as a month and a year. The index's name, its exchange, its units, tick size, first notice, last delivery, settlement. A temporary reader: the handle path is proven, and a second kind adds no seam code. Market data, pricing.
