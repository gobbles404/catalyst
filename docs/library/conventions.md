# Conventions

How a function page is written, the skeleton to copy for a new one, and the few rules that hold everywhere. The process a page moves through is in [README.md](README.md#the-process-for-fifty-functions).

## Names

| Item | Convention | Example |
|---|---|---|
| Worksheet functions | `_` then PascalCase leading with one of the verbs below, so that typing `_` in a cell lists the library's functions and nothing of Excel's; a utility leads with `util_` instead | `_CreateValuationDate`, `util_ReadHandle` |
| Parameters | snake_case, matching the wording used in Excel help | `as_of`, `day_fraction_elapsed`, `header_row`, `values` |
| Data fields | snake_case | `unit`, `reference_unit`, `size_in_reference_unit` |
| Object and seam types | PascalCase, reusing the seam's spelling where one exists | `ValuationDate`, `DiscountCurve`, `Date`, `NumberArray` |
| Worksheet headers | lowercase snake_case, as declared in the function's schema; bound by name in any order, case ignored ([inputs.md](../seam/inputs.md) decision 29) | `date`, `discount_factor` |
| Utility functions | `util_` then PascalCase, when the owner states it; a product decision. `util_Read*` reads information from an existing library object through its handle; every other `util_*` function derives or transforms values and takes a name that describes its result or operation | `util_ReadHandle`, since #73; `util_ReadPrompt`, since #129; `util_NextFut`, `util_FutToCme`, `util_DateToFut`, `util_FutToDate`, `util_StartDate` and `util_EndDate`, since #129; `util_ReadDiscountFactor` was one until #66 |
| Handles | `Handle[Kind]` around the library's own class, as a creator's result and as a consumer's parameter; the cell shows `pid:kind:count`, or `pid:kind:index-name:count` where the object carries an index's name, the process ID of the Excel first | `Handle[DiscountCurve]`, `30512:discount_curve:2`; `Handle[Market]`, `30512:market:WTI:36` |
| Category codes | exact codes in capitals, like the unit codes they hold, matched case-sensitively; since #129, lowercase until then | `VOLUME`, `MASS`, `ENERGY`, `USD` |
| Unit codes | one documented spelling each, matched case-sensitively | `GAL`, `BBL`, `MWH` |

The bridge exports the declared function name verbatim, so the Python name *is* the worksheet name. Every function the library lists is `_Name` or `util_Name` since #73; the seam's `Ping` and its hidden probes keep their names, being the seam's instruments and not the desk's.

Trade-input exception, decided on 3 October 2026 and built in #138 and #139: `_CreateTradeTemplate`
and `_CreateTrades` require exact field identifiers from the selected instrument definition,
including case, with no trimming or aliases. Column order may vary. The
[trade-input binding page](../engineering-tickets/trade-valuation-pipeline/excel-trade-input-binding.md)
records this deliberate difference from the general Table binder, and inputs.md records both
rules when the extension is built. Existing table functions retain their documented matching
rules.

## Verbs

A worksheet function leads with a verb that says what it does, and the verbs stay few, so the language stays simple: each means one thing, and a new one is added only when none of these fits, as a row here in the pull request that first uses it. Before adding one, ask whether the function is really a Create or a Read under another name.

| Verb | Means | Such as |
|---|---|---|
| Create | makes an object from what the sheet supplies and shows its handle | `_CreateDiscountCurve` |
| Read | shows what an object holds, and changes nothing | `util_ReadHandle` |
| List | spills the identifiers and descriptions in a library-owned definition catalog | `_ListInstruments`, built in #137 |
| Show | spills the field definition for a named catalog entry supplied as text | `_ShowInstrument`, built in #137 |
| Prepare | binds a batch to one market history, the dated side settled once, and shows its handle: a Create by another name, kept apart since what it makes is a step of the pipeline and not a thing the sheet types | `_PrepareTrades`, built in #141 |
| Evaluate | values a preparation against one market and shows its handle, the other step | `_EvaluateTrades`, built in #141 |
| Report | spills one aspect of a result's numbers under their labels, a Read by another name, kept for what a desk reads off a sheet | `_ReportValues`, `_ReportRisk`, built in #141 |

List and Show are the owner's agreed verbs for instrument-definition inspection. Both read
the library catalog directly and return tables without creating handles; they precede
template and trade construction. Their contracts are recorded in
[ListInstruments](instruments/list-instruments.md) and
[ShowInstrument](instruments/show-instrument.md).

The `util_` functions divide in two, by the owner's call in #129: `util_Read*` reads information from an existing library object through its handle, `util_ReadHandle` and `util_ReadPrompt`; every other `util_*` function derives or transforms values, making no object, and is named for its result or operation, `util_NextFut`, `util_FutToCme`, `util_DateToFut`, `util_FutToDate`, `util_StartDate`, `util_EndDate` and `util_ShiftDate`; one of these may read an object the seam resolved for a fact its derivation needs, `util_ShiftDate` a holiday calendar for the closed days since #171 and the two period functions a valuation-date handle for its day since #173, and it stays a derivation, the object's text in and a value out, nothing made and nothing of the object read back.

## Tables

A function that takes a table, a header row and a body, declares a schema, a class deriving from the seam's `Table` with one line per column, and takes the header row as a `TextRow` in the parameter just before the table. How the headers bind, what each column type accepts, and every message are the seam's: [inputs.md](../seam/inputs.md) decisions 27 to 33 and [bridge.md](../seam/bridge.md#a-table-a-header-row-and-a-schema). A page shows its schema and restates nothing about binding. A mixed range crosses only as a table: a function never declares a bare `MixedArray`, because without headers its columns mean nothing ([inputs.md](../seam/inputs.md) decision 38). Whether a range of one kind needs headers too is not decided; the next few functions will show, and `_CreateFuturesSchedule`, built in #60, is the first, taking three columns without headers at the cost its page states; `_CreateHolidayCalendar`, built in #67, is the second, taking one column, where that cost does not arise; `_CreateFuturesCurve`, built in #74 and removed in #83, was the third, taking two columns for the seam's cost, since a curve is hot data; `_CreatePriceVector`, built in #85, is the fourth, taking one column of prices, the hot data the market will take, where that cost does not arise; what the columns save and what they risk is stated at [inputs.md](../seam/inputs.md) decision 38.

## What holds everywhere

Every date is a calendar day, weekends and holidays included; no business-day adjustment happens anywhere; `_CreateHolidayCalendar` lists the days a market is closed, and `_CreateFuturesFixings` reads the list to refuse a fixing on a closed day or a business day without one, never to move a date; where a contract's terms will first need business days, and how, is decided in [time.md](time.md), and this sentence changes in that pull request. Interpolation is a straight line on the thing itself, weighted by calendar days, wherever the library fills gaps; a spline, or another basis, is a discussion, not a default. A rejection is a `ValueError` with the page's message, and a failed call publishes nothing.

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
curve:      A discount-curve handle: the cell showing _CreateDiscountCurve's result, such as B5, or a name for it.
```

- Write the line as if the argument were required. For an optional one registration adds the brackets and the default, `[factor]` and `One multiplier. 1 when omitted.`, from the signature; for one that may be left out with nothing in its place, `option_expiry: DateColumn | None = None`, it adds the brackets alone. Never write "optional" or the default yourself.
- The function's line says what the function makes. For a creator it explains the handle once, `shows its handle, the text other formulas take as the curve`, because that is where the desk first meets the word.
- Rules stay out of the help. A line says what to pick; the page and the error message say what must hold and what went wrong. No seam words: nothing about serials, ranges, schemas or types.
- Where an argument takes a unit code, its help lists the accepted codes.
- The declaration is the one source of the help, and `tests/unit/test_help.py` pins its words. A page need not quote it; one that does changes with it in the same pull request.

The optional form, written once, as the `Times` probe declares it:

```python
def Times(
    x: Annotated[float, "One number to multiply."],
    factor: Annotated[float, "One multiplier."] = 1.0,
) -> float:
```

Excel shows `Times(x, [factor])`, and on the second argument `[factor]: One multiplier. 1 when omitted.`

## A function page, section by section

A page says what the desk types, sees and is told, and what must hold; how it crosses and what it costs belongs to the build, its pull request and its pins. Our functions are well defined, so most pages are short. The seam already checks every argument's type and shape and converts every result, so a page cites [inputs.md](../seam/inputs.md) and [outputs.md](../seam/outputs.md) rather than restating them, describes nothing that is neither built nor specified, and lists only its own tests. A rule on a page is one a consumer needs today; a rule for a reader that is not built yet is a guess, and belongs to that reader when it is written. It says what the function does today and moves with the code in the same pull request; it carries no routine stamps, status lines or counts, which age, while a link to the pull request or the ticket that explains a decision stays, and [history.md](../seam/history.md) keeps the chronology.

The sections, in this order:

| Section | Holds |
|---|---|
| Title, then one sentence | what the function is and does today; a function not yet built says so, naming in words the one seam item it waits on, if any |
| Worksheet contract | the Python declaration, the formula a user types, what the cell shows, and one line that the seam checks the declared types |
| Excel help | optional: the function line and the argument lines, quoted when the page has something to say about them; the declaration is the source and `tests/unit/test_help.py` pins the words |
| The library checks | the rules of meaning a consumer needs today, usually one or two, each with its exact message in the seam's grammar |
| What it computes | the calculation, under a heading that names it, such as The interpolation or The definitions, where there is one |
| Tests | the files that pin the page's rules and numbers, each named once with what it holds in a phrase; not a list of every case |
| Not here | what a reader might expect and will not find, and who decides it when that is known: a question only a later function can settle is a sentence here, not a rule |
