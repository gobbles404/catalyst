# Outputs

How a value a function returns becomes what the cell shows. The mirror of [inputs.md](inputs.md): the same words, the same one place, the same strictness. This file changes whenever a result type is added or a question below is decided.

## What a function may return

The declared return type is the contract, read at registration the way parameters are. A function with no return annotation, or one the seam cannot send, refuses to register. So does `-> None`: a worksheet function returns something or fails.

| Declared | The function returns | The cell shows | Fails on |
|---|---|---|---|
| `float`, a number | a Python float or numpy float64; an integer too, since the sheet has one kind of number | the number | NaN, infinity, text, TRUE/FALSE, nothing, an array |
| `int`, a whole number | a Python or numpy integer, or a number with no fraction | the number | a fraction, NaN, anything above 2^53, which a cell cannot hold exactly |
| `str`, text | text of 1 to 32,767 characters, counted as Excel counts them | the text | empty text, longer text, a number |
| `bool`, a boolean | True or False | TRUE or FALSE | 1, 0, `"TRUE"` |
| `Date` | a numpy day, the same thing the seam hands in | the serial, which the sheet formats as a date | a day outside 1 March 1900 to 31 December 9999, a date with a time of day, a date in months or years, not a date |
| `NumberArray` | a plain two-dimensional numpy array of numbers, at least one cell | the array, spilled as returned | one-dimensional, empty, a masked array, a cell that is not a finite number, named as INDEX counts |
| `NumberColumn`, `NumberRow` | a one-dimensional numpy array of numbers | spilled down, or across | two-dimensional, empty, a bad cell |
| `DateColumn`, `DateRow` | a one-dimensional array of numpy days | serials, spilled | a day outside the calendar, not a date |
| `Handle[Kind]`, a class the library defines inside the brackets | an object of exactly that class, which the seam keeps | the handle: text such as `discount_curve:2`, which a later formula hands back through a reference to this cell | another type returned, a subclass, nothing |
| `MixedArray`, the mirror of the way in | the same record the way in hands a function, kinds, numbers and texts in the sheet's shape, at least one cell; `MixedArray.table` builds one from rows of headings over columns of one kind each, dates going out as serials | the rectangle, spilled as returned, one tagged value per cell: text as text, numbers as numbers, dates as serials the sheet formats, booleans as TRUE and FALSE | a blank, a missing or an empty-text cell, named as INDEX counts; a number cell that is not finite; a text holding a NUL, or longer than a cell holds; a boolean slot that is not 0 or 1; no cells; and in `MixedArray.table`, a column that is not a plain one-dimensional array, a masked array say, or a whole number beyond 2^53, named as INDEX counts, both checked before the column is copied |

Integers count as numbers, scalar or array, converted exactly. That is not coercion of meaning the way TRUE-as-1 would be: on the sheet a whole number and a number are one kind.

Next, one at a time, each when the first function needs it, as [inputs.md](inputs.md) keeps its own list. Each adds one result rule, a road out of the host where none carries it, and one row here. Nothing is wanted today.

## Result validation

One place converts: the prepared path, `Registered.run` in `bridge.py`, after the function runs. It converts the result by the declared return type into one of the five things the host can show, a number, text, a boolean, an array of numbers, or a rectangle of numbers, text and booleans, and fails with the function's name when it cannot. The host reads the type it is handed and never asks Python a question about it.

Rules:

1. Match the declared type. No coercion beyond integers as numbers: a `-> float` that returns text fails, a `-> NumberColumn` that returns a grid fails, a `-> int` that returns 2.5 fails. A whole number means the same in both directions: a number with no fraction.
2. Nothing that looks like a number but is not reaches the sheet. A NaN or an infinity anywhere in a result fails the whole call. In an array the message names the cell: `#ERROR Prices: result cell (3, 1) is not a finite number`.
3. Orientation comes from the declaration, never from the array. A `NumberColumn` spills down, a `NumberRow` spills across, a `NumberArray` spills as returned. The seam reshapes, so the host has one road out for numbers, one block copied in one move, and one for a mixed rectangle, laid out cell by cell.
4. A date goes out as its whole serial, the meaning exception mirrored. A date with a time of day fails.
5. Text is at most 32,767 characters as Excel counts them, in UTF-16 units the way `LEN` does, because Excel would cut longer text without a word. Empty text fails: a cell that looks blank is the quiet result tenet 2 forbids.
6. An empty array fails. A whole number beyond 2^53, scalar or in an array, fails, because a cell would hold it inexactly.
7. A failure names the function, what was returned, and what was expected: `#ERROR Forward: returned text 'x', expected number`. Something the sheet has no word for is named by its own: `returned a Python list`, `returned a numpy MaskedArray`. An error raised inside the function keeps its type and message: `#ERROR Forward: ValueError: no curve for that date`.
8. An object a creator returns is kept in the seam's one store, and its handle goes to the cell as text: `discount_curve:2`, the kind's tag and the runtime's publication count, with the index's name between them, `market:WTI:36`, for a kind whose object carries one (decision 11). A creator that returns the wrong thing fails as any result does, `#ERROR _CreateDiscountCurve: returned a Python list, expected discount curve`, and a creator that raises fails as any function does; neither publishes, and neither moves the number.

## Decided

Decided 2026-09-10.

1. The declared return type is the contract; `-> None` refuses to register.
2. The way out uses the same words as the way in. Text ranges out (`TextColumn`, `TextRow`, a `TextArray`) are possible under the same rules and not built, because no function returns one.
3. The seam converts once and fails with the function's name; integers are numbers, and a whole number is a number with no fraction in both directions.
4. NaN and infinity fail the whole call, with the cell named in an array. Arrays therefore cross as plain doubles, with no boxing and no `#N/A` standing in for a failed number.
5. Orientation from the declaration.
6. Dates out as serials.
7. Text bounded at 32,767 characters as Excel counts them, and never empty.
8. This file is the map for results, beside `inputs.md` for arguments.

Decided 2026-09-13.

9. A table's schema and a column of booleans are inputs. A function declaring either as its result is refused at registration, as the text ranges are, because no function returns one.

Decided 2026-09-14, handles.

10. A creator declares `Handle[Kind]` around a class the library defines and returns the object; the seam keeps it and the cell shows its handle. The object must be of exactly that class: a subclass, another type or nothing is refused as any result is, and the failure names the kind in lowercase words, `expected discount curve`.
11. The handle's text is `kind:count` or `kind:index-name:count`, lowercase tags joined by colons: the kind's tag from its class name, `discount_curve`; for the index, the calendar, the three fixings, the market history, the price vector and the market, the name of the index the object carries, read at publication and written whole as typed, spaces, colons and any character kept; and the runtime's publication count, a plain number shared by every kind that starts at 1 when Python starts and never repeats while it runs. The whole text is the key and nothing parses it. A text longer than a cell holds fails before it is stored, `returned handle of 32790 characters, expected at most 32767`. The session part of #53 went in #NN, with [handles.md](handles.md#the-handles-text)'s standing assumption in its place; the readable label dropped on 2026-09-13 returned as the index's name.
12. Every creator call publishes. Two creator cells with equal inputs hold two objects and show two handles, and a recalculated creator publishes anew. Reuse of the same handle on an unchanged recalculation, and release when a creator is deleted or its workbook closes, are open in [handles.md](handles.md); until then the store grows until Excel closes.

Decided 2026-09-15, the mixed road out.

13. `MixedArray` is a result as well as an input, the mirror of the way in: a function returns the same record the way in hands one, and the rectangle spills as returned, one tagged value per cell. The rule checks it as the way in checks one, the earliest cell holding no value named as INDEX counts, then what the way in never has to ask: a number cell holds a finite number, a boolean slot 0 or 1, no text holds a NUL, since NUL separates the texts on their way to the host, and every text is within what a cell holds, counted as Excel counts, checked on the joined text in one encode and split per text only when the total runs past the limit. The host receives the kinds, the numbers and the texts joined with NUL, by position, and lays the array out cell by cell: a box per number cell, a string per text cell, two shared boxes for the booleans; there is no block of mixed cells to copy in one move, so this road is per cell where the numbers road is one copy. `MixedArray.table` builds a rectangle from rows of headings over columns of one kind each, dates to serials, so no function writes kinds by hand. Reverses [inputs.md](inputs.md) decision 24. First wanted by `util_ReadHandle`. Since #84 one table is not the builder's, and since #86 two: the market history's `fixing_price` and the market's `price` each hold a number on some days and a word on the others, and one helper in `utilities.py` composes the record's three fields for both, the calendar's table widened by one column; the builder still takes columns of one kind only, the second case having stayed in the library's helper rather than open the seam in a library build, and a mixed column for the builder is a seam pull request of its own, if the owner wants one.

## Parked

Handles, built in part by #53: the way out is decisions 10 to 12 above, the way in is [inputs.md](inputs.md), and the store and the text are [bridge.md](bridge.md#a-handle-one-store-and-the-text). Release, reuse on an unchanged recalculation, and columns of handles are open; the spec is [handles.md](handles.md).
