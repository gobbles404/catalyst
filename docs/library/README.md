# Library planning: review entry point

This is a planning snapshot for a fresh review, before specifying more functions
or implementing the library. The Excel / C# / Python seam already exists. The
objects, constructors, utility, and acceptance cases below are draft specifications;
they are not implemented by this change.

The intended end state is a library that prices linear instruments, initially
futures and swaps on a variety of indices. This snapshot captures the first
shared building blocks. It does not propose an instrument taxonomy or additional
worksheet functions.

## Shared context and conventions

Start with the [existing seam](../seam/README.md) for what is already built and
where type/shape validation and conversion occur. Then read the
[function conventions](function-conventions.md) for names, scalar/array shapes,
NumPy defaults, header matching, and Excel help.

## Handles and Excel dependencies

The [handle worksheet contract](handles/README.md) states the agreed use case:
creator formulas live in cells, consumers use cell references or defined names
referring to cells, Excel propagates their values, and the runtime protects the
objects behind valid handles. It includes Excel examples and separates this
settled workflow from the favored reuse direction and undecided lifecycle details.
The [Excel-DNA research](handles/excel-dna-research.md) is supporting evidence.

## Globals

The `globals/` directory holds the shared library objects discussed so far.

| Document | What to review |
|---|---|
| [CreateValuationDate](globals/valuation-date.md) | A date and progress through that named calendar day. |
| [UnitConversions](globals/unit-conversions.md) | The library-owned collection of fixed unit definitions and conversion math. |
| [CreateDiscountCurve](globals/discount-curve.md) | An explicit daily curve and its final date as a library-wide upper bound. |

## Utilities

The `utilities/` directory holds worksheet data-preparation functions. Its first
draft is [discount-factor interpolation](utilities/interpolate-discount-factors.md),
which prepares a daily numeric table from sparse source points.

## Agreed direction

- `CreateValuationDate` takes two required scalars. `as_of` follows the seam's
  whole Excel serial range `[61, 2958465]`. The finite fraction is in `[0, 1]`.
  Fraction `1` preserves the supplied date as EOD. Friday at `1` and Saturday at
  `0` share a calendar boundary but remain different date-and-fraction records.
- `UnitConversions` groups `volume`, `mass`, `energy`, and `usd` in one immutable
  internal collection, passed by explicit Python reference. There is no Excel
  constructor, category handle, or workbook override. The specification includes
  all 16 supplied definitions and the agreed Btu/therm meanings.
- `CreateDiscountCurve` takes a separate header row and a two-column numeric
  body. Its first date defines `as_of`; there is no separate valuation-date input.
  Every calendar date through the final row must be supplied. Factors begin at
  exactly `1`, are finite and in `(0, 1]`, and never increase; equal values are
  allowed. The upper cap of `1` is an intentional restriction of this library.
- The curve's final date is an inclusive hard upper bound for library processes,
  including processes that do not request a discount factor and dates generated
  during processing. How the governing curve reaches those processes is open.
- The interpolation utility fills calendar-day gaps by linear interpolation of
  discount factors from the first supplied date through the last. Invalid source
  data, including increasing factors, fails; it is not repaired or extrapolated.
- Worksheet headers have one canonical name and match case-insensitively.
  `date`/`df` are accepted; `Maturity`/`Mid` are not aliases. Unit and category
  codes retain their exact, case-sensitive spellings.
- NumPy is the default for numerical arrays and calculations. Scalars keep their
  scalar shapes, and text headers remain the seam's tuples. Worksheet functions
  should explain their arguments in formula-entry help and the Function Arguments
  dialog.

## Proposals and open questions

The individual drafts mark proposals separately from confirmed behavior. The
main questions a reviewer should examine are:

1. **Date preparation at the seam.** A `NumberArray` carries date serials as
   numbers. How should header-based column identification connect to the existing
   date validation and conversion, so the numerical library receives typed dates
   and each check occurs once?
2. **Date-bound ownership.** Which curve governs a calculation, how is its bound
   supplied explicitly, and how are standalone constructors handled before a
   curve exists? Alignment with `ValuationDate` and treatment of dates before
   `as_of` remain open.
3. **Remaining worksheet details.** General naming conventions and the `util_`
   prefix, header whitespace and column reordering, minimum curve/source length,
   and the proposed two-column utility spill without headers need final decisions.

The supplied long interpolation sample is deliberately preserved as invalid:
its factor rises on 2028-11-07. The owner confirmed that error; no replacement
values were supplied. The document also contains a separate valid worked segment.
Neither source tables nor draft test examples are a reviewed pricing golden suite.

## Suggested review brief

Review the captured approach against the existing seam and repository principles.
Identify contradictions, missing decisions, and assumptions that would make the
first implementation difficult or misleading in Excel. Distinguish flaws in the
approach from choices that are deliberately still open. Keep the review within
these concepts; do not implement them or add adjacent functions.

This snapshot contains documentation only. Proposed domain tests have not been
implemented or run. The repository's existing checks remain the baseline for the
built seam, not evidence that these specifications work.

Handle review should check the implementation candidates against that worksheet
contract. Independent pasted-token ownership, permanent cell-slot identity, and
automatic recovery from arbitrary object eviction are not assumed requirements.
The implementation and detailed lifetime/recovery promises remain open.
