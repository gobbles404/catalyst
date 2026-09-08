# Inputs

How a value from Excel becomes a typed value the library can trust. This file changes whenever a declared type is added or a question below is decided. The tests are the record; this file is the map.

## What Excel can send

Every argument arrives in one of two shapes: a scalar, or an array. An array is always two-dimensional, even for one row or one column. Nothing else exists.

A scalar is one of six kinds.

| Kind | Examples | Notes |
|---|---|---|
| Number | `42`, `3.14`, a date, a time, `5%`, `$1,250` | Always a finite double. The format never travels: a date is its serial (2026-09-08 is 46273), 5% is 0.05, $1,250 is 1250, 14:30 is 0.604. Digits typed past the fifteenth become zeros. |
| Text | `"Brent"`, `""`, `'123`, `"WTI "` | Exactly as typed, up to 32,767 characters. Empty text is text. A number stored as text is text. Trailing and non-breaking spaces survive. |
| Boolean | `TRUE`, `FALSE` | Never a number. |
| Blank | an empty cell | Never zero and never empty text. |
| Error | `#N/A`, `#DIV/0!`, `#VALUE!`, `#REF!`, `#NAME?`, `#NUM!`, `#NULL!`, `#GETTING_DATA` | The host returns the first one it finds before Python runs. Newer errors such as `#SPILL!` and `#CALC!` arrive as `#VALUE!`. So do rich data types, in-cell images, LAMBDA values, multi-area references like `(A1:B2,D1:D2)`, and 3-D references. |
| Missing | the argument left out: `=Fn(A1,)` | Distinct from blank. Can appear inside an array in rare cases, such as `EXPAND` with its pad argument omitted. |

An array holds the six kinds, cell by cell.

| What was written | Arrives as |
|---|---|
| `A1`, `Sheet2!B7`, `A1:A1`, a one-cell name, `Table1[@Price]`, `@A1:A10` | A scalar. A one-cell reference is never a 1×1 array. |
| `{5}`, `SEQUENCE(1)`, a `FILTER` that matches one row | A 1×1 array. Excel does not unwrap it. |
| `A1:A8`, `B1:D1`, `A1:D3`, `G1#`, `Table1[Price]`, `{1,2;3,4}`, `SEQUENCE(3)` | An array of that shape. A column is N×1, a row is 1×N, in sheet order. |
| `A:A` | 1,048,576 rows, every unused cell blank. `1:1` is 16,384 columns. |
| A range with hidden or filtered rows, or merged cells | Every row. A merged block is its top-left value and blanks. |
| A reference to another sheet, a defined name, a closed workbook | The values only. No sheet, address, or name ever crosses. |

Everything in both tables was checked against the Excel-DNA source at the pinned version, and most rows were measured in Excel with a probe add-in.

## The guard

One place checks: `call` in `bridge.py`, before the function runs. The host ships the six kinds unchanged. The library trusts whatever the guard hands it. Nothing else in the package checks a kind or a shape.

The declaration is the function's own signature.

```python
@excel_function
def Forward(price: float, days: float, rate: float) -> float: ...
```

Rules:

1. Match the declared kind exactly. No coercion. A boolean is not a number, `"123"` is not a number, and empty text is not text a function may receive.
2. Blank and missing match nothing. Only a missing argument takes a declared default; a blank cell never does.
3. An array into a scalar slot fails, even a 1×1 one. `=Add(SEQUENCE(1), 2)` fails where Excel's own functions would take the one cell. A scalar into an array slot becomes a 1×1 array.
4. Every cell of an array is checked as a scalar would be. A blank inside an array of numbers fails, so `A:A` fails on its first unused row.
5. A one-row-or-column type declares its orientation. A column type fails on a row.
6. A failure names the function, the argument, what arrived, and what was expected: `#ERROR Forward: price is text 'Brent', expected number`. Inside an array the message names the cell by row and column within the range, because no sheet address crosses.

Scalars, rows arriving against columns declared:

| Arrives | number | whole number | text | boolean |
|---|---|---|---|---|
| Number | pass | pass when it has no fraction | fail | fail |
| Text | fail | fail | pass unless empty | fail |
| Boolean | fail | fail | fail | pass |
| Blank | fail | fail | fail | fail |
| Error | returned unchanged by the host | same | same | same |
| Missing | fail, or the declared default | same | same | same |

## Declared types

Built in the scalar pull request:

| Declared | Accepts | Example | Fails on |
|---|---|---|---|
| `float`, a number | one number | `=Forward(B2, 30, 0.05)` | text, boolean, blank, missing, any array |
| `int`, a whole number | one number with no fraction | `=McPrice(curve, 100000)` | 2.5, 2.9999999996, text, boolean, blank, missing, any array |
| `str`, text | one text with at least one character | `=CurveNames("WTI")` | empty text, number, boolean, blank, missing, any array |
| `bool`, a boolean | TRUE or FALSE | `=Price(curve, TRUE)` | 1 or 0, `"TRUE"`, blank, missing, any array |
| any of the above with a default | the argument missing | `=OptionPrice(curve, K, T)` | a blank cell |

Decided, and built in the array pull request:

| Declared | Accepts | Example | Fails on |
|---|---|---|---|
| `Block`, an array of numbers | a range of numbers with no blank cell, a scalar as 1×1 | `=ScaleBlock(A1:B2, 10)` | any blank, text, or boolean cell, named by row and column |

Next, one at a time, each when the first function needs it. Each adds one parser to the guard and one row here.

| Declared | Would accept | Example | The trap it must handle |
|---|---|---|---|
| Day, a calendar date | a whole serial | `=Expiry(B5)` with B5 = 08-Sep-2026 | A price typed into a date slot is also a whole number. `NOW()` has a fraction. Serials 1 to 60 fall on Excel's fictional 1900 leap day. |
| ContractMonth | a whole serial on the first of a month | B5 = 01-Dec-2027, shown as Dec-27 | Typing Dec-27 into a cell stores the 27th of December this year. |
| A choice from text | text equal to one member: call, put | `=OptionPrice(curve, K, T, "put")` | C/P and +1/−1 are desk aliases and stay on the sheet. |
| Unit | text equal to one member: bbl, MT, MWh, MMBtu | `=Convert(1000, "bbl", "MT")` | "BBLS" and "tonne" are aliases. `$/bbl` is a price, not a unit. |
| Handle to a live object | the text a builder function returned | `=Forward(B1, B5)` with B1 = `=BuildCurve(A3:B62)` | A reopened workbook keeps the text, not the object. A rebuilt curve with unchanged text does not recalculate its dependents. |
| Vector, a 1-D list of numbers | one row or one column | `=Npv(rates, B2:B25)` | A row and a column of the same numbers are the same Vector. |
| Matrix, a full grid | a range with no blank cell | `=Surface(expiries, strikes, C3:L14)` | A blank in a vol grid. Axis labels selected with the grid. |
| Days, a list of dates | one row or column of whole serials | `=Fixings(curve, B3:B25)` | Text dates from a CSV export. |
| Curve, dates and values | N×2 with no blanks | `=BuildCurve(A3:B62)` | The header row inside the selection. |
| Table with a header row | first row text naming the record's fields, body typed per column | `=PriceBook(curve, A1:H501)` | One text cell makes the host send every cell one at a time. Over-selected blank rows. |
| Optional with a default | the argument missing, never a blank cell | `=OptionPrice(curve, K, T)` | A blank mark taking a default prices silently. |

## Decided

Decided 2026-09-08, strict in every case.

1. A blank inside an array of numbers fails.
2. A 1×1 array into a scalar slot fails. `=Add(SEQUENCE(1), 2)` is the surprise to expect.
3. Whole-column references fail, on their first blank cell.
4. Optional arguments exist. Only a missing argument takes the default; a blank cell fails. The host sends missing as its own value.
5. Messages quote the offending value.
6. There is a whole-number type. 3.0 passes it; 2.9999999996 fails.
7. Empty text fails a text slot.
8. A one-row-or-column type declares its orientation; the other fails.

## Open questions

Each waits for the type that raises it.

1. Dates: whole serials only? Refuse 1 to 60? Text dates never?
2. Rates and percentages: 0.05 or 5? The seam cannot see the format, so the library must say which.
3. Choices from text: is folding "Call" to call coercion? Aliases stay on the sheet?
4. Units: does the unit ride with the number, or arrive as its own argument? Is currency a unit?
5. Handles: what the text carries, and how a rebuilt curve reaches its dependents when the handle text is unchanged.
6. Tables: how headers are matched, trailing blank rows, a blank in a body column.
7. An error inside a large range: the host returns it with no cell address. Should it name the cell? A host change.
8. Newer Excel errors arrive as `#VALUE!`. Accept as a known renaming and say so?

The way out, results returning to the sheet, is decided separately.
