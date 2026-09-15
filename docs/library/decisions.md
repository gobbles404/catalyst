# Decisions

The record: the choices that could have gone another way, and what is still open. A rule that
follows from a tenet, from the seam, or from what the owner asked for is not a decision; it is
written on its page, once, and not here. An entry says what was chosen over what, why, and what
it costs, in a paragraph; an open one says what would decide it. A choice recorded here is not
reopened from memory, and an open one is not a licence to guess.

The numbers are stable, so pages can cite them. The gaps are entries that turned out to restate
a page, cut in #57. Two open items are library-wide, release of handles (D26) and the work
counter (D27); they are listed once in [README.md](README.md), and a page's Open section holds
only what gates that page.

## D3 · The valuation date keeps a fraction nothing uses yet — open

`=CreateValuationDate(A2, 0.5)` stores the 0.5 with the date, because the owner supplied it as
part of what a valuation date means: how far through the day the calculation stands. Nothing
reads it yet, which is generality bought before a consumer exists, and `(2026-09-11, 1)` and
`(2026-09-12, 0)` are two records that describe one moment, the end of Friday, so how two
valuation dates order is undefined. Decided by: the first function that orders two valuation
dates or measures the time between them, which decides whether the fraction stays and how such
a pair sorts.

## D10 · Interpolation runs on the discount factors themselves

`InterpolateDiscountFactors` draws a straight line between adjacent supplied factors, weighted
by calendar days, over a straight line on `log df`. Chosen as the simplest reading of "fill the
gaps" for data that is already close to daily. It costs a model choice, not data preparation:
the implied forward rate ramps inside each gap and steps at each knot, about one basis point of
drift over a one-year gap in the owner's own sample, and worth knowing it was chosen rather
than inherited.

## D12 · How a curve's last date reaches a calculation — open

A curve's last date is a hard stop ([tenet 2](../../PRINCIPLES.md)): a calculation that needs
a later date fails, naming the operation, the date it wanted and the curve's last, and
nothing is extrapolated or clamped. Not decided: which curve governs when a calculation holds
several, how the stop is supplied without the library reading it from somewhere global
([golden rule 11](../golden-rules.md)), what a date before the curve's start means, and the name
of the curve's first date, which today shares `as_of` with the valuation date's field and
should not. The direction under consideration: one object holds the valuation date and the
curve or curves, is passed as one argument, and the stop is checked in one place, where dates
are produced; with several curves the stop is the earliest of theirs. Decided by: the first
pricing function, which has to carry a valuation date and a curve together.

## D13 · Units are the library's, in four categories that do not convert into each other

One reviewed set of unit definitions ships inside the library, `volume`, `mass`, `energy` and
`usd`, each with its own reference unit, over a workbook table or a configuration file: a unit
that means different things in two workbooks is worse than a unit that cannot be changed, so a
desk convention the library does not know is added by an engineer. Conversion between the
categories, `BBL` to `MWH` say, is refused, because it needs a density or a heat content that
no table here carries. It costs that commodity work does convert across categories, and when
it does the assumption has to become an explicit input somewhere, which is not specified.

## D18 · `util_` on a worksheet function's name — open

`util_ReadDiscountFactor` leads with a working prefix at the owner's word, and
`InterpolateDiscountFactors` has none. Excel groups functions by category, which the host does
not set; a category would do the prefix's job without putting two conventions in one name.
Decided by: the owner; a category would be a seam item first.

## D21 · The curve is a table, a header row and a body

`=CreateDiscountCurve(A1:B1, A2:B4)`, with `date` and `discount_factor` in either order over
a body of dates and factors; `df` was declined as a header, to keep clear of "dataframe". The
candidates weighed, each of which the seam could carry:

| Layout | Formula | What it costs |
|---|---|---|
| a table: a header row and a body, schema `date: DateColumn`, `discount_factor: NumberColumn` | `=CreateDiscountCurve(A1:B1, A2:B4)` | the sheet keeps the pairing; two ranges to select instead of one |
| separate typed columns, no headers | `=CreateDiscountCurve(A2:A4, B2:B4)` | two ranges can be selected one row out of step, `A2:A10` beside `B3:B11`, and equal lengths cannot catch it |
| a numeric body with fixed positions, no headers | `=CreateDiscountCurve(A2:B4)` | meaning by position alone; swapped columns are silent until the rules catch them |
| a start date and factors, the dates generated | `=CreateDiscountCurve(A2, B2:B4)` | one row per factor from the start; the supplied dates are gone, so a missing source observation shifts every factor after it with nothing to say so |

The table won because the sheet keeps the pairing and the headers say which column is which;
it costs two ranges to select instead of one, and the seam reading two arguments together,
which it does for nothing else. `InterpolateDiscountFactors` takes the same table.
`CreateExpirySchedule` takes separate columns instead, by the owner's choice, to put the typed
columns through a real function, and because its third column can be left out, which a table
cannot express. Decided 2026-09-13 by the owner.

## D26 · Release and reuse of a handle — open

Built in #53: a creator's cell shows its handle, a consumer's formula refers to that cell and
receives the object, and every failure is text in the cell. Not built: releasing the object
when its creator is deleted or its workbook closes, and reusing the same handle when an
unchanged creator recalculates. Today every creator call publishes anew and the store grows
until Excel closes, about 58 KB for a ten-year curve. The contract is
[handles.md](../seam/handles.md); the evidence for the two ways of building release is
[excel-dna-handles.md](../seam/excel-dna-handles.md). Decided by: the next handle pull request,
with counts: correct worksheet behaviour first, then the work per creator recalculation, then
retained memory.

## D27 · Whether library code takes a work counter — open

`CLAUDE.md` says code that prices, caches, hashes or converts takes a `WorkCounter`;
[golden rule 9](../golden-rules.md) says instrumentation is not threaded through pricing code;
a function reached through the seam can do neither, since its signature is the seam's. The
functions built so far take no counter and their work is pinned at the seam, at the owner's
word. Decided by: the owner, in one line, in the measurement session (issue #10).

## D30 · An argument left out, with nothing in its place — open

The seam's optional argument is a default: a missing argument takes a stored value of the
declared type, checked once at registration, and `None` is the host's word for a blank cell,
so no declaration today says "may be left out, and then there is nothing"
([inputs.md](../seam/inputs.md) decision 4, and what
[bridge.md](../seam/bridge.md#what-is-deliberately-absent-and-why) lists as deliberately
absent). `CreateExpirySchedule`'s `options_expiry` needs exactly that: an index without options
has no column to pass, and a stand-in column would be a value that looks right, which
[tenet 2](../../PRINCIPLES.md) forbids. The owner's word, 2026-09-14: optional means it may be
left out. The item is in [inputs.md](../seam/inputs.md) under what comes next, with the
recommended form beside it; its design is the seam's, and a blank cell in the slot must still
fail, because blank and left out are different facts. Decided by: the seam pull request that
builds it, before the function is built.
