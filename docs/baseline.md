# The baseline at 024486f

What the seam costs before anything is changed, measured in one session on 2026-09-11 at revision 024486f, with the probes standing in for the library. Every measured number here is read from a CSV row written that session, or is arithmetic on such rows that names the rows it uses; the counts and ceilings under "What the tests pin" are the tests' own constants at this revision. The CSVs and the environment files are in `docs/baseline/`. What each instrument includes and leaves out is in [measuring.md](measuring.md); this file is the numbers and what they say about how the library's formulas should be shaped.

How to read a number. A microsecond (µs) is a millionth of a second; a millisecond (ms) is a thousand microseconds; a nanosecond (ns) is a thousandth of a microsecond. Each runner times batches: a batch is a run of calls lasting about 50 ms, and its batch mean is the batch's elapsed time divided by the calls in it, so 52.7 ms over 65,536 calls of `Zero` is 0.80 µs each. Five batches give five means; the number printed is their median, the middle one when they are sorted, Excel's MEDIAN, with the smallest and largest of the five in brackets. Numbers are microseconds per call unless the table says otherwise.

The three clocks are separate. The Python runner times `bridge.call` on cells already built. The host runner times the function as the add-in hands it to Excel, but without Excel. The Excel runner times a recalculation of a hidden Excel driven over COM, the Windows channel through which one program drives another. Read them side by side; a stage's cost is named only where one clock measured that stage alone.

The machine: AMD64 family 25, 16 logical processors. Excel 16.0 build 20326 with multithreaded calculation on and 16 calculation threads, which native formulas may use and the seam's functions do not. Python 3.13.13, numpy 2.5.2, pythonnet 3.1.0, Excel-DNA integration 1.1.0, .NET Framework 4.8, Release build.

## What a call costs

One scalar call, single numbers in and one number out: `=Add(a, b)`, beside `=HostAdd(a, b)`, a C# function with the host's argument shape and no Python, and beside `=a+b`. Excel, per formula, over a column of formulas recalculated together:

| Rows | Add | HostAdd | native `+` |
|---:|---:|---:|---:|
| 100 | 13.23 (11.79..606.49) | 5.35 (5.24..5.83) | 3.47 (3.29..3.86) |
| 1,000 | 7.19 (7.17..11.19) | 2.46 (2.30..2.86) | 0.44 (0.43..0.48) |
| 10,000 | 6.76 (6.60..7.20) | 1.99 (1.94..2.07) | 0.15 (0.14..0.77) |

Read the 1,000 and 10,000 rows. At 100 rows the native column's whole recalculation takes 0.35 ms (its per-recalculation row), and its formulas cost 0.15 µs each at 10,000 rows, so nearly all of that 0.35 ms is the recalculation itself, and it sits under every column, spread over only a hundred formulas. One batch of Add at 100 rows took 606 µs per formula; the other four agree at 12 to 14, the median is unmoved, and the CSV does not say where that batch's time went.

The same call without Excel, and its Python part alone:

| Call | Python runner | Host runner |
|---|---:|---:|
| `Zero()` | 0.80 (0.80..0.80) | 2.52 (2.50..2.53) |
| `Add(1, 2)` | 1.30 (1.29..1.31) | 3.55 (3.53..3.57) |
| `Times(5)`, factor omitted | 1.14 (1.14..1.16) | 3.59 (3.55..3.62) |

So a user pays about 7 µs for a scalar call through the seam. Excel's and Excel-DNA's own share of a call is what `HostAdd` pays, 2 to 2.5 µs per formula, of which a native `+` is 0.15 to 0.44. Without Excel, the host runner times the call at 3.6 µs, one trip included; a trip is one crossing from the host into Python and back with the answer. No one clock measured the seam's share inside Excel, so those three figures stand side by side. A thousand per-trade formulas cost about 7 ms, and ten thousand about 68 ms.

## What a cell in costs

`=SumArray(A1:A_N)`, one range in and one number out, beside `=SUM`. The host runner also times the way in alone: the scan of the range, the two pinned buffers, and the trip that hands them to Python, with nothing called afterwards. A pinned buffer is memory the host fills and holds still in place, so Python can read it where it lies before taking its own copy; one holds what kind each cell is, the other its number.

| Cells in | Python | Host | Host, way in alone | Excel `SumArray` | Excel `SUM` |
|---:|---:|---:|---:|---:|---:|
| 1 | 4.4 (4.4..4.4) | 18.8 (18.6..18.9) | 9.6 (9.5..10.3) | | |
| 100 | 5.0 (4.7..5.0) | 21.6 (21.4..21.9) | 11.5 (11.3..11.6) | 46.4 (42.0..49.8) | 4.5 (4.0..6.1) |
| 1,000 | 5.9 (5.7..6.1) | 38.4 (36.8..39.9) | 25.2 (24.5..25.9) | 84.7 (83.4..92.7) | 8.9 (8.6..10.1) |
| 10,000 | 15.1 (14.5..15.3) | 180.3 (177.2..187.4) | 158.0 (154.2..159.9) | 450.1 (442.7..459.7) | 55.2 (53.9..57.5) |
| 100,000 | 94.2 (93.4..95.4) | 2,127.0 (2,087.2..2,181.9) | 1,748.8 (1,719.6..1,800.6) | | |

Owning the range, which is Python taking its own copy of the host's two buffers so the host can let go of them (`cells_from_buffers`, then named `cells_block`), timed alone: 6.2 (6.1..6.3) at one cell, 6.4 (6.1..6.5) at a hundred, 7.5 (7.4..8.1) at a thousand, 16.9 (16.5..17.2) at ten thousand, 95.6 (91.9..121.6) at a hundred thousand.

Per added cell, from the 100 and 10,000 rows above: Excel charges about 41 nanoseconds for a cell through the seam and 5 for a cell through `SUM`; the host runner about 16, of which the way in alone is 15; the Python runner about 1. A range in is the host's cost: at ten thousand cells the host runner puts 158 of its 180 µs in the way in alone, and Python's validation and sum together are 15.

Every range is one look, one pass over all its cells at once the way `=SUM` reads a range, however many cells it holds; a bad cell is named without a walk, a loop that visits cells one by one. Rejections at ten thousand cells, Python and host:

| Rejection | Python | Host |
|---|---:|---:|
| a column where a row was declared | 2.6 (2.5..2.7) | 170.7 (166.2..178.1) |
| text in the first cell | 21.4 (17.9..26.2) | 194.4 (191.5..198.5) |
| text in the last cell | 28.9 (28.7..36.4) | 195.8 (192.9..199.0) |
| a blank in the middle | 15.0 (14.7..16.0) | 187.5 (184.5..214.5) |
| an Excel error in the first cell | | 2.4 (2.4..2.5) |
| an Excel error in the last cell | | 132.8 (130.9..138.7) |

The shape rejection is decided in 2.6 µs of Python but still pays the transport, 170 µs in the host, because the range is scanned and pinned before Python sees its shape. An Excel error stops the host's scan where it is found and makes no trip.

## What a cell out costs

`=Grid(N, 1)`, two numbers in and an array of N cells out. An array is the rectangle of values one formula returns; Excel spills it, filling the cells below and beside the formula, as `=SEQUENCE(3)` fills three rows. The host runner also times the way out alone: an array Python already holds, copied into memory the host owns.

| Cells out | Python | Host | Host, way out alone | Excel `Grid` |
|---:|---:|---:|---:|---:|
| 1 | 4.2 (4.1..4.5) | 9.4 (9.3..10.2) | 1.0 (1.0..1.0) | |
| 100 | 4.4 (4.3..4.5) | 9.4 (9.3..9.7) | 1.1 (1.0..1.1) | 32.2 (31.1..36.1) |
| 1,000 | 5.3 (5.2..5.3) | 12.5 (11.9..12.6) | 1.9 (1.8..1.9) | 137.4 (113.3..140.6) |
| 10,000 | 10.8 (10.7..10.8) | 33.5 (29.6..36.1) | 8.7 (8.5..8.9) | 1,122.0 (1,040.4..1,167.6) |
| 100,000 | 62.8 (61.0..63.6) | 511.6 (492.0..679.4) | 203.3 (201.0..216.7) | | 

Per added cell, from the 100 and 10,000 rows: Excel charges about 110 nanoseconds for a cell out; the host runner about 2.4, of which the way out alone is 0.8; the Python runner about 0.6. A cell out costs a user nearly three times a cell in. The host's two copies are a small part of it, and what Excel itself spends on the spill was not measured alone.

## The round trip and one answer per row

`EchoColumn` is N cells in and N out. `RowSums` is a grid in and one number per row out, the shape of pricing every row. `Dot` is two ranges in.

| Cells in | EchoColumn, Python | EchoColumn, Host | RowSums, Python | RowSums, Host | Dot, Python | Dot, Host |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 6.7 (6.1..7.2) | 24.9 (24.2..25.6) | | | 8.4 (8.3..8.4) | 34.3 (33.6..38.8) |
| 100 | 6.3 (6.2..6.3) | 27.6 (27.2..27.8) | 7.8 (7.8..7.9) | 28.3 (27.6..30.6) | 9.1 (8.9..9.1) | 40.3 (39.7..45.7) |
| 1,000 | 7.4 (7.2..7.6) | 45.0 (43.9..45.6) | 9.8 (9.5..10.1) | 36.5 (36.1..37.5) | 11.0 (10.9..11.1) | 72.8 (71.1..79.9) |
| 10,000 | 15.9 (15.3..16.5) | 199.6 (197.2..207.7) | 26.7 (26.2..27.4) | 119.0 (110.0..133.3) | 25.9 (25.1..26.2) | 350.5 (346.5..362.9) |
| 100,000 | 86.6 (85.9..88.7) | 2,533.9 (2,427.2..2,547.9) | 180.8 (179.4..193.1) | 1,260.2 (1,215.5..1,427.2) | 266.3 (261.9..272.2) | 4,323.9 (4,222.8..4,463.5) |

RowSums at 10,000 cells in is 1,000 rows of ten cells and 1,000 answers out. For Dot the cells-in count is per range: its 10,000 row is two ranges of 10,000 cells each, which the CSV records as 20,000 cells in, each range its own scan and trip.

## The same answers three ways

The batching question, in Excel: a thousand answers from a thousand one-row formulas, from ten formulas over hundred-row arrays, or from one formula over the whole column. The echo arrangements are `=Times(Ai)` filled down against `=EchoColumn` arrays; the RowSums arrangements are `=RowSums(Ai:Ji)` filled down against `=RowSums` arrays over ten columns. Full is every formula of the arrangement recalculated; edit is one input changed in the middle row and Excel recalculating what depends on it. Milliseconds per recalculation:

| Arrangement, 1,000 rows | Formulas | Echo, full | Echo, one edit | RowSums, full | RowSums, one edit |
|---|---:|---:|---:|---:|---:|
| one formula per row | 1,000 | 7.28 (7.11..9.04) | 0.82 (0.79..0.88) | 40.43 (40.01..41.06) | 0.91 (0.89..1.00) |
| ten arrays of 100 | 10 | 1.08 (1.05..1.11) | 1.34 (0.88..1.58) | 1.46 (1.40..1.49) | 1.35 (0.96..1.36) |
| one array of 1,000 | 1 | 1.03 (0.73..1.20) | 1.82 (1.34..2.01) | 1.02 (0.99..1.06) | 1.50 (1.47..1.55) |
| the edit's floor: the same write, nothing dependent | 0 | | 0.54 (0.52..0.58) | | |

| Arrangement, 10,000 rows | Formulas | Echo, full | Echo, one edit | RowSums, full | RowSums, one edit |
|---|---:|---:|---:|---:|---:|
| one formula per row | 10,000 | 67.95 (65.72..69.46) | 0.89 (0.86..1.03) | 385.72 (382.69..396.76) | 1.22 (0.98..1.84) |
| ten arrays of 1,000 | 10 | 2.50 (2.47..2.50) | 1.34 (1.18..1.41) | 5.91 (5.82..5.97) | 1.78 (1.42..2.00) |
| one array of 10,000 | 1 | 2.09 (2.03..2.85) | 2.33 (2.16..3.16) | 8.09 (7.99..8.15) | 8.28 (7.93..9.53) |
| the edit's floor: the same write, nothing dependent | 0 | | 0.58 (0.55..0.60) | | |

Three facts stand out.

- **Arrays win a full recalculation by a wide margin.** At 1,000 rows, ten arrays or one array deliver the same answers in 1 to 1.5 ms against 7 ms for the echo and 40 ms for RowSums row by row. At 10,000 rows the margin is 68 ms against 2 to 2.5, and 386 ms against 6 to 8.
- **A one-row formula that takes a range is the worst shape there is.** `=RowSums(Ai:Ji)` filled down costs 40 µs per row, five and a half times `=Add(Ai, Bi)`. The range is what costs, not the one-cell array it returns: a range in and a number out, `SumArray` over a hundred cells, costs 46 µs too. Each such row pays for a range in and an array out, which the counters pin at two trips, four buffers and two copies; what that costs inside Excel was not measured alone. A function that answers one row from a handful of single values is cheap; one that reads a range per row is not, whatever it returns.
- **An edit costs one to two milliseconds whatever the arrangement, at 1,000 rows.** The floor, one cell written and Excel asked to recalculate with nothing depending on it, is 0.54 ms. One formula per row adds 0.3 to 0.4 ms to that; an array of 100 or 1,000 adds 0.8 to 1.3 ms. At 10,000 rows a whole-column array's edit grows to 2.3 ms for the echo and 8.3 ms for RowSums, against 0.9 and 1.2 per row.

## What the tests pin

The counts are tests, so a seam change states what it moved. A trip is one crossing into Python and back. A name lookup is the host asking Python for something by its text name, the function to call or the marker for a missing argument, as `INDIRECT` finds a cell by its address: a scalar call makes one, and each range or omitted argument adds one. Objects built are the Python values the host makes to carry the call. As of this revision:

| The host did, for | trips | name lookups | objects built | cells scanned | buffers, bytes | result copies, cells |
|---|---:|---:|---:|---:|---:|---:|
| a scalar call, `Add(1, 2)` | 1 | 1 | 4 | | | |
| an omitted argument, `Times(5)` | 1 | 2 | 4 | | | |
| a range in, N cells | 2 | 2 | 7 | N | 2, 9N | |
| an Excel error at cell 5 of 10,000 | 0 | 0 | 2 | 5 | 2, 90,000 | |
| an array out, N cells, `Grid` | 1 | 1 | 4 | | 2, 16N | 2, N |
| one answer per row, 100 in and 10 out | 2 | 2 | 7 | 100 | 4, 1,060 | 2, 10 |

One text cell in a range adds one to `text_cells` and nothing else. A shape rejection pays the whole range budget. Memory the host's own runtime hands out per call and later reclaims, which measuring.md calls managed allocation, is metered on the host's thread. A warm call, one made after the first so nothing is being set up for the first time, allocates under 512 bytes; this session measured 440. A range in adds 9 bytes per cell and an array out 16, both pinned as ceilings with a little slack. This session's runner saw 90,890 bytes per `SumArray` call at ten thousand cells, 160,796 per `Grid` of ten thousand, and 251,240 per `EchoColumn` of ten thousand.

On the Python side, `call_profile` pins each probe's own functions exactly: a range is one look whatever it holds, a bad cell deep inside is named without a walk, a failing body costs no look. The numpy ledger pins three things. Owning a range is two views (reading the host's buffers where they lie), two copies, and one look for text. A sum is one look and one reduction, the folding of an array to one number as `SUM` does. A column out copies nothing of its own.

The peaks from `tracemalloc`, Python's meter of how much memory a call holds at its highest point, are pinned as ceilings. A scalar call stays under 1,024 bytes; this session measured 160 to 256. A range in stays under 8 bytes per cell plus slack; measured 77,008 at ten thousand cells, which the test reads as a scratch array of 8-byte integers that the check of each cell's kind builds before its 1-byte-per-cell list of yes-or-no answers. A column out is the same 77,008. An array out stays under 9 per cell; measured 90,401. Owning a range stays under 9 per cell; measured 90,536.

## What this says about the library's formulas

Everything above is about one decision: whether a pricing function is called once per trade, once per array of trades, or once per sheet. The numbers say:

- **Declare pricing functions over arrays.** In Excel, ten arrays of a hundred rows deliver a thousand answers in 1.08 ms (echo) and 1.46 ms (RowSums) per recalculation, against 7.28 ms for the same rows as `=Times(Ai)` and 40.43 ms as `=RowSums(Ai:Ji)`. So at a thousand rows an array formula is about seven times cheaper than the same rows as scalar calls, and twenty-eight to forty times cheaper than the same rows as one-row range formulas. Below a hundred rows nothing was measured in Excel. The host runner, which does measure a one-cell array, prices `EchoColumn` at one cell at 24.9 µs, seven of its scalar calls, and at a hundred cells at 27.6, eight; if Excel follows the host, the crossover is under ten rows, but that was not measured. A function that takes a column of trades and returns a column of prices is the default shape.
- **A per-row formula takes single values, not a range.** The one shape to forbid is a range read per row: 40 µs per row against 7 for `=Add(Ai, Bi)`, whatever the formula returns.
- **Arrays of a hundred to a thousand rows keep both bills small.** Ten arrays cost 1.1 to 1.5 ms for a thousand rows and 2.5 to 5.9 ms for ten thousand on a full recalculation, and 1.3 to 1.8 ms on an edit. One array over ten thousand rows costs 2.1 ms for the echo and 8.1 for RowSums on a full recalculation, and about the same on every edit, 2.3 and 8.3 ms, because one changed cell recalculates the whole array.
- **What a scalar call still costs is worth holding down.** Sheets will have per-trade formulas whatever the default. A user pays 7 µs per scalar call, a C# function with no Python pays 2 to 2.5, and without Excel the host runner times the seam's call at 3.6. The counters name the moves: one trip and one name lookup per call, four objects, and no buffer.

For the seam itself, the curves say where the work is. A range in is the host's scan and two pinned buffers: 158 of the host runner's 180 µs at ten thousand cells. A cell out costs a user 110 nanoseconds through Excel. Beside it, the host runner charges 2.4 per cell, of which the way out alone is 0.8, and the Python runner about a nanosecond per cell in and 0.6 per cell out. The refactors that follow are judged against these rows: checking each cell's kind as a plain integer, against the 8-byte-per-cell peak; filling both buffers in one pass over the range and reusing them, against `buffers_allocated`; finding the Python function once instead of on every call, against `name_lookups` and `objects_built`; and handing an array to Excel with one copy instead of two, against `result_copies`.
