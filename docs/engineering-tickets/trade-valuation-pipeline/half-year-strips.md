# Half-year strip labels

[Pipeline overview](README.md) · [UAT item 15](surface-uat-notes.md#15-half-year-strip-labels)

**Status:** Built in #182 on `claude/half-year-strips`, stacked on PR #181 at `a61ac19`, 12 October
2026, the page as the ticket; the [As built](#as-built-182) section at the end says what was built
and what was not. One focused PR extending the existing period parser and its consumers on the
current prototype; it does not claim the stack has shipped.

## Outcome

Accept `1H27` and `2H27`, case-insensitively, as half-year strips in a trade's
`contract_code`. Half-years are calendar periods shared across commodities, resolved
against the supplied index's monthly schedule just like existing quarter/year strips.

| Input | Covered monthly contracts | Start date | End date, inclusive |
|---|---|---|---|
| `1H27` or `1h27` | F27 through M27 | 2027-01-01 | 2027-06-30 |
| `2H27` or `2h27` | N27 through Z27 | 2027-07-01 | 2027-12-31 |
| `H27` or `h27` | H27 only: March | 2027-03-01 | 2027-03-31 |

The half number is required. `H27` remains the existing March contract code.
The two-digit year retains the parser's existing 2000–2099 interpretation.

## Shared parsing and surface

Extend `src/goosedove/index_definitions/periods.py`; do not introduce a second
trade-only parser. The accepted form is `1Hyy` or `2Hyy`, with `H` in either case.
Existing range syntax also accepts these endpoints: `1H27-2H27` covers all of 2027,
and `2H27-1H28` covers July 2027 through June 2028. Preserve the existing ordering
checks, whole-string validation and refusal attribution.

The shared date helpers inherit the same labels without a signature change:

```text
util_StartDate("1h27") -> 2027-01-01
util_EndDate("2H27")   -> 2027-12-31
```

Their existing `BAL` wrapper also works with a half-year: with a valuation-date
handle for 2027-03-15, `BAL1H27` returns 2027-03-15 / 2027-06-30. Before the half
starts it returns the full half; after it ends both helpers fail. Case handling,
the explicit valuation-date dependency and the workflow of freezing dates into a
ticket remain unchanged. A code used to resolve a trade's period still cannot
carry `BAL`; complete explicit dates continue to take precedence over any code.

## Trade behavior

Resolve a half-year once at creation into six ordinary monthly components. Each
uses the existing schedule method, unit conversion, observation generation and
payment rule. Retain the original trade occurrence and entered label through the
ordinary readback path; do not turn the six components into six original trades.

The quantity basis keeps its current meaning:

- `quantity_per = month`: entered quantity applies to each of the six months.
  One LOT per month means six LOT in total, not one LOT divided across the half.
- `quantity_per = calday`: entered quantity applies to every covered calendar
  day. One LOT per day gives 181 LOT for `1H27`, 184 for `2H27`, and 182 for `1H28`.

Payment dates remain per component and existing compression rules remain intact.
A half-year label creates no new market reference, payment convention, schedule
method or risk-report bucket. Schedule rows and utilities that require a single
monthly contract remain single-contract inputs.

Preserve complete-date precedence over `contract_code`, template/ticket field
rules, missing-schedule-month refusals, and duplicate-occurrence counting.

## Acceptance

1. Pin both halves in both cases, `H27` as March, year boundaries and the two range
   examples above. Include a leap-year first half. Reject malformed forms such as
   `0H27`, `3H27`, `1H7`, `1H2027`, surrounding spaces and trailing text; reversed
   ranges fail as they do today. Errors name the original input and trade row
   where applicable.
2. Pin helper dates, including one mixed-case BAL half with an explicit valuation
   date, a future half and an expired half. Ordinary half labels need no valuation
   date. Preserve existing month, quarter, calendar, winter and summer results.
3. Hand-check one all-live, cleared, financially settled, `lastday` `1H27` trade
   with quantity 1 LOT/month and a market price 2 quote units above its fixed price
   in every component. For a synthetic specification worth 1 currency unit per
   quote unit per LOT, the aggregate mark
   is 12 and nominal delta is 6 LOT. Compare it with six monthly rows with the same
   economic terms, and with the equivalent existing `F27-M27` strip. Compare
   payment dates, encoded exposures, values and risk; per-occurrence metadata and
   one-time reserves naturally need not match six separate tickets.
4. Pin the `calday` totals above and a missing constituent schedule month. Show
   that an Asian half uses the existing monthly observation generation rather
   than treating six months as one averaging/payment period.
5. Add a small kept-workbook example demonstrating a half-year trade and its date
   helpers, with the usual seam/host/smoke coverage. Update the period grammar,
   instrument help and relevant docs wherever accepted strip forms are listed.

Run the full gate. Update work-budget evidence only where affected: half-year
creation should do the same structural work as its equivalent six-month strip,
with no new parsing or expansion during preparation, evaluation or reporting.
No unrelated parser rewrite or new public function belongs in this PR.

## As built (#182)

Built on `claude/half-year-strips` above #181's `a61ac19`, one pull request.

**The grammar.** `_label_months` in `index_definitions/periods.py` reads a half number, `1` or `2`, `H` in either case and two digits as six months from January or July, beside the quarter it already read; `H` and two digits alone stays March, so a half leads with its number as a quarter does. The forms' words name the new form, `a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28`, in every refusal that lists them. Ranges, the BAL balance, `util_StartDate`, `util_EndDate` and a trade's `contract_code` take the halves through that one reading; nothing else changed in the code.

**What follows from it.** A half resolves at creation into six ordinary monthly components on one occurrence, the entered code kept as typed and read back under `entered_contract_code`; each component keeps its month's dates, its schedule method's observations, its quantity basis and its payment rule, so `quantity_per = month` books a lot a month, six in all, and `calday` books the month's days, 181 for `1H27`, 184 for `2H27` and 182 for the leap `1H28`. A half whose months the schedule lacks is refused as a strip is, naming the first missing month. The hand check holds on the sheet: one lot of `1h27` at 3 with every month quoted 5 marks 12 and carries 6 lots, as `F27-M27` and six monthly rows do, with the same payment days, exposures and risk by day. The creation budget pins that a half does its six-month strip's work, the same calls and numpy but one label read where a range reads two.

**Where it is checked.** `tests/unit/test_periods.py`, the forms table, the refusals, the reversed ranges, the halves six months long for any year and the balance of a half; `tests/unit/test_utilities.py` and `tests/unit/test_help.py`, through the seam; `tests/unit/test_create_trades.py`, the six components against the strip and the rows, calday totals, the missing month, the asian half, a repeat; `tests/unit/test_trade_valuation.py`, the mark of 12 and the 6 lots on all three bookings; `tests/performance/test_trade_creation_budgets.py`, the half's work against the strip's. The host's smoke rows and a fact on a nine-month index; the smoke's HALF block, SA1 onward, booking and valuing `1h27` and `F27-M27` alike with the date helpers beside them; the kept workbook's block from row 2552.

**Not here.** No new instrument, signature, market contract, payment convention, schedule method or risk-report bucket. Schedule rows and the utilities that take one contract still take one. No parser rewrite: one branch beside the quarter's.
