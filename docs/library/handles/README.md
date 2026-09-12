# Handles: the Excel worksheet contract

This is a planning specification. The worksheet use case below is agreed. The
reuse direction is favored; the implementation and detailed lifecycle still need
discussion and verification. No handle infrastructure or new worksheet functions
are implemented by this document.

**Excel owns the worksheet dependency graph. The runtime owns the retained
objects. The seam resolves the current handle value to the expected Python object.**

Read this contract before the [Excel-DNA research](excel-dna-research.md). Handles
are shared infrastructure for the library, alongside the Globals and Utilities
specifications, rather than a subclass of either.

## Agreed: we use ordinary Excel references

A creator formula returns a handle into its cell. A consumer formula refers to
that cell, directly or through an Excel defined name that refers to the cell.
The handle is opaque text identifying an object retained in memory. Workbook
authors use Excel references and names to connect formulas; they do not maintain
handle strings themselves.

Concrete worksheet example:

```excel
Data!A1:B1    date / df headers
Data!A2:B15   the daily discount-curve table

Inputs!B2    =CreateDiscountCurve(Data!A1:B1, Data!A2:B15)
              displays Curve:17

Defined name DeskCurve refers to =Inputs!$B$2
```

A future consumer's curve argument can be either `Inputs!$B$2` or `DeskCurve`.
These fragments illustrate the connection, not additional proposed functions:

```text
consumer(..., Inputs!$B$2, ...)
consumer(..., DeskCurve, ...)
```

Excel tracks the dependency on `Inputs!B2` in both cases. On evaluation it passes
that cell's current value, such as `Curve:17`, to the seam. The seam resolves the
value once and hands the library the expected typed Python object. The library
does not need to receive, parse, or look up the worksheet address or defined name.
The current value-only host also does not tell Python whether an argument came
from a reference, a name, or literal text.

`DeskCurve` is an Excel name for a cell. It is not a second object registry, a
permanent alias maintained by the library, or the curve's content identity.

## Favored direction: reuse unchanged objects; publish changed objects

The handle strings below are illustrative. Their spelling and numbering are not
a selected implementation, a persistent ID, or a user-managed version sequence.

| Worksheet action | Creator cell when evaluated | Consumer behavior |
|---|---|---|
| Supply a valid curve table | Displays `Curve:17`, identifying the retained curve. | A reference to the creator supplies `Curve:17`; the seam resolves it. |
| Recalculate the same active creator with unchanged inputs | Reuses the existing object and handle. | Resolves the same retained object without reconstruction during lookup. |
| Change a factor to another valid value | Publishes a changed immutable curve and displays `Curve:18`. | Excel propagates the dependency change; the same consumer formula now receives `Curve:18`. |
| Supply invalid curve data | Displays the construction error and publishes no successful replacement handle. | Dependent formulas receive the failure through the seam's error path. |

The update is:

```text
curve inputs change
    -> creator cell recalculates: Curve:17 -> Curve:18
    -> dependent formula recalculates using its existing cell/name reference
    -> seam resolves Curve:18
```

The old curve is not mutated or retargeted to contain the new data. Its handle
keeps its original meaning for as long as that handle remains valid. Failure to
construct the replacement must not present the previous successful handle as
though it represented the invalid new inputs.

This follows Excel's calculation mode. In manual mode, editing input cells does
not promise immediate propagation: when the user requests calculation, the
creator and dependents must update in Excel's dependency order. The runtime must
not invalidate the still-retained current object merely because no lookup has
happened recently.

Reuse across multiple identical creator cells, inputs that differ only before
normalization, or a return to previously used inputs still needs a precise rule.
The favored unchanged-input behavior does not promise a history, rollback,
permanent handles, or retention of every old curve. A new handle can identify a
new immutable object without a formal version system.

## Supported references and unsupported text-token workflows

Cell references and defined names referring to cells are the supported workbook
workflow. Ordinary formula references may relay a creator's current value; such
a relay remains an Excel dependency, not an independent owner simply because it
displays handle text. Renaming a name, inserting rows, or moving formulas must
follow Excel's reference behavior without creating a second identity system.

Pasting a handle as a value, typing it into a formula, assigning a literal handle
string to a defined name, or saving it outside the workbook dependency chain does
not establish a supported ownership or persistence promise. A name referring to
`Inputs!$B$2` and a name containing the constant string `"Curve:17"` are different
workflows.

This is a usage contract, not a claim that the current seam can reject every
literal. A live handle value might resolve regardless of how it reached the
argument. Rejecting based on its worksheet provenance would need additional host
information and has not been specified. Unknown, expired, or wrong-kind values
must fail visibly; matching-looking text must never select an unrelated object.

## Ownership and the division of responsibilities

| Layer | Responsibility |
|---|---|
| Excel | Maintains references and names, schedules calculation according to its dependency graph and calculation mode, and displays creator values and failures. |
| Host and seam | Publish and resolve handles, enforce the declared object kind at the boundary, retain/release the Python references they own, and integrate with Excel's lifecycle. |
| Library | Builds valid immutable objects, consumes typed objects, and retains actual Python dependencies needed by other retained objects. It does not navigate worksheets or import the Excel bridge. |

A live creator owns its currently published object. A lookup or an additional
cell displaying its value is not automatically a separate ownership record. If
another retained Python object depends on it, that object must retain a valid
Python reference of its own. Those references can keep the underlying object
alive even after the original creator moves on to a replacement.

The previous object is eligible for release when no owner still needs it. Do not
choose the moment by seeing a changed input or an old generation number alone:
in-flight calls and retained dependencies must remain safe during replacement.
The exact release timing and whether a published handle remains resolvable after
its creator releases it remain open; retaining the underlying Python object and
retaining its public handle are different facts.

Cell addresses locate formulas. They must not become object IDs, semantic cache
keys, or permanent producer slots. A moved formula follows Excel's rules; it
must not collide with the object that previously occupied the destination or be
treated as an unauthorized second producer merely because its address changed.
This does not prohibit Excel-DNA from tracking subscriptions internally.

## A missing object is not an ordinary cache miss

Memory cleanup must not delete an object still owned by a live creator or needed
by a retained dependency. In particular, an LRU or age limit must not evict the
object behind a still-valid worksheet handle merely to admit another object.
If a capacity policy is introduced, failed new construction must leave existing
owned objects valid. The capacity mechanism itself has not been selected.

Excel sees the value in the creator cell, not the object store. Removing the
object behind `Curve:17` does not change that cell or automatically ask Excel to
rebuild the curve. A missing object where our ownership contract promises one is
a runtime failure: report it, never substitute another curve or silently reuse a
previous calculated answer. Recovery behavior must be designed and verified;
neither consumer recalculation nor a generic full-recalculation instruction is an
established repair. See the [native recovery finding](excel-dna-research.md#removal-and-recalculation).

Collecting objects proven unused is distinct from evicting live handle objects.
An optional calculated-result cache can discard an answer that can be recomputed
from available inputs on the next request. It must not discard the required input
objects along with it. Construction reuse, calculation reuse, and object lifetime
remain separate responsibilities.

Saving a workbook preserves formulas, names, inputs, and possibly displayed
handle text; it does not persist the Python object store. Startup/reopening must
have a defined creator-reconstruction policy before the feature ships. Cached
handle text from a previous runtime must not accidentally resolve to an unrelated
new object. Session identification, startup calculation, undo, and interrupted
calculation remain implementation questions.

## Draft acceptance scenarios

These are planning cases, not implemented tests or claims that native Excel-DNA
already meets the entire contract. Pseudocode consumers above are diagnostic
stand-ins; no companion product functions are introduced here.

| Scenario | What must be established |
|---|---|
| Consumer uses a direct creator-cell reference or a name referring to it | Both paths supply the current handle and resolve the correct typed object. |
| Unchanged creator recalculation | Favored behavior reuses the active object/handle; measure preparation as well as publication and lookup. |
| Valid factor change | The creator publishes the new curve; consumers update through their existing references; retained old objects stay unchanged. |
| Invalid factor change | The creator and dependent formulas show the appropriate failure; no successful handle is published for the invalid inputs. |
| Manual calculation | Owned objects remain available between calculation requests; a requested calculation follows Excel's dependency behavior. |
| Insert rows, sort a table, cut/paste a formula block, move across sheets, or update a name | Values and references follow Excel's semantics; no cell-slot collision or false second-producer error is introduced. |
| Duplicate creator formulas, then remove one | Removing one owner does not invalidate an object still owned by another. The exact reuse rule is to be finalized. |
| Replace/delete a creator while another retained object uses its old curve | The dependent Python object retains valid immutable data; verify release when its final owner is gone. |
| A live object's store entry is deliberately removed in a diagnostic test | The failure is visible; any promised recovery is verified against the chosen native call-state behavior. |
| Pasted literal, old-session token, or diagnostic display | These do not acquire ownership just by appearing as text. Verify unknown/expired/wrong-kind failures and stale-session safety. |
| Undo, interrupted calculation, workbook closure, and reopening | Agree exact promises, then exercise them in Excel before treating the lifecycle as complete. |

Use deterministic work counts for construction, transport, copies, fingerprinting,
lookup, publication, scans, and release where they occur. Observe retained bytes
and peak occupancy with shared ownership accounted for. Record end-to-end timing
as diagnostic evidence, following the repository's rule against timing gates.
Existing seam checks are a baseline; they do not validate an unbuilt handle system.

## Still to decide

Excel-DNA 1.9 remains the first candidate to evaluate. Its store and subscription
tracking may supply much of the host work; no custom Python registry, COM workbook
scan, collector, LRU, recovery macro, or fingerprint framework is selected here.

The remaining discussion covers precise reuse/equality rules; native registration
and Python ownership; release timing; session safety and reopening; recovery from
unexpected loss; and the user-visible behavior of undo and interrupted work.
The supported use of Excel cell references and names is settled and should not
be reopened as a requirement to support independently managed text tokens.
