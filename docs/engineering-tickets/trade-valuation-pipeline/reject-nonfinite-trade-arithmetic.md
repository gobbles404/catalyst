# Reject nonfinite trade arithmetic before publishing handles

[Pipeline overview](README.md) · [Separate text transport fix](../reject-nul-input-text.md)

**Status:** Built in #190 on `claude/reject-nonfinite-arithmetic` from `main` at `bb4a72f`, 16
October 2026, one commit; the [As built](#as-built-190) section at the end says what was built and
what was not.
**Delivery:** One focused PR from current main, independent of the fee-applicability
and text-transport fixes. Preserve financial formulas and worksheet signatures.

## Problem and reproduced failure

Finite inputs can produce infinity or NaN through multiplication or addition. The
trade pipeline checks some produced values, but leaves gaps in encoding, preparation
and cleared evaluation. An invalid number can therefore reach a saved object before
a reader refuses it.

The review reproduced this on main `a1776b7`: a cleared trade with a monetary
coefficient of 1, fixed price -1e308 and live price +1e308 produces a fixed-leg
amount of +1e308 and a live contribution of +1e308. Both are finite; their sum is
infinity. Evaluation returns a result whose mark is infinite, with no numerical
warning. Publishing that result succeeds; `_ReportValues` subsequently refuses
the nonfinite result cell. This is an invalid saved result, not evidence of an
ordinary-sized finite price being calculated incorrectly.

The same review produced nonfinite coefficients and fixed-leg amounts during
creation, and nonfinite fixed floating amounts during preparation. The fix must
cover these producing stages, rather than just intercept the final report.

## Required behavior and ownership

Each stage checks the new numerical values it produces before they enter its
returned record or feed the next stage. Failure names the operation and the most
specific available trade, contract, observation day or payment group. No new
trade, preparation or result handle is published for the failed call.

Do not rescan already validated inputs in every downstream function. Preserve the
existing finite checks for quantities, input prices, lot risk, cash, reserves,
bilateral results and aggregation; close gaps without duplicating those checks.

| Producing stage | Values to cover |
|---|---|
| Creation and encoding | Selected unit-conversion products, quote quantities, monetary coefficients, fixed-leg amounts (`offset` internally), payment-group fixed-leg sums, weighted exposures and compressed slot sums |
| Preparation | Exposure times fixing, set amounts by payment group, new reference sensitivity sums, unpaid fixed-leg and fixed-floating totals, and any newly produced cash/group amounts not already covered |
| Evaluation | Live contribution per slot, reductions used by that route, and the cleared mark formed from fixed, set and live amounts; preserve the bilateral checks and cover shared arithmetic before either route consumes it |

A reduction can overflow even if all its elements are finite. Scalar Python float
addition and NumPy grouped reductions may produce a nonfinite result without raising
or warning. Check produced values, not just warning flags or input magnitude bounds.

Move the existing global live reduction into the cleared path, where it is used.
Bilateral evaluation reduces live contributions by payment group and must not perform
or refuse an unused global live sum. The prepared `offset_unsettled` and
`set_unsettled` scalars are currently retained for both routes and remain checked
for both; removing those fields would be a separate change.
Every value actually retained or consumed must be finite. If stored legs themselves
cannot be represented, refuse them even if a hypothetical netting could cancel them.

Use local NumPy error handling around the covered arithmetic and explicit finite
checks so failures become contextual library errors, not stray RuntimeWarnings.
No process-wide warning suppression, `nan_to_num`, clipping, replacing bad values
with zero, arbitrary size caps, or changes to summation order to conceal a failure.
Keep operations vectorized; construct detailed diagnostic attribution only on failure.

## Acceptance cases

Build small deterministic fixtures with valid schedules and finite inputs. Use zero
fee rates where needed so an unrelated reserve overflow cannot mask the target.

| Case | Expected refusal boundary |
|---|---|
| Quantity 1e308 converted with factor 2 | Creation: the converted quantity or coefficient |
| Coefficient 2 times fixed price 1e308 | Creation: the fixed-leg amount |
| Individually finite fixed-leg amounts sharing a payment group sum past the float limit | Creation: that payment group's sum |
| Individually finite weighted exposures coalesce into a nonfinite slot | Creation: that slot's exposure |
| Finite slot exposure 2 times a fixing of 1e308 | Preparation: that fixed observation's amount |
| Finite fixed observations sum to a nonfinite payment-group amount | Preparation: the affected group |
| Finite group amounts sum to a nonfinite unpaid fixed or set total | Preparation: the affected total |
| Live exposure 2 times quote 1e308 | Evaluation: that live slot's contribution |
| Finite live contributions sum to a nonfinite cleared live amount | Evaluation: that reduction |
| Fixed-leg +1e308, live +1e308, no set amount | Evaluation: cleared mark; the reproduced silent scalar-addition case |

Also pin negative overflow, a nonfinite grouped result produced by extreme opposing
contributions, and finite large values that remain representable and must still pass.
Cover both routes at shared arithmetic; keep existing bilateral/aggregation overflow
tests passing. Do not require every operation to have a separate mirroring test: cover
the independent arithmetic failure modes and their externally observable boundaries.

For element failures, name the first failing position in the existing stored order.
For a group sum, identify the contract and payment date where available; do not blame
one arbitrary trade for a sum across several. For a batch total, name the total and
currency or risk unit. Pin the chosen diagnostic order and worksheet error wording.

Add seam/host coverage proving a failing creator publishes no usable new handle and
returns a useful `_CreateTrades`, `_PrepareTrades` or `_EvaluateTrades` error. A corrected
input must recover through the ordinary lifetime path. Readers remain read-only;
they are not the first line of validation for these arithmetic failures. Capture
warnings in the focused numerical cases to prove the expected error is the outcome.

## Work and implementation scope

Start in `src/catalyst/trades/encoding.py`, `preparation.py` and `evaluation.py`.
Current field names such as `offset` are code references, not a naming change request.
Use the existing tests in `tests/unit/test_trades.py`, `test_create_trades.py`,
`test_trade_valuation.py` and `test_bilateral_kernel.py`, plus the applicable seam/host
and creation, preparation and valuation budget suites.

Account for added finite scans and temporary boolean arrays in the work/allocation
budgets. State the before/after work by components, slots and payment groups. Preserve
one quote read per distinct live reference, no schedule expansion or fixing work on a
tick, prepared-object reuse, and no pricing or validation arithmetic in readers.
Do not relax existing budget guards merely to accommodate unexplained work.

Update only the affected current kernel/reference wording and quoted error fixtures.
Run `check.ps1`; retain current financial acceptance numbers for valid cases. Any
golden-baseline acceptance remains separately reviewed under repository policy.

No new instrument fields, public functions, report layouts, financial methodology,
global numerical-validation framework or general module reorganization is included.

## Done when

The reproduced failure and independent producing-stage cases fail before publication;
large finite controls and ordinary cleared/bilateral examples still pass; diagnostics,
work budgets and lifecycle recovery are pinned; the full gate passes. Deliver this PR
on its own so the numerical fix can be reviewed and merged independently.

## As built (#190)

Built on `claude/reject-nonfinite-arithmetic` from `main` at `bb4a72f`, one pull request of one
commit and the number stamped after.

**The encoding, `trades/encoding.py`.** The conversion products, the quote quantities, the
coefficients and the fixed legs are made with numpy's flags down and checked where they are made,
the first component past the largest number refused by its trade and its operation, the quote
quantity before the coefficient before the fixed leg: `trade 1 at row 1 has inf of quote quantity,
expected a finite number of MMBTU; its count times its specification's size in the quote unit
outruns the largest number`. The groups' fixed legs are summed under the same flags and refused by
the group, `the fixed leg of Z26 paying on 2026-11-30 is -inf, expected a finite amount of USD; its
components' fixed legs, each finite, sum past the largest number`, a physical group by its contract
alone; the slots' exposures likewise, refused by the slot's first trade, its day and the contract
pricing it. `group_words` names a group once for the encoding and the preparation.

**The preparation, `trades/preparation.py`.** Three helpers run before the record is made.
`_the_set_amounts`: each fixed slot's exposure times its settle, refused by the slot and the settle,
`trade 1 at row 1 on 2026-11-25, a day Z26 prices, fixed at 1e+308, has inf of set amount, expected
a finite amount of USD; its exposure times the settle outruns the largest number`, and the groups'
sums refused by the group. `_the_sensitivity`: the live exposures summed by contract and refused by
the contract before any lot is counted, `Z26 has inf of price sensitivity, expected a finite amount
of USD per USD/MMBTU; its live exposures, each finite, sum past the largest number`, where the
lot-delta rule of #164 spoke one step later. `_the_unsettled_totals`: the unsettled fixed legs and
set amounts summed for both routes and refused for the batch by the total. The lot, bucket and cash
rules of #164, #166 and #176 stand as they were; after review, their block keeps the invalid
flag down beside the overflow flag, so two paid groups past the largest number each way are
refused as cash, `the batch has nan of cash in all, ...`, and two contracts' lot deltas past it
each way by the first contract, no warning escaping either.

**The evaluation, `trades/evaluation.py`.** Each live slot's contribution is checked before either
route sums it, refused by the slot and its quote, `trade 1 at row 1 on 2026-11-25, a day Z26 prices,
quoted at 1e+308, has inf of live contribution, expected a finite amount of USD; its exposure times
the quote outruns the largest number`. The global live sum runs on the cleared route only, under
the same flags, and is refused for the batch, `the batch has inf of live amount in all, expected a
finite amount of USD; the live slots' contributions, each finite, sum past the largest number`; the
cleared mark, the unsettled fixed legs, set amounts and live amount added in Python, is refused for
the batch, `the batch has inf of mark in all, expected a finite amount of USD; its unsettled fixed
legs, set amounts and live amount, each finite, sum past the largest number`, the reproduced case.
The bilateral path's checks of #176 are unchanged, and it makes no global live sum.

**Tests.** `tests/unit/test_trades.py`: the acceptance table and its edges in three tests on a
one-MMBTU lot, warnings as errors around each refusal: the fixed leg and its totals past the largest
number on the negative side, the opposing exposures and contributions that would net back to 1e308
and are refused in the order summed, the physical group named by its contract, and the large finite
controls, 5e307 twice as 1e308 of exposure and of unsettled set amount, 1e300 at 1e7 quoted at
1.5e7 marking 5e306. `tests/unit/test_bilateral_kernel.py`: two barrels quoted at the largest number
refused by the slot on both routes before either sums; the existing bilateral and aggregation
overflow tests stand. `tests/unit/test_trade_valuation.py`: `_CreateTrades`, `_PrepareTrades` and
`_EvaluateTrades` each refusing in the kernel's words after their own, the live count standing
each time, and the ordinary market valued at 7,000 after. `host/Catalyst.Host.Tests/CallTests.cs`:
the refused batch owns nothing in the host's store and a corrected row publishes and releases.
`tools/excel_smoke.ps1`: a row of 9E+307 LOT refused as a quote quantity. The work budgets are
re-pinned; the pull request states the counts before and after.

**Not done.** No new fields, functions, layouts or methodology; no change to summation order, no
`nan_to_num`, clipping, zeroing or size caps, no process-wide warning filter; `offset_unsettled` and
`set_unsettled` kept and checked for both routes; no Excel smoke case for a preparation or
evaluation overflow, the creation row standing for the boundary; the inputs' own finite rules,
quantities, prices, rates, lots, buckets, cash, reserves, the bilateral path and the aggregation, as
they were.
