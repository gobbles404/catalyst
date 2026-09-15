# The library

The pricing library: what each worksheet function is meant to do, one page per function, and the rules and decisions behind them. The [seam](../seam/README.md) that carries a function to Excel is built and documented separately, and nothing here restates it. The end state is a library that prices linear instruments, futures and swaps on a variety of indices; these pages are the first shared building blocks.

These pages are for an engineer building a function and for the owner reviewing what will be built. They are not the desk's documentation: what a person sees when typing a formula is Excel's own help text, the function line and one line per argument, and each page carries that text under Excel help so there is one source for it. Nothing here ships with a release.

## The pages

| Page | What it holds |
|---|---|
| [conventions.md](conventions.md) | how a function page is written, and the skeleton to copy for a new one |
| [decisions.md](decisions.md) | the record: the choices that could have gone another way, what each cost, and what is still open |
| [globals/valuation-date.md](globals/valuation-date.md) | `CreateValuationDate`, a date and progress through that day |
| [globals/discount-curve.md](globals/discount-curve.md) | `CreateDiscountCurve`, an explicit daily curve and its upper date bound, with `util_ReadDiscountFactor`, a temporary reader |
| [globals/unit-conversions.md](globals/unit-conversions.md) | `UnitConversions`, the shipped unit definitions and the conversion between them |
| [utilities/interpolate-discount-factors.md](utilities/interpolate-discount-factors.md) | `InterpolateDiscountFactors`, sparse points to a daily table |
| [market-definitions/expiry-schedule.md](market-definitions/expiry-schedule.md) | `CreateExpirySchedule`, the contract months of one index and their expiry dates |

The handle that the two constructors return, text in a cell that stands for a live object, is the seam's: its spec is [handles.md](../seam/handles.md), with the evidence for its store in [excel-dna-handles.md](../seam/excel-dna-handles.md).

## A page's life

A function page starts as the spec and becomes the reference when the function ships, so nothing is written twice and nothing goes stale in a second copy. The first line after its title is its state, exactly one of three:

- `Open: D30.` Something that gates this function is undecided, and those are the decisions.
- `Ready.` Nothing gates it; it can be built.
- `Built in #53.` It exists, and the page describes what exists; anything still open about it stays in its Open section.

The state is read off the page's own Open section and moves with the code, in the same pull request. A page is drafted from the skeleton in [conventions.md](conventions.md); a question the owner has to answer before the function can be built becomes a numbered entry in [decisions.md](decisions.md) that ends with what would decide it, and the page's Open section lists the numbers; the pull request that builds the function follows [working.md](../seam/working.md#2-adding-a-worksheet-function) for the code, the pins, the smoke row and the help text, and sets the page to `Built in #NN`. The record holds only the choices that could have gone another way, where another way was weighed and declined, and the questions still open; a rule that follows from a tenet, from the seam, or from what the owner asked for is written on its page once and is not a decision. Two open items are library-wide, release of handles (D26) and the work counter (D27); they are listed here, not on each page, and gate nothing: the functions built so far take no counter, their work is pinned at the seam, and their handles live until Excel closes.

A spec for something the seam must do, such as [handles.md](../seam/handles.md), is written the same way and lives with the seam, but it is transitional: when it is built, its content moves into the seam's pages, [inputs.md](../seam/inputs.md), [outputs.md](../seam/outputs.md) and [bridge.md](../seam/bridge.md), and the page goes, as the page for tables went in #51.

## Where it stands

Two functions are built, `CreateValuationDate` and `CreateDiscountCurve`, in #53, with `util_ReadDiscountFactor` beside them as a temporary reader that proves a handle resolves; three are specified. `UnitConversions` and `InterpolateDiscountFactors` are ready. `CreateExpirySchedule`, the first market definition, waits on one seam item: an argument that may be left out with nothing in its place, D30, wanted in [inputs.md](../seam/inputs.md). Open across the library and gating nothing: release of handles, D26, and the work counter, D27.

## Reading it as a reviewer

Start with [conventions.md](conventions.md), which says what a page contains. Then any one function page. Then [decisions.md](decisions.md) for anything you want to argue with: a decision recorded there is not reopened from memory, and an open one says what it is waiting for.
