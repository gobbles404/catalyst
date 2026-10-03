# util_StartDate

Built in #129.

Gives the first calendar day of a contract or strip from its label: 1 January 2026 for `F26`, 1 January 2027 for `1Q27`, 1 November 2029 for `W29`, and the first day of the left label of `F26-Z28`. Text in and one date out, no object and no handle; the cell holds a date the sheet formats, as every date the seam sends. It derives a date from a label and reads no object, so it is no `util_Read*` function, as [conventions.md](../conventions.md) divides them. These are period boundaries, the days a label covers from and to: a contract's expiry, an index's publication day and a payment day are facts the [schedules](../index-definitions/futures-schedule.md) supply, and nothing here is one. This page holds the grammar the two functions share; [util_EndDate](end-date.md) gives the last day through the same reading. The code is `src/goosedove/index_definitions/periods.py`, the reading and the two days, and `src/goosedove/excel/utilities.py`, the worksheet functions.

## Worksheet contract

```python
def util_StartDate(period: str) -> Date: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | f26 | `=util_StartDate(A1)` shows `46023`, 1-Jan-2026 once formatted | `=util_EndDate(A1)` shows `46053`, 31-Jan-2026 |
| 2 | 1Q27 | `46388`, 1-Jan-2027 | `46477`, 31-Mar-2027 |
| 3 | CAL28 | `46753`, 1-Jan-2028 | `47118`, 31-Dec-2028 |
| 4 | W29 | `47423`, 1-Nov-2029 | `47573`, 31-Mar-2030 |
| 5 | w28-w29 | `47058`, 1-Nov-2028 | `47573`, 31-Mar-2030 |
| 6 | Z28-F26 | `#ERROR util_StartDate: ValueError: period is 'Z28-F26', expected range endpoints in chronological order` | the same from `util_EndDate` |

One argument, required: the label as text, typed in the formula, `=util_StartDate("f26")`, or in a cell, which the seam checks as it checks any text scalar, as [inputs.md](../../seam/inputs.md) says, refusing a number, a blank, empty text and a range in its own words, `period is number 46023.0, expected text`; nothing here restates that. The result is a date, which goes out as its serial, as [outputs.md](../../seam/outputs.md) says, so a fresh cell shows `46023` until it is formatted once.

## Excel help

Quoted from the declaration in `src/goosedove/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Gives the first calendar day of a contract or strip, 1-Jan-2026 for F26, 1-Nov-2029 for W29 and the first day of the left label of F26-Z28. |
| `period` | One contract or strip label, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28, typed or in a cell such as A2. |

## The grammar

A label is one of five forms, or two of them joined by one hyphen. The letters are read in either case, `f26`, `F26`, `cal28` and `Cal28` alike, by the owner's decision for these functions, recorded in [time.md](../time.md); the year is exactly two digits and means 2000 to 2099, the library's fixed horizon, never a decade inferred or today's date consulted.

| Form | Means | Such as | First day | Last day |
|---|---|---|---|---|
| a month letter and two digits | one calendar month | `F26` | 1-Jan-2026 | 31-Jan-2026 |
| a quarter number, `Q` and two digits | a calendar quarter, `1Q` January to March, `2Q` April to June, `3Q` July to September, `4Q` October to December | `1Q27` | 1-Jan-2027 | 31-Mar-2027 |
| `CAL` and two digits | a calendar year | `CAL28` | 1-Jan-2028 | 31-Dec-2028 |
| `W` and two digits | a winter, November of that year to the March after | `W29` | 1-Nov-2029 | 31-Mar-2030 |
| `S` and two digits | a summer, April to October of that year | `S28` | 1-Apr-2028 | 31-Oct-2028 |
| two labels joined by `-` | every day from the left label's first to the right label's last | `F26-Z28` | 1-Jan-2026 | 31-Dec-2028 |
| two seasonal labels joined by `-` | the same rule, the months between included | `W28-W29` | 1-Nov-2028 | 31-Mar-2030 |

The month letters are the exchanges', `F G H J K M N Q U V X Z` for January to December, the same twelve [util_NextFut](next-fut.md) reads; `Q27` alone is August 2027, a month, since a quarter leads with its number. A winter is labelled by the year it starts in and runs `X` to `H`, five months; a summer runs `J` to `V`, seven; both as CME describes its natural-gas strips. A winter may end in the next century: `W99` runs to 31 March 2100 and never wraps to 2000.

A range covers every calendar day between its ends, so `W28-W29` includes the summer of 2029 and is not two winters. Its right label may start and end no earlier than its left, so that a range can never cut off part of either end unnoticed: `F26-F26` is January 2026, `1Q27-CAL27` is all of 2027, `Z28-F26` is refused, and so is `CAL28-F28`, whose right end finishes before its left does. Nothing is sorted or swapped.

## The library checks

Two rules, the first failure being the message, and both functions run them over the whole expression, so asking for a start cannot hide an end that is no label.

| Rule | Message |
|---|---|
| each label is one of the forms, with a two-digit year | `period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28` |
| a range's right end starts and ends no earlier than its left | `period is 'Z28-F26', expected range endpoints in chronological order` |

The first rule refuses a space anywhere, `Q1 27` and `F26 -Z28`; a year of one or four digits, `W8` and `F2026`; a quarter that is not 1 to 4; an empty end of a range, `F26-`; a second hyphen; `I`, which the exchanges skip; and any other word, `Jan26`. The message names the whole expression as it arrived. Nothing else is checked: a label is not held to any schedule, and whether an exchange lists the month is nobody's business here.

## The reading

Each label is read for two months, numpy's month unit: its first month and the month after its last, built from the year and the form's first month and length, three for a quarter, twelve for a year, five for a winter and seven for a summer, one `np.timedelta64` in months each. The first day is the first month as a day, one conversion, and the last day is the day before the month after begins, one conversion and one day subtracted, so February's length in a leap year, a winter's March in the next year and `W99`'s in the next century fall out of numpy with no leap-year or month arithmetic written here. No array of months or days is made, nothing is cached and nothing is published: the work and the bytes are the same for one month and for the whole century, as the pins below say.

## Tests

The library's examples and properties are `tests/unit/test_periods.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| every example in the grammar's table, in lowercase, capitals and mixed case: the first and the last day each | example |
| the twelve month letters in either case, each one month long; `Q27` is August and `3Q27` the third quarter | example |
| February 2000 and 2028, leap years, and 2027; `W99`, ending in 2100; `Z99`; the whole horizon as `f00-cAL99` | example |
| one-digit years, a four-digit year, a space anywhere, a fifth and a zeroth quarter, an empty end, two hyphens, three labels, a month by name, `I`, a letter that is no month, `CA`, `CALS`, `WS`, a letter or a year alone: refused by both functions, naming the whole expression | example |
| `Z28-F26`, `CAL28-F28`, two months the wrong way round, a winter then the summer that began before it, a summer then the quarter before it, a year then the quarter before it: refused by both functions | example |
| for any month of the horizon in either case: its first day, its last the day before the next month's first, 28 to 31 days; and the range from it to any month on or after it, the left's start and the right's end | property |
| for any year: a quarter is three months, a year twelve, a winter five from November, a summer seven from April; `1Q` to `CAL` of a year is the year, a later quarter to it refused | property |
| the first and last days through the seam as serials, a month, a quarter, a year, a winter, a summer, a range and `W99`; a malformed label and a reversed range refused by both in the library's words; left out, blank, empty text, a number and a range of cells in the seam's | example, through the seam |
| eleven calls across eleven functions for one label, twelve for a range, one numpy conversion of the library's and the seam's way out for a date; a peak of 1,264 bytes for a month and for the whole century alike, within twice the slack, and nothing published | budget |
| the schedule's own `m26`, a quarter, a year, a winter across the year end, a summer and two ranges in a real workbook, with a malformed label, a reversed range, a number and a blank refused | Excel smoke |

## Not here

A contract's expiry, an index's publication day, a payment day and anything else a schedule supplies: the [schedules](../index-definitions/futures-schedule.md)', read through [util_ReadHandle](read-handle.md). Building a schedule from a strip, pricing a strip, weighting its months and checking a market covers it: separate work, not these functions'. Aliases, `Jan26`, `Cal 28`, `Win29`, a year of four digits, a label with a space: refused, one spelling per form. Sorting or swapping the ends of a range. The schedule creators reading their codes: unchanged, their codes still labels, as [time.md](../time.md) records.
