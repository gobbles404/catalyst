# Check repository documentation links

**Status:** Agreed 16 October 2026 and built the same day; the pull request that carries this page is the record. Kept as the plan as it was: later changes update [working.md §11](../seam/working.md#11-checking-the-links), not this page.
**Suggested PR title:** `test(docs): check local documentation links and anchors`
**Base:** Stacked on [PR 191](https://github.com/gobbles404/goosedove/pull/191) at its reviewed head `cdcc6be`, the branch `docs/ownership`, targeted while it remains open. If it has merged, start from current main.

PR 191 establishes documentation ownership and links between current contracts, implementation explanations and historical plans. This slice makes those links mechanically trustworthy. A moved file, renamed heading or target present only in an author's untracked files must fail the normal repository checks with an actionable location.

One focused PR: the checker, its tests, narrow repairs needed to enable it, and a short usage section in the existing contribution guide. No runtime or worksheet behavior changes. The [ownership ticket](documentation-ownership-and-workflow.md) remains the preceding plan.

## Files and repository view

Check all Git-indexed Markdown files in the repository, including root instructions, `.github`, function pages, seam pages, research and engineering tickets. Historical Markdown is included by default. Do not scan virtual environments, generated output or other untracked files.

Use one explicit local mode: **working-tree content of Git-indexed files**. Git supplies the file inventory; both source text and target headings come from the working tree. This sees uncommitted edits saved on disk and staged new files without combining staged source text with different target contents. CI uses the same mode on its clean checkout.

- A linked file must be in that inventory and present on disk. A file that exists only untracked, ignored or in another checkout is a missing target. New documentation and its targets must be added to Git before this check can see them.
- Resolve ordinary paths relative to the source document and leading `/` paths from the repository root. Normalize `.` and `..`; refuse a local path that escapes the repository. A directory link is valid if the directory contains tracked files.
- Match path spelling against Git's inventory, including case, even on Windows. An incorrectly capitalized link must not pass because the local filesystem tolerates it.
- Support URL-encoded paths/fragments and angle-bracket destinations containing spaces. Separate the URL components before decoding. Local query strings do not change which file or Markdown anchor is checked.
- Do not accept machine-specific drive, UNC or `file:` paths as portable repository links. Plain paths in inline code are explanatory text and outside this check.

Build the inventory once per scan and reuse parsed target headings. Find the repository independently of the caller's current directory. No per-link Git subprocess, network access or dependence on another worktree.

## Links and anchors

Check inline Markdown links and image destinations, plus reference-style links resolved through their definitions. Include full, collapsed and defined shortcut references. Do not interpret every bracketed phrase as a missing reference. Link-like examples inside fenced or indented code, inline code and HTML comments are not active links or anchors.

For Markdown targets, validate same-page and cross-page fragments against rendered heading anchors and supported explicit anchors. Follow GitHub's relative-link and section-link conventions, including formatted headings, punctuation and repeated headings with numbered suffixes. The reference is [GitHub's Markdown syntax guide](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links).

Support explicit `<a id="...">` and `<a name="...">` anchors. Reject repeated explicit identifiers within a file, and ambiguous collisions with a generated heading anchor. Repeated heading text is valid when its rendered anchors are distinct; do not reject headings merely because their titles repeat. Do not invent a second spelling convention or silently treat unsupported Markdown syntax as successfully validated.

For non-Markdown targets, check file existence only. Source-line and PDF-page fragments need no interpretation in this slice. External URLs, including commit-pinned GitHub links, and non-file schemes such as `mailto:` are not fetched or validated. Keep useful historical citations; this check does not establish whether their contents are correct.

Document the supported syntax and any intentionally unvalidated forms. Choose a small implementation appropriate to that scope; do not build a general Markdown renderer. If a parser dependency is justified, keep it development-only and explain its purpose in the PR. No new production dependency.

## Preserve unambiguous legacy rule references

The NUL incident exposed a second problem: two different rules both called decision 43. PR 191 removes that collision and stops allocating new global numbers. As a narrow regression check, ensure the existing explicit decision numbers are unique within each current `Decided` section of `docs/seam/inputs.md` and `docs/seam/outputs.md`.

Check only those identified sections and their top-level decision items. Do not enforce contiguous numbering, renumber anything, scan arbitrary numbered instructions, or compare numbers across files or historical snapshots. Named sections and explicit anchors remain the path for new rules. This check protects an existing reference convention; it is not a general prose linter.

## Diagnostics and integration

Return failures in deterministic source-path and line order. Each diagnostic identifies the source file, one-based line, original destination and reason, with the resolved target where helpful. For a reference-style link, include the definition location when that is what needs editing. Duplicate identifiers should name both locations.

Example shapes, not mandatory exact wording:

```text
docs/architecture.md:18: missing tracked target: library/trades/missing.md
docs/seam/host.md:60: unknown fragment: inputs.md#old-input-rule
docs/seam/inputs.md:80: duplicate explicit anchor 'input-text' (first at line 35)
```

Provide a developer command, suggested `uv run python tools/check_doc_links.py`, and invoke the same checking logic from a pytest repository check. A failure must fail pytest, `check.ps1` and the existing CI check job. The current pytest integration is sufficient; a separate scheduled job or external service is unnecessary. Keep the helper out of `src/goosedove/` and avoid a second implementation in the test wrapper.

Add a short usage/reference section to `docs/seam/working.md`: the command, the Git-indexed working-tree view, supported forms, diagnostic meaning and exception policy. Link to it where needed rather than duplicating instructions in several pages. The checker needs no pricing work counters, Excel function or retained handle.

## Existing breakage and historical exceptions

Run an initial inventory and fix clear broken paths and obsolete fragments needed to turn the check on. Keep these repairs to references and, where justified, stable anchors; do not fold in semantic rewrites, source refactors or bulk archival.

One confirmed example at PR 191's reviewed head, `99b9b64`: `docs/engineering-tickets/trade-valuation-pipeline/mixed-trade-fields.md` links to `#as-built-nn`, but its heading is `As built, #163`, whose anchor is `#as-built-163`. Repair this with the checker. This is an example for the implementation work, not a claim that the initial inventory is complete.

Do not hide failures by deleting useful links, manufacturing empty target files, exempting an entire folder or making the real repository check warning-only. A target in an unmerged sibling PR should be an existing PR link or clearly pending text until the target is part of this branch.

If a frozen historical document intentionally refers to a vanished historical path, allow a narrow exception recording the source, exact destination and reason. Prefer a commit-pinned historical link when the intended revision is known. Exceptions must match an actual failure and become errors when stale or unused; no wildcard catch-all. A valid surviving historical relative link needs no exception.

Report the initial failures by category, the repairs and any exceptions in the PR. If a missing target's intended meaning is unclear, record that question rather than redirecting it to a merely similar page.

## Acceptance tests

Use small fixtures for link resolution and a temporary Git repository for the inventory behavior. Preserve at least these cases:

| Case | Expected result |
|---|---|
| Existing relative/root-relative files, tracked directories and local images | Pass |
| Same-page and cross-page headings, including formatting, punctuation and repeated titles | Pass for the rendered anchor; an absent or renamed anchor fails |
| Named reference links and explicit anchors | Valid definitions resolve; duplicate explicit anchors and ambiguous identifiers fail |
| A missing file, renamed target, missing directory or wrong path case | Fail with the source location and destination |
| A target present only as an untracked file | Fail; adding it to Git makes it eligible without requiring a commit |
| A tracked target changed or deleted in the working tree | Check the current text or report its absence, never fall back to a stale Git blob |
| Encoded spaces, angle-bracket destinations and a fragment following a path | Resolve correctly without confusing encoded filename characters with separators |
| Link-like examples and headings inside code/comments, and external URLs | Ignore without a network call or false missing-target failure |
| Duplicate legacy decision IDs in the two selected current sections | Fail; ordinary numbered steps elsewhere and valid repeated heading titles pass |
| A narrowly documented historical exception | Suppresses only its intended failure; an unused exception fails |

The real repository scan must pass on the committed PR tree. Demonstrate that removing or renaming an owning section in a fixture breaks its inbound reference and that adding an untracked local file cannot hide a missing target. Tests should establish resolution behavior, not snapshot entire documents or assert that particular prose remains unchanged.

Run the focused checker tests, the real scan and the repository's required `check.ps1`. Verify the existing CI job actually runs the repository scan. Commit this ticket with the implementation and record the supported scope, exclusions and check results in the PR.

Done means contributors get a useful failure before shipping a broken local reference. It does not claim that a working link proves a financial rule, that every code-comment citation has been checked, or that external websites remain available.
