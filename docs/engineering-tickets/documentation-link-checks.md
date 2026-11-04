# Check repository documentation links

**Status:** Agreed 17 October 2026 and built the same day from PR 191's accepted head `cdcc6be` on the branch `docs/link-checks`; the pull request that carries this page is the record, and [PR 192](https://github.com/gobbles404/catalyst/pull/192) was the prototype it replaces. Kept as the plan as it was: later changes update [working.md §11](../seam/working.md#11-checking-the-links), not this page.
**Suggested PR title:** `test(docs): check local documentation links and anchors`
**Base:** The accepted head of [PR 191](https://github.com/gobbles404/catalyst/pull/191), or current main once it merges. Treat [PR 192](https://github.com/gobbles404/catalyst/pull/192) as a prototype and source of evidence, not the implementation to keep extending.

## The outcome

A contributor who moves a file or renames a heading should learn which local documentation links broke before merging. The command and CI must check the same repository contents and give a useful location for each failure.

Build a small repository link checker. Markdown syntax belongs to a Markdown parser; HTML attribute syntax belongs to an HTML parser. Our code owns the relationship between parsed links and tracked repository files and anchors.

This is one development-tool PR: implementation, focused tests, necessary link repairs and one short usage section. Keep duplicate decision-number protection as a separate regression test in the same PR. No runtime, Excel, valuation or release-packaging changes.

## What the prototype taught us

The prototype used a parser for blocks and headings while regexes independently recognized links, reference definitions and anchor attributes. The two interpretations disagreed. Fixing the latest example left the same disagreement available in another form.

The earlier ticket also required exact original destinations and detailed source locations, a generic exception mechanism and legacy decision-number lint inside the checker. Simplify the diagnostics, defer speculative exception machinery, and give the decision-number rule its own test.

| Earlier requirement or approach | Revised scope |
|---|---|
| Parser plus custom Markdown recognition | Parser tokens and resolved reference definitions are authoritative. No second syntax recognizer. |
| Exact destination spelling and exact link/definition lines | Source file, enclosing block line, parsed destination and reason. Use finer locations when the parser supplies them. |
| Exception configuration for possible historical problems | No exception mechanism without an actual unresolved repository need. |
| Decision-number uniqueness inside the link checker | Retain as a separate pytest regression test over the two owning pages. The link checker has no decision-number policy. |
| Broad claims of reading everything as GitHub does | Explicit support for the repository's Markdown links and section anchors, with the exclusions below. |

Rebuild from this boundary. Reuse prototype fixtures and correct link repairs where they prove this contract; do not preserve its internal records or regex pipeline for continuity. Keep a single operative ticket in the implementation PR, replacing its earlier `check-repository-documentation-links.md` brief with this revision.

## Ownership and implementation

Use `markdown-it-py`, the development-only dependency already selected in the prototype, declared in the dev group and locked with `uv`. Use Python's standard-library `HTMLParser` for explicit HTML anchors. No further parser dependency is requested.

| Responsibility | Owner |
|---|---|
| Which Markdown links, images and reference links exist; which definition wins; code/comments versus content; heading content | Markdown parser |
| Attribute names and quoted values in explicit `<a id>` and `<a name>` anchors | HTML parser, applied only to HTML content identified by the Markdown parser |
| File inventory, path resolution, spelling, existence, heading identifiers and target lookup | Repository checker |
| Command output and exit status | Thin command entry point over the same checker invoked by pytest |

Consume the parser's link/image tokens and resolved reference information, including its source maps where available. Reference definitions in lists or quotes follow the parser's ordinary rules. Do not reconstruct definitions from uncovered lines, strip Markdown with regexes, or discover links again in raw text for better diagnostics. Feed identified HTML through the HTML parser; comments and code must not manufacture anchors.

Keep heading-identifier generation in one small function over parser-produced heading content. It owns GitHub-style spelling and collision suffixes, not heading recognition or inline formatting. Keep parsed pages for the duration of one scan, so target lookup does not parse the same page repeatedly.

These are function boundaries, not a requirement for a new package hierarchy, plugin interface or framework. One tool under `tools/` and focused tests are sufficient if the implementation stays clear.

## Supported repository contract

Read **working-tree content of Git-indexed files**. Obtain the inventory once with Git; scan all indexed Markdown, including instructions, research and historical tickets. Staged new files count, untracked-only targets do not, and a tracked file deleted on disk fails. The caller's current directory must not change the repository being checked.

For parser-recognized Markdown links and images:

- Check relative and repository-root-relative local targets, including same-page fragments. Normalize `.` and `..`, reject repository escapes, and match Git's path spelling including case on Windows.
- Check file existence and, for Markdown targets, section existence. A directory target must exist and contain an indexed file that is present on disk. Ignore local URL query strings; separate path and fragment before URL decoding.
- Accept the parser's treatment of encoded or angle-bracket destinations. Do not reinterpret Markdown escapes independently.
- Build section identifiers from parsed headings, including formatted words and duplicate-heading suffixes. Include explicit `<a id>` / `<a name>` identifiers. Reject duplicate explicit identifiers and collisions with generated heading identifiers.
- Include ordinary inline, image and reference forms, including wrapped links and links inside lists/quotes. Code and comments supply no Markdown links or anchors.

External URLs and non-file schemes are not fetched. For a recognized machine-specific drive, UNC or `file:` destination, report that it is not a portable repository link. This is not a raw-text path linter: syntax the Markdown parser renders as ordinary text is not a checked link, including undefined reference-like phrases and destinations the parser rejects. State that boundary in the usage section rather than adding a parallel source scan.

For non-Markdown files, check existence only. Source-line and PDF-page fragments, raw HTML `href`/`src` links, MDX, embedded templates and full GitHub renderer/sanitizer compatibility are outside this slice. Preserve existing external and commit-pinned historical citations.

## Diagnostics and integration

Each diagnostic needs the source path, the containing block's one-based line, the parsed destination and a specific reason such as missing target, wrong case or unknown fragment. Sort diagnostics deterministically by source location and destination. Definition locations and exact original spellings are helpful when supplied by the parser, but not acceptance requirements. Do not invent precision that the parser does not provide.

Provide `uv run python tools/check_doc_links.py` and call the same checking logic from pytest. Failures return a nonzero exit status and fail the existing CI test job. No separate service, scheduled run, network call, pricing counter or new CI job is needed.

Keep usage, coverage and exclusions in one short section of `docs/seam/working.md`, linked from the existing check instructions. The ticket describes the proposed change; that section becomes the maintained usage contract. Do not create another catalogue of every probe or parser edge case.

## Separate decision-number regression test

Keep the protection against two rules sharing a decision number in a separate test file, such as `tests/test_doc_decision_numbers.py`. It runs through ordinary pytest and CI, independently of the link-checking command and implementation.

Check the explicit numbers on top-level decision items within each `Decided` section of `docs/seam/inputs.md` and `docs/seam/outputs.md`. Numbers must be unique within that section of that file. Report the file, duplicate number and both locations. Do not require contiguous numbering, compare numbers across the two files, renumber decisions or inspect unrelated pages. PR 191's move to named sections for new rules remains unchanged.

Use the Markdown parser's structure and source locations to distinguish those items from nested lists, code, comments and numbered steps outside the section. This does not add another Markdown recognizer, content-lint framework, command or configuration file to the project.

Prove that a duplicate fails and that gaps, nested/example numbers and numbers outside the selected section do not. Run the check on the actual two pages as well. Keep this small regression protection separate from the link checker's fixtures and diagnostics.

## Bringing the repository under the check

Run the initial scan and fix clear broken paths and obsolete fragments. The prototype found the `#as-built-nn` reference in the mixed-trade-fields ticket; use its intended heading rather than an invented target. Keep repairs limited to links and justified stable anchors.

There is no demonstrated need for an exception system. Do not build one speculatively. Where a historical reference genuinely names removed material, prefer the correct commit-pinned link. If its intended target cannot be established, bring that specific reference back for a decision. Do not hide a failure by dropping a directory from the scan, deleting useful links or accepting an untracked target.

## Acceptance and stopping point

Use a small set of fixtures proving the boundary and the useful failures. The parser's grammar is not ours to reimplement or exhaustively retest.

| Failure class | Evidence required |
|---|---|
| Links interpreted differently from their rendered meaning | Parser-derived inline, image and reference destinations agree with worked examples, including a wrapped link and first-definition-wins inside a quote/list. A commented-out definition cannot override a live one. |
| Anchors interpreted incorrectly | Formatted headings and duplicate suffixes resolve; ordinary explicit anchors resolve with attributes in different orders and quoted `>`; `data-id` does not become `id`; duplicate identifiers fail. |
| Repository contents misidentified | Valid files/directories pass; missing, wrong-case, deleted and untracked-only targets fail. Adding an untracked target to Git makes it eligible. |
| References become stale after editing | Renaming or removing a target heading breaks its inbound link using the current working-tree contents. |
| Examples mistaken for links | Code/comments and undefined reference-like text produce no invented links. External URLs cause no network access. |
| Integration diverges | The command and pytest use the same implementation; the real committed repository passes and CI includes that scan. |
| Decision numbers become ambiguous | The separate regression test rejects a duplicate within either owning section, while allowing numbering gaps and ignoring unrelated numbered content. |

Keep direct expected answers in these fixtures. Do not reproduce the checker in tests or derive its expected destinations using its own extraction helper. Preserve the useful prototype counterexamples as evidence of ownership; they must not lead to one special-case branch per example.

Run the focused tests, the real scan and the repository's required `check.ps1`. In review, distinguish:

- **Fix before landing:** a reproduced breach of this supported contract, a false pass/failure on repository content, duplicated syntax interpretation or broken CI integration.
- **Separate proposal:** another syntax extension, content lint beyond the agreed decision-number test, speculative escape hatch, cosmetic diagnostic preference or alternative organization with no demonstrated defect. Record a concrete need before adding scope.

Severity labels alone do not decide scope. A demonstrated defect in an owned rule still matters; a hypothetical extension does not become a requirement because it can be described as a finding.

Done means the actual repository passes, the failure classes above are caught, and syntax has one authoritative interpretation. Do not expand the PR into a general documentation validator or an open-ended Markdown conformance project.
