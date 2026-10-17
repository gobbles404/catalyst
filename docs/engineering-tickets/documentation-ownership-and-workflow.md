# Establish documentation ownership and contribution workflow

**Status:** Agreed 16 October 2026 and built the same day from `main` at `83b7a7a`; the pull request that carries this page is the record. Kept as the plan as it was: later changes update the current pages, not this one.
**Suggested PR title:** `docs: establish current documentation ownership and workflow`
**Scope:** First PR of the consolidation stack. Documentation and contributor instructions only.

The trade pipeline has landed and works in Excel. Its documentation still mixes current contracts, implementation explanations and the history of how the prototype evolved. Contribution instructions require the same change to be retold in several places, so correcting one paragraph can leave another contradicting it.

Establish a short path into the current system, give each rule one maintained home, and change the workflow that recreates duplication. Demonstrate the improvement on input-text restrictions and reserve fee applicability. This PR does not reorganize the source tree or rewrite the entire documentation set.

## Baseline and stacking

Start from current `main`; the inspected baseline is `83b7a7a`, after PRs 188, 189 and 190, and the build started from that same commit. Record the actual starting commit in the PR and reconcile any subsequent changes. Older review documents describe earlier revisions and are evidence, not instructions to restore that state. Use the current `AGENTS.md` and `PRINCIPLES.md`; do not restore the former `CLAUDE.md` arrangement.

This is the base of a short stack. The next PR adds local documentation-link checks against the ownership and reference conventions established here. Later result/reporting and schedule-rule work gets separately scoped tickets before implementation. Each PR must be independently reviewable, pass its checks and leave a coherent repository at its own tip. List its base PR and purpose; keep unrelated fixes outside the stack. Land in dependency order using the repository's squash-and-rebase practice.

## Current reading path

Add a concise `docs/architecture.md`, linked from the root README and the existing library and seam indexes. It describes the system that exists at the PR's base, not the proposed future module layout.

Show the responsibilities and dependencies of:

1. Instrument definitions, index specifications and conventions.
2. Template and ticket resolution, then static encoding inside trade creation.
3. Preparation against history, including fixed/live observations and payment state.
4. Evaluation against live prices and, for bilateral trades, a discount curve.
5. Saved results, collection of compatible saved risk, and readers.
6. The Excel boundary, handle ownership and work counters.

Include a small source map and a compact table explaining what changes on a trade edit, history/as-of change, price tick and discount-curve change. Distinguish observation dates, pricing contracts and payment dates. Describe current reuse accurately: a price tick reuses preparation, but evaluation still processes the batch's live exposures and repeats applicable discounting work.

The overview owns the cross-pipeline summary of what is made again when something changes; duplicate whole-pipeline tables elsewhere become links to it. Function-specific guarantees stay on their owning pages, for example that evaluation consumes an existing preparation and never silently prepares again, and the overview links to them: less duplicated specification, each function still understandable on its own page. Link to the owning contracts for details. Do not copy the function catalogue, all signatures, instrument schemas, exact-error catalogue, test counts or PR chronology into the overview. In particular, do not describe the proposed `results.py` or `risk_report.py` as existing modules.

## Documentation ownership

Put the short governing rule in `AGENTS.md`, with a link to the ownership table in `docs/seam/working.md`; the other contribution pages link there rather than repeat the policy. Use this division:

| Information | Maintained owner |
|---|---|
| Instrument fields, types, choices and descriptions | Executable instrument metadata; preserve the existing consistency checks for its displayed/reference tables |
| Worksheet signatures and Excel help | Function declarations and parameter annotations |
| Current product behavior, units, limitations and useful examples | The relevant page in `docs/library/` |
| Input acceptance and failure precedence | `docs/seam/inputs.md` |
| Output conversion and handle lifetime | `docs/seam/outputs.md` and `docs/seam/handles.md`, respectively |
| How the transport or calculation implements a rule | Relevant implementation explanation and source comments, linking to the rule |
| Assertions of exact errors, independently worked financial answers and meaningful work budgets | Executable tests pin these expectations; pages retain useful derivations and link to focused evidence rather than duplicate exhaustive test inventories |
| Why a change was made and evidence at that revision | Its PR and relevant historical record |
| Proposed behavior and unresolved decisions | Active tickets, clearly distinguished from current contracts |

This means one owner per fact, not one edited document per PR. Different contracts can legitimately change together. Short contextual explanations and worked examples remain useful; independently maintained copies of the same rule table do not.

Keep contracts precise. Ownership cleanup must preserve units, accepted inputs, financial meaning, failure precedence and intentional limitations. If code, tests and agreed intent disagree, record the discrepancy for a separate decision instead of silently choosing one as the new behavior.

## Contribution workflow

Update the relevant instructions in `docs/seam/README.md`, `docs/seam/working.md`, `docs/library/README.md` and `docs/library/conventions.md`. Review the root instructions and PR template for conflicting documentation duties; change only those duties where needed. Preserve the financial principles, required checks, golden policy and performance obligations. Leave `PRINCIPLES.md` unchanged; amendments to it require their own PR.

- Replace mandatory updates to every narrative mentioning a feature with updates to the affected contract owners and the implementation explanations that actually changed.
- Stop requiring repeated PR-number stamps, manually maintained test/probe totals, exhaustive test lists, and a timeline entry for every routine change. Keep useful rationale, versioned measurements and historical links.
- Make the function-page skeleton describe today's worksheet behavior and point to implementation and evidence. It should not require a copied declaration/help block or full error catalogue merely to duplicate the source. Preserve existing generated-content consistency checks; replacing their mechanism is outside this PR.
- Use descriptive section references for new current rules. Do not allocate a global next decision number. Existing numbered rules remain meaningful during gradual migration; do not renumber the entire seam or reuse an old number for another rule.
- For current code, point to a file and name the relevant symbol or test. Use commit-pinned links when a historical line or implementation matters. Avoid line-number references into a moving branch.
- Completed tickets are historical plans, not another specification to update whenever the implementation changes. The pipeline packet's README should point readers to current contracts and distinguish open work from completed plans. Do not bulk-edit or relocate completed tickets in this PR.

The overview and workflow must be usable without consulting the external architecture reviews. Do not introduce a new documentation framework, hosting service, generator or prose linter.

## Prove the approach on two existing rules

### Input text restrictions

Use `docs/seam/inputs.md` as the current owner. At the inspected baseline it assigns decision 43 to both NUL rejection and the blank/empty period-field rule. Give NUL restrictions a descriptive section anchor, update current references by their intended meaning, and preserve the blank-field rule's identity. Do not resolve this by renumbering unrelated decisions.

Preserve PR 189's acceptance and failure order, including the first encountered Excel error or NUL, scalar and range attribution, and the distinction between NUL and ordinary backslash-zero text. The host page should explain enforcement and link to the acceptance rule. Remove competing current rule descriptions in the touched input/host/bridge pages; retain distinct implementation explanations and historical evidence.

### Reserve fee applicability

Use the existing reserve report page as the owning explanation of booked reserves, linked from trade creation and instrument inspection. The instrument metadata continues to own the entry-field descriptions.

Preserve the implemented rules: an omitted broker or the case-insensitive `none` token incurs no brokerage; a named broker enables the selected specification's brokerage rate; clearing applies to the cleared route. Marketing is the booked amount summed once per original ticket row. Reserves do not change mark, cash or risk.

The reserve report's worksheet-contract paragraph still says marketing is unbuilt and always zero, despite its later implemented example. Remove that contradiction after verifying the implementation and tests. Keep useful hand-worked examples. Replace competing applicability descriptions in the touched trade-creation/reserve pages with a link or a short explanation of that stage's responsibility.

For each example, include a small before/after table in the PR description: current rule owner, duplicate descriptions removed or linked, implementation/test pointers and the historical change reference. Then describe which maintained documents a hypothetical next change would require. The expected improvement is fewer synchronized descriptions, not fewer words at any cost.

## Scope boundaries

Keep the implementation diff to the overview, navigation/workflow pages, the two rule examples and their directly affected current references, plus this ticket page, committed in the same pull request with the clarifications agreed before the build. Source docstrings/comments may change only to repair those citations, without changing exported Excel help or behavior. List unrelated stale claims discovered along the way for later work; do not expand this into a repository-wide prose sweep.

No runtime changes, signature or spill changes, file/package moves, result-record extraction, schedule refactor, workbook changes, new quoting behavior or test-budget weakening. The automated link checker is the next PR, not an unimplemented acceptance dependency of this one.

## Acceptance and validation

- From the root README, a new engineer can find the pipeline, its current responsibilities and its contract owners without reconstructing completed tickets.
- The contribution instructions no longer require the duplicated narratives and bookkeeping identified above.
- Both worked rule examples have an unambiguous current owner, preserve their implemented meaning and retain useful evidence. No current reference conflates the two former decision-43 meanings.
- Follow every link changed or introduced, including section targets, against the files committed in this PR and its base. Another checkout or an untracked-only target does not satisfy a link. Use an existing PR link or plain pending text when a target has not landed.
- Preserve exact-error, hand-pricing, instrument-description consistency and work-budget coverage. Run `./check.ps1` and report the result; no new runtime tests are required for editorial changes. Report runtime/work counts as unchanged rather than inventing new measurements for this documentation PR.
- The PR contains the two before/after maintenance examples and identifies any remaining contradiction that requires a separate decision. Do not add a permanent full test inventory or whole-document snapshot to prove editorial quality.

Done means the current system is easier to find and the next contributor has fewer conflicting update instructions. The remaining documentation can migrate when its own boundary changes, under these rules.
