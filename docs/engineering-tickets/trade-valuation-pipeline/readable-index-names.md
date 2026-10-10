# Human readable index names

[Pipeline overview](README.md) · [UAT item 6](surface-uat-notes.md#6-human-readable-index-names)

**Status:** Built in #169 on the prototype stack above #168, the page as a ticket; the
[As built](#as-built-169) section at the end says what was built and what was not. Ready for
engineering, 9 October 2026. Inspected prototype: PR #168 at `d1633d7`. Delivered as one
focused PR on the prototype successor.

## Outcome

Add a human-readable description when creating an index so someone unfamiliar with a
desk's short names can identify it. Store this text as `display_name` on the index and
show it through `util_ReadHandle`. No pricing function consumes the new field.

| Existing `name` | New `display_name` |
|---|---|
| `WTI` | West Texas Intermediate crude oil - NYMEX |
| `NG` | Henry Hub natural gas - NYMEX |
| `HG` | Copper - COMEX |

These are illustrative user-supplied descriptions, not a library lookup table.

## Creation and readback

Add **required text immediately after `name`**:

```text
_CreateIndex(
    name,
    display_name,
    schedule,
    index_conventions,
    contract_specifications,
    [holiday_calendar],
    [reporting_lot]
) -> index handle
```

Use the existing required-text validation: missing, blank, empty text and nontext values
fail at the seam. Preserve supplied text without trimming or changing case. No fixed
list, uniqueness rule, parsing, default or fallback to `name`. The two fields may contain
the same text if the desk wants that.

Retain `display_name` on the immutable Index record. In `util_ReadHandle(index)`, insert
a `display_name` column immediately after `name`, with type `str` and the supplied value.
Preserve the remaining columns' order and meanings.

The existing `name` keeps its current meaning, price-vector matching and handle labels.
Descriptions do not select indices, alias names, infer contracts or change conventions,
valuation or risk. No new reader or changes to the trade reports are needed.

Editing the description follows normal index recreation and dependency behavior. It
creates a new index when the creator's inputs change; its dependent objects rebuild as
usual. Preserve existing object-identity checks and lifetime rules. No special reuse or
cache mechanism is part of this change.

## Delivery

Update the Index record and builder, `_CreateIndex`, index readback and Excel help. The
current locations are `src/goosedove/index_definitions/index.py`,
`src/goosedove/excel/index_definitions.py` and `src/goosedove/excel/utilities.py`.

Migrate every kept `_CreateIndex` formula and internal caller to the new argument order,
including tests, host replay, smoke/lifetime scripts, workbook examples and documentation.
Preserve existing `name` values and economic inputs. Check IFERC and Gas Daily examples
where the optional holiday-calendar argument is omitted, as well as futures examples
with a calendar and reporting lot. Update the index/help/readback pages and UAT item 6.

Acceptance is deliberately small:

- A created index retains the exact display text and readback shows both name columns.
- The new argument follows existing required-text refusals, with no coercion or default.
- Price-vector matching and handle labels continue to use `name`, not `display_name`.
- All migrated examples retain their existing value and risk expectations. Run the full
  gate and keep existing work-budget checks passing; no new work belongs in preparation
  or evaluation. Any existing golden changes remain separately reviewed.

Do not add a name registry, search/selector UI, new metadata handle or downstream report
fields. This PR supplies, stores and exposes one descriptive field.

## As built, #169

Engineering's record of what landed, in the ticket's terms.
[index.md](../../library/index-definitions/index.md) is the page.

- **The field.** `Index.display_name` sits after `name` in `src/goosedove/index_definitions/index.py`,
  kept as given, read by nothing but the readback; `index(name, display_name, schedule, ...)` takes
  it second. `_CreateIndex(name, display_name, schedule, index_conventions,
  contract_specifications, [holiday_calendar], [reporting_lot])` in
  `src/goosedove/excel/index_definitions.py` declares it as required text, so the seam's own rules
  refuse a missing, blank, numeric, empty or array value in its words, `display_name is blank,
  expected text`; nothing is trimmed, re-cased, defaulted or compared with the name, and the two
  may say the same thing. Its help: `A description a reader who does not know the desk's short
  names would understand, such as Henry Hub natural gas - NYMEX, kept as typed and read for
  nothing else.`
- **Readback.** `util_ReadHandle(index)` spills `display_name` as the second column, type `str`,
  right after `name`; the columns after it keep their order and meaning, so a futures index with a
  reporting lot reads back eleven columns and one without seven. The handle, the price vector's
  match against the history's index and every message keep the name.
- **Migration.** Every creator gives a description: the tests' fixtures by name, `Henry Hub natural
  gas - NYMEX`, `West Texas Intermediate crude oil - NYMEX`, `Waha basis - ICE` and the like, a
  helper's variable name followed by `index`; the smoke's 27 formulas, the lifetime and retention
  scripts' one each, the host's facts and data rows, the pages' example formulas and the kept
  workbook's seventeen `_CreateIndex` formulas, each with a literal after the name, every object
  over them rebuilt and every block's numbers standing.
- **Counts.** The creator's seam ledger validates seven declared arguments where it validated six
  and runs the text rule once more, for the display name; `_resolve`, the library's `index` and
  the publish are as they were, and nothing is counted in preparation or evaluation. The index's
  record holds one more reference.
- **Not built.** No registry, selector, alias or lookup by description, no new handle, no field on
  the trade reports, and no reading of the description by any pricing function.
