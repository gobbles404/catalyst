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

Integers count as numbers, scalar or array, converted exactly. That is not coercion of meaning the way TRUE-as-1 would be: on the sheet a whole number and a number are one kind.

## Result validation

One place converts: the prepared path, `Registered.run` in `bridge.py`, after the function runs. It converts the result by the declared return type into one of the four things the host can show, a number, text, a boolean, or an array of numbers, and fails with the function's name when it cannot. The host reads the type it is handed and never asks Python a question about it.

Rules:

1. Match the declared type. No coercion beyond integers as numbers: a `-> float` that returns text fails, a `-> NumberColumn` that returns a grid fails, a `-> int` that returns 2.5 fails. A whole number means the same in both directions: a number with no fraction.
2. Nothing that looks like a number but is not reaches the sheet. A NaN or an infinity anywhere in a result fails the whole call. In an array the message names the cell: `#ERROR Prices: result cell (3, 1) is not a finite number`.
3. Orientation comes from the declaration, never from the array. A `NumberColumn` spills down, a `NumberRow` spills across, a `NumberArray` spills as returned. The seam reshapes, so the host has one road out.
4. A date goes out as its whole serial, the meaning exception mirrored. A date with a time of day fails.
5. Text is at most 32,767 characters as Excel counts them, in UTF-16 units the way `LEN` does, because Excel would cut longer text without a word. Empty text fails: a cell that looks blank is the quiet result tenet 2 forbids.
6. An empty array fails. A whole number beyond 2^53, scalar or in an array, fails, because a cell would hold it inexactly.
7. A failure names the function, what was returned, and what was expected: `#ERROR Forward: returned text 'x', expected number`. Something the sheet has no word for is named by its own: `returned a Python list`, `returned a numpy MaskedArray`. An error raised inside the function keeps its type and message: `#ERROR Forward: ValueError: no curve for that date`.

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

## Parked

Handles, in both directions. When the first builder function exists, its object kind joins both tables as a type: on the way in, text that must name a live object of that kind, handed to the function as the object; on the way out, the object, stored by the seam, with its handle text in the cell. The text's format and the store are designed then. The spec is [handles.md](handles.md).
