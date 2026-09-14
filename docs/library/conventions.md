# Conventions

How a function page is written, and the skeleton to copy for a new one. Why these choices, and what they cost, is in [decisions.md](decisions.md): D18 to D20 for the names and shapes, D28 for the pages themselves.

## Names

| Item | Convention | Example |
|---|---|---|
| Worksheet functions | PascalCase | `CreateValuationDate`, `CreateDiscountCurve` |
| Parameters | snake_case, matching the wording used in Excel help | `as_of`, `day_fraction_elapsed`, `header_row`, `values` |
| Data fields | snake_case | `unit`, `reference_unit`, `size_in_reference_unit` |
| Object and seam types | PascalCase, reusing the seam's spelling where one exists | `ValuationDate`, `DiscountCurve`, `Date`, `NumberArray` |
| Worksheet headers | lowercase snake_case, as declared in the function's schema; bound by name in any order, case ignored ([inputs.md](../seam/inputs.md) decision 29) | `date`, `discount_factor` |
| Handles | `Handle[Kind]` around the library's own class, as a creator's result and as a consumer's parameter; the cell shows `kind:session:number` | `Handle[DiscountCurve]`, `discount_curve:3f9a1c:000002` |
| Category values | exact lowercase codes, matched case-sensitively | `volume`, `mass`, `energy`, `usd` |
| Unit codes | one documented spelling each, matched case-sensitively | `GAL`, `BBL`, `MWH` |

The bridge exports the declared function name verbatim, so the Python name *is* the worksheet name. `util_` on the interpolation utility is a working name, not a convention (D18).

## Tables

A function that takes a table, a header row and a body, declares a schema, a class deriving from the seam's `Table` with one line per column, and takes the header row as a `TextRow` in the parameter just before the table. How the headers bind, what each column type accepts, and every message are the seam's: [inputs.md](../seam/inputs.md) decisions 27 to 33 and [bridge.md](../seam/bridge.md#a-table-a-header-row-and-a-schema). A page shows its schema and restates nothing about binding. A mixed range crosses only as a table: a function never declares a bare `MixedArray`, because without headers its columns mean nothing ([inputs.md](../seam/inputs.md) decision 38). Whether a range of one kind needs headers too is not decided; the next few functions will show.

## What the library receives

Each declared type and what it hands the function is the table in [bridge.md](../seam/bridge.md#the-declared-input-types); a page cites it and does not restate it. Inside the library use numpy directly and never import the bridge: numpy is the default for numerical arrays and calculations, `float64` the default dtype, `datetime64[D]` for dates. Scalars keep their scalar shapes: a single date is a numpy scalar, a single fraction a Python float, and nothing is wrapped in a one-element array to make it uniform (D20). Text stays as the seam's tuples. Mixed text-and-numeric records stay as records, never an object-dtype array. A creator returns its object and the seam keeps it, showing its handle in the cell; a consumer's parameter declared `Handle[Kind]` receives the object, never the text: [bridge.md](../seam/bridge.md#a-handle-one-store-and-the-text).

## Errors

A library rejection reaches the cell as `#ERROR {function}: {ExceptionType}: {message}`. The type is `ValueError` for every business rule (D29), so the message is the part a page writes. Messages follow the seam's grammar, `{argument} is {what arrived}, expected {what was wanted}`, with cells and rows counted as `INDEX` counts within the range that was passed: [inputs.md](../seam/inputs.md) rule 8 and [outputs.md](../seam/outputs.md) rule 7 are the pattern, and `describe` is not imported from the bridge to build one. A failed call publishes nothing: no partial result, no object, no handle.

## Excel help

This is the desk's documentation. Every worksheet function explains itself while the user types the formula: the signature, the active argument, and that argument's description, and the same wording appears in the Function Arguments dialog. So it is written for the desk, in the desk's words, and kept in one place: with the function declaration, passed through registration.

- Each argument description fits about 255 characters; longer text is truncated by Excel.
- Say the meaning, the shape, the allowed values, and whether it is required.
- Where an argument takes a unit code, its help lists the accepted codes.

The function description crosses today; argument descriptions do not, because the host registers each parameter's name only. That is the seam's open item, recorded in [history.md](../seam/history.md#open-and-parked), and it lands with the first library function.

## A function page, section by section

A page holds only what is new to its function. The seam already checks every argument's type and shape and converts every result, so a page cites [inputs.md](../seam/inputs.md) and [outputs.md](../seam/outputs.md) rather than restating them, describes nothing that is neither built nor specified, and lists only its own tests. Its first line is its state, read off its own Open section, and it moves with the code in the same pull request.

The sections, in this order:

| Section | Holds |
|---|---|
| Title, then the status line alone | `Open: D21, D26.`, `Ready.` or `Built in #NN.`, then one sentence saying what the function is and the D-range behind it |
| Worksheet contract | the Python declaration, the formula a user types, what the cell shows, and one line that the seam checks the declared types |
| Excel help | the function line and one line per argument, the desk-facing text |
| The library checks | one row per business rule, with its exact message in the seam's grammar; every row is a rule of meaning |
| What it computes | the calculation, under a heading that names it, such as The interpolation or The definitions, where there is one |
| In memory | what is received, by citing bridge.md, and what is retained, with dtype and shape |
| Counted work | the counters and their expected values, or none and why |
| Tests | one row per test to write: the case and its kind, example, property or golden; when built, where each is pinned |
| Open | the numbers of the open decisions, and nothing else |
| Not here | what a reader might expect and will not find |
