# Decisions

The record holds what applies above one function: a rule every function inherits, or a
question no single function can settle. Anything decided for one function is on that
function's page and not here, and a rule that follows from a tenet, from the seam, or from
what the owner asked for is not a decision at all. An entry is a paragraph: what holds, why,
what it costs; an open one says what would decide it. A choice recorded here is not reopened
from memory, and an open one is not a licence to guess.

The numbers are stable, so pages can cite them; the gaps are entries that belonged to one
function, cut in #57. Two open items gate no page and are listed once in
[README.md](README.md): release of handles (D26) and the work counter (D27).

## D10 · Interpolation is a straight line on the thing itself

Wherever the library fills gaps, it draws a straight line between the supplied values,
weighted by calendar days: `InterpolateDiscountFactors` interpolates the discount factors
themselves, not `log df`. Chosen as the simplest reading of "fill the gaps", and it is the
default everywhere, so the next function that interpolates does the same without a
discussion; a spline, or another basis, is a discussion. It costs a model choice, not data
preparation: on a discount curve the implied forward rate ramps inside each gap and steps at
each knot, about one basis point over a one-year gap in the owner's sample.

## D12 · A cash flow outside a curve's dates fails — open how a calculation is told

A curve covers its first date through its last, and a calculation whose cash flow falls
outside them fails, naming the operation, the date and the curve's dates
([tenet 2](../../PRINCIPLES.md)); nothing is extrapolated or clamped. Not decided: how a
calculation that holds several curves knows which dates it must stay inside, and how it is
handed them without reading anything global ([golden rule 11](../golden-rules.md)). The
direction under consideration: one object holds the valuation date and the curves, is passed
as one argument, and the check runs where dates are produced, against the tightest curve.
Decided by: the first pricing function, which has to carry a valuation date and a curve
together.

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
absent). The library needs exactly that, first for `CreateExpirySchedule`'s `options_expiry`:
an index without options has no column to pass, and a stand-in column would be a value that
looks right, which [tenet 2](../../PRINCIPLES.md) forbids. The owner's word, 2026-09-14:
optional means it may be left out. The item is in [inputs.md](../seam/inputs.md) under what
comes next, with the recommended form beside it; its design is the seam's, and a blank cell in
the slot must still fail, because blank and left out are different facts. Decided by: the seam
pull request that builds it, before the function is built.
