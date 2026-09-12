# The baseline at aaa5259

What the seam costs after the five seam changes that followed the first baseline, measured in one session on the evening of 2026-09-11 at revision aaa5259. The seam is the one place where Excel and Python talk; the probes, hidden worksheet functions that do no work beyond crossing it, stand in for the library. Every measured number here is read from a CSV row written that session, or is arithmetic on such rows that names the rows it uses; the counts and ceilings under "What the tests pin" are the tests' own constants at this revision. The CSVs and the environment files are in `docs/baseline/`, and `docs/baseline/since-024486f.md` sets every row of this session beside the same row of the first baseline, the document committed at 134d6d3. What each instrument includes and leaves out is in [measuring.md](measuring.md); this file is the numbers, what moved, and what they say about how the library's formulas should be shaped.

How to read a number. A microsecond (µs) is a millionth of a second; a millisecond (ms) is a thousand microseconds; a nanosecond (ns) is a thousandth of a microsecond. Each runner times batches: a batch is a run of calls lasting about 50 ms, and its batch mean is the batch's elapsed time divided by the calls in it, so 50.9 ms over 65,536 calls of `Zero` is 0.78 µs each. Five batches give five means; the number printed is their median, the middle one when they are sorted, Excel's MEDIAN, with the smallest and largest of the five in brackets. Numbers are microseconds per call unless the table says otherwise.

The three clocks are separate. The Python runner times each function's prepared path, the Python side of a call with everything it needs found once beforehand, on cells already built. The host runner times the function as the host, the C# add-in that stands between Excel and Python, hands it to Excel, but without Excel. The Excel runner times a recalculation of a hidden Excel driven over COM, the Windows channel through which one program drives another. Read them side by side; a stage's cost is named only where one clock measured that stage alone.

The session. The Python runner, the host runner and the 1,000-row Excel runner wrote their files within one minute of each other; the environment files stamp them in UTC at the end of each run, 2026-09-12 00:35 to 00:36. The 10,000-row Excel control, a run at a larger size kept to show how costs grow rather than to define the ordinary case, was written at 00:40, four minutes later, because its first attempt failed before timing anything. That runner rebuilds the add-in, and the Excel of the 1,000-row run had not yet let go of the file. The machine's load was checked by hand before each part and found under a tenth of one of its sixteen processors, but no file records it.

The machine: AMD64 family 25, 16 logical processors. Excel 16.0 build 20326 with multithreaded calculation on and 16 calculation threads, which native formulas may use and the seam's functions do not. Python 3.13.13, numpy 2.5.2, pythonnet 3.1.0, Excel-DNA integration 1.1.0, the framework that plugs the add-in into Excel, .NET Framework 4.8, Release build. The same machine and versions as the first baseline.

## What a call costs

One scalar call, single numbers in and one number out: `=Add(a, b)`, beside `=HostAdd(a, b)`, a C# function with the host's argument shape and no Python, and beside `=a+b`. Excel, per formula, over a column of formulas recalculated together:

| Rows | Add | HostAdd | native `+` |
|---:|---:|---:|---:|
| 100 | 10.90 (10.38..11.03) | 5.71 (5.57..6.22) | 3.85 (3.58..5.83) |
| 1,000 | 6.45 (6.31..6.66) | 2.40 (2.33..2.85) | 0.47 (0.45..0.49) |
| 10,000 | 5.73 (5.68..6.42) | 2.00 (1.93..2.37) | 0.14 (0.14..0.15) |

Read the 1,000 and 10,000 rows. At 100 rows the native column's whole recalculation takes 0.38 ms (its per-recalculation row), and its formulas cost 0.14 µs each at 10,000 rows. So nearly all of that 0.38 ms is the recalculation itself, which sits under every column, spread here over only a hundred formulas.

The same call without Excel, and its Python part alone:

| Call | Python runner | Host runner |
|---|---:|---:|
| `Zero()` | 0.78 (0.77..0.78) | 1.59 (1.55..1.65) |
| `Add(1, 2)` | 1.25 (1.25..1.26) | 2.66 (2.65..2.71) |
| `Times(5)`, factor omitted | 1.12 (1.11..1.12) | 2.36 (2.34..2.37) |

So a user pays about 6.4 µs for a scalar call through the seam at a thousand rows, and 5.7 at ten thousand. Excel's and Excel-DNA's own share of a call is what `HostAdd` pays, 2 to 2.4 µs per formula, of which a native `+` is 0.14 to 0.47. Without Excel, the host runner times the call at 2.7 µs, one trip included; a trip is one crossing from the host into Python and back with the answer. No one clock measured the seam's share inside Excel, so those three figures stand side by side. A thousand per-trade formulas cost about 6.4 ms, and ten thousand about 57 ms.

## What a cell in costs

`=SumArray(A1:A_N)`, one range in and one number out, beside `=SUM`. The host runner also times the way in alone: the scan of the range into the host's two kept buffers, and the trip that hands them to Python, with nothing called afterwards. A buffer is memory the host fills and holds still in place, so Python can read it where it lies before taking its own copy; one holds what kind each cell is, the other its number. The host keeps both between calls and grows them only for a range larger than any it has seen. A call is warm when nothing is being set up for the first time; for a range, that means the host has already scanned one at least as large, so the buffers are already there and the call allocates nothing for its cells.

| Cells in | Python | Host | Host, way in alone | Excel `SumArray` | Excel `SUM` |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.8 (1.8..1.8) | 7.6 (7.4..7.6) | 4.3 (4.1..4.6) | | |
| 100 | 1.9 (1.8..1.9) | 8.1 (8.0..8.4) | 4.7 (4.7..4.8) | 25.2 (25.0..26.7) | 4.7 (4.2..7.6) |
| 1,000 | 2.2 (2.1..2.2) | 12.1 (12.1..12.6) | 7.7 (7.7..7.8) | 57.0 (56.3..58.8) | 9.3 (8.6..10.2) |
| 10,000 | 4.2 (4.1..4.5) | 44.7 (44.4..46.2) | 37.7 (36.8..38.1) | 325.8 (317.9..328.9) | 54.9 (53.3..56.1) |
| 100,000 | 22.6 (22.2..22.8) | 1,044.3 (687.5..1,297.0) | 342.0 (340.0..353.4) | | |

Owning the range, which is Python taking its own copy of the host's two buffers so the host can reuse them (`cells_from_buffers`), timed alone: 3.1 (3.1..3.2) at one cell, 3.2 (3.1..3.3) at a hundred, 3.7 (3.6..3.8) at a thousand, 5.6 (5.6..5.7) at ten thousand, 26.0 (24.0..28.7) at a hundred thousand.

Per added cell, from the 100 and 10,000 rows above: Excel charges about 30 nanoseconds for a cell through the seam and 5 for a cell through `SUM`; the host runner about 3.7, of which the way in alone is 3.3; the Python runner about 0.2. A range in is still the host's scan: at ten thousand cells the host runner puts 37.7 of its 44.7 µs in the way in alone, and Python's validation and sum together are 4.2. The 100,000-cell control is the row whose batches disagree most: the host runner's `SumArray` ranges from 687 to 1,297 µs while the way in alone holds at 340 to 353. The CSV's collection counts are zero in every batch of that row, so it is not the host's memory being reclaimed; beyond that the CSV does not say.

Every range is one look, one pass over all its cells at once the way `=SUM` reads a range, however many cells it holds; a bad cell is named without a walk, a loop that visits cells one by one. A range of nothing but numbers is accepted without even that look, on the summary of kinds the host records while scanning. Rejections at ten thousand cells, Python and host:

| Rejection | Python | Host |
|---|---:|---:|
| a column where a row was declared | 2.5 (2.5..2.5) | 45.4 (44.3..47.1) |
| text in the first cell | 7.7 (7.6..7.8) | 56.3 (53.9..60.4) |
| text in the last cell | 9.1 (8.7..9.3) | 55.7 (54.8..57.4) |
| a blank in the middle | 5.6 (5.6..5.8) | 50.7 (49.7..51.2) |
| an Excel error in the first cell | | 0.2 (0.2..0.2) |
| an Excel error in the last cell | | 29.5 (28.9..30.2) |

The shape rejection is decided in 2.5 µs of Python but still pays the transport, 45 µs in the host, because the range is scanned and handed over before Python sees its shape. An Excel error stops the host's scan where it is found and makes no trip.

## What a cell out costs

`=Grid(N, 1)`, two numbers in and an array of N cells out. An array is the rectangle of values one formula returns; Excel spills it, filling the cells below and beside the formula, as `=SEQUENCE(3)` fills three rows. The host runner also times the way out alone: an array Python already holds, copied once into the array Excel receives.

| Cells out | Python | Host | Host, way out alone | Excel `Grid` |
|---:|---:|---:|---:|---:|
| 1 | 4.3 (4.2..4.5) | 7.6 (7.3..7.6) | 0.9 (0.9..0.9) | |
| 100 | 4.4 (4.4..4.7) | 8.1 (7.8..8.2) | 0.9 (0.9..1.0) | 29.9 (27.7..847.1) |
| 1,000 | 5.3 (5.2..5.4) | 9.6 (9.5..9.6) | 1.3 (1.2..1.3) | 118.3 (109.7..187.9) |
| 10,000 | 10.8 (10.7..10.9) | 19.9 (19.6..20.1) | 9.3 (5.6..14.7) | 1,066.1 (1,024.3..1,146.3) |
| 100,000 | 62.0 (61.2..62.7) | 363.0 (334.2..521.9) | 172.6 (164.1..172.9) | |

Per added cell, from the 100 and 10,000 rows: Excel charges about 105 nanoseconds for a cell out; the host runner about 1.2; the Python runner about 0.6. The way out alone at ten thousand cells is the one row timing a stage alone whose batches spread, 5.6 to 14.7; the CSV records the same bytes and, within one, the same collection counts in every one of its batches, and the `Grid` row that holds the same allocation is tight, so the CSV does not say what spread it. Its per-cell figure is read from the 100 and 1,000 rows instead: about a third of a nanosecond on the host's clock. A cell out costs a user about three and a half times a cell in, and what Excel itself spends on the spill was not measured alone. One batch of `Grid` at 100 cells took 847 µs per formula; the other four agree at 28 to 30, and the median is unmoved.

## The round trip and one answer per row

`EchoColumn` is N cells in and N out. `RowSums` is a grid in and one number per row out, the shape of pricing every row. `Dot` is two ranges in.

| Cells in | EchoColumn, Python | EchoColumn, Host | RowSums, Python | RowSums, Host | Dot, Python | Dot, Host |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3.2 (3.2..3.3) | 11.3 (11.1..11.6) | | | 3.0 (3.0..3.0) | 13.6 (13.4..13.7) |
| 100 | 3.2 (3.2..3.6) | 12.2 (12.0..12.7) | 4.5 (4.4..4.6) | 13.6 (13.2..14.3) | 3.2 (3.1..3.2) | 15.0 (14.8..15.3) |
| 1,000 | 3.6 (3.6..3.6) | 18.1 (17.7..19.1) | 5.6 (5.5..5.7) | 19.1 (18.4..19.6) | 3.3 (3.3..3.4) | 22.3 (22.1..22.5) |
| 10,000 | 5.2 (5.1..5.2) | 60.6 (58.5..63.2) | 15.3 (14.9..15.5) | 61.3 (60.0..61.4) | 4.8 (4.8..4.9) | 85.2 (83.3..93.1) |
| 100,000 | 19.1 (18.9..19.2) | 905.3 (872.5..978.7) | 110.9 (107.8..130.8) | 517.5 (508.8..531.3) | 113.8 (112.4..114.6) | 1,402.0 (1,349.9..1,416.3) |

RowSums at 10,000 cells in is 1,000 rows of ten cells and 1,000 answers out. For Dot the cells-in count is per range: its 10,000 row is two ranges of 10,000 cells each, which the CSV records as 20,000 cells in, each range its own scan and trip.

## The same answers three ways

The batching question, in Excel: a thousand answers from a thousand one-row formulas, from ten formulas over hundred-row arrays, or from one formula over the whole column. The echo arrangements are `=Times(Ai)` filled down against `=EchoColumn` arrays; the RowSums arrangements are `=RowSums(Ai:Ji)` filled down against `=RowSums` arrays over ten columns. Full is every formula of the arrangement recalculated; edit is one input changed in the middle row and Excel recalculating what depends on it. Milliseconds per recalculation:

| Arrangement, 1,000 rows | Formulas | Echo, full | Echo, one edit | RowSums, full | RowSums, one edit |
|---|---:|---:|---:|---:|---:|
| one formula per row | 1,000 | 6.06 (5.93..6.18) | 0.89 (0.88..0.91) | 24.58 (23.65..24.96) | 0.96 (0.93..0.97) |
| ten arrays of 100 | 10 | 0.96 (0.88..1.30) | 1.88 (1.09..2.32) | 1.23 (1.21..1.34) | 1.36 (1.03..1.38) |
| one array of 1,000 | 1 | 0.57 (0.57..0.60) | 1.12 (1.04..1.30) | 0.94 (0.91..0.98) | 1.46 (1.44..1.49) |
| the edit's floor: the same write, nothing dependent | 0 | | 0.59 (0.57..0.61) | | |

| Arrangement, 10,000 rows | Formulas | Echo, full | Echo, one edit | RowSums, full | RowSums, one edit |
|---|---:|---:|---:|---:|---:|
| one formula per row | 10,000 | 54.25 (52.25..56.71) | 0.88 (0.88..1.06) | 226.91 (225.45..232.36) | 1.17 (1.00..1.72) |
| ten arrays of 1,000 | 10 | 2.26 (2.13..2.31) | 1.50 (1.04..1.65) | 5.91 (5.59..6.82) | 1.92 (1.53..2.03) |
| one array of 10,000 | 1 | 2.08 (2.05..2.69) | 2.54 (2.23..3.11) | 7.93 (7.35..11.02) | 8.85 (8.12..9.60) |
| the edit's floor: the same write, nothing dependent | 0 | | 0.60 (0.57..0.62) | | |

Three facts stand out, the same three as at the first baseline.

- **Arrays win a full recalculation by a wide margin.** At 1,000 rows, ten arrays or one array deliver the same answers in 0.6 to 1.2 ms against 6 ms for the echo and 25 ms for RowSums row by row. At 10,000 rows the margin is 54 ms against 2.1 to 2.3, and 227 ms against 6 to 8. Each of these rows carries one recalculation's own cost over COM, about 0.4 ms before any formula runs, so the arrays' own work is smaller still and the margins are lower bounds.
- **A one-row formula that takes a range is the worst shape there is.** `=RowSums(Ai:Ji)` filled down costs 25 µs per row, nearly four times `=Add(Ai, Bi)`. The range is what costs, not the one-cell array it returns: a range in and a number out, `SumArray` over a hundred cells, costs 25 µs too. Each such row pays for a range in and an array out, which the counters pin at two trips, three Python values built to carry the call, one buffer and one copy; what that costs inside Excel was not measured alone.
- **An edit costs about a millisecond or two whatever the arrangement, at 1,000 rows.** The six edit rows run from 0.9 to 1.9 ms. The floor, one cell written and Excel asked to recalculate with nothing depending on it, is 0.59 ms. One formula per row adds 0.3 to 0.4 ms to that; an array of 100 or 1,000 adds 0.5 to 1.3 ms. At 10,000 rows a whole-column array's edit grows to 2.5 ms for the echo and 8.9 ms for RowSums, against 0.9 and 1.2 per row, because one changed cell recalculates the whole array.

## What the tests pin

The counts are tests, so a seam change states what it moved. A name lookup is the host asking Python for something by its text name, as `INDIRECT` finds a cell by its address; the path is prepared at registration, when the add-in loads and tells Excel its functions, so a call makes none, and the tests check that the counter never appears. Objects built are the Python values the host makes to carry the call. An array out counts one buffer, the array Excel receives, filled by one copy. As of this revision:

| The host did, for | trips | name lookups | objects built | cells scanned | buffers, bytes | result copies, cells |
|---|---:|---:|---:|---:|---:|---:|
| a scalar call, `Add(1, 2)` | 1 | 0 | 2 | | | |
| an omitted argument, `Times(5)` | 1 | 0 | 1 | | | |
| a warm range in, N cells | 2 | 0 | 3 | N | | |
| the first range larger than any before, N cells | 2 | 0 | 5 | N | 2, 9N | |
| an Excel error at cell 5 of 10,000 | 0 | 0 | 0 | 5 | | |
| an array out, N cells, `Grid` | 1 | 0 | 2 | | 1, 8N | 1, N |
| one answer per row, 100 in and 10 out | 2 | 0 | 3 | 100 | 1, 80 | 1, 10 |

One text cell in a range adds one to `text_cells` and one object, the text. A shape rejection pays the whole range budget.

Memory the host's own runtime hands out per call and later reclaims, which measuring.md calls managed allocation, is metered on the host's thread and pinned three ways. A warm scalar call allocates under 384 bytes; this session's runner saw 312. A warm range in adds nothing per cell between a thousand and ten thousand cells and stays under 640 bytes at ten thousand; the runner saw 496 at one, a hundred, a thousand and ten thousand cells, 497 at a hundred thousand, and 264 for the way in alone at every size. An array out adds 8 bytes per added cell between a thousand and ten thousand, within a small allowance; what it allocates besides is not pinned, and the runner saw 80,642 per `Grid` of ten thousand and 80,824 per `EchoColumn` of ten thousand, 642 and 824 above eight per cell.

On the Python side, `call_profile`, the list of the seam's own functions that ran, pins each probe exactly: a range of numbers is accepted on the host's summary with no look at its kinds, a bad cell deep inside is named with one look and no walk, a failing body costs no look. The numpy ledger, the list of what the seam asked numpy (the number library under the seam) to do, pins four things. Owning a range is two views of the host's buffers where they lie and two copies, with no look. A sum is one reduction, the folding of an array to one number as `SUM` does, and no look. Two ranges in are no look at all. A column out looks once, for finite numbers (neither infinite nor undefined), and copies nothing of its own.

The peaks from `tracemalloc`, Python's meter of how much memory a call holds at its highest point, are pinned as ceilings, each with a slack of 1,024 bytes for the small objects a call makes besides its per-cell work. A scalar call stays within the slack; this session measured 160 to 240. A range of numbers in stays within the slack at ten thousand cells, because nothing is made per cell; the runner saw 192 at one cell and at ten thousand alike. A rejected range stays under 2 bytes per cell plus slack: one mask, a yes-or-no answer per cell, over the kinds, and a second while the bad cell's text is found; measured 20,640 at ten thousand cells with the text last, 12,912 with it first, 13,008 for a blank in the middle. A column out stays under 1 byte per cell plus slack, its mask of which cells are finite; measured 10,385. An array out stays under 9 per cell plus slack; measured 90,385. Owning a range stays under 9 per cell plus slack, its two copies; measured 90,752.

## What moved since 024486f

Five seam changes landed between the two baselines: the call path prepared once at registration (#37), the host's summary of which kinds a range holds (#38), the kinds compared as plain integers (#39), one pass over the range into buffers the host keeps (#40), and one copy out into the array Excel receives (#41). `docs/baseline/since-024486f.md` pairs every row of the first baseline's session with this one, 139 rows across the three clocks, the Excel clock twice, at 1,000 and at 10,000 rows; 91 moved down far enough that the two sessions' batch spreads do not overlap, and none moved up. The two are separate sessions of the same day, hours apart, not one session's before and after. On the Python and host rows and on Excel's full recalculations at a thousand rows and up, a few percent either way is the noise between them; Excel's edit rows and its hundred-row rows differ between the sessions by up to 40% with overlapping spreads, and nothing is read from them here. The rows below are the ones large enough to read through the noise. Microseconds per call unless marked.

| Row | 024486f | aaa5259 | Change |
|---|---:|---:|---:|
| Excel, `Add` per formula, 1,000 rows | 7.19 | 6.45 | −10% |
| Excel, `Add` per formula, 10,000 rows | 6.76 | 5.73 | −15% |
| Excel, `HostAdd` per formula, 1,000 rows | 2.46 | 2.40 | not moved |
| Excel, `SumArray` over 100 cells | 46.4 | 25.2 | −46% |
| Excel, `SumArray` over 10,000 cells | 450.1 | 325.8 | −28% |
| Excel, `SUM` over 10,000 cells | 55.2 | 54.9 | not moved |
| Excel, `Grid` of 10,000 cells | 1,122.0 | 1,066.1 | not moved |
| Excel, `=RowSums(Ai:Ji)` down 1,000 rows, full, ms | 40.43 | 24.58 | −39% |
| Excel, `=Times(Ai)` down 1,000 rows, full, ms | 7.28 | 6.06 | −17% |
| Excel, one `=EchoColumn` array of 1,000, full, ms | 1.03 | 0.57 | −44% |
| Host, `Add` | 3.55 | 2.66 | −25% |
| Host, `SumArray` over 10,000 cells | 180.3 | 44.7 | −75% |
| Host, the way in alone, 10,000 cells | 158.0 | 37.7 | −76% |
| Host, `Dot` over two ranges of 10,000 | 350.5 | 85.2 | −76% |
| Host, `EchoColumn` of 10,000 | 199.6 | 60.6 | −70% |
| Host, `RowSums` over 10,000 cells | 119.0 | 61.3 | −48% |
| Host, `Grid` of 10,000 cells | 33.5 | 19.9 | −41% |
| Host, the way out alone, 1,000 cells | 1.86 | 1.26 | −32% |
| Host, the way out alone, 10,000 cells | 8.68 | 9.30 | not moved, spread 5.6..14.7 |
| Host, text in the last of 10,000 cells | 195.8 | 55.7 | −72% |
| Host, an Excel error in the last of 10,000 cells | 132.8 | 29.5 | −78% |
| Python, `SumArray` over 10,000 cells | 15.1 | 4.2 | −72% |
| Python, `Dot` over two ranges of 10,000 | 25.9 | 4.8 | −81% |
| Python, `EchoColumn` of 10,000 | 15.9 | 5.2 | −68% |
| Python, owning a range of 10,000 cells | 16.9 | 5.6 | −67% |
| Python, `Grid` of 10,000 cells | 10.8 | 10.8 | not moved |

What did not move is as telling as what did. Excel's own floors, `HostAdd`, `+` and `SUM`, sit where they were, so the sessions are comparable. `Grid` did not move in Python because nothing in the five changes touched the Python side of an array out: its numpy ledger and its peak are the same at both revisions. In Excel, the host's 14 µs saving on `Grid` at ten thousand cells sits inside a row of 1,066 whose batches run 1,024 to 1,146, so it cannot be read there; what Excel spends on the spill was not measured alone. The way out alone moved at a thousand cells and not at ten thousand, where its batches spread for a reason the CSV does not record.

Where a counter belongs to one change, it names it. Name lookups went from 1 to 0 on a scalar call and from 2 to 0 on a range in with the prepared path (#37), which also took a scalar call's objects from 4 to 2. Result copies went from 2 to 1, and an array out's bytes from 16 per cell to 8, with the one copy out (#41). Objects built for a range in moved three times: from 7 to 5 with the prepared path (#37), 5 to 6 with the kinds seen (#38), and 6 to 3 with the kept buffers (#40). Buffers moved twice: a range in's two of 9 bytes per cell on every call to none on a warm call (#40), and an array out's two to one (#41). The Python side's peak for a range of numbers in went from 77,008 bytes at ten thousand cells to 192 with the host's summary (#38), which spared the look at the kinds. A rejected range's peak went from 87,247 to 20,640 with the plain-integer compare (#39), which spared the 8-byte scratch copy that compare had made. The host's managed allocation for a range in went from 90,890 bytes at ten thousand cells to 496, and for a scalar call from 440 to 312.

## What this says about the library's formulas

Everything above is about one decision: whether a pricing function is called once per trade, once per array of trades, or once per sheet. The first baseline's answer stands, and the margins have widened where the seam got cheaper. The numbers say:

- **Declare pricing functions over arrays.** In Excel, ten arrays of a hundred rows deliver a thousand answers in 0.96 ms (echo) and 1.23 ms (RowSums) per recalculation, against 6.06 ms for the same rows as `=Times(Ai)` and 24.58 ms as `=RowSums(Ai:Ji)`. So at a thousand rows an array formula is six to eleven times cheaper than the same rows as scalar calls, and twenty to twenty-six times cheaper than the same rows as one-row range formulas. Below a hundred rows nothing was measured in Excel. The host runner, which does measure a one-cell array, prices `EchoColumn` at one cell at 11.3 µs, four of its scalar calls, and at a hundred cells at 12.2, four and a half. But at a hundred rows, the one size both clocks measured, Excel prices one `EchoColumn` array at 96 µs per formula (its ten-array row, per formula, which also carries the recalculation's own cost spread over ten formulas) against 6.06 per `=Times(Ai)`, sixteen scalar calls, so the host's curve does not stand in for Excel's. The size from which an array beats one call per row lies somewhere below a hundred rows and was not measured. A function that takes a column of trades and returns a column of prices is the default shape.
- **A per-row formula takes single values, not a range.** The one shape to forbid is a range read per row: 25 µs per row against 6.4 for `=Add(Ai, Bi)`, whatever the formula returns.
- **Arrays of a hundred to a thousand rows keep both bills small.** Ten arrays cost 1.0 to 1.2 ms for a thousand rows and 2.3 to 5.9 ms for ten thousand on a full recalculation, and 1.4 to 1.9 ms on an edit. One array over ten thousand rows costs 2.1 ms for the echo and 7.9 for RowSums on a full recalculation, and about the same on every edit, 2.5 and 8.9 ms, because one changed cell recalculates the whole array.
- **What a scalar call still costs is worth holding down.** Sheets will have per-trade formulas whatever the default. A user pays 6.4 µs per scalar call, a C# function with no Python pays 2 to 2.4, and without Excel the host runner times the seam's call at 2.7. The counters name what is left: one trip, no lookup, two objects, no buffer.

For the seam itself, the curves say where the work is now. Per cell, side by side: Excel charges about 30 nanoseconds through `SumArray` and 5 through `SUM`; the host runner charges 3.7, nearly all of it the way in; a cell out is 105 in Excel and 1.2 in the host runner. What lies between the two clocks, Excel-DNA's handing of the range to the host and Excel's own handling of a function's range argument and of the spill, no clock measured alone. What remains on the host's clock is per call. A range in at one cell costs the host runner 7.6 µs against 2.7 for a scalar call, and the host's own stage row puts 4.3 of the 7.6 in the way in alone: the scan, the three objects built to carry the range, and the trip that owns it. On its own clock the Python runner prices owning a one-cell range at 3.1. The seam changes that follow, if any, are judged against these rows and against the counters above. The counters now stand at the floor the design allows: one trip per call plus one per range, nothing looked up, nothing allocated for a warm range in, and one copy out.
