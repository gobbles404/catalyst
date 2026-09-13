# The library

The pricing library: what it is meant to do, function by function. The
[seam](../seam/README.md) that carries it to Excel is built and documented separately;
nothing here restates it.

The end state is a library that prices linear instruments, initially futures and swaps on a
variety of indices. These are the first shared building blocks. None of it is implemented.

## Every page is one of two things

| | | |
|---|---|---|
| **Normative** | the contract | an engineer builds from it, and needs nothing else |
| **Informative** | the reasoning | read it when you want to know why, or when you disagree |

Each page says which it is on its first line. A normative page links to the reasoning
behind each choice; it never contains it.

Same split the seam uses: [inputs.md](../seam/inputs.md) holds the rules,
[history.md](../seam/history.md) holds why they are the rules and what was declined.

## Normative

| Page | What it fixes |
|---|---|
| [conventions.md](conventions.md) | names, header matching, shapes, error grammar, Excel help, and what a specification contains |
| [handles.md](handles.md) | how a retained object is reached from a worksheet |
| [globals/valuation-date.md](globals/valuation-date.md) | `CreateValuationDate` — a date and progress through that day |
| [globals/discount-curve.md](globals/discount-curve.md) | `CreateDiscountCurve` — an explicit daily curve and its upper date bound |
| [globals/unit-conversions.md](globals/unit-conversions.md) | `UnitConversions` — the shipped unit definitions and the conversion between them |
| [utilities/interpolate-discount-factors.md](utilities/interpolate-discount-factors.md) | `InterpolateDiscountFactors` — sparse points to a daily table |

## Informative

| Page | What it holds |
|---|---|
| [decisions.md](decisions.md) | every choice: what was decided, because of what, and what it costs. Twenty-seven entries, seven of them still open |
| [notes/excel-dna-research.md](notes/excel-dna-research.md) | what Excel-DNA 1.9 supplies, read from its source. Evidence, not a selected mechanism |

A decision recorded in `decisions.md` is not reopened from memory.

## Where it stands

Two of the four can be built with the seam exactly as it is today:

| | Buildable now | Waiting on |
|---|---|---|
| `UnitConversions` | yes — no worksheet surface at all | nothing |
| `InterpolateDiscountFactors` | yes — returns a `NumberArray` | D21, the input table shape |
| `CreateValuationDate` | no | D26, a handle return type |
| `CreateDiscountCurve` | no | D26, and D21 |

## The open questions

Seven, listed here so they are not rediscovered. Each is also marked in the specification
it affects.

| | Question | Blocks |
|---|---|---|
| D3, D4 | Ordering of two valuation dates, and whether the day fraction stays before anything consumes it | nothing yet; cheaper now than later |
| D12 | How the curve's date bound reaches a calculation, which curve governs when there are several, and dates before the curve's start | the bound's enforcement |
| D19 | Header whitespace, and whether columns may be reordered | the curve and the utility |
| D21 | How a date/factor table crosses the seam, so the library receives typed dates and each check happens once | the curve and the utility |
| D18 | The `util_` prefix, and general naming beyond what conventions.md fixes | the utility's name |
| D26 | What the seam needs before a constructor can return a handle | both constructors |
| D27 | How a work counter reaches library code, where CLAUDE.md and golden rule 9 disagree | every internal signature |

## Reading it as a reviewer

Start with [conventions.md](conventions.md), which says what a specification contains and
why every rule has to declare who checks it. Then any one function page. Then
[decisions.md](decisions.md) for anything you want to argue with.

The worked examples in these pages are inputs and hand-computed targets, not a reviewed
pricing golden suite. Where a page says a sample must fail validation, it means it: the
owner's 34-point interpolation sample contains a confirmed bad factor and is kept as a
rejection case.
