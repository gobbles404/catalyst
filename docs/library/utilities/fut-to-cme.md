# util_FutToCme

Built in #129.

Gives the contract month as CME's data feeds spell it, the year then the month, two digits for the month: `202601` for `F26`, `202612` for `Z26`. Text in and text out, no object and no handle: the desk builds the symbols its RTD formulas take from the codes it already holds, instead of typing each month twice. It reads a code for its month and year as [util_NextFut](next-fut.md) does, through the same reading and the same rules, and takes the same one form, a month letter and a two-digit year. The code is `src/catalyst/index_definitions/contract_codes.py`, the reading and the function over it, and `src/catalyst/excel/utilities.py`, the worksheet function.

## Worksheet contract

```python
def util_FutToCme(contract: str) -> str: ...
```

| | A | B |
|---|---|---|
| 1 | F26 | `=util_FutToCme(A1)` shows `202601` |
| 2 | Z26 | `=util_FutToCme(A2)` shows `202612` |
| 3 | u26 | `=util_FutToCme(A3)` shows `202609` |
| 4 | W29 | `=util_FutToCme(A4)` shows `#ERROR util_FutToCme: ValueError: contract is 'W29', expected a month letter and a two-digit year, such as F26` |

One argument, required: a contract code as text, typed in the formula or in a cell, which the seam checks as it checks any text scalar, as [inputs.md](../../seam/inputs.md) says, refusing a number, a blank, empty text and a range in its own words; nothing here restates that. The result is text and not a number, `202601` and never `202,601`, so the cell is ready to be joined into a feed's symbol, as [outputs.md](../../seam/outputs.md) sends text. The letter is read in either case, `u26` and `U26` naming one month, since the digits out carry no case.

## Excel help

Quoted from the declaration in `src/catalyst/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Gives the contract month as CME's data feeds spell it, the year then the month, 202601 for F26. |
| `contract` | One contract code, a month letter and a two-digit year such as F26, typed or in a cell such as A2. |

## The library checks

One rule, the reading's: a code is one month letter and two digits, nothing before, between or after, the twelve letters `F G H J K M N Q U V X Z` for January to December in either case and the digits the year after 2000, as [util_NextFut](next-fut.md) says in full. A strip, a season, a four-digit year, a space and a letter that is no month are refused naming what arrived.

| Rule | Message |
|---|---|
| one month letter and two digits | `contract is 'W29', expected a month letter and a two-digit year, such as F26` |

`Z99` has a month to name, `209912`, and is taken; only its next is not. Nothing else is checked: the code is not held to any schedule, and whether CME lists the month, or spells its symbol with these six digits for the product in hand, is the feed's business, which this helper does not read.

## Tests

The library's examples and property are `tests/unit/test_contract_codes.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| January, February with its leading zero, April as `J`, September as `U`, October as `V`, November as `X`, December; a lowercase code the same month; the year 2000 and `Z99`: text each | example |
| every code that is no single contract, the strip, the season, the four-digit year and the rest: refused naming what arrived, the same message as the next contract's | example |
| from any month and any year, the next contract's month is one more than this one's, December to January included | property |
| the month through the seam, in capitals and in lowercase, and text in the cell; a strip and a four-digit year in the library's words; left out, blank, empty text, a number, a boolean and a range in the seam's | example, through the seam |
| nine calls across nine functions and no numpy call; a peak within the slack, measured 234 bytes, and nothing published | budget |
| `F26` to `202601` and the schedule's `V26` to `202610` in a real workbook, a season, a blank and empty text refused | Excel smoke |

## Not here

The product's root beside the month, `CL` or `NG`, and the whole symbol a feed takes: the desk's formula joins them, this helper giving the month alone. Reading the symbol back into a code, a strip's months, and a four-digit year in: refused or absent, as [util_NextFut](next-fut.md) says. Whether a month is listed, and any price: the market's, through handles, never through a feed's symbol here.
