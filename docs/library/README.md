# The library

The pricing library: what each worksheet function is meant to do, one page per function, and the rules and decisions behind them. The [seam](../seam/README.md) that carries a function to Excel is built and documented separately, and nothing here restates it. The end state is a library that prices linear instruments, futures and swaps on a variety of indices; these pages are the first shared building blocks.

These pages are for an engineer building a function and for the owner reviewing what will be built. They are not the desk's documentation: what a person sees when typing a formula is Excel's own help text, the function line and one line per argument, and each page carries that text under Excel help so there is one source for it. Nothing here ships with a release.

## The pages

| Page | What it holds |
|---|---|
| [conventions.md](conventions.md) | the rules every function page follows, and the skeleton to copy for a new one |
| [decisions.md](decisions.md) | the record: every choice, what decided it, what it costs, and for an open one what would decide it |
| [globals/valuation-date.md](globals/valuation-date.md) | `CreateValuationDate`, a date and progress through that day |
| [globals/discount-curve.md](globals/discount-curve.md) | `CreateDiscountCurve`, an explicit daily curve and its upper date bound |
| [globals/unit-conversions.md](globals/unit-conversions.md) | `UnitConversions`, the shipped unit definitions and the conversion between them |
| [utilities/interpolate-discount-factors.md](utilities/interpolate-discount-factors.md) | `InterpolateDiscountFactors`, sparse points to a daily table |

The handle that the two constructors return, text in a cell that stands for a live object, is the seam's: its spec is [handles.md](../seam/handles.md), with the evidence for its store in [excel-dna-handles.md](../seam/excel-dna-handles.md).

## A page's life

A function page starts as the spec and becomes the reference when the function ships, so nothing is written twice and nothing goes stale in a second copy. The first line after its title is its state, exactly one of three:

- `Open: D21, D26.` Something is undecided, and those are the decisions.
- `Ready.` Nothing is open; it can be built.
- `Built in #51.` It exists, and the page describes what exists.

The state is read off the page's own Open section, and it moves with the code, in the same pull request. Five steps take a function from an idea to a built one:

1. Draft the page from the skeleton in [conventions.md](conventions.md), writing only what is new: the seam already checks types and shapes, and the page cites it.
2. Every open question becomes a numbered entry in [decisions.md](decisions.md), marked open, ending with what would decide it. The page's Open section lists the numbers and nothing else.
3. Review closes them, one decision at a time, with the reason and the cost recorded. A page with an empty Open section is `Ready.`
4. Build it in one pull request, following [working.md](../seam/working.md#2-adding-a-worksheet-function) for the code, the pins, the smoke row and the help text; the same pull request sets the page to `Built in #NN` and names the pins under Tests.
5. The record catches up: anything tried and declined, or found and parked on the way, goes in [decisions.md](decisions.md), so it is not proposed again from memory.

A spec for something the seam must do, such as [handles.md](../seam/handles.md), is written the same way and lives with the seam, but it is transitional: when it is built, its content moves into the seam's pages, [inputs.md](../seam/inputs.md), [outputs.md](../seam/outputs.md) and [bridge.md](../seam/bridge.md), and the page goes, as the page for tables went in #51.

## Where it stands

Four functions are specified and none is built. Each page's first line says what it waits on. Two decisions are library-wide and gate every page: D27, how a work counter reaches library code, and D29, the exception type a library rejection raises. `UnitConversions` waits on nothing else and needs nothing from the seam; the two constructors also wait on handles, D26; the curve and the utility wait on their input layout, D21.

## Reading it as a reviewer

Start with [conventions.md](conventions.md), which says what a page contains and why every rule names who checks it. Then any one function page. Then [decisions.md](decisions.md) for anything you want to argue with: a decision recorded there is not reopened from memory, and an open one says what it is waiting for.
