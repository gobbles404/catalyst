# The library

The pricing library: what each worksheet function is meant to do, one page per function. The [seam](../seam/README.md) that carries a function to Excel is built and documented separately, and nothing here restates it. The end state is a library that prices linear instruments, futures and swaps on a variety of indices; these pages are the first shared building blocks.

These pages are for an engineer building a function and for the owner reviewing what will be built. They are not the desk's documentation: what a person sees when typing a formula is Excel's own help text, the function line and one line per argument, and each page carries that text under Excel help so there is one source for it. Nothing here ships with a release.

## The pages

| Page | What it holds |
|---|---|
| [conventions.md](conventions.md) | how a function page is written, the skeleton to copy for a new one, and the few rules that hold everywhere |
| [globals/valuation-date.md](globals/valuation-date.md) | `CreateValuationDate`, a date and progress through that day |
| [globals/discount-curve.md](globals/discount-curve.md) | `CreateDiscountCurve`, an explicit daily curve and its upper date bound, with `util_ReadDiscountFactor`, a temporary reader |
| [globals/unit-conversions.md](globals/unit-conversions.md) | `UnitConversions`, the shipped unit definitions and the conversion between them |
| [utilities/interpolate-discount-factors.md](utilities/interpolate-discount-factors.md) | `InterpolateDiscountFactors`, sparse points to a daily table |
| [market-definitions/expiry-schedule.md](market-definitions/expiry-schedule.md) | `CreateExpirySchedule`, the contract months of one index and their expiry dates |

The handle that the creators return, text in a cell that stands for a live object, is the seam's: its spec is [handles.md](../seam/handles.md), with the evidence for its store in [excel-dna-handles.md](../seam/excel-dna-handles.md).

## The process, for fifty functions

Four steps, and the page is the only document. A page says what the desk types, sees and is told, and what must hold. How it crosses and what it costs belongs to the build.

1. **Write the page when the function is next, not before.** From the skeleton in [conventions.md](conventions.md): the formula a person types, the cells beside it, what the cell shows, the declaration, the help lines, the rules it needs today with their messages, the tests to write, and Not here. That is the spec, and it is a docs pull request.
2. **Engineering answers one question on that pull request: can the seam carry it as written?** If yes, the page's first line reads `Ready to ship.` If not, the page names the one seam item in words, the item goes in the seam's wanted-next table in [inputs.md](../seam/inputs.md) with the recommended form, and the first line reads `Waiting on the seam: ...`. That answer is the merge gate.
3. **Seam first, when needed, in its own pull request.** A new type follows [working.md §3](../seam/working.md#3-adding-a-declared-type); a new form of declaration is the same shape and smaller.
4. **Build in one pull request**, following [working.md §2](../seam/working.md#2-adding-a-worksheet-function). Open it against the seam branch when there is one, so GitHub shows only its own changes and it can merge only after the seam does. The build sets the first line to `Built in #NN`, points the Tests table at the files, and the page becomes the reference.

Three things not to do:

- Do not write fifty pages up front. A page written before its function is next is a guess, and every guess is prose to keep in step with code that does not exist.
- Do not write a rule for a reader that is not built. A creator checks that its own record is well formed and nothing more.
- Do not count functions in prose. Words that say how many functions register, or name "the three of the globals module", age with every build; say what a thing is, not how many there are.

## Where it stands

Built in #53: `CreateValuationDate` and `CreateDiscountCurve`, with `util_ReadDiscountFactor` beside them as a temporary reader that proves a handle resolves. Ready to ship: `UnitConversions` and `InterpolateDiscountFactors`. Waiting on the seam: `CreateExpirySchedule`, for an argument that may be left out with nothing in its place, wanted in [inputs.md](../seam/inputs.md).

Open across the library, gating nothing: release of a handle when its creator is deleted or its workbook closes, and reuse on an unchanged recalculation, specified in [handles.md](../seam/handles.md) and built by the next handle pull request; and whether library code takes a work counter, parked for the measurement session (issue #10), the functions built so far taking none, their work pinned at the seam. What the first pricing function must settle is under Not here on the pages it touches: how a calculation with several curves stays inside their dates, and the ordering of two valuation dates.

## Reading it as a reviewer

Start with [conventions.md](conventions.md), which says what a page contains. Then any one function page: its first line says where it stands, its rules are the only rules, and its Not here says what you will not find and who decides it.
