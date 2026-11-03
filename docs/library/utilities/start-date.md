# util_StartDate

Built in #129; the balance of a period, a `BAL` label, in #160, from a reference date, and since #173 from a valuation-date handle, the later of its day and the label's first; the ticket is [date-helper-inputs.md](../../engineering-tickets/trade-valuation-pipeline/date-helper-inputs.md).

Gives the first calendar day of a contract or strip from its label: 1 January 2026 for `F26`, 1 January 2027 for `1Q27`, 1 November 2029 for `W29`, and the first day of the left label of `F26-Z28`; since #160, the first day of the balance of any of these, `BALZ26`, which since #173 is the later of the valuation day, read off the valuation-date handle given, and the label's first day, so that a future period is the whole period and a current one runs from the day itself, and a period that ended before the day is refused. Text and a handle in and one date out, no object made; the cell holds a date the sheet formats, as every date the seam sends. It derives a date from a label and reads the handle for its day alone, making nothing, so it is no `util_Read*` function, as [conventions.md](../conventions.md) divides them. These are period boundaries, the days a label covers from and to: a contract's expiry, an index's publication day and a payment day are facts the [schedules](../index-definitions/futures-schedule.md) supply, and nothing here is one. This page holds the grammar the two functions share; [util_EndDate](end-date.md) gives the last day through the same reading. The code is `src/catalyst/index_definitions/periods.py`, the reading and the two days, which take the day and never the handle, and `src/catalyst/excel/utilities.py`, the worksheet functions, which read the day off the handle the seam resolved.

## Worksheet contract

```python
def util_StartDate(period: str, valuation_date: Handle[ValuationDate] | None = None) -> Date: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | | `=_CreateValuationDate(DATE(2026,10,12),0)` shows `30512:valuation_date:3`, 12 October 2026 | |
| 2 | f26 | `=util_StartDate(A2)` shows `46023`, 1-Jan-2026 once formatted | `=util_EndDate(A2)` shows `46053`, 31-Jan-2026 |
| 3 | 1Q27 | `46388`, 1-Jan-2027 | `46477`, 31-Mar-2027 |
| 4 | CAL28 | `46753`, 1-Jan-2028 | `47118`, 31-Dec-2028 |
| 5 | W29 | `47423`, 1-Nov-2029 | `47573`, 31-Mar-2030 |
| 6 | w28-w29 | `47058`, 1-Nov-2028 | `47573`, 31-Mar-2030 |
| 7 | Z28-F26 | `#ERROR util_StartDate: ValueError: period is 'Z28-F26', expected range endpoints in chronological order` | the same from `util_EndDate` |
| 8 | balv26 | `=util_StartDate(A8,$B$1)` shows `46307`, 12-Oct-2026, the valuation day, inside October | `=util_EndDate(A8,$B$1)` shows `46326`, 31-Oct-2026 |
| 9 | BALX26 | `=util_StartDate(A9,$B$1)` shows `46327`, 1-Nov-2026, the whole of a month still to come | `46356`, 30-Nov-2026 |
| 10 | balf26 | `=util_StartDate(A10,$B$1)` shows `#ERROR util_StartDate: ValueError: valuation_date is 2026-10-12, after 'balf26' ended on 2026-01-31, expected a valuation day on or before the period's last day` | the same from `util_EndDate` |
| 11 | BALZ26 | `=util_StartDate(A11)` shows `#ERROR util_StartDate: ValueError: valuation_date is missing, expected a valuation-date handle with 'BALZ26', whose day starts the balance of a period` | the same from `util_EndDate` |

Two arguments. The label, required, as text, typed in the formula, `=util_StartDate("f26")`, or in a cell, which the seam checks as it checks any text scalar, as [inputs.md](../../seam/inputs.md) says, refusing a number, a blank, empty text and a range in its own words, `period is number 46023.0, expected text`; nothing here restates that. The valuation date, since #173, which may be left out with nothing in its place, decision 39's form around a handle, `valuation_date: Handle[ValuationDate] | None = None`: the cell showing `_CreateValuationDate`'s result or a name for it, checked as the seam checks any handle, a blank, a raw date, a text naming no live object and a handle of another kind refused in its words whatever the label beside them, `valuation_date is blank, expected valuation date handle`, `valuation_date is number 46371.0, expected valuation date handle`, `valuation_date is holiday calendar handle '30512:holiday_calendar:7', expected valuation date handle`; a blank is no omission. The library requires it with a `BAL` label and reads it for nothing with any other, so one pair of formulas serves a column of both kinds; it reads the handle's day, `as_of`, and never the fraction of the day elapsed, so a day's end and its start give the same dates. The result is a date, which goes out as its serial, as [outputs.md](../../seam/outputs.md) says, so a fresh cell shows `46023` until it is formatted once. Nothing is published and no object is made: the functions are nonvolatile, a cell recalculating when its label or its handle's cell changes and never otherwise.

## Excel help

Quoted from the declaration in `src/catalyst/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Gives the first calendar day of a contract or strip, 1-Jan-2026 for F26, 1-Nov-2029 for W29 and the first day of the left label of F26-Z28; of its balance, the later of the valuation day and that first day. |
| `period` | One contract or strip label, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28, or its balance, BALZ26, typed or in a cell such as A2. |
| `[valuation_date]` | For a BAL label, the valuation-date handle whose day the balance starts on, such as B1 showing _CreateValuationDate's result; left out for any other label. |

## The grammar

A label is one of six forms, or two of them joined by one hyphen, the half-year since #182, [half-year-strips.md](../../engineering-tickets/trade-valuation-pipeline/half-year-strips.md). The letters are read in either case, `f26`, `F26`, `cal28` and `Cal28` alike, by the owner's decision for these functions, recorded in [time.md](../time.md); the year is exactly two digits and means 2000 to 2099, the library's fixed horizon, never a decade inferred or today's date consulted.

| Form | Means | Such as | First day | Last day |
|---|---|---|---|---|
| a month letter and two digits | one calendar month | `F26` | 1-Jan-2026 | 31-Jan-2026 |
| a quarter number, `Q` and two digits | a calendar quarter, `1Q` January to March, `2Q` April to June, `3Q` July to September, `4Q` October to December | `1Q27` | 1-Jan-2027 | 31-Mar-2027 |
| a half number, `1` or `2`, `H` and two digits | a calendar half-year, `1H` January to June, `2H` July to December, since #182; `H` and two digits alone is March, the contract month, so a half leads with its number as a quarter does | `1H27` | 1-Jan-2027 | 30-Jun-2027 |
| `CAL` and two digits | a calendar year | `CAL28` | 1-Jan-2028 | 31-Dec-2028 |
| `W` and two digits | a winter, November of that year to the March after | `W29` | 1-Nov-2029 | 31-Mar-2030 |
| `S` and two digits | a summer, April to October of that year | `S28` | 1-Apr-2028 | 31-Oct-2028 |
| two labels joined by `-` | every day from the left label's first to the right label's last | `F26-Z28` | 1-Jan-2026 | 31-Dec-2028 |
| two seasonal labels joined by `-` | the same rule, the months between included | `W28-W29` | 1-Nov-2028 | 31-Mar-2030 |

The month letters are the exchanges', `F G H J K M N Q U V X Z` for January to December, the same twelve [util_NextFut](next-fut.md) reads; `Q27` alone is August 2027, a month, since a quarter leads with its number. A winter is labelled by the year it starts in and runs `X` to `H`, five months; a summer runs `J` to `V`, seven; both as CME describes its natural-gas strips. A winter may end in the next century: `W99` runs to 31 March 2100 and never wraps to 2000.

A range covers every calendar day between its ends, so `W28-W29` includes the summer of 2029 and is not two winters. Its right label may start and end no earlier than its left, so that a range can never cut off part of either end unnoticed: `F26-F26` is January 2026, `1Q27-CAL27` is all of 2027, `Z28-F26` is refused, and so is `CAL28-F28`, whose right end finishes before its left does. Nothing is sorted or swapped.

**The balance of a period, since #160, from the valuation day since #173.** One `BAL` prefix, in either case, `BALZ26`, `balcal26`, `BalX26-Z26`, on any label or range above, and the valuation-date handle beside it: the balance runs from the later of the handle's day and the label's first day to the label's last day. A period still to come is the whole period, so `balv26` on 20 September 2026 is October entire, as `V26` is; a period under way runs from the day itself, `BALV26` on 12 October from the 12th; on the last day it is one day; and a period that ended before the day is refused by both functions, naming the label, the day and the end, so that a deal in a month that has gone never books as one day at its end. These are calendar boundaries, not pricing observations: a Saturday or a holiday is a day like any other, no business-day rule applies here, the schedule method choosing the pricing days later, and a one-day window may still find no eligible observation when a trade is made. The prefix is read once: `BALBALZ26` leaves `BALZ26` under it, which is no form, so it is refused naming the whole expression as it arrived, and so are `BAL` alone and a malformed or reversed label under the prefix. A `BAL` label is no spelling of a contract code: a trade ticket's `contract_code` refuses it as any other word where a row books by it, and since #161 a trade takes these dates through `start_date` and `end_date`, [create-trades.md](../trades/create-trades.md), the two helpers feeding one dated ticket from a column of ordinary and `BAL` labels. The helpers' cells follow the handle as the valuation day advances, so the ticket says: paste the two dates as values before booking, and the trade's window stays fixed while the market moves on.

| Label | Valuation day | First day | Last day |
|---|---|---|---|
| `balv26` | 20-Sep-2026 | 1-Oct-2026, the whole month to come | 31-Oct-2026 |
| `BALV26` | 12-Oct-2026 | 12-Oct-2026 | 31-Oct-2026 |
| `BalV26` | 31-Oct-2026 | 31-Oct-2026, one day | 31-Oct-2026 |
| `balv26` | 1-Nov-2026 | `valuation_date is 2026-11-01, after 'balv26' ended on 2026-10-31, expected a valuation day on or before the period's last day` | the same |
| `balf26` | 20-Dec-2025 | 1-Jan-2026 | 31-Jan-2026 |
| `balf26` | 15-Jan-2026 | 15-Jan-2026 | 31-Jan-2026 |
| `balf26` | 31-Jan-2026 | 31-Jan-2026 | 31-Jan-2026 |
| `balf26` | 1-Feb-2026 | `valuation_date is 2026-02-01, after 'balf26' ended on 2026-01-31, expected a valuation day on or before the period's last day` | the same |
| `balx26-z26` | 12-Nov-2026 | 12-Nov-2026 | 31-Dec-2026 |
| `balcal27` | 12-Oct-2026 | 1-Jan-2027 | 31-Dec-2027 |
| `BALG28` | 29-Feb-2028 | 29-Feb-2028, the leap day, one day | 29-Feb-2028 |
| `V26` | left out, or any valid valuation-date handle | 1-Oct-2026 | 31-Oct-2026 |
| `BALZ26` | left out | `valuation_date is missing, expected a valuation-date handle with 'BALZ26', whose day starts the balance of a period` | the same |

## The library checks

Four rules, the first failure being the message, and both functions run them over the whole expression, so asking for a start cannot hide an end that is no label, nor a period that has ended.

| Rule | Message |
|---|---|
| each label is one of the forms, with a two-digit year, under a `BAL` prefix or not | `period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28`; `period is 'BALBALZ26', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28` |
| a range's right end starts and ends no earlier than its left | `period is 'Z28-F26', expected range endpoints in chronological order` |
| a `BAL` label has its valuation-date handle, since #160 a second argument and since #173 the handle | `valuation_date is missing, expected a valuation-date handle with 'BALZ26', whose day starts the balance of a period` |
| the label's period ends on or after the valuation day, since #173; before it, the period has gone | `valuation_date is 2027-01-05, after 'BALZ26' ended on 2026-12-31, expected a valuation day on or before the period's last day` |

The first rule refuses a space anywhere, `Q1 27` and `F26 -Z28`; a year of one or four digits, `W8` and `F2026`; a quarter that is not 1 to 4; an empty end of a range, `F26-`; a second hyphen; `I`, which the exchanges skip; and any other word, `Jan26`. The message names the whole expression as it arrived. Nothing else is checked: a label is not held to any schedule, and whether an exchange lists the month is nobody's business here. The seam's own checks of the handle come before any of these, [inputs.md](../../seam/inputs.md) decisions 35 and 39.

## The reading

Each label is read for two months, numpy's month unit: its first month and the month after its last, built from the year and the form's first month and length, three for a quarter, twelve for a year, five for a winter and seven for a summer, one `np.timedelta64` in months each. The first day is the first month as a day, one conversion, and the last day is the day before the month after begins, one conversion and one day subtracted, so February's length in a leap year, a winter's March in the next year and `W99`'s in the next century fall out of numpy with no leap-year or month arithmetic written here. No array of months or days is made, nothing is cached and nothing is published: the work and the bytes are the same for one month and for the whole century, as the pins below say. The balance adds one look for the prefix, the handle's one resolution at the seam, the bound the day is held to, the last day as well as the first, one conversion more, and one comparison that raises the day to the first where the period is still to come; a label with no prefix pays the look and nothing else, so the ordinary readings cost what they did.

## Tests

The library's examples and properties are `tests/unit/test_periods.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| every example in the grammar's table, in lowercase, capitals and mixed case: the first and the last day each | example |
| the twelve month letters in either case, each one month long; `Q27` is August and `3Q27` the third quarter | example |
| February 2000 and 2028, leap years, and 2027; `W99`, ending in 2100; `Z99`; the whole horizon as `f00-cAL99` | example |
| one-digit years, a four-digit year, a space anywhere, a fifth and a zeroth quarter, an empty end, two hyphens, three labels, a month by name, `I`, a letter that is no month, `CA`, `CALS`, `WS`, a letter or a year alone: refused by both functions, naming the whole expression | example |
| `Z28-F26`, `CAL28-F28`, two months the wrong way round, a winter then the summer that began before it, a summer then the quarter before it, a year then the quarter before it: refused by both functions | example |
| since #182, `1h27` and `2H27` in either case, `H27` as March, a leap first half, `1H27-2H27` and `2h27-1h28`, a quarter to its half; `0H27`, `3H27`, a one-digit and a four-digit year, spaces and trailing text, `HH` and `H` before a number refused naming the expression; `2H27-1H27` refused by its order; the balance of a half from a day inside it, from before it, on its last day, and refused after it; halves six months long from January or July for any year | example, property |
| for any month of the horizon in either case: its first day, its last the day before the next month's first, 28 to 31 days; and the range from it to any month on or after it, the left's start and the right's end | property |
| for any year: a quarter is three months, a year twelve, a winter five from November, a summer seven from April; `1Q` to `CAL` of a year is the year, a later quarter to it refused | property |
| the first and last days through the seam as serials, a month, a quarter, a year, a winter, a summer, a range and `W99`; a malformed label and a reversed range refused by both in the library's words; left out, blank, empty text, a number and a range of cells in the seam's | example, through the seam |
| since #173 the balance of a period from the valuation day: the ticket's table, October 2026 from 20 September, the whole month, from the 12th, that day, and on the 31st, one day, January 2026 the same way, a strip from 12 November and from the October before, a calendar year from the October before, slice B's labels, a quarter in mixed case, a winter from its second year, a summer on its last day, a Saturday, the leap day, a leap February from its first day and a February without one, a year-end range and `BALW99`; an ordinary label the same with a day or without; a day left out, and the day after October, January, December, a strip, a winter and a leap February refused by both naming the label, the day and the end; the prefix alone, twice, and over a malformed or reversed label refused naming the whole expression | example |
| for any month and any day from forty before its first to forty after: the balance runs from the later of the day and the first to the month's last while the day is on or before the last, and is refused once past it | property |
| the balance's days through the seam from valuation-date handles, the ticket's table as serials, the fraction of the day read for nothing, two handles each giving its own start and an ordinary label the same with either; a handle left out with a `BAL` label and a period that has ended in the library's words from both; a blank, a raw date, a fraction of a day, a text naming no live object, a holiday-calendar handle and a range of cells in the seam's, the same beside an ordinary label; the valuation dates published and nothing of the days | example, through the seam |
| fourteen calls across thirteen functions for one label, fifteen for a range, the label and the left-out handle each checked once and the prefix looked for once, one numpy conversion of the library's and the seam's way out for a date; the balance of a month sixteen across fourteen and of a strip seventeen, the handle's text checked and resolved once and the day held to the bound, two conversions; a peak of 1,264 bytes for a month and for the whole century alike and the balance within the same twice the slack, nothing published | budget |
| the schedule's own `m26`, a quarter, a year, a winter across the year end, a summer and two ranges in a real workbook, with a malformed label, a reversed range, a number and a blank refused; since #173 the balance of the ticket's labels over valuation-date handles in QH1:QH12, a future month, a current one, a last day and a day after, a strip, a calendar year, a leap day and a Saturday, an ordinary label with a handle, and a handle left out, a period that has ended, a repeated prefix, a blank, a raw date, a text, a fraction of a day and a holiday-calendar handle refused; the dated ticket booked from the helpers over a handle in IU16 | Excel smoke |
| rows 1531 to 1536 and 1541 to 1542 of the kept workbook over handles in F, and rows 1955 to 1973, two handles, a future month, an expired label, a label without its handle, and one window booked three ways, from the helpers at 12 October, pasted as values and from the helpers at 20 October, the first two the same to the number | workbook |

## Not here

A contract's expiry, an index's publication day, a payment day and anything else a schedule supplies: the [schedules](../index-definitions/futures-schedule.md)', read through [util_ReadHandle](read-handle.md). Building a schedule from a strip, pricing a strip, weighting its months and checking a market covers it: separate work, not these functions'. Aliases, `Jan26`, `Cal 28`, `Win29`, a year of four digits, a label with a space: refused, one spelling per form. Sorting or swapping the ends of a range. Reading a period that has ended as a one-day deal at its end: refused; a future period is the whole period. An implicit valuation date, a clock, a market or a workbook name consulted for the day: the handle is explicit, and a raw date in its place is refused. Freezing the helpers' cells, writing to other cells or making a trade: the desk pastes the dates as values and books them through [create-trades.md](../trades/create-trades.md). A business-day rule on the valuation day, a Saturday kept as it is. `BAL` in a trade's `contract_code`: refused there as any other word where a row books by it. The schedule creators reading their codes: unchanged, their codes still labels, as [time.md](../time.md) records.
