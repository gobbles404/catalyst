# util_ReadPrompt

Built in #129.

Reads the prompt of a calendar onto the sheet as text: the code of the contract on the calendar's first unfixed period, which is the contract the first price of a market over that calendar is for, as [_CreateMarket](../market/market.md) has read it since #86. The desk shows it beside each index so that a sheet holding several markets says, in one cell each, which contract each price vector starts at; nothing is made, no handle is published, and the valuation date is the calendar's own. Prompt here means that one contract and nothing more: on a futures calendar the contract prompt on the valuation day, on a Gas Daily calendar the month of the first unfixed flow day and on an IFERC calendar the first month whose index has not published. The code is `src/catalyst/calendar/calendar.py`, where `Calendar.prompt_code` reads it off the calendar's own columns, and `src/catalyst/excel/utilities.py`, the worksheet function.

## Worksheet contract

```python
def util_ReadPrompt(calendar: Handle[Calendar]) -> str: ...
```

| | A | B |
|---|---|---|
| 1 | as_of | 22-Jun-2026 |
| 2 | `=_CreateValuationDate(B1, 0.5)` | shows `30512:valuation_date:3` |
| 3 | `=_CreateCalendar(A2, B12)` | shows `30512:calendar:WTI NYMEX:14`, B12 the index whose schedule holds m26, n26 expiring 22-Jun-2026 and q26 |
| 5 | `=util_ReadPrompt(A3)` | shows `n26` |

One argument, required: the calendar's handle, the cell showing `_CreateCalendar`'s result or a name for it, declared `Handle[Calendar]`, so the seam resolves it to the calendar and refuses anything else in its own words, a blank, a number, text naming no live object or a handle of another kind, `calendar is market history handle '30512:market_history:WTI NYMEX:19', expected calendar handle`, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say; nothing here restates that. The result is text, the code as the schedule spells it, `n26` for a schedule that spells it so and `Jul 2026` for one that does, as [outputs.md](../../seam/outputs.md) sends text: no object is kept and no handle shown, so the cell is ordinary text other formulas read. Type 23-Jun-2026 over B1 and the cell shows `q26`, the day after n26's expiry belonging to the next contract.

## Excel help

Quoted from the declaration in `src/catalyst/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Reads the contract code for the first price expected in the calendar's market price vector. |
| `calendar` | The calendar handle: the cell showing _CreateCalendar's result, such as B5, or a name for it. |

## The library checks

One rule: the calendar has an unfixed period, since a calendar whose every period has fixed has no first price to name, as it has no market. The market says the same of its history, in its own words, `market_history has no unfixed period, expected at least one to quote`; this message names the calendar, the argument given here.

| Rule | Message |
|---|---|
| the calendar has an unfixed period | `calendar has no unfixed period, expected at least one to quote` |

The worksheet shows `#ERROR util_ReadPrompt: ValueError: calendar has no unfixed period, expected at least one to quote`.

## The reading

Three reads and no array: the row of the first unfixed period, which the calendar counted once when it was made and holds as `first_unfixed`; the schedule row of the contract on it, `contract[first_unfixed]`; and that row's code, read off the schedule through the calendar's index. The calendar's own rules decide the period, and nothing is decided again here, as the table below shows, each row the calendar's rule and nothing new:

| Calendar | The first unfixed period | The prompt |
|---|---|---|
| futures | the valuation day, since a day is fixed only once it is before the valuation date's day, whatever fraction of the day has elapsed and whether or not the market is open that day | the contract prompt on the valuation day: the expiring contract on its expiry day, the next from the day after; on a weekend or a holiday, the contract that day belongs to, no day skipped |
| Gas Daily | the day after the valuation day, since a flow day is fixed once its print has preceded it | the month of that day: the month in progress while it has a flow day left, the next month from the month's last day |
| IFERC | the first month whose publication day is not before the valuation date's day | that month: the month publishing on the valuation day itself, the next from the day after |
| any, valued before the calendar begins | the calendar's first period | its first contract, which on a futures calendar is the schedule's second, the first only bounding the calendar |

| Calendar | Valuation date | Schedule | Prompt |
|---|---|---|---|
| futures | 22-Jun-2026 | n26 expires 22-Jun, q26 follows | `n26` |
| futures | 23-Jun-2026 | the same | `q26` |
| Gas Daily | 18-Sep-2026 | U26 covers September, V26 October | `U26` |
| Gas Daily | 30-Sep-2026 | the same, September's last flow day fixed | `V26` |
| IFERC | 1-Sep-2026 | U26 publishes 1-Sep, V26 1-Oct | `U26` |
| IFERC | 2-Sep-2026 | the same | `V26` |

## Tests

The library's examples are `tests/unit/test_calendar.py` under the prompt code; the agreement with the market, that the prompt is the code of `first_contract` on every kind and for any history, is `tests/unit/test_market.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| futures: the expiry day and the day after, the expiring contract then the next; a Saturday and a holiday, the contract prompt that day, no day skipped; the last day, the last contract | example |
| Gas Daily: inside a month, that month; a month's last day, the next month; the day before the last flow day, the last month | example |
| IFERC: the publication day, the month publishing; the day after, the next month; two months published, the third; the last publication day, the last month | example |
| valued before the calendar begins, each kind: its first contract, never the futures schedule's boundary contract | example |
| the fraction of the valuation day changes the prompt of no kind | example |
| every period fixed, each kind: refused with the exact message | example |
| a lowercase month, a label with a space and a year in full come back as the schedule spells them | example |
| the prompt is the code of the market's first contract, on the three kinds and across a roll; for any history of any kind, the same | example and property |
| the three kinds read through the seam as text, the error for each kind in the library's words, and the calendar left out, blank, a number, text naming no live object, or the handle of an index, of fixings or of a history, in the seam's | example, through the seam |
| reading the prompt publishes nothing: the store's live count and bytes as they were | example, with handles |
| nine calls across nine functions and no numpy call, for a calendar of a year of days and of a hundred years alike; a peak within the slack at either, measured 192 bytes, and nothing published | budget |
| the three kinds in a real workbook, the futures calendar's prompt in the schedule's own case, a calendar valued before it begins, a calendar every month of which has published, and the calendar left out, blank or a number | Excel smoke |

## Not here

The prompt on a date other than the calendar's valuation date, a contract some count of positions after the prompt, labels for a price vector, a feed's symbol built from the code, and any change to how the calendar fixes a period or the market reads its first price: none of these, by the ticket. Which contract a given day belongs to: the calendar's spill shows it for every day, through [util_ReadHandle](read-handle.md). The market's own first contract: the market reads it from the same row and the same column, and this function reads it for a sheet that has no market yet.
