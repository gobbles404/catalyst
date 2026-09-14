# The library

The pricing library: what each worksheet function is meant to do, one page per function, and the rules and decisions behind them. The [seam](../seam/README.md) that carries a function to Excel is built and documented separately, and nothing here restates it. The end state is a library that prices linear instruments, futures and swaps on a variety of indices; these pages are the first shared building blocks.

These pages are for an engineer building a function and for the owner reviewing what will be built. They are not the desk's documentation: what a person sees when typing a formula is Excel's own help text, the function line and one line per argument, and each page carries that text under Excel help so there is one source for it. Nothing here ships with a release.

## The pages

| Page | What it holds |
|---|---|
| [conventions.md](conventions.md) | how a function page is written, and the skeleton to copy for a new one |
| [decisions.md](decisions.md) | the record: every choice, what decided it, what it costs, and for an open one what would decide it |
| [globals/valuation-date.md](globals/valuation-date.md) | `CreateValuationDate`, a date and progress through that day |
| [globals/discount-curve.md](globals/discount-curve.md) | `CreateDiscountCurve`, an explicit daily curve and its upper date bound, with `util_ReadDiscountFactor`, a temporary reader |
| [globals/unit-conversions.md](globals/unit-conversions.md) | `UnitConversions`, the shipped unit definitions and the conversion between them |
| [utilities/interpolate-discount-factors.md](utilities/interpolate-discount-factors.md) | `InterpolateDiscountFactors`, sparse points to a daily table |
| [market-definitions/expiry-schedule.md](market-definitions/expiry-schedule.md) | `CreateExpirySchedule`, the contract months of one index and their expiry dates |

The handle that the two constructors return, text in a cell that stands for a live object, is the seam's: its spec is [handles.md](../seam/handles.md), with the evidence for its store in [excel-dna-handles.md](../seam/excel-dna-handles.md).

## A page's life

A function page starts as the spec and becomes the reference when the function ships, so nothing is written twice and nothing goes stale in a second copy. The first line after its title is its state, exactly one of three:

- `Open: D21, D26.` Something is undecided, and those are the decisions.
- `Ready.` Nothing is open; it can be built.
- `Built in #53.` It exists, and the page describes what exists; anything still open about it stays in its Open section.

The state is read off the page's own Open section and moves with the code, in the same pull request. A page is drafted from the skeleton in [conventions.md](conventions.md); each open question becomes a numbered entry in [decisions.md](decisions.md) that ends with what would decide it, and the page's Open section lists the numbers; the pull request that builds the function follows [working.md](../seam/working.md#2-adding-a-worksheet-function) for the code, the pins, the smoke row and the help text, and sets the page to `Built in #NN`. Anything tried and declined on the way goes in the record, so it is not proposed again from memory.

A spec for something the seam must do, such as [handles.md](../seam/handles.md), is written the same way and lives with the seam, but it is transitional: when it is built, its content moves into the seam's pages, [inputs.md](../seam/inputs.md), [outputs.md](../seam/outputs.md) and [bridge.md](../seam/bridge.md), and the page goes, as the page for tables went in #51.

## Where it stands

Two functions are built, `CreateValuationDate` and `CreateDiscountCurve`, in #53, with `util_ReadDiscountFactor` beside them as a temporary reader that proves a handle resolves; three are specified, `UnitConversions`, `InterpolateDiscountFactors` and `CreateExpirySchedule`. Each page's first line says where it stands. One decision is library-wide and gates the unbuilt pages: D27, how a work counter reaches library code; the two built functions take no counter, and their work is pinned at the seam. Handles are published and resolved, and their release is D26. The utility takes the curve's table, decided in D21, and waits on its name, D18, and on D27. The expiry schedule is the first market definition, the first function to take columns of one kind without headers (D30), and waits on one seam item before it can be built: an argument that may be left out with nothing in its place, D33, wanted in [inputs.md](../seam/inputs.md).

## Reading it as a reviewer

Start with [conventions.md](conventions.md), which says what a page contains. Then any one function page. Then [decisions.md](decisions.md) for anything you want to argue with: a decision recorded there is not reopened from memory, and an open one says what it is waiting for.
