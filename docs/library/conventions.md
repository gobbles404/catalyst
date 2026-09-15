# Conventions

How a function page is written, the skeleton to copy for a new one, and the few rules that hold everywhere. The process a page moves through is in [README.md](README.md#the-process-for-fifty-functions).

## Names

| Item | Convention | Example |
|---|---|---|
| Worksheet functions | PascalCase, leading with one of the verbs below | `CreateValuationDate`, `ReadHandle` |
| Parameters | snake_case, matching the wording used in Excel help | `as_of`, `day_fraction_elapsed`, `header_row`, `values` |
| Data fields | snake_case | `unit`, `reference_unit`, `size_in_reference_unit` |
| Object and seam types | PascalCase, reusing the seam's spelling where one exists | `ValuationDate`, `DiscountCurve`, `Date`, `NumberArray` |
| Worksheet headers | lowercase snake_case, as declared in the function's schema; bound by name in any order, case ignored ([inputs.md](../seam/inputs.md) decision 29) | `date`, `discount_factor` |
| Utility functions | `util_` before the name, when the owner states it; a product decision | none today; `util_ReadDiscountFactor` was one until #66 |
| Handles | `Handle[Kind]` around the library's own class, as a creator's result and as a consumer's parameter; the cell shows `kind:session:number` | `Handle[DiscountCurve]`, `discount_curve:3f9a1c:000002` |
| Category values | exact lowercase codes, matched case-sensitively | `volume`, `mass`, `energy`, `usd` |
| Unit codes | one documented spelling each, matched case-sensitively | `GAL`, `BBL`, `MWH` |

The bridge exports the declared function name verbatim, so the Python name *is* the worksheet name.

## Verbs

A worksheet function leads with a verb that says what it does, and the verbs stay few, so the language stays simple: each means one thing, and a new one is added only when none of these fits, as a row here in the pull request that first uses it. Before adding one, ask whether the function is really a Create or a Read under another name.

| Verb | Means | Such as |
|---|---|---|
| Create | makes an object from what the sheet supplies and shows its handle | `CreateDiscountCurve` |
| Read | shows what an object holds, and changes nothing | `ReadHandle` |
| Interpolate | fills the gaps between supplied points | `InterpolateDiscountFactors` |

## Tables

A function that takes a table, a header row and a body, declares a schema, a class deriving from the seam's `Table` with one line per column, and takes the header row as a `TextRow` in the parameter just before the table. How the headers bind, what each column type accepts, and every message are the seam's: [inputs.md](../seam/inputs.md) decisions 27 to 33 and [bridge.md](../seam/bridge.md#a-table-a-header-row-and-a-schema). A page shows its schema and restates nothing about binding. A mixed range crosses only as a table: a function never declares a bare `MixedArray`, because without headers its columns mean nothing ([inputs.md](../seam/inputs.md) decision 38). Whether a range of one kind needs headers too is not decided; the next few functions will show, and `CreateExpirySchedule`, built in #60, is the first, taking three columns without headers at the cost its page states.

## What holds everywhere

Every date is a calendar day, weekends and holidays included; no business-day adjustment happens anywhere. Interpolation is a straight line on the thing itself, weighted by calendar days, wherever the library fills gaps; a spline, or another basis, is a discussion, not a default. A rejection is a `ValueError` with the page's message, and a failed call publishes nothing.

## What the library receives

Each declared type and what it hands the function is the table in [bridge.md](../seam/bridge.md#the-declared-input-types); a page cites it and does not restate it. Inside the library use numpy directly and never import the bridge: numpy is the default for numerical arrays and calculations, `float64` the default dtype, `datetime64[D]` for dates. Scalars keep their scalar shapes: a single date is a numpy scalar, a single fraction a Python float, and nothing is wrapped in a one-element array to make it uniform. Text stays as the seam's tuples. Mixed text-and-numeric records stay as records, never an object-dtype array. A creator returns its object and the seam keeps it, showing its handle in the cell; a consumer's parameter declared `Handle[Kind]` receives the object, never the text: [bridge.md](../seam/bridge.md#a-handle-one-store-and-the-text).

## Errors

A library rejection reaches the cell as `#ERROR {function}: {ExceptionType}: {message}`. The type is `ValueError` for every business rule, so the message is the part a page writes. Messages follow the seam's grammar, `{argument} is {what arrived}, expected {what was wanted}`, with cells and rows counted as `INDEX` counts within the range that was passed: [inputs.md](../seam/inputs.md) rule 8 and [outputs.md](../seam/outputs.md) rule 7 are the pattern, and `describe` is not imported from the bridge to build one. A failed call publishes nothing: no partial result, no object, no handle.

## Excel help

This is the desk's documentation. Every function Excel lists explains itself while a person types the formula: the signature, the argument they are on, and one line about it, and the same words appear in the Function Arguments dialog. It is written for the desk, in the desk's words, once, in the declaration: the docstring is the function's line, and the words beside each parameter, `as_of: Annotated[Date, "One date, ..."]`, are that argument's line. Registration reads both, refuses a function Excel lists that leaves either out or runs past the 253 characters Excel shows, and adds what the signature already says: an optional argument's name in brackets, `[factor]`, and what it takes when omitted, `1 when omitted.` Nothing about an argument is written twice. The mechanism is [bridge.md](../seam/bridge.md#declaring-a-worksheet-function), and [host.md](../seam/host.md#at-registration) says how the words reach Excel and the display that shows them while typing.

An argument's line is one sentence with three parts, in this order: what to select, in the desk's words; an example, or where it comes from; and at most one thing that must hold. It ends with a period, which registration checks, because what it adds follows that period.

```text
name: What to select, such as an example, and the one thing that must hold.

header_row: The header cells of your curve table, such as A1:B1, reading date and discount_factor in either order.
curve:      A discount-curve handle: the cell showing CreateDiscountCurve's result, such as B5, or a name for it.
```

- Write the line as if the argument were required. For an optional one registration adds the brackets and the default, `[factor]` and `One multiplier. 1 when omitted.`, from the signature; for one that may be left out with nothing in its place, `option_expiry: DateColumn | None = None`, it adds the brackets alone. Never write "optional" or the default yourself.
- The function's line says what the function makes. For a creator it explains the handle once, `shows its handle, the text other formulas take as the curve`, because that is where the desk first meets the word.
- Rules stay out of the help. A line says what to pick; the page and the error message say what must hold and what went wrong. No seam words: nothing about serials, ranges, schemas or types.
- Where an argument takes a unit code, its help lists the accepted codes.
- A page quotes the declaration under Excel help, as it quotes the messages that tests pin, so a reviewer reads it in one place per function; a change to one changes both in the same pull request.

The optional form, written once, as the `Times` probe declares it:

```python
def Times(
    x: Annotated[float, "One number to multiply."],
    factor: Annotated[float, "One multiplier."] = 1.0,
) -> float:
```

Excel shows `Times(x, [factor])`, and on the second argument `[factor]: One multiplier. 1 when omitted.`

## A function page, section by section

A page says what the desk types, sees and is told, and what must hold; how it crosses and what it costs belongs to the build, its pull request and its pins. Our functions are well defined, so most pages are short. The seam already checks every argument's type and shape and converts every result, so a page cites [inputs.md](../seam/inputs.md) and [outputs.md](../seam/outputs.md) rather than restating them, describes nothing that is neither built nor specified, and lists only its own tests. A rule on a page is one a consumer needs today; a rule for a reader that is not built yet is a guess, and belongs to that reader when it is written. Its first line is its state, in words, and it moves with the code in the same pull request.

The sections, in this order:

| Section | Holds |
|---|---|
| Title, then the state alone | `Ready to ship.`, `Waiting on the seam: ...` naming the one item in words, or `Built in #NN.`; then one sentence saying what the function is |
| Worksheet contract | the Python declaration, the formula a user types, what the cell shows, and one line that the seam checks the declared types |
| Excel help | the function line and one line per argument, quoted from the declaration: the desk-facing text |
| The library checks | the rules of meaning a consumer needs today, usually one or two, each with its exact message in the seam's grammar |
| What it computes | the calculation, under a heading that names it, such as The interpolation or The definitions, where there is one |
| Tests | one row per test to write: the case and its kind, example, property or golden; when built, where each is pinned |
| Not here | what a reader might expect and will not find, and who decides it when that is known: a question only a later function can settle is a sentence here, not a rule |
