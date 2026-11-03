# Leftover chores after the landing

**Status:** Agreed 19 October 2026 as two pull requests stacked on #208, the deletions first and the rename second, each from the branch before it. Two small cleanups the October reviews listed and no PR picked up, and the code's names for the deltas brought to the sheet's words.

## Outcome

The repository stops carrying two things nothing uses, and the code calls the deltas by the sheet's words, so a reader of the code and a reader of the sheet mean the same thing by `nominal_delta` and `delta`. Nothing a sheet shows changes but one readback header, decided below.

## PR 1: the deletions

1. **Drop the scipy dependency.** `pyproject.toml` pins `scipy==1.18.1` and nothing in `src`, `tools`, `tests` or `host` imports it. Remove the pin, regenerate `uv.lock`, and prove the checks pass without it: run `uv sync --locked` after the lockfile is updated and before `./check.ps1`, since an ordinary `uv run` can leave the old package installed and the checks would then prove nothing. `docs/getting-started.md` says the environment holds numpy and scipy; it says numpy.
2. **Remove `hello()`.** `src/catalyst/__init__.py` holds a two-line `hello()` that returns a greeting, the package skeleton's leftover; nothing calls it and no test covers it. Remove it, leaving the package docstring.

No code path changes, no number moves, and the counts the gate reports stay as they were.

## PR 2: the deltas by the sheet's words

The sheet names the two deltas `nominal_delta` and `delta`: in `_ReportRisk`'s `risk` argument, in the risk labels (`HNG nominal_delta [LOT]`) and in the readback columns. The code calls them lot deltas: `lot_delta`, `lot_delta_total`, `discounted_lot_delta`, `discounted_lot_delta_total` and `contract_lot_delta` across nine source files, with three refusals saying "of lot delta" and "of discounted lot delta". Rename, the sheet's name winning as decided on 15 October:

| Today | After | Meaning |
|---|---|---|
| `lot_delta`, `lot_delta_total` | `nominal_delta`, `nominal_delta_total` | the undiscounted exposure in reporting lots |
| `discounted_lot_delta`, `discounted_lot_delta_total` | `delta`, `delta_total` | the exposure after the route's discounting treatment |
| the readback header `contract_lot_delta` | `contract_nominal_delta` | the one sheet-visible name, giving the pair `contract_nominal_delta` and `contract_delta` |
| "has inf of lot delta", "of discounted lot delta in all" | "has inf of nominal delta", "of delta in all" | the refusals' words |

The currency-based price sensitivity keeps its name and its meaning; it is not a delta of either kind.

**Rename only.** The numerical expectations, the units, which arrays are shared rather than copied, the work counts and the readbacks' column positions are unchanged, and the existing tests prove it: a pin moves only where it names a renamed name or quotes a reworded refusal, never in a number. The intended visible changes are the one header and the specified refusal wording. The readback pins in the Python tests, the host tests, the smoke and the kept workbook's results spills follow the header, and the workbook is re-saved through the hidden-Excel harness. The current pages that use the old names follow: `kernel.md`, `prepare-trades.md`, `evaluate-trades.md`, `aggregate-results.md`, `report-risk.md`, `read-handle.md`, `bump-discount-curve.md` and the library README; the tickets under `docs/engineering-tickets/trade-valuation-pipeline/` and `docs/seam/history.md` are history and keep their words. No new test framework: the existing suites prove the rename.

## Checks

- Both PRs: `./check.ps1` green, the full smoke and lifetime run, the counts stated before and after; PR 1 after `uv sync --locked`.
- After PR 2 a grep over `src`, `tests`, `docs/library`, `docs/architecture.md` and `tools` for `lot_delta` and `lot delta` finds nothing.

## Not here

The DV01 help wording the October tech-debt review listed as "U10": the note behind it could not be found in the UAT notes, so it joins neither PR unless the owner recalls what was wrong. The keyword-only records, the seam unions, the bridge split, the folder renames and the broader documentation consolidation stay parked, as the consolidation arc decided.
