# Inputs

How a value from Excel becomes a typed value the library can trust. This file changes whenever a declared type is added or a question below is decided. The tests are the record; this file is the map.

## What Excel can send

Every argument arrives in one of two shapes: a scalar, or an array. An array is always two-dimensional, even for one row or one column. Nothing else exists.

A scalar is one of six kinds.

| Kind | Examples | Notes |
|---|---|---|
| Number | `42`, `3.14`, a date, a time, `5%`, `$1,250` | Always a finite double. The format never travels: a date is its serial (2026-09-08 is 46273), 5% is 0.05, $1,250 is 1250, 14:30 is 0.604. Digits typed past the fifteenth become zeros. A workbook on the 1904 date system sends serials 1,462 days lower, with no signal; such workbooks are not supported. |
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
| A range with hidden or filtered rows, or merged cells | Every row. A merged array is its top-left value and blanks. |
| A reference to another sheet, or a defined name | The values only. No sheet, address, or name ever crosses. |

Everything in both tables was checked against the Excel-DNA source at the pinned version, and most rows were measured in Excel with a probe add-in.

## Type validation

One place checks: the prepared path, `Registered.run` in `bridge.py`, which the host fetches once per function at registration with `entry`, and `call` reaches by name. It checks before the function runs. It validates the type of every argument against the function's signature and hands the library the typed value: a date from a serial, a plain list from a column, never the raw cell. The seam validates type; the library validates meaning. Nothing else in the package checks a kind or a shape.

The declaration is the function's own signature.

```python
@excel_function
def Forward(price: float, days: float, rate: float) -> float: ...
```

Rules:

1. Match the declared type exactly. No coercion. A boolean is not a number, `"123"` is not a number, and empty text is not text a function may receive.
2. Blank and missing match nothing. Only a missing argument takes a declared default; a blank cell never does.
3. An array into a scalar slot fails, even a 1×1 one. `=Add(SEQUENCE(1), 2)` fails where Excel's own functions would take the one cell. A scalar into a range slot becomes a 1×1 range.
4. Every cell of a range is checked as a scalar would be, and the range keeps its order. A blank inside a range of numbers fails, so `A:A` fails on its first unused row.
5. A one-row-or-column type declares its orientation. A column type fails on a row.
6. The boundary checks each argument alone, by type and shape, never by meaning. Which name goes with which column, whether a column is sorted, whether two arguments agree: all of that belongs to the library. The one documented exception is that a date serial must lie inside Excel's own calendar, 61 to 2958465, which is 1 March 1900 to 31 December 9999.
7. Shape is checked before cells. A range of the wrong shape is reported as a shape failure even when it also holds a bad cell.
8. A failure names the function, the argument, what arrived, and what was expected: `#ERROR Forward: price is text 'Brent', expected number`. Inside a range the message names the cell the way `INDEX` counts, row then column from 1 within the range, because no sheet address crosses: `#ERROR Strip: values cell (3, 1) is blank, expected number`.

Scalars, rows arriving against columns declared:

| Arrives | number | whole number | date | text | boolean |
|---|---|---|---|---|---|
| Number | pass | pass when it has no fraction | pass when whole and 61 or more | fail | fail |
| Text | fail | fail | fail | pass unless empty | fail |
| Boolean | fail | fail | fail | fail | pass |
| Blank | fail | fail | fail | fail | fail |
| Error | returned unchanged by the host | same | same | same | same |
| Missing | fail, or the declared default | same | same | same | same |

## Declared types

Built in the scalar pull request:

| Declared | Accepts | Example | Fails on |
|---|---|---|---|
| `float`, a number | one number | `=Forward(B2, 30, 0.05)` | text, boolean, blank, missing, any array |
| `int`, a whole number | one number with no fraction | `=McPrice(curve, 100000)` | 2.5, 2.9999999996, text, boolean, blank, missing, any array |
| `str`, text | one text with at least one character | `=CurveNames("WTI")` | empty text, number, boolean, blank, missing, any array |
| `bool`, a boolean | TRUE or FALSE | `=Price(curve, TRUE)` | 1 or 0, `"TRUE"`, blank, missing, any array |
| any of the above with a default | the argument missing | `=OptionPrice(curve, K, T)` | a blank cell |

Built in the range pull request. A date is a whole serial of 61 or more, handed over as a calendar date; a range keeps its order and its shape.

| Declared | Accepts | Example | Hands over | Fails on |
|---|---|---|---|---|
| `Date` | one whole number from 61 to 2958465 | `=Discount(B5)` with B5 = 22-May-2026 | the date 2026-05-22 | 46164.5, `"2026-05-22"`, 60, 2958466 |
| `NumberArray` | a range of numbers, any shape | `=Total(A2:B4)` | the grid, as on the sheet | a blank, text, or boolean cell, named |
| `Column` | a range of numbers, one column wide | `=Strip(A2:A4)` | a plain list of numbers | a row, a wider range, a bad cell |
| `Row` | a range of numbers, one row tall | `=Weights(A2:C2)` | a plain list of numbers | a column, a taller range, a bad cell |
| `DateColumn` | a range of dates, one column wide | `=Schedule(A2:A7)` | a plain list of dates | a fraction, a serial under 61, a blank |
| `DateRow` | a range of dates, one row tall | `=Expiries(A1:F1)` | a plain list of dates | the same, or a column |
| `TextColumn` | a range of text, one column wide | `=Names(A2:A4)` | a plain list of text | empty text, a number or boolean cell, a row |
| `TextRow` | a range of text, one row tall | `=Headers(A1:C1)` | a plain list of text | the same, or a column |

A single cell fits any range type as a 1×1. A `TextArray`, text of any shape, is possible under the same rules and is not built, because no function needs one.

Next, one at a time, each when the first function needs it. Each adds one rule to the validator and one row here.

| Declared | Would accept | Example | The trap it must handle |
|---|---|---|---|
| ContractMonth | a whole serial on the first of a month | B5 = 01-Dec-2027, shown as Dec-27 | Typing Dec-27 into a cell stores the 27th of December this year. |

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

Decided 2026-09-09, for ranges and dates.

9. A cell is named the way `INDEX` counts: row then column, from 1, within the range that was passed.
10. A `Column` or `Row` hands the function a plain list. A `NumberArray` keeps its shape. Nothing is sorted or reordered.
11. Headers never sit inside a range of numbers. They cross as their own argument, a row of text.
12. Seven range types: `NumberArray`, `Column` and `Row` hold numbers; `DateColumn` and `DateRow` hold dates; `TextColumn` and `TextRow` hold text. A `TextArray` is possible and not built.
13. A date is a whole serial inside Excel's own calendar, 61 to 2958465. A fraction fails. There is no time-of-day type.
14. The boundary never checks meaning. Matching header names to columns and checking that a column is sorted belong to the library, not the validator.
15. Shape before cells. A wrong-shaped range is reported as such before any cell is looked at.

Decided 2026-09-09, closing the input side.

16. The seam never scales a number. A vol given in percent is divided by 100 in the library, in one place.
17. A choice from text, such as call or put, crosses as text. The library decides what the text means.
18. A unit is its own argument. One cell holds one value, never `1000 bbl`.
19. An error inside a range comes back as that error, with no cell named.
20. Newer Excel errors such as `#SPILL!` arrive as `#VALUE!`. Known, and left alone.
21. Every range crosses the host the same way: a kind per cell, a number per cell, the text cells in sheet order, and a summary of which kinds occurred, all from one pass into two buffers the host keeps between calls and grows only for a larger range than any before. The host never chooses a road. A range the summary shows to be all numbers, or all text, is accepted without a look at the kinds; otherwise one look names the first offending cell.

## Not supported

- References to other workbooks. The seam sees values only, so this is policy, not a check.
- Workbooks on the 1904 date system. Their serials arrive 1,462 days low with no signal.

## Parked

Handles: text that stands for a live object such as a curve. The seam's part is one rule per object kind, the text must name a live object of that kind, checked before the library sees it. The text's format, the store, and columns of handles are designed when the first builder function exists.

The way out, results returning to the sheet, is [outputs.md](outputs.md).
