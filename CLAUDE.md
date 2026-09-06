# second

A commodities derivatives pricing library exposed to Excel through Excel-DNA.
Python 3.13.13, managed with uv. Run everything through `uv run`.

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

- Every behaviour gets a property test or a golden case. Never a test that asserts absence.
- Never change source and golden files in the same pull request.

## Pull requests

- One purpose, under 400 lines. Conventional commit titles: `feat(scope): ...`, `fix(scope): ...`, `chore: ...`.
- Say what you did not do.