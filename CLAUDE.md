# goosedove

A commodities derivatives pricing library exposed to Excel through Excel-DNA.
Python 3.13.13, managed with uv. Run everything through `uv run`.

## Principles

PRINCIPLES.md holds the tenets these rules derive from. When no rule applies, or a rule and a tenet conflict, the tenet decides.

## Before finishing any task

Run `.\check.ps1` (format, lint, types, tests) and fix what it reports.
Never add `# type: ignore` or `# noqa` to make it pass; fix the code.

## Style

- Validate untrusted input only at the Excel boundary. Inside, trust the types.
- No `isinstance` or `type(x) is` checks on internal calls. No `runtime_checkable` Protocols.
- No `__post_init__` that re-checks what its caller already established. Normalize, do not verify.
- `match` over enums with `assert_never` in the default arm. `NewType` for units and digests.
- Numerical code takes arrays and returns arrays. No per-item loops.
- No reload support, no retired-name lists, no compatibility shims. Cut over and let stale callers fail.

## Tests

- Use example tests for specific cases, property tests for general rules,
  and goldens for reviewed reference outputs.
- Test observable behavior and meaningful work budgets. Assertions that
  unwanted work or side effects do not occur are valid.
- Never change source and golden files in the same pull request.

## Pull requests

- One purpose, under 400 lines. Conventional commit titles: `feat(scope): ...`, `fix(scope): ...`, `chore: ...`.
- Say what you did not do.

## Performance

- Work is measured by counts, not time. Code that prices, caches, hashes, or
  converts data takes a `WorkCounter` and reports what it did.
- Every change to such code keeps or updates the budget tests under
  `tests/performance`, and the pull request states the counts before and after.
- `tools/performance` holds the profiler and memory scripts. Use them to find
  where time goes; never gate a merge on a timing.
