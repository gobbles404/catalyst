# Decisions

The record: why each page says what it says, and what each choice costs. Nothing here
binds an implementation; the rules are on the pages. Same job as
[history.md](../seam/history.md) does for the seam: a decision recorded here is not
reopened from memory.

Each entry is *decided*, *because*, and *costs*. An entry marked **open**, or the **Open**
tail of a decided one, is not settled; the page that waits on it says so in its first line,
and neither is a licence to guess. Whatever is open ends with what would decide it, as the
seam's open table does.

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

**What would decide it:** the first function that orders two valuation dates or measures
the time between them.

### D4 · The fraction is retained before anything consumes it

**Decided.** `day_fraction_elapsed` is stored now so later specifications can use it.

**Because** the owner supplied it as part of what a valuation date means.

**Costs** this is generality bought before a second consumer exists, which
[golden rule 34](../golden-rules.md) advises against. The alternative — leave the field
out until something needs it — was not taken. **Open:** worth revisiting when the first
consumer is specified, together with D3.

**What would decide it:** that first consumer, decided with D3.

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

**What would decide it:** the owner naming the field, `start_date` or another word,
decided with D12.

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
collision noted in D6. Behaviour for dates *before* the start date is separately open. The
temporary reader built in #53, `util_ReadDiscountFactor`, fails for a day before the curve's
start as it does for one after it, because it has no data there; that is the reader's own
rule, not a decision of this question.

**What would decide it:** the object that carries the valuation date and the curve or
curves as one explicit argument, designed with the first pricing function.

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

**What would decide it:** the owner; a category would be a seam item first, since the host
sets none today.

### D19 · Worksheet headers have one canonical name, matched without regard to case

**Decided.** Each field has exactly one name. `date`, `Date` and `DATE` identify the same
header; `Maturity` and `Mid` are different names and fail. Unknown headers fail. Duplicates
fail after case-insensitive matching. Headers bind in any order, and nothing else is
forgiven: a header with a space in it is unknown, and the message quotes it as typed. Built
by #51 as [inputs.md](../seam/inputs.md) decisions 29 and 30: the function owns the field
names and their column types through its schema, and the library receives typed columns.

**Because** case is how a spreadsheet looks, not what a column is; an alias list is a second
name for one thing; and the seam never coerces, so a stray space is not forgiven either.

**Costs** source data has to be renamed rather than mapped, and a stray space is an error
rather than a guess.

### D20 · NumPy is the default for numerical arrays and calculations

**Decided.** Numerical collections are NumPy arrays with `float64` as the default dtype,
`datetime64[D]` for dates, and `bool` for a column of booleans. Scalars keep their scalar
shapes — a single date is a NumPy scalar, a single fraction stays a Python float. Text stays
as the seam's tuples, and a table arrives as the schema's record, one typed attribute per
column ([bridge.md](../seam/bridge.md#a-table-a-header-row-and-a-schema)). Worksheet
declarations keep their seam types, because registration selects its validation from them.

**Because** the numerical work is vectorized and the seam already hands over arrays.

**Costs** nothing here. Mixed text-and-numeric records stay as typed records; they are not
forced into an object-dtype array to make the collection "a NumPy thing".

### D21 · A table crosses as a header row and a schema-bound body, and the curve's table is that table

**Decided.** A table crosses as two arguments, a `TextRow` of headers then a mixed body,
and the function declares a schema, one line per column, the header name and its column
type. The seam binds the headers by name and checks each column against its type, and the
library receives one record with a typed attribute per column: dates as `datetime64[D]`
arrays, numbers as `float64` arrays, text as tuples, booleans as bool arrays, aligned by
row. Built by #51: [inputs.md](../seam/inputs.md) decisions 27 to 33 and
[bridge.md](../seam/bridge.md#a-table-a-header-row-and-a-schema). Business rules stay in
the library and run once on the typed columns.

**Because** a body preserves the date/factor pairing the worksheet supplied, a schema says
which numbers are date serials, and doing that at the seam keeps Excel's conversions at the
boundary, as [tenet 1](../../PRINCIPLES.md) requires.

**Costs** the seam reads two arguments together for a table, which it does for nothing else;
and a one-row table costs what about thirty-five scalar calls cost, so a function that takes
one trade at a time takes scalars.

**Decided 2026-09-13** for the curve, by the owner in conversation, and built in #53:
`CreateDiscountCurve` takes the table, a header row `date` and `discount_factor` over a
welded body of dates and factors, `=CreateDiscountCurve(A1:B1, A2:B4)`. `df` was rejected as
a header, to keep clear of "dataframe". `InterpolateDiscountFactors` takes the same table
when it is built and returns `date` and `discount_factor` columns. The table won because the
sheet keeps the pairing and the headers say which column is which; its cost is two ranges to
select instead of one. The candidates weighed, each of which the seam could carry:

| Layout | Formula | What it costs |
|---|---|---|
| a table: a header row and a body, schema `date: DateColumn`, `discount_factor: NumberColumn` | `=CreateDiscountCurve(A1:B1, A2:B4)` | the sheet keeps the pairing; two ranges to select instead of one |
| separate typed columns, no headers | `=CreateDiscountCurve(A2:A4, B2:B4)` | two ranges can be selected one row out of step, `A2:A10` beside `B3:B11`, and equal lengths cannot catch it |
| a numeric body with fixed positions, no headers | `=CreateDiscountCurve(A2:B4)` | meaning by position alone; swapped columns are silent until the rules catch them |
| a start date and factors, the dates generated | `=CreateDiscountCurve(A2, B2:B4)` | one row per factor from the start; the supplied dates are gone, so a missing source observation shifts every factor after it with nothing to say so |

Two earlier candidates were no longer live: a header row over a `NumberArray` body,
superseded by the table type, which binds and converts the columns that layout would have
needed; and headers inside the body, against [inputs.md](../seam/inputs.md) decisions 11
and 27.

### D29 · A library rejection raises `ValueError`

**Decided.** Every business rule a page lists raises `ValueError` with the page's message,
so the cell shows `#ERROR {function}: ValueError: {message}`. Decided 2026-09-13.

**Because** the type is part of what the desk sees, and one family name for every rejection
means the message is the thing to read; it is also the seam's own example in
[outputs.md](../seam/outputs.md) rule 7.

**Costs** nothing. An invented type would be a longer word in the cell that says nothing
the message does not.

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
That describes economic equality for calculation reuse; equal content does not collapse
separate trade occurrences into one retained object. Occurrence separation is fixed in D25.

**Costs** reuse of an unchanged object needs some other key, which is not yet chosen.

### D24 · A missing object is a failure, not a cache miss

**Decided.** Cleanup must not delete an object a live creator owns or a retained dependency
needs. If a capacity policy is ever introduced, failed new construction leaves existing owned
objects valid. A missing object where the contract promises one is reported, never
substituted and never silently answered from a previous result.

**Because** [tenet 2](../../PRINCIPLES.md): a wrong number that looks right is the worst
outcome.

**Costs** memory is bounded by what workbooks hold open, not by a cache size.

### D25 · Separate occurrences, replace current objects, release old ownership

**Decided.** Separate creator formulas produce separate immutable objects and handles even
with identical inputs. Separate trade rows within one batch also produce distinct objects;
they may reference shared dependencies such as a curve or valuation date. A creator can own
multiple objects, not just one object per formula.

A successful replacement publishes new objects/handles and releases the creator's previous
store ownership. There is no version history and no mutation of published objects. Deleting
the creator or closing its workbook releases that ownership promptly. Independent Python
references can keep the old data alive; they do not keep a removed token resolvable.
Failed construction/publication must not leak temporary ownership or present the previous
handle as a successful answer for new inputs. Reopening builds fresh objects through creator
execution, not reconnection to old-session text.

**Because** duplicate trade occurrences must remain independent, while memory should reflect
current ownership rather than the number of edits made to a workbook.

**Costs** identical occurrences occupy distinct objects. Excel-DNA's default argument-based
sharing does not meet this rule unchanged. Prompt release requires reliable host tracking;
ordinary Python references handle continued use of the underlying objects.

**Decided:** an unchanged creator reuses its existing objects and handles and consumes no
new publication numbers; this includes an entirely unchanged batch, and it never merges
separate creators or trade occurrences. Not yet built: since #53 a recalculated creator
publishes anew, and D26 holds the reuse with release, because both need the same creator
tracking.

**Naming direction agreed**, and amended on 2026-09-13 by the owner, who dropped the readable
label because nothing supplies one: the text is `kind:session:number`, built in #53 as
[outputs.md](../seam/outputs.md) decision 11. The kind's tag is lowercase with underscores
between words. One decimal number starts at 1 across all kinds and workbooks in the store; at
least six digits are displayed, growing without wrapping or recycling. It identifies a
publication, not a version or array position. Closing a workbook does not reset a continuing
runtime's sequence; a reset comes with a new session part, six hex characters drawn when
Python starts. The full exact text identifies the entry. Python type and function names do
not change. The [handle's text](../seam/handles.md#the-handles-text) holds examples. No label
parameter is added to a constructor.

### D26 · What the seam needs before any of this exists — **open**

**Built in #53:** the declaration `Handle[Kind]`, the seam's one alias around a class the
library defines, so a creator returns the object and its cell shows the handle, and a
consumer receives the object; one store in the bridge, a dictionary from the handle's text to
the verified kind and a strong Python reference; the three-part text; publishing as a result
rule and resolving as an accept rule, with every failure as text in the cell.
[inputs.md](../seam/inputs.md) decisions 34 to 37, [outputs.md](../seam/outputs.md)
decisions 10 to 12, [bridge.md](../seam/bridge.md#a-handle-one-store-and-the-text).
Registration keeps all of it out of the pricing library, and adding a kind adds no code of
its own. Every creator call publishes, so two equal creator cells hold two objects, as D25
asks; a recalculated creator publishes anew, which D25's reuse rule forbids, and this entry
holds that with release. The store grows until Excel closes.

**Open:** release and reuse, which need the same creator tracking, and the host hooks no
Excel event today. Two ways were researched. Excel-DNA's own object handler, in the version
the host references, tracks a creator through Excel's live-data subscription and disposes
the object when the formula goes away; but it shares one object between creator cells with
equal inputs, against D25, pays a caller lookup, a hash of the whole input and one extra
Excel call on every recalculation of a creator, and is documented as unreliable inside array
formulas. Shipped add-ins with handles, xlOil, PyXLL's earlier cache and QuantLibXL, remember
which cell made each object, replace that cell's previous object on its next recalculation,
purge on workbook close, and let a deleted creator's object wait for the close. The evidence
is [excel-dna-handles.md](../seam/excel-dna-handles.md). Open with it: creator tracking and
callback timing, including safe shutdown; the batch spill's declaration, row errors, blocked
spill, resizing and partial reuse of unchanged rows when others change; the equality key and
the preparation work for unchanged-creator reuse; whether moving a creator may rebuild its
objects or must keep their handles; reopen calculation timing, interrupted calculation, undo
and unexpected loss.

**What would decide it:** the next pull request, with counts: correct worksheet behaviour
first, then the work per creator recalculation, then retained memory, measured on whole
calls. The store and the text stay as built under either way.

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

**What would decide it:** the owner, in one line. The host's precedent is #31: the observer
supplies the counter, and the worksheet path passes none.

---

## The pages

### D28 · One page per function, the spec that becomes the reference

**Decided.** Each worksheet function has one page, which starts as the spec and becomes
the reference when the function ships. Its first line is its state, `Open: D21, D26.`,
`Ready.` or `Built in #NN.`, read off its own Open section and moved with the code in the
same pull request. How a page is written, and the skeleton to copy, are
[conventions.md](conventions.md); this record holds why. The desk reads Excel's own help text as it types, so a page's Excel help
section is the one product-facing text; since #55 the declaration carries that text, the
docstring and the words beside each parameter, and the page quotes it. `docs/library/` is for
engineers and the owner as reviewer, and does not ship. A spec for something the seam must do lives with the seam and
is absorbed into the seam's pages when built. Decided 2026-09-13.

**Because** a page with one job cannot go stale in a second copy, and the seam's own pages
already work this way: `inputs.md` holds the rules with what is built and what is next side
by side, and `history.md` holds why. The first drafts mixed the contract with the seam's
own rules, their own history, and sample data, and said as planned what #51 had built.

**Costs** an engineer reads two directories, the seam's and this one, and the desk's words
live in a table on a page rather than in a document of their own.

---

## Market definitions

### D30 · An argument left out, with nothing in its place: what the seam needs first — **open**

**Wanted, not built.** The seam's optional argument is a default: a missing argument takes a
stored value of the declared type, checked once at registration, and `None` is the host's
word for a blank cell, so no declaration today says "may be left out, and then there is
nothing" ([inputs.md](../seam/inputs.md) decision 4, and what
[bridge.md](../seam/bridge.md#what-is-deliberately-absent-and-why) lists as deliberately
absent). `CreateExpirySchedule`'s `options_expiry` needs exactly that: an index without
options has no column to pass, and a stand-in column would be a value that looks right,
which [tenet 2](../../PRINCIPLES.md) forbids. The owner's word, 2026-09-14: optional means it
may be left out. The item is in [inputs.md](../seam/inputs.md) under what comes next, with the
recommended form beside it; its design is the seam's, and a blank cell in the slot must still
fail, because blank and left out are different facts.

**What would decide it:** the seam pull request that builds it, before the function is built.
