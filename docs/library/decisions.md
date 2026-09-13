# Decisions

**Informative.** Nothing here binds an implementation. The rules are in the
specifications; this is why they say what they say, and what each choice costs.

Same job as [history.md](../seam/history.md) does for the seam: a decision recorded here
is not reopened from memory.

Each entry is *decided*, *because*, and *costs*. An entry marked **open** has not been
settled; the specification says so too, and neither is a licence to guess.

---

## Dates and the valuation date

### D1 · Dates are calendar dates, weekends included

**Decided.** Every date in the library is a named calendar day. No business-day
adjustment happens anywhere in this slice.

**Because** the owner confirmed it, and because a curve that covers every calendar day
(D7) has no reason to know about holidays.

**Costs** a holiday calendar has to arrive later, as its own thing, rather than falling
out of what exists.

### D2 · A valuation date is a date plus a fraction of that day

**Decided.** `ValuationDate` holds `as_of` and `day_fraction_elapsed`, a finite number in
`[0, 1]`. Zero is the start of that date, one is the end of that same date, and the date
is preserved at every accepted fraction.

**Because** the owner asked for progress through a day to be representable, and keeping
the two fields separate means the supplied date is never silently advanced.

**Costs** the fraction has no consumer yet — see D4.

### D3 · Friday at 1.0 and Saturday at 0.0 are different records

**Decided.** They describe the same calendar-time boundary — no additional calendar time
passes between them — and they remain distinct, because they describe progress through
differently named dates. `(2026-09-11, 1)` is not normalized to Saturday, relabeled, or
merged.

**Because** the supplied date is part of the object's identity, and rewriting it would
mean the record no longer says what the user typed.

**Costs** ordering is now undefined in a way that will matter. The first function that
sorts two valuation dates, or measures elapsed time between them, meets a pair that sorts
strictly while being zero apart. **Open:** the ordering key is not decided.

### D4 · The fraction is retained before anything consumes it

**Decided.** `day_fraction_elapsed` is stored now so later specifications can use it.

**Because** the owner supplied it as part of what a valuation date means.

**Costs** this is generality bought before a second consumer exists, which
[golden rule 34](../golden-rules.md) advises against. The alternative — leave the field
out until something needs it — was not taken. **Open:** worth revisiting when the first
consumer is specified, together with D3.

### D5 · The record is a small frozen object, not a DataFrame

**Decided.** Two scalar fields, immutable after construction. No array is allocated to
hold one date and one fraction, and the constructor does not become a batch function.

**Because** it is read far more often than built and never iterated.

**Costs** nothing yet.

---

## The discount curve

### D6 · The curve's first date is its own start, with no separate valuation-date input

**Decided.** The first row of the supplied table defines the date the curve begins at, and
it is retained with the curve.

**Because** a curve anchored at a factor of exactly one (D8) already carries its start
date in its data; a second argument could disagree with it.

**Costs** the relationship between this date and a `ValuationDate` used in the same
calculation is now undefined. **Open** — see D12. The field is also currently called
`as_of`, which is the same name the valuation date uses for a different thing.

### D7 · Every calendar day through the final date must be supplied

**Decided.** For `N` rows the dates are the start, start + 1 day, through start + (N − 1)
days. Weekends, holidays and other non-trading days each need their own factor. Missing,
duplicate, reversed or otherwise non-sequential dates fail. The table is not sorted, gaps
are not filled, and factors are not generated to repair it.

**Because** an explicit daily table means no interpolation happens at lookup time, and
nothing has to guess what a missing day meant.

**Costs** a ten-year curve is 3,631 rows the user has to have on a sheet. The
[interpolation utility](utilities/interpolate-discount-factors.md) exists to produce them
from sparse points; the constructor still rejects a sparse table passed directly.

### D8 · The factor at the start date is exactly one

**Decided.** Another value is rejected rather than overwritten or rescaled.

**Because** the curve discounts back to its own start, so its first factor is one by
definition.

**Costs** a table whose first row is not the anchor has to be corrected upstream.

### D9 · Factors are finite, in (0, 1], and non-increasing

**Decided.** Zero, negative values, and values above one fail. Equal consecutive factors
are allowed, including a flat curve of all ones. Any increase is rejected even when both
values lie in the interval. Nothing is clipped, smoothed or rounded.

**Because** the owner asked for it, and an increase in this data has so far meant bad
input rather than a real negative rate.

**Costs** the upper limit of one is an artificial restriction, and the owner accepts it.
The [ECB's discount-factor formula](https://www.ecb.europa.eu/pub/pdf/other/mb200812_focus04.en.pdf)
(page 41, footnote 5) implies a factor above one for a negative zero-coupon yield over a
positive maturity. Such curves cannot be built here.

Two notes for whoever implements it. The rules overlap: `df[0] == 1` and non-increasing
together already imply `df ≤ 1`, and positivity only needs checking at the last element.
And NaN or infinity cannot arrive from a cell at all — Excel sends finite doubles only
([inputs.md](../seam/inputs.md)) — so those rejections exist for Python callers, not for
worksheet users.

### D10 · Linear interpolation runs on the discount factors themselves

**Decided.** The [utility](utilities/interpolate-discount-factors.md) interpolates `df`
directly, weighted by calendar days, between adjacent supplied points.

**Because** it is the simplest reading of "fill the gaps", and the source data is already
close to daily.

**Costs** this is a model choice, not data preparation. Interpolating on `df` rather than
on `log df` makes the implied forward rate ramp inside each knot gap and step at each
knot; over a one-year gap in the owner's own sample that is roughly one basis point of
drift. Small at daily spacing, and worth knowing it was chosen rather than inherited.

### D11 · The curve's final date is a hard upper bound

**Decided.** `max_date` is the last date in the validated table, inclusive. A process
using a later date fails before publishing a result, naming the operation, the requested
date and the curve's maximum. The rule covers processes that never request a discount
factor, and dates generated during processing, not only supplied ones. Nothing is
extrapolated, extended, substituted or clamped.

**Because** the owner wants a calculation to fail rather than quietly run past the data
it has.

**Costs** as written, the bound is a property of *the library*, which means every
date-touching function either reads it from somewhere global or re-checks it. That
conflicts with [golden rule 11](../golden-rules.md), no ambient state, and with the same
requirement's own insistence that the governing curve be an explicit dependency. See D12.

### D12 · How the bound reaches a calculation — **open**

**Not decided.** Which curve governs, how its bound is supplied, and what happens to a
standalone constructor built before any curve exists.

The direction under consideration: treat the bound as a property of the inputs a
calculation was given rather than of the library. One object holds the valuation date and
the curve or curves, is passed explicitly as an argument, and the bound is checked in one
place — where dates are produced. Excel then tracks the dependency through the ordinary
handle contract, and with several curves the bound is the minimum of theirs.

This also has to absorb a second and third curve, which a swap needs, and the naming
collision noted in D6. Behaviour for dates *before* the start date is separately open.

---

## Units

### D13 · Unit definitions are owned by the library

**Decided.** One reviewed set, shipped in a small internal module. Workbook users cannot
create, replace or override them. There is no worksheet constructor, no handle, no file
path and no configuration override. Changing a code, factor or convention takes a reviewed
library change.

**Because** a unit that means different things in two workbooks is worse than a unit that
cannot be changed.

**Costs** a desk convention the library does not know about has to be added by an engineer.

### D14 · Four categories in one collection, no conversion between them

**Decided.** `UnitConversions` groups `volume`, `mass`, `energy` and `usd`. Each keeps its
own definitions and reference unit. Grouping them does not permit cross-category
conversion. `contract` is excluded.

**Because** internal code that needs conversions can take one object reference instead of
four arguments, while a cross-category conversion needs an assumption — a density, a heat
content — that no table here carries.

**Costs** commodity work does convert across categories. When it does, the assumption has
to become an explicit input somewhere, and that is not specified.

### D15 · One reference unit per category, with a self-reference row of one

**Decided.** Every definition is expressed directly in its category's reference unit, so
conversion is `quantity_to = quantity_from * size_from / size_to` with no chains to follow.

**Because** the supplied tables are already in that shape and the arithmetic stays in one
line.

**Costs** floating point. The relations are exact in decimal but not in binary: `1 GAL` to
`L` gives 3.7854117839999994 against an exact 3.785411784, and `1 MWH` to `GJ` gives
3.5999999999999996 against 3.6. Both are one unit in the last place. Round trips through
the reference unit are exact. Acceptance tests need a stated tolerance rather than
equality.

### D16 · BTU means Btu_IT, and THERM is 100,000 of them

**Decided.** One Btu is exactly 1055.05585262 joules
([NIST, footnote 9](https://www.nist.gov/pml/special-publication-811/nist-guide-si-footnotes)).
`MMBTU` is one million Btu_IT; `THERM` is exactly 100,000 Btu_IT, so `1 THERM = 0.1 MMBTU`.
`GJ` is 1e9 joules, `MWH` is 3.6e9 joules.

**Because** "Btu" alone names several different definitions, and the supplied factors match
this one.

**Costs** none, provided the meanings stay written down beside the codes.

### D17 · Unit and category codes match exactly, including case

**Decided.** `GAL`, `BBL`, `MWH`, `MT` and the rest have one spelling each. `volume` is not
`Volume`. Codes are not trimmed or re-cased on the way in.

**Because** a code is an identifier, not prose.

**Costs** a user who types `gal` gets an error. This is deliberately different from
worksheet header matching (D19).

---

## Worksheet surface

### D18 · Names

**Decided.** Worksheet functions are PascalCase; parameters and data fields are
snake_case, matching the wording used in Excel help; object and seam type names are
PascalCase, reusing the seam's spelling where one exists.

**Because** it matches what the bridge already exports and what the probes already do.

**Costs** nothing. **Open:** the `util_` prefix on the interpolation utility is a working
name, not a convention. Excel groups functions by Category, which the host does not
currently set; a category would do the same job without putting two conventions in one
name.

### D19 · Worksheet headers have one canonical name, matched without regard to case

**Decided.** Each field has exactly one name. `date`, `Date` and `DATE` identify the same
header; `Maturity` and `Mid` are different names and fail. Unknown headers fail. Duplicates
fail after case-insensitive matching. Header text crosses the seam unchanged and the
library interprets it.

**Because** case is how a spreadsheet looks, not what a column is; an alias list is a second
name for one thing.

**Costs** source data has to be renamed rather than mapped. **Open:** leading and trailing
whitespace, and whether columns may be reordered when their headers move with them.

### D20 · NumPy is the default for numerical arrays and calculations

**Decided.** Numerical collections are NumPy arrays with `float64` as the default dtype and
`datetime64[D]` for dates. Scalars keep their scalar shapes — a single date is a NumPy
scalar, a single fraction stays a Python float. Text stays as the seam's tuples. Worksheet
declarations keep their seam types, because registration selects its validation from them.

**Because** the numerical work is vectorized and the seam already hands over arrays.

**Costs** nothing here. Mixed text-and-numeric records stay as typed records; they are not
forced into an object-dtype array to make the collection "a NumPy thing".

### D21 · How a date/factor table crosses the seam — **open**

**Not decided.** `NumberArray` hands the library `float64`, so date serials arrive as plain
numbers. The seam cannot convert them, because it identifies arguments by declared type and
the date column is identified by header text, which is meaning the seam does not read
([inputs.md](../seam/inputs.md) rule 6). If the library converts them instead, Excel-date
parsing has moved into pricing code, against
[tenet 1](../../PRINCIPLES.md).

Shapes under consideration:

| | Shape | Needs new seam work |
|---|---|---|
| a | one table type whose columns are typed by position | yes, and one more per table shape |
| b | `dates: DateColumn` + `factors: NumberColumn` | no — both types exist |
| c | `as_of: Date` + `factors: NumberColumn`, daily spacing structural | no |
| d | keep one body, convert in the library | no, but against tenet 1 |

The trade-off is misalignment. One welded body means a date and its factor cannot be
separated; two ranges means `A2:A15` against `B3:B16` is equal-length, off by one row, and
nothing catches it. (c) has no date column to misalign, and would also remove the header row
and with it the open questions in D19.

Whichever is chosen, it applies to both the curve constructor and the interpolation utility;
they share the input shape today and should keep sharing it.

---

## Handles

### D22 · Handles travel through ordinary Excel references

**Decided.** A creator formula returns a handle into its cell; a consumer refers to that
cell, directly or through a defined name referring to it. Workbook authors use Excel's own
references, not handle strings they maintain themselves. Pasting a handle as a value, typing
one into a formula, or assigning the literal text to a name is not a supported workflow and
acquires no ownership.

**Because** Excel already maintains a dependency graph, and a second identity system would
have to be kept in step with it.

**Costs** the seam cannot tell where an argument came from, so a live handle may resolve
however it reached the argument. This is a usage contract, not a check.

### D23 · Cell addresses are not object identity

**Decided.** An address locates a formula. It must not become an object ID, a cache key or a
permanent producer slot. A moved formula follows Excel's rules and must not collide with
whatever previously occupied the destination.

**Because** [golden rule 10](../golden-rules.md): identity is content, never address.

**Costs** reuse of an unchanged object needs some other key, which is not yet chosen.

### D24 · A missing object is a failure, not a cache miss

**Decided.** Cleanup must not delete an object a live creator owns or a retained dependency
needs. If a capacity policy is ever introduced, failed new construction leaves existing owned
objects valid. A missing object where the contract promises one is reported, never
substituted and never silently answered from a previous result.

**Because** [tenet 2](../../PRINCIPLES.md): a wrong number that looks right is the worst
outcome.

**Costs** memory is bounded by what workbooks hold open, not by a cache size.

### D25 · Reuse unchanged objects, publish changed ones — **favored, not settled**

The direction: recalculating an unchanged creator reuses its existing object and handle;
changing an input publishes a new immutable object under a new handle, and the old object is
not mutated or retargeted. Failed construction publishes nothing and must not present the
previous handle as though it described the new inputs.

Not yet decided: the precise reuse and equality rule, reuse across duplicate creator cells,
inputs that differ only before normalization, release timing, whether a published handle stays
resolvable after its creator releases it, behaviour across save and reopen, and recovery from
unexpected loss. [The research notes](notes/excel-dna-research.md) are the evidence gathered so
far; they select no mechanism.

### D26 · What the seam needs before any of this exists — **open**

Nothing in `_RESULTS` stores an object today, so a constructor returning one refuses to
register. The pieces are a result rule that stores and returns text, a store, an argument rule
that resolves text back to an object, and somewhere for those registrations to live that does
not make the pricing library import the bridge. The C# host needs no change for a Python-side
store: it already returns a string as a string and already passes strings in. Excel-DNA's
`[ExcelHandle]` machinery is one way to own the store, not a requirement.

---

## Measurement

### D27 · How a work counter reaches library code — **open**

[CLAUDE.md](../../CLAUDE.md) says code that prices, caches, hashes or converts takes a
`WorkCounter` and reports what it did. [Golden rule 9](../golden-rules.md) says instrumentation
does not thread collectors through pricing code. Both cannot hold for a function reached
through the seam, whose signature is fixed by the seam contract and can neither accept a
counter nor return one.

Worth settling before the first library pull request, because it decides the shape of every
internal signature.
