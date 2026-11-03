# Give schedule methods a clear owner

**Status:** Agreed 17 October 2026 and built the same day from PR 195's head `ffd34a9` on the branch `refactor/schedule-methods`; the pull request that carries this page is the record. Kept as the plan as it was: the code, the module map and the kernel page are maintained, not this page.
**Suggested PR title:** `refactor(trades): centralize schedule method rules`
**Base:** Stack on [PR 195](https://github.com/gobbles404/catalyst/pull/195), branch `refactor/risk-report`, reviewed at `ffd34a9`. Target that branch while it is open; use its accepted successor or main if it lands first. Record the actual base in the PR.
**Scope:** One behavior-preserving PR with two reviewable commits. Include this ticket as the plan in the implementation PR.

## Outcome

Make the shared meaning of `lastday`, `penultimate`, `last3day` and `asian` easy to find and change deliberately. Keep the existing pipeline and all worksheet behavior.

The current code has reasonable stage boundaries, but several stages infer a method's rules from comparisons such as `method != ASIAN` or `method == LASTDAY`. The economic meaning of those comparisons is spread across terms, observation generation and encoding. A new engineer must read all three to establish which methods accept partial months, allow physical settlement or require their booked contract to price every observation.

Give those shared facts one small owner. Keep the work that applies them in its existing stage. This is the next consolidation slice after saved-result ownership and shared risk-reporting vocabulary; it does not require another trade representation or execution framework.

## Current and proposed ownership

| Responsibility | Current | Proposed |
|---|---|---|
| Method vocabulary and encoded positions | `terms.py`: `ScheduleMethod`, `METHODS`, `METHOD_NAMES` | Move together to `trades/schedule_methods.py` |
| Which methods IFERC supports | Comparisons in `terms.py` and `observations.py` | One named rule in `schedule_methods.py`, called at the same stages |
| Which methods permit physical settlement on a futures index | Comparison in `terms.py` | Named method rule in `schedule_methods.py`; settlement validation and refusal remain in `terms.py` |
| Which methods require a whole month | Comparison in `observations.py` | Named rule in `schedule_methods.py`; date validation remains in `observations.py` |
| Which methods count backwards from expiry | Comparison in `observations.py` | Named rule in `schedule_methods.py`; expiry validation and business-day arithmetic remain in `observations.py` |
| Which methods require the booked pricing reference | Comparison in `encoding.py` | Named rule in `schedule_methods.py`; reference lookup and refusal remain in `encoding.py` |
| Read the entered method text | `template.py`: `schedule_method_of`, also used by resolution | Unchanged parsing boundary, importing the shared enum |
| Generate observation days and weights | `observations.py` | Unchanged algorithms and owner |
| Choose payment anchors and apply payment instructions | `resolution.py` | Unchanged |
| Prepare, evaluate, collect and report | Existing downstream modules | Unchanged |

`Settlement`, `Route`, `QuantityPer`, `BASES` and `BASIS_NAMES` stay where they are. This is not a general extraction of every enum or validation function.

## Rules to make explicit

The table below describes existing behavior to preserve, not new product choices.

| Method | Supported on IFERC | Permits physical settlement on a futures index | Requires whole month | Counts backwards from expiry | Requires booked reference |
|---|---|---|---|---|---|
| `lastday` | Yes | Yes | Yes | No | Yes |
| `penultimate` | No | No | Yes | Yes | Yes |
| `last3day` | No | No | Yes | Yes | Yes |
| `asian` | No | No | No | No | No |

IFERC still requires financial settlement regardless of the method. Its supported `lastday` method observes the month's publication date and requires the whole month. The physical-settlement column is a method permission on a futures index, not a replacement for index or route validation.

“Counts backwards from expiry” identifies the penultimate and last-three-day rules that need an open expiry before calculating preceding business days. It does not say that a closed expiry is acceptable for `lastday`: that method's observation is refused later by encoding's existing closed-day check.

“Requires booked reference” means each observation must price off the component's booked contract. Under futures `asian`, the calendar chooses the pricing contract for each observation day and can roll between contracts. IFERC continues to reference its own monthly published index.

Keep these facts distinct even when their answers coincide today. Whole-month coverage and booked-reference ownership are different requirements. Likewise, IFERC support and permission for physical settlement are different requirements. One must not be inferred from the other just because both currently select the same methods.

## Shared module and implementation boundary

Create `src/catalyst/trades/schedule_methods.py`. Move the enum, member tuple and display-name array without changing their values, order, dtype or read-only behavior. Preserve encoded positions exactly:

```text
0 lastday    1 penultimate    2 last3day    3 asian
```

Expose small, named functions for the five facts above. Each takes the existing integer method-code array and returns a Boolean mask of the same shape. Names should describe the rule, for example `requires_whole_month` and `requires_booked_reference`. Use direct NumPy comparisons over arrays, as the current callers do. Positive or negative predicate names may follow the caller's existing check to avoid unnecessary inverse masks; the five economic facts must remain explicit and independent.

These functions classify already typed method codes. They do not parse text, validate code ranges again, inspect an index or settlement, construct dates, format refusals or retain masks on a trade. They run only at the current creation/encoding call sites. Move the existing comparisons behind them; do not add a preliminary pass that calculates every rule for every row.

The new module imports only NumPy and the standard library. It must not import terms, observations, resolution, encoding, index records, market data or Excel. Existing consumers import the definitions directly from their new owner, including readback code and tests. Do not keep compatibility re-exports in `terms.py` or introduce local imports to break a cycle.

Keep `observations.py`'s finite method dispatch and vectorized date/weight generation. Keep its `Observations` record and builder. Keep method-specific refusal explanations with the checks that issue them. No policy objects, strategy registry, callback map, generic rule engine, per-trade Python dispatch or extra saved state is required.

Instrument metadata continues to own the user-facing field description, options layout and help. Do not make `instruments/definitions.py` import the trade engine or generate economic rules from prose. Preserve its existing output, including its option order, which need not match the internal numeric encoding order.

## Behavior to preserve

| Boundary | Required behavior |
|---|---|
| Input and encoding | Exact method strings, case sensitivity, error wording and method-code positions remain unchanged. Template and ticket inputs take their existing path. |
| Mixed methods | Interleaved methods, strips and duplicate occurrences produce the same components, observation ordering, dates and weights. One method and many use the existing batch path. |
| Partial periods | Futures `asian` accepts booked partial months with eligible pricing days. Expiry-based methods and IFERC still require whole months. Quantity-per-month and per-calendar-day scaling stay unchanged. |
| Futures observations | `lastday`: expiry with weight one; `penultimate`: preceding pricing business day with weight one; `last3day`: expiry and two preceding pricing business days with equal thirds; `asian`: eligible pricing days in the booked window with equal weights. Use the same index calendar. |
| IFERC | One observation on publication day; payment instructions anchored on that day since [iferc-publication-payment-anchor.md](trade-valuation-pipeline/iferc-publication-payment-anchor.md), using the supplied payment calendar. Publication and payment are not interchangeable. |
| Payment groups | Futures payments remain anchored on each component's last observation. Keep distinct resolved payment dates, existing grouping and the requirement that payment follows the final observation. |
| References and coverage | Preserve rolling Asian references, own-reference restrictions for expiry-based methods, schedule boundaries and IFERC publication alignment. No broader contract/day history is introduced. |
| Validation | Keep every check at its current stage, in its current order, naming the same first offending row/component/contract. Do not remove apparently repeated checks or move settlement admission ahead of observation/payment construction. |
| Downstream | Same fixed leg, exposure compression, reserves, fixings, live evaluation, discounting, delta, DV01, reports and debug spills. No new work on a tick or reader call. |

In particular, checking each method separately can change which error appears first in a mixed ticket. Keep the current whole-month check over the relevant components, followed by the open-expiry check over its relevant components, before method-specific observation generation. Preserve the creator and direct kernel entry paths; this ticket does not redesign their validation responsibilities.

## Two commits

1. Move `ScheduleMethod`, `METHODS` and `METHOD_NAMES`; update direct imports and affected ownership pointers. Preserve behavior.
2. Name the five method facts in the new module and route the existing checks through them. Keep calculation and refusal construction in place. Add only the focused coverage needed to protect this boundary.

If a behavior discrepancy appears, record it separately. Do not use this refactor to add a method, change supported index kinds, alter payment conventions or silently repair an economic result.

## Documentation

Update the module map in `docs/architecture.md` and the relevant method-ownership explanation in `docs/library/trades/kernel.md`. Current worksheet contracts remain on their existing pages; link to their owners rather than adding another complete schedule specification. Adjust directly affected implementation pointers and imports.

This ticket's table is the historical acceptance baseline once built. Maintain the code's rule owner and current contract pages thereafter, not this plan. Leave unrelated chronology and stale prose for their own scope; no documentation sweep or new generated reference is required.

## Acceptance and evidence

- The shared method vocabulary and five named facts have one implementation owner. Callers no longer encode these policies independently through unexplained enum comparisons. Method dispatch for different date algorithms remains explicit where the algorithms live.
- Reuse the existing hand-priced and refusal tests for all four methods, mixed tickets, partial Asian periods, rolling WTI references, IFERC and physical settlement. Retain their expected values and messages.
- A small independent table test may pin the five facts for the four current methods, with repeated/interleaved codes. Do not create another full financial test matrix or assert whole source-file layouts.
- Retain the existing instrument metadata checks; confirm the catalog's supported method choices still agree with the enum without changing either display order or encoded order.
- Existing checks must still cover first-offending-row behavior for mixed methods, interleaved strip components and anchors, IFERC publication versus payment dates, and own-reference refusals. Add a focused case only where inspection finds a real gap.
- Preserve work-counter meanings and counts, date-generation calls, grouping/sorting/reductions, retained numeric-buffer sizes and downstream budgets. Helper-call ledgers may change with the extraction; those calls must be per existing phase, not per trade or observation.
- Measure creation's transient allocations on the existing small and large fixtures. Keep the current array operations where possible. Explain any unavoidable mask/bookkeeping difference specifically; do not raise broad ceilings or claim identical allocation merely because values match. No new retained per-row arrays or numeric work in preparation, evaluation or reporting is allowed.
- Run relevant creation, observation, encoding, metadata and performance tests, the documentation-link checks and the full `check.ps1`. The existing workbook, smoke and host expectations stay unchanged.

Done means an engineer can find the shared method rules in one small module, then follow a named rule to the stage applying it, with the same numbers, failures, work boundaries and Excel behavior.
