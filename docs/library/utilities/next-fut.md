# util_NextFut

Built in #129.

Gives the contract after the one given, the next month in the exchanges' sequence: `G26` after `F26`, `F27` after `Z26`. Text in and text out, no object and no handle: a desk that holds one contract code in a cell gets the following month's code in the next, to label the second column of a strip or to walk a schedule a month at a time. The code is read for its month and its year, which no other function does: the schedules keep their codes as labels and never read them, and so do the fixings, the calendar and the market; this helper and its sibling [util_FutToCme](fut-to-cme.md) are the two places a code's letters mean something, and they take one form only. The code is `src/catalyst/index_definitions/contract_codes.py`, the reading and the two functions over it, and `src/catalyst/excel/utilities.py`, the worksheet function.

## Worksheet contract

```python
def util_NextFut(contract: str) -> str: ...
```

| | A | B |
|---|---|---|
| 1 | F26 | `=util_NextFut(A1)` shows `G26` |
| 2 | Z26 | `=util_NextFut(A2)` shows `F27` |
| 3 | m26 | `=util_NextFut(A3)` shows `n26` |
| 4 | Cal27 | `=util_NextFut(A4)` shows `#ERROR util_NextFut: ValueError: contract is 'Cal27', expected a month letter and a two-digit year, such as F26` |

One argument, required: a contract code as text, typed in the formula, `=util_NextFut("F26")`, or in a cell. The seam checks that it is text, one cell and not a range, not empty, as [inputs.md](../../seam/inputs.md) says of a text scalar, and refuses anything else in its own words, `contract is number 26.0, expected text`; nothing here restates that. The result is text, as [outputs.md](../../seam/outputs.md) sends text: the next code, in the case the given code's letter was typed in, so a schedule spelled `m26`, `n26` walks on in lowercase and one spelled `V26`, `X26` in capitals.

## Excel help

Quoted from the declaration in `src/catalyst/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Gives the next contract in the monthly sequence, G26 after F26 and F27 after Z26, spelled as the code given. |
| `contract` | One contract code, a month letter and a two-digit year such as F26, typed or in a cell such as A2. |

## The library checks

Two rules, the first failure being the message. A code is one month letter and two digits, nothing before, between or after: the twelve letters are the exchanges' month codes, `F G H J K M N Q U V X Z` for January to December, in capitals or in lowercase, and the digits name the year after 2000, since the desk's codes are of this century. Three looks at three characters decide it, no pattern and no trimming: a calendar strip, `Cal27`, a season, `W29`, a quarter, `Q1 27`, a four-digit year, `F2026`, a space at either end and `I`, which the exchanges skip, are all refused naming what arrived, since a strip has no one next month and another spelling is another spelling. The owner asked for single contracts alone, the next contract of a strip being ambiguous. And December 2099 has no next that two digits can name: `Z99` is refused rather than wrapped to `F00`, which would read as January 2000.

| Rule | Message |
|---|---|
| one month letter and two digits | `contract is 'Cal27', expected a month letter and a two-digit year, such as F26` |
| a month before December 2099 | `contract is 'Z99', expected a month before December 2099, the last a two-digit year can name` |

Nothing else is checked: the code is not held to any schedule, since no schedule is given, and whether the next month is a listed contract of some index is that index's schedule's business, read through the calendar. The letter's case is kept as given and the digits are written back as two, `F00` after `Z99` never arising and `G00` after `F00` the year 2000's.

## Tests

The library's examples and property are `tests/unit/test_contract_codes.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| each of the twelve months to the next, December to the next January, across a decade and into the last year two digits name; a lowercase code to a lowercase code; the year 2000 | example |
| a strip, a season, a quarter, a four-digit year, a one-digit year, a letter alone, a year alone, the year before the letter, a space at either end, a hyphen, `I`, a letter that is no month, two letters, a letter among the digits and a digit from another script: refused naming what arrived | example |
| `Z99` and `z99`: refused, no next that two digits can name | example |
| from any month and any year in either case, twelve steps are one year, each step one month on by the code read back and by the CME month | property |
| the next contract through the seam, in capitals and in lowercase; a strip, a four-digit year and `Z99` in the library's words; left out, blank, empty text, a number, a boolean and a range in the seam's | example, through the seam |
| nine calls across nine functions and no numpy call; a peak within the slack, measured 192 to 232 bytes, and nothing published | budget |
| `F26` to `G26`, `Z26` to `F27` and the schedule's `m26` to `n26` in a real workbook, with a strip, `Z99`, a number, a blank and empty text refused | Excel smoke |

## Not here

The next contract of a strip or a season, `Cal27` or `W29`, and any reading of such labels: refused, by the owner's call, since the next of a strip is ambiguous. The contract after this one in a given index's schedule, which may skip months: the schedule's, read through [util_ReadHandle](read-handle.md). A step of more than one month, a step back, and a four-digit year. Whether the exchange lists the month given: nobody's here, a code being a label the desk types. Reading a code anywhere else: the schedules, the fixings, the calendar and the market keep their codes as labels and never read them, and this helper does not change that.
