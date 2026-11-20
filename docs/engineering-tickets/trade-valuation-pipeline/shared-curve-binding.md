# One shared step binds a discount curve key to its curve

**Status:** Built in #259, stacked on #258, agreed with the owner on 20 November 2026 for
[issue #257](https://github.com/gobbles404/catalyst/issues/257), this page in its first
commit. One rule written twice becomes one function two callers share, ahead of the
cashflows of [issue #254](https://github.com/gobbles404/catalyst/issues/254), which would
have written it a third time. One refusal changes its words by quote marks; no number, no
worksheet function and no argument changes.
[collect-discount-curves.md](../../library/globals/collect-discount-curves.md) owns the rule;
[kernel.md](../../library/trades/kernel.md), [evaluate-trades.md](../../library/trades/evaluate-trades.md)
and [quote.md](../../library/quoting/quote.md) point to it.

## The issue

A row or a template names its discount curve by a key, such as `SOFR`. Before anything is
discounted, a step finds the curve of that exact name in the collection. The step is written
out twice:

| Caller | Where | What is its own |
|---|---|---|
| Trades | `_the_curves` in `trades/evaluation.py` | Many keys a batch; the refusal names the trade booking the key; each curve covers its own unpaid payment days |
| Quotes | `the_curve` in `quoting/request.py` | One key a template; the cleared route, where a collection is refused; coverage checked later, when the payment days are known |

The rule is the same in both: the name matched exactly, case and all, and no fallback to the
first curve, a collection of one included. Each module also carries its own helper listing
the collection's names in the refusal, and the two differ: the trades' lists them bare and
the quotes' lists them quoted.

```text
trades   discount_curve_key 'Sonia' of trade 1003 at row 3 names no curve of the collection, which holds SOFR, FFOIS and SONIA; expected a curve of that name
quotes   discount_curve_key 'SOFR' names no curve of the collection, which holds 'FFOIS'; expected a curve of that name
```

One rule in two places is a change made twice, and the two had already drifted by a pair of
quote marks.

## Decisions of 20 November 2026

| Decision | Agreed |
|---|---|
| The shared step | Find the curve of an exact name in a collection, and the one refusal of a key that names none, with the collection's names listed once. |
| Its home | `globals/discount_curve_set.py`, beside the collection whose names it reads. |
| The names in the refusal | One spelling, quoted, as the library quotes a name everywhere else: `which holds 'SOFR', 'FFOIS' and 'SONIA'`. The trades' refusal gains the marks; the quotes' is as it was. |
| Each caller keeps | Who it names in the refusal, a trade or nobody; whether a collection is required or refused; its own coverage check, which needs its own payment days; and its own count of the curves it selects. |
| `curve_starts_on` | Already shared, in `globals/payments.py`, and stays there. |
| Order | This first, stacked on #258; the cashflows of #254 above it, calling the shared step from the start. |

## The shared step

```python
def curve_named(curve_set: DiscountCurveSet, key: str) -> DiscountCurve | None: ...
def no_curve_named(curve_set: DiscountCurveSet, key: str, booked_by: str = "") -> ValueError: ...
```

`curve_named` is the rule: the collection's curve whose name is the key, exactly, or none.
`no_curve_named` is the refusal, made on the failing path alone by whoever looked, so that a
caller names who booked the key only when there is someone to tell:

```text
discount_curve_key 'Sonia' of trade 1003 at row 3 names no curve of the collection, which holds 'SOFR', 'FFOIS' and 'SONIA'; expected a curve of that name
discount_curve_key 'SOFR' names no curve of the collection, which holds 'FFOIS'; expected a curve of that name
```

The names are listed in the collection's order: one alone, two joined by `and`, more by
commas and a last `and`.

## What changes for a reader

One refusal, by quote marks:

| Caller | Before | After |
|---|---|---|
| Trades | `which holds SOFR and FFOIS;` | `which holds 'SOFR' and 'FFOIS';` |
| Quotes | `which holds 'FFOIS';` | the same |

Every other refusal of either caller reads as it did: a collection missing, a collection
given to a cleared quote, a curve starting on another day, a payment past a curve.

## Acceptance

- The shared step by itself: the exact name found, another case not found, a collection of
  one giving no fallback, and the refusal's words with and without who booked the key, for a
  collection of one name, of two and of three.
- The trades' refusal reads the new words wherever it is pinned: the unit tests, the host's
  fact, the smoke and the lifetime check. The quotes' pinned refusals pass unchanged.
- Every other test passes unchanged.

## Engineering boundaries and delivery

One pull request stacked on #258, this page and its index row in the first commit, the build
in the next. The two functions in `globals/discount_curve_set.py`; `_the_curves` and
`the_curve` calling them, each module's `_listed` gone; the tests, the host's fact, the smoke
and the lifetime check that pin the trades' words; the owning pages and a history row. The
kept workbook shows the refusal in no cell and is not saved.

Measure before and after. No `WorkCounter` count changes. The function ledgers move: a
bilateral evaluation runs `curve_named` once per distinct key of the batch, where it built a
dictionary of the collection inside `_the_curves`; a quote runs `curve_named` once, where it
ran a generator inside `the_curve`. The pull request states the counts it measured.

## Outside this ticket

Coverage checks, which differ by caller because the payment days do. The collection's own
rules. How a key is entered or stored. The cashflows, which are #254's.
