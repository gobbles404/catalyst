# The library

The pricing library: what each worksheet function is meant to do, one page per function. The [seam](../seam/README.md) that carries a function to Excel is built and documented separately, and nothing here restates it. The end state is a library that prices linear instruments, futures and swaps on a variety of indices; these pages are the first shared building blocks.

These pages are for an engineer building a function and for the owner reviewing what will be built. They are not the desk's documentation: what a person sees when typing a formula is Excel's own help text, the function line and one line per argument, and each page carries that text under Excel help so there is one source for it. Nothing here ships with a release.

## The pages

| Page | What it holds |
|---|---|
| [conventions.md](conventions.md) | how a function page is written, the skeleton to copy for a new one, and the few rules that hold everywhere |
| [time.md](time.md) | the decisions on contract months, their codes, calendar days and business days, recorded ahead of the functions that need them |
| [globals/valuation-date.md](globals/valuation-date.md) | `_CreateValuationDate`, a date and progress through that day |
| [globals/discount-curve.md](globals/discount-curve.md) | `_CreateDiscountCurve`, a daily curve from anchors, the days between filled by a straight line, and its upper date bound |
| [globals/unit-conversions.md](globals/unit-conversions.md) | `UnitConversions`, the shipped unit definitions and the conversion between them |
| [index-definitions/expiry-schedule.md](index-definitions/expiry-schedule.md) | `_CreateExpirySchedule`, the contract months of one index and their expiry dates |
| [index-definitions/holiday-calendar.md](index-definitions/holiday-calendar.md) | `_CreateHolidayCalendar`, the days one market is closed, listed one by one |
| [index-definitions/index-conventions.md](index-definitions/index-conventions.md) | `_CreateIndexConventions`, the units one index is quoted, settled and measured in |
| [index-definitions/contract-specs.md](index-definitions/contract-specs.md) | `_CreateContractSpecs`, the name, lot size and fees per lot of each contract an index trades as, from a table |
| [market-data/futures-curve.md](market-data/futures-curve.md) | `_CreateFuturesCurve`, the price of each contract of one index, code beside price |
| [market-data/daily-fixings.md](market-data/daily-fixings.md) | `_CreateDailyFixings`, the settle of one index on each day it fixed, from a table |
| [market-data/monthly-fixings.md](market-data/monthly-fixings.md) | `_CreateMonthlyFixings`, the price of one index for each month it fixed, the months kept as months |
| [utilities/read-handle.md](utilities/read-handle.md) | `util_ReadHandle`, the object behind any handle spilled as a table, the one its creator took or, for a curve, the daily one it built |

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

Built in #53: `_CreateValuationDate` and `_CreateDiscountCurve`. Built in #60: `_CreateExpirySchedule`, the first index definition, the first function to take columns of one kind without headers, and the first to leave an argument out with nothing in its place ([inputs.md](../seam/inputs.md) decision 39). Built in #66: `util_ReadHandle`, the object behind any handle spilled as the table its creator took, on the two seam items of #64 and #65; `util_ReadDiscountFactor`, the temporary reader of #53, went with it. Built in #67: `_CreateHolidayCalendar`, the second index definition, one column of dates without headers, the list being the calendar. Built in #68: `_CreateIndexConventions`, the third, five codes as text scalars kept as typed, their allowed values a task for later. Built in #69: `_CreateContractSpec`, the fourth, a name, a whole-number lot size and two fees kept as given, what must hold of them a task for later too. Since #70 `_CreateDiscountCurve` takes anchors, the days between filled by `interpolate_discount_factors` in the library; the owner declined a worksheet surface for the interpolation, and its page folded into the curve's. Built in #71: `UnitConversions`, the first thing in the library with no worksheet surface, four categories of units authored in code, checked once when the module is imported and shared by reference as `UNITS`, and the conversion between two units of one category; the conventions sample spells its category `volume` since, lowercase as [conventions.md](conventions.md) lists categories. Decided in #72, ahead of any function: [time.md](time.md), a contract month as a unit of its own, one spelling for codes, every period calendar days with weekends kept, and business days only through the holiday calendar where a contract states them. Renamed in #73: the market definitions became the index definitions, the pieces one index is defined by, ahead of the creator that will tie them together; every function the library lists leads with `_`, or `util_` for a utility, so typing `_` in a cell lists the library's functions; and the shared workbook gains an `index` tab where one index's pieces are built from editable inputs. Built in #74: `_CreateFuturesCurve`, the first market data, the price of each contract of one index from two columns of one kind, codes and prices, the third function to take columns without headers and the first to take them for the seam's cost, since a curve is rebuilt whenever prices move; nothing binds it to an index yet. Built in #75: `_CreateDailyFixings`, the second market data, the settle of one index on each day it fixed, from a table by the owner's call, since a history is nearer static data and a body selected as one range cannot misalign; each date after the row above, the curve's rule. Built in #76: `_CreateMonthlyFixings`, its sibling for an index that fixes once a month, two columns for the sheet's ergonomics, each month typed as its first day and kept as a month, the first function to hold [time.md](time.md)'s month unit. Refactored in #78 after use: `_CreateContractSpecs` takes a header row and a table, one contract per row, so an index traded as NYMEX lots and as ICE lots has a spec for each, each name once and each lot size whole, the rest still a task for later.

Open across the library, gating nothing: release of a handle when its creator is deleted or its workbook closes, and reuse on an unchanged recalculation, specified in [handles.md](../seam/handles.md) and built by the next handle pull request; and whether library code takes a work counter, parked for the measurement session (issue #10), the functions built so far taking none, their work pinned at the seam, and the unit conversions' directly. What the first pricing function must settle is under Not here on the pages it touches: how a calculation with several curves stays inside their dates, and the ordering of two valuation dates.

## Reading it as a reviewer

Start with [conventions.md](conventions.md), which says what a page contains. Then any one function page: its first line says where it stands, its rules are the only rules, and its Not here says what you will not find and who decides it.
