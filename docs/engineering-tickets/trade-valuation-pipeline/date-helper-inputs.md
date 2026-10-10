# BAL period dates from a valuation-date handle

[Pipeline overview](README.md) · [UAT item 3](surface-uat-notes.md#3-dates-and-period-labels-through-the-same-helpers)

**Status:** Built in #NN, 10 October 2026, one prototype PR stacked on PR #172 at
`7f14a83`, awaiting review. This ticket supersedes this page's earlier raw-reference-date
and date-passthrough proposal. [As built](#as-built) at the foot records what the build settled.

## Outcome

Type `balv26` and obtain the remaining calendar dates of October from an explicitly
supplied valuation-date handle. For a future period, return its full dates. For an
expired period, fail loudly. The user pastes the resulting dates as values before
booking so the trade's period stays fixed as market time advances.

## Public functions

```text
util_StartDate(period, [valuation_date]) -> date
util_EndDate(period, [valuation_date])   -> date
```

| Input | Contract |
|---|---|
| `period` | Required text using the existing period grammar, including case-insensitive `BAL` labels. |
| `valuation_date` | Optional existing `_CreateValuationDate` handle; required when `period` is a BAL label. |
| Return | One actual Excel date per function, using the existing numeric date output. No handle or spill. |

Keep the names, argument count and argument order. Replace the second argument's
public name and type: `reference_date: Date` becomes `valuation_date: Handle[ValuationDate]`.
This is a deliberate cutover; raw dates are no longer accepted in that position.
Migrate kept callers together, with no compatibility overload.

Use the handle's `as_of` calendar date. Ignore `day_fraction_elapsed`: even at the end
of a day, that calendar day remains included in the entry window. Ordinary labels
such as `V26` or `CAL27` need no handle and keep their full-period meaning. A supplied
handle is still validated normally when the label does not use it.

Resolve handles through the existing seam. A blank, dead handle, wrong-kind handle or
raw date supplied as the second argument fails normally. Omission is distinct from a
blank cell. An omitted handle with a BAL label fails by meaning, naming the label and
the missing `valuation_date` input. There is no implicit global valuation date, clock
lookup, market lookup or workbook-name convention.

## Calendar-date rule

Resolve the underlying label to its inclusive first and last calendar dates, then:

```text
if as_of > period_end:
    fail in BOTH helpers

start_date = max(as_of, period_start)
end_date   = period_end
```

A future BAL period starts at its first day. A current BAL period starts on `as_of`
itself. `as_of == period_end` is valid and returns that date from both helpers.
An expired period must not silently become a one-day trade at month end.

Both expired-period errors must identify the original entered BAL label, `as_of` and
period end. For example, the message's substance is:

```text
period 'balf26' ended on 2026-01-31; valuation_date.as_of is 2026-02-01,
expected a BAL period ending on or after as_of
```

Use the existing error style; exact text is pinned with the implementation. EndDate
must perform the same expiry validation even though it could compute the end without it.

| Entered period | Handle `as_of` | Start | End |
|---|---|---|---|
| `balv26` | 20-Sep-2026 | 1-Oct-2026 | 31-Oct-2026 |
| `BALV26` | 12-Oct-2026 | 12-Oct-2026 | 31-Oct-2026 |
| `BalV26` | 31-Oct-2026 | 31-Oct-2026 | 31-Oct-2026 |
| `balv26` | 1-Nov-2026 | Error | Error |
| `balf26` | 20-Dec-2025 | 1-Jan-2026 | 31-Jan-2026 |
| `balf26` | 15-Jan-2026 | 15-Jan-2026 | 31-Jan-2026 |
| `balf26` | 31-Jan-2026 | 31-Jan-2026 | 31-Jan-2026 |
| `balf26` | 1-Feb-2026 | Error | Error |
| `balx26-z26` | 12-Nov-2026 | 12-Nov-2026 | 31-Dec-2026 |
| `balcal27` | 12-Oct-2026 | 1-Jan-2027 | 31-Dec-2027 |
| `V26` | omitted, or any valid valuation-date handle | 1-Oct-2026 | 31-Oct-2026 |

These are calendar boundaries, not pricing observations. Do not roll weekends or
holidays. A one-day calendar window can still fail later trade validation if its
schedule has no eligible observations. Preserve the existing label grammar for
months, quarters, calendar years, seasons and ranges; malformed or reversed labels,
`BAL` alone and doubled prefixes still fail. Do not add new label forms or coercion.

## Entry and booking workflow

With the valuation-date handle in B1:

```excel
B1: =_CreateValuationDate(DATE(2026,10,12),0)
A2: balv26
C2: =util_StartDate(A2,$B$1)
D2: =util_EndDate(A2,$B$1)
```

C2 returns 12-Oct-2026 and D2 returns 31-Oct-2026. They can occupy the ticket's
`start_date` and `end_date` columns. While these are formulas, changing B1 can change
the entry dates. The helpers remain nonvolatile; their explicit dependencies cause
normal recalculation.

1. Enter the BAL label and inspect the returned dates.
2. Paste the two date cells as values to freeze the intended booking window.
3. Optionally clear `contract_code` to make the controlling date fields obvious.
4. Create the trades from those fixed dates through the existing pipeline.

Freeze the dates **before** clearing their source label. PR #172 already allows a
complete date pair with a blank code, or an inactive retained text code. The helpers
do not freeze formulas, write to other cells or create a trade. Subsequent valuation
uses the booked dates; advancing market `as_of` does not move them.

## Implementation boundary and migration

Reuse the existing optional-handle input support. The Excel utility wrapper receives
the resolved `ValuationDate` object and passes its scalar `as_of` to the pure period
functions in `src/goosedove/index_definitions/periods.py`. Keep handle resolution out
of that module. Reuse the existing parser and shared BAL boundary validation; replace
the before-period refusal with the maximum rule, retaining an after-end refusal.

Update both utility signatures, help and library pages, `docs/library/time.md`, and
comments that describe the former inside-period-only reference rule. Update
`docs/library/conventions.md` where it says utilities read no objects: these helpers
read explicit valuation-date context while returning dates, without creating objects.
Audit all kept callers: period and utility tests, trade-valuation booking examples, help tests, seam
budget/allocation tests, host replay, Excel smoke and `workbooks/handles.xlsx`.
The smoke has BAL booking cells as well as its utility block; migrate both.

Use an existing valuation-date handle where its date matches the example, otherwise
create an explicit one. Preserve the examples' intended dates and economics. Do not
leave a raw serial where the new signature expects a handle. The typed seam continues
to own type/shape checks; the library owns BAL period meaning.

## Acceptance and verification

- Pin the table above through the registered worksheet functions, with actual numeric
  date outputs. Cover missing, blank, wrong-kind and dead handles and raw-date rejection;
  supplied invalid handles must fail even for ordinary period labels.
- Verify both helpers reject an expired period, reporting the original label, as_of and
  end. Pin the day before the period, first day, last day and day after; future periods
  are now accepted. Include leap-year February and a multi-month BAL range.
- Preserve case-insensitive parsing, supported ordinary period forms and malformed-label
  refusals. Different day fractions on the same as_of produce the same dates.
- Two independent valuation-date handles must produce their own BAL starts with no
  ambient state. An ordinary label returns the same dates for either valid handle.
- Keep a worksheet example of BAL entry, a future BAL month and an expired-label refusal.
  Demonstrate that helper formulas update with the handle; a separate booked example
  with pasted date values stays unchanged as the valuation date advances. Its trade
  creation and value/risk must match direct entry of those same dates.
- Preserve nonvolatile registration. Resolve a supplied handle once per call, publish
  no object, and retain no new cache. Boundary resolution must not expand calendar days
  or strip months. State relevant work counts before/after and maintain existing budget
  coverage; do not introduce a timing gate.
- Update the UAT status on delivery and run the full repository gate. Source and existing
  golden baseline changes remain separately reviewed under the repository's rule.

## Scope kept separate

The earlier idea of accepting an actual Excel date in the first argument is deferred;
`period` stays text. Pasted booking dates go directly into the trade ticket. This work
also leaves `_CreateTrades` unchanged: no direct active BAL-code booking, automatic
snapshot, new `exact` method or quantity/schedule change. `util_ShiftDate` remains the
separate offset utility. The handle-based BAL inputs above are the complete scope of
this PR.

## As built

PR #NN on `claude/bal-date-helpers`, stacked on #172. The library pages are
[start-date.md](../../library/utilities/start-date.md) and [end-date.md](../../library/utilities/end-date.md);
the seam's record is the #NN row of [history.md](../../seam/history.md).

- The rule as specified: `start = max(as_of, first)`, `end = last`, both helpers refusing
  `as_of > last`; `day_fraction_elapsed` is never read, so 0, 0.5 and 1 on one day give the same dates.
- The messages, pinned in `tests/unit/test_periods.py` and `tests/unit/test_utilities.py`: a `BAL`
  label without its handle, `valuation_date is missing, expected a valuation-date handle with 'BALZ26',
  whose day starts the balance of a period`; a period that has ended, `valuation_date is 2026-02-01,
  after 'balf26' ended on 2026-01-31, expected a valuation day on or before the period's last day`, the
  same words from both helpers; the seam's own for a blank, a raw date, a fraction of a day, a text
  naming no live object and a handle of another kind, `valuation_date is number 46371.0, expected
  valuation date handle` among them, whatever the label beside.
- Where the code is: `src/goosedove/index_definitions/periods.py`, `start_date(period, as_of=None)` and
  `end_date(period, as_of=None)` over one `_balance_from`, taking the day and never a handle;
  `src/goosedove/excel/utilities.py`, the two wrappers, `valuation_date: Handle[ValuationDate] | None =
  None`, passing `as_of` through. Both stay nonvolatile, publish nothing and keep no cache.
- Migrated callers: the period, utility, help and valuation tests, the seam budget and allocation
  tests, the host's theory rows and a new fact, the smoke's utility block, now over twelve handles in
  `QH1:QH12`, and its dated booking block over a handle in `IU16`, and `workbooks/handles.xlsx`: rows
  1531 to 1536 and 1541 to 1542 take handles in F over the days in C, and rows 1955 to 1973 hold the
  worksheet example, two handles, 12 and 20 October 2026, `balv26` from each, `BALX26` a month to
  come, `balcal27`, `balf26` refused as ended and `balv26` refused without a handle, then one window
  booked three ways, from the helpers at 12 October, pasted as values and from the helpers at 20
  October: the first two the same to the number, 400 of mark and 0.2 lots, the third 240 and 0.12.
- Counts: the balance of a month 16 calls across 14 functions and of a strip 17, where #160's were 16 across 15, the handle's text checked and resolved where the reference date's serial was checked by two functions; one label and a range unchanged at 14 across 13 and 15; the numpy ledger unchanged at 8 calls; the peak within twice the slack as before, nothing published. The Python tests 2,503 to 2,514, the smoke 922 formulas to 936, the host's 325 to 313, the theory's twenty-two balance rows over a reference date become nine refusals and one fact of nineteen asserts, the lifetime's 128 unchanged.
- Not done, as the ticket keeps separate: `period` stays text; `_CreateTrades` is unchanged, no `BAL`
  code booking and no snapshot; `util_ShiftDate` untouched; the helpers freeze nothing and write to no
  cell; no golden file changed.
