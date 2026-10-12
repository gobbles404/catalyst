# Combine holiday calendars

[Pipeline overview](README.md) · [UAT item 16](surface-uat-notes.md#16-combine-payment-holiday-calendars)

**Status:** Built in #NN on `claude/combine-holiday-calendars`, stacked on PR #182 at `9c00a9f`,
12 October 2026, the page as the ticket; the [As built](#as-built-nn) section at the end says what
was built and what was not. One focused PR on the current prototype, reusing its existing
collection-of-handles input support; it does not claim the stack has shipped.

## Outcome

Combine one or more holiday calendars into one ordinary holiday-calendar handle.
Use that handle in `payment_holiday_calendar` or `util_ShiftDate` wherever a
business day must be open on every supplied calendar.

The rule is the **union of closed dates**: a holiday in any input calendar is a
holiday in the result. Business-day consumers continue to exclude weekends under
their existing Monday–Friday convention.

| Calendar A | Calendar B | Combined business day |
|---|---|---|
| Open | Open | Open |
| Closed | Open | Closed |
| Open | Closed | Closed |
| Closed | Closed | Closed |

## Worksheet contract

```text
_CombineHolidayCalendars(calendar_handles) -> holiday-calendar handle

B2 = existing calendar A handle
B3 = existing calendar B handle
B5 = _CombineHolidayCalendars(B2:B3)

util_ShiftDate(A1, "+1bd", B5) -> date
payment_holiday_calendar = B5 in the template or trade row
```

`calendar_handles` is required: one handle in a cell, or a row or column of
holiday-calendar handles. Reuse `Handles[HolidayCalendar]` and its existing seam
rules. Refuse a two-dimensional block by shape; resolve each supplied cell once
in input order. Blank cells, failed creators, stale handles and other handle
kinds fail with the existing cell-qualified messages. Do not skip bad cells or
publish a partial calendar. At least one calendar is required.

One calendar follows the same path as many. Repeated calendars and overlapping
holidays do not change the resulting dates. An already combined calendar is an
ordinary valid input, so combining can be nested without a special case.

## Saved state and integration

Concatenate the input date arrays and take their sorted unique dates with NumPy.
Return a normal immutable `HolidayCalendar` owning its resulting date array. Keep
listed weekend dates in the result; business-day consumers already handle them.
Source arrays remain untouched, including their original order and duplicates.
The existing `_CreateHolidayCalendar` keeps its current input-preserving behavior.

Use the existing handle kind, publication/release machinery and
`util_ReadHandle` holiday column. No new calendar wrapper, reader or source
membership report is needed. Readback shows the combined dates chronologically,
once each, including when a single source was supplied.

Trade creation continues to resolve payment dates from its existing anchor and
`payment_time_lag`, using the combined handle as its payment calendar. Existing
payment-after-observation checks remain unchanged. `util_ShiftDate` also consumes
the result unchanged; for compound offsets the same combined calendar applies to
every `bd` instruction, while `cd` and `em` retain their existing behavior.

Source-cell changes recalculate the combining formula and its dependents through
the normal Excel graph. Existing held calendars/trades/results remain immutable
snapshots. Combining and resolving payment dates add no work to price ticks.

## Worked acceptance

Use synthetic calendars; these dates do not claim any exchange's holiday rules.

| Input | Listed holidays, as supplied |
|---|---|
| A | 2026-10-14, 2026-10-12, 2026-10-14 |
| B | 2026-10-13, 2026-10-14 |
| Combined readback | 2026-10-12, 2026-10-13, 2026-10-14 |

Starting on Friday 9 October 2026, the weekend and all three listed weekdays are
closed, so `+1bd` gives Thursday 15 October and `+2bd` gives Friday 16 October.
From 15 October, `-1bd` gives 9 October. A synthetic financially settled trade
whose payment anchor is 9 October and whose rule is `+1bd` must therefore resolve
its payment date to 15 October using the combined calendar.

Acceptance should cover:

1. The worked dates through the utility and trade creation, plus the combined
   readback. Pin agreement with a calendar explicitly containing the union.
2. One input, reversed input order, repeated input handles, overlapping dates,
   unsorted source arrays, weekend dates and nested combinations. Inputs remain
   unchanged and the result's array is read-only.
3. The normal seam refusals above, including a bad cell after valid inputs and no
   published result on failure. A row and a column produce equivalent calendars.
4. A source update, failed source and recovery through worksheet dependencies;
   retained old snapshots remain unchanged. Include a small kept-workbook example
   and the usual smoke/host checks, using existing lifetime coverage where possible.

Measure work with the existing counter pattern: calendars consumed, listed dates
consumed and unique dates produced. Pin one handle resolution per occurrence,
one publication, and no calendar union during preparation/evaluation/reporting.
Run the full gate and document the function and its UAT checks.

## Scope

This combines supplied holiday dates only. It does not choose exchange, clearing
or currency calendars, download holiday data, add coverage horizons or introduce
custom weekends. Inputs carry no coverage horizon today, so combining them cannot
detect a missing future holiday.

It also does not implement "count on calendar A, then roll on calendar B."
Every business day counted uses the same combined calendar. That different
payment convention would require a separate specification.

## As built (#NN)

Built on `claude/combine-holiday-calendars` above #182's `9c00a9f`, one pull request. The function's page is [combine-holiday-calendars.md](../../library/index-definitions/combine-holiday-calendars.md).

**The function.** `combine_holiday_calendars(calendars, counter)` in `index_definitions/holiday_calendar.py` concatenates the sources' days, keeps their distinct days in order with `np.unique` and makes the result through `holiday_calendar`, the one builder, so a combination is an ordinary frozen calendar owning its days. It counts `calendars_combined`, `holidays_read` and `holidays_kept`. `_CombineHolidayCalendars(calendar_handles: Handles[HolidayCalendar])` in `excel/index_definitions.py` is the worksheet function, the second use of decision 44's vector of handles after `_AggregateResults`: one cell, one row or one column, each cell resolved once in sheet order, a block refused by shape, a blank, a number, an empty text, text naming nothing, another kind and a creator's failure refused at their cell, the failure carried whole so a consumer shows the creator's text once. Nothing is published by a refusal.

**What was checked.** The worked acceptance holds everywhere it is written: A and B combine into the 12th, the 13th and the 14th of October 2026 once each; from Friday the 9th `+1bd` is the 15th and `+2bd` the 16th, from the 15th `-1bd` the 9th; a cleared financial trade anchored on the 9th under `+1bd` pays the 15th on the combination as on a calendar listing the union. One input, reversed order, repeats, overlaps, unsorted sources, a Saturday listed and nested combinations; the sources left as listed and the result read-only; a row and a column equivalent. The budgets pin the seam's calls growing with the handles and the numpy constant, a hundred distinct days kept in 800 bytes and freed on release, and a trade on a combined calendar doing the plain calendar's work at creation, preparation, evaluation and reporting. The lifetime group `calendars` moves a source's day and clears a source, the combination, a shift and a readback following, failing and recovering with every old publication released; the trades group already shows a template and a batch following a payment calendar that changes.

**Where.** `tests/unit/test_holiday_calendar.py`, `test_index_definitions.py`, `test_utilities.py`, `test_create_trades.py`, `test_help.py`; `tests/performance/test_seam_budgets.py`, `test_seam_allocation.py`, `test_trade_valuation_budgets.py`; the host's fact; the smoke's TA block; the kept workbook from row 2624 of the handles sheet; the gate runs the new lifetime group.

**Not here.** Nothing chooses, downloads or generates a calendar, no coverage horizon, no custom weekends, no count-on-one-roll-on-another convention. `_CreateHolidayCalendar`, `util_ShiftDate`, the template and trade creation are unchanged in code; the shift and the payment rules read the combination as they read any calendar. No seam change.
