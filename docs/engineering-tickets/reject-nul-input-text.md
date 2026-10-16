# Reject NUL characters before packing Excel input text

[Pipeline ticket index](trade-valuation-pipeline/README.md) · [Separate numerical fix](trade-valuation-pipeline/reject-nonfinite-trade-arithmetic.md)

**Status:** Built in #NN on `claude/reject-nul-input` from `main` at `4a8d873`, 16 October 2026; the
[As built](#as-built-nn) section at the end says what was built and what was not.
**Scope:** One focused fix PR from current main. No worksheet signature or transport
format change. Suggested title: `fix(excel): reject NUL characters in input text`.
Independent of the numerical and fee-applicability PRs; merge separately.

## Problem

The host packs a range's text cells into one string separated by NUL (`U+0000`).
`cells_from_buffers` splits that string back into cells. A NUL inside an input cell
is currently indistinguishable from a separator and can move text into another field.

This is a correctness defect, not just a display problem. A host-equivalent packed
buffer passed through the real Python seam produced this template:

| Field | Supplied text | Stored text today |
|---|---|---|
| `broker` | `desk` + U+0000 + `penultimate` | `desk` |
| `schedule_method` | `lastday` | `penultimate` |

The probe on main `a1776b7` reproduced buffer decoding and template creation; it was not an Excel UI
test. Add coverage through the actual C# host call path rather than relying on that
reconstruction. The intended outcome is a visible refusal and no template publication.

## Behavior

Reject text containing an actual U+0000 before it crosses into Python. Apply the same
rule to scalar text, one-cell arrays and larger ranges. Scalar text currently bypasses
range packing; checking it at the same host boundary prevents shape-dependent behavior.

- Do not remove, replace or escape the character and continue.
- Name the function and one-based argument position; for a range, also name its
  one-based row and column relative to the supplied range. Use the existing
  `#ERROR host:` prefix and explicitly identify `NUL (U+0000)` in readable text.
- Never include a raw NUL in the error message. An argument name may supplement its
  position if retained from registration; do not look up metadata on each call.
- Literal backslash followed by zero (`\0`) is ordinary text and remains accepted.
  Ordinary Unicode, nonbreaking spaces, tabs and line breaks retain existing behavior.
- Preserve blank, empty-text, missing/default and ordinary type-validation rules.
  This does not reserve other text, such as strings beginning with `#ERROR`.

Host transport refusals occur before Python shape, type and economic validation.
Use the existing host traversal: arguments left to right, range cells row-major.
Stop at the first encountered Excel error or NUL. An earlier Excel error is returned
unchanged; an earlier NUL is reported without scanning ahead for later errors.
Document and test this narrow priority rule; do not redesign the seam's other orders.

## Implementation boundary

The owner is input marshalling in `host/Goosedove.Host/AddIn.cs`:

- Check strings in the existing `Marshal.Range` cell traversal before adding them to
  the text list, and check scalar strings in `Marshal.ToPython` before conversion.
- Ensure both `Bridge.Call` and the creator's `Bridge.Publish` path return the same
  contextual refusal. Retain their cleanup of already-converted arguments; the
  publisher must return an outcome that owns no publication.
- Check each reached input string once. Do not add a second walk over the range,
  split-and-reassemble the joined text, or allocate sanitized copies of every string.
- Preserve the reusable buffers and text list. A refused call must not contaminate
  the next call, including a smaller range or one with no text.

Keep `src/goosedove/excel/bridge.py:cells_from_buffers` as a trusted consumer of
host-produced buffers. Do not add a second input-validation pass in Python to
compensate for an unsafe host. Existing result-side NUL rejection remains unchanged.
Length-prefixed transport, escaping and a general bridge refactor are out of scope.

## Acceptance tests

1. Through the actual host creator path, submit the two-field example above to
   `_CreateTradeTemplate`. The result names argument 3, cell (1, 1), and U+0000;
   no handle is published and the store's live count is unchanged. Correcting the
   broker text creates a template with `schedule_method = lastday`.
2. Cover scalar text, a 1x1 array, a row, a column and a mixed rectangle. Exercise
   NUL at the beginning, middle and end, consecutive NULs and text consisting only
   of NUL. Refusals name the first affected argument and cell accurately.
3. Pin the same rejection through ordinary calls and creator publications. Include
   a previously converted argument so early-return cleanup is exercised.
4. Pin priority with an earlier/later Excel error in the same range and across
   arguments. Include an otherwise-invalid shape with NUL to establish that the
   host transport refusal precedes Python validation.
5. After refusal, make valid calls using the same reusable buffers: a smaller mixed
   range, a numeric-only range and a valid template. Texts remain in their intended
   fields; valid Unicode and literal `\0` survive unchanged.
6. Preserve existing blank, empty-text, missing/default, error-relay and valid-input
   behavior. Add a small Excel smoke case if that harness can deliver a genuine
   U+0000; do not label a literal `\0` test as an embedded-NUL test.

Host tests should invoke `Bridge.Call` / `Bridge.Publish` with the actual prepared
entries, not only a new string-check helper. Reuse the existing live-handle diagnostics
and release successful test publications normally.

## Work and documentation

Extend `tests/performance/HostWorkBudgets.cs` for valid and refused text input.
Measure checks of reached strings; preserve one range traversal, existing copies and
warm-buffer reuse. Numeric-only calls do no text checks. The offending range must not
reach `cells_from_buffers`, and no refused call invokes the prepared Python function;
earlier arguments may already have crossed as they do today. State before/after
counts without inventing a timing gate or a broad new instrumentation framework.

Record the input text constraint and host refusal priority in `docs/seam/inputs.md`,
with the corresponding short update to the host/transport reference where it
describes NUL-separated inputs. Do not repeat the full policy across the docs.

Run the full repository gate (`.\check.ps1`). Done means the shifting-fields example
cannot publish, scalar and range behavior agree, valid inputs retain their contents,
and a failed call leaves subsequent calls and handle ownership correct.

## As built (#NN)

Built on `claude/reject-nul-input` from `main`, one pull request, the number stamped after.

**The host.** `Marshal.ToPython` takes the function's name and the argument's one-based position
from `Bridge.Call` and `Bridge.Publish`, which already walk the arguments left to right and
release what they converted when one is refused. A scalar text is checked there; a range's text
cells are checked inside the existing `Marshal.Range` traversal, in the branch that collects them,
before the text joins the list, so one pass, no second walk, no copies and the kept buffers and
text list as they were. The refusal is `#ERROR host: <function> argument <n> cell (<r>, <c>) is
text holding NUL (U+0000), expected text without it`, the cell left out for a scalar; the text
itself is never in it. An Excel error or a NUL stops the pass where it is met, so the first in
traversal order is the one reported and nothing after it is looked at. The counter learns
`texts_checked`, one per text reached, the refused one included; a range of numbers reports none.
`cells_from_buffers` and the result side are unchanged.

**The tests.** `host/Goosedove.Host.Tests/NulInputTests.cs`: the shifting-fields example through
the creator's publication, refused naming argument 3 and cell (1, 1) with the live count
unchanged, and the corrected broker making a template whose `schedule_method` is `lastday`; the
character at the start, middle and end, twice over and alone, as scalar text, a one-cell array, a
row, a column, a rectangle and a table's body; the first in sheet order named; the ordinary call
and the publication refusing alike after earlier arguments crossed; the priority against Excel
errors within a range and across arguments; a wrong shape holding a NUL refused by the host before
the seam; the kept buffers serving the next calls with Unicode, a nonbreaking space, a tab, a line
break, backslash-zero and a text beginning `#ERROR` surviving unchanged; and the blank, empty,
missing and error-text rules standing. `tests/performance/HostWorkBudgets.cs`: the valid mixed
ranges and tables count `texts_checked` per text, a column of numbers none; a NUL in a text cell
stops the scan at its cell with no trip and the next call pays the warm range as before; a NUL in
a scalar text is one check and nothing else.

**Not here.** No Excel smoke case for the refusal: in a hidden Excel on 16 October, `CHAR(0)`
and `UNICHAR(0)` were `#VALUE!`, and `fixed` + U+0000 + `float` typed into a cell through COM, by
`Value2` and by `Formula` alike, arrived as `fixed`, five characters, so the harness cannot deliver
a genuine U+0000 and the refusal is the host tests' alone. The smoke types the two characters
backslash and zero into `_ShowInstrument` and shows them refused as the ordinary text they are,
which is no embedded-NUL test. No length-prefixed transport, escaping, second Python check or
bridge refactor.
