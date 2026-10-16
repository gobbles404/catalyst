using System;
using System.Collections.Generic;
using System.Linq;
using ExcelDna.Integration;
using Xunit;
using Xunit.Abstractions;

namespace Goosedove.Host.Tests
{
    /// <summary>
    /// What the host does for one call, counted at its boundaries: trips into Python, objects
    /// built, cells scanned, buffers allocated, copies made, and look-ups by name, of which a
    /// prepared call makes none, so their absence from every dict is asserted too. The worksheet
    /// path passes no counter; these tests supply one. Every dict is today's truth, pinned so a
    /// seam change states what it moved.
    /// </summary>
    [Collection("python")]
    public class HostWorkBudgets
    {
        private readonly ITestOutputHelper output;

        public HostWorkBudgets(ITestOutputHelper output)
        {
            this.output = output;
        }

        private static object[,] Column(int cells)
        {
            var column = new object[cells, 1];
            for (var i = 0; i < cells; i++)
            {
                column[i, 0] = 1.0;
            }
            return column;
        }

        // A column holding all three kinds a mixed range may, in turn: text, a number, a boolean.
        private static object[,] Mixed(int cells)
        {
            var column = new object[cells, 1];
            for (var i = 0; i < cells; i++)
            {
                column[i, 0] = (i % 3) switch { 0 => "n" + i, 1 => (object)(double)i, _ => i % 2 == 0 };
            }
            return column;
        }

        // Every third cell of Mixed holds text, counting from the first.
        private static int MixedTexts(int cells) => (cells + 2) / 3;

        // The table probe's header row, and a body with a date, a text, a number and a boolean per
        // row: one column of each type a table may declare. The quantity column sums to Total(rows).
        private static object[,] Headers()
        {
            return new object[,] { { "date", "product", "quantity", "cleared" } };
        }

        private static object[,] Trades(int rows)
        {
            var trades = new object[rows, 4];
            for (var i = 0; i < rows; i++)
            {
                trades[i, 0] = 46276.0 + i;
                trades[i, 1] = "p" + i;
                trades[i, 2] = (double)i;
                trades[i, 3] = i % 2 == 0;
            }
            return trades;
        }

        private static double Total(int rows) => (double)rows * (rows - 1) / 2;

        private static object[,] Grid(int rows, int cols)
        {
            var grid = new object[rows, cols];
            for (var r = 0; r < rows; r++)
            {
                for (var c = 0; c < cols; c++)
                {
                    grid[r, c] = 1.0;
                }
            }
            return grid;
        }

        /// <summary>One warm call, counted. The first call of a name is not the one measured.</summary>
        private IReadOnlyDictionary<string, long> Counted(object expected, string name, params object[] args)
        {
            var prepared = Bridge.Prepare(name);
            Bridge.Call(prepared, args);
            var work = new WorkCounter();
            Assert.Equal(expected, Bridge.Call(work, prepared, args));
            var counts = work.Freeze();
            output.WriteLine(name + ": " + string.Join(", ", counts.OrderBy(pair => pair.Key).Select(pair => pair.Key + "=" + pair.Value)));
            return counts;
        }

        private static void Same(Dictionary<string, long> expected, IReadOnlyDictionary<string, long> counts)
        {
            Assert.Equal(expected.OrderBy(pair => pair.Key).ToArray(), counts.OrderBy(pair => pair.Key).ToArray());
        }

        // A warm range in: the buffers are kept from earlier calls, so nothing is allocated and
        // only the shape and the kinds seen are built to carry it.
        private static Dictionary<string, long> RangeIn(int cells)
        {
            return new Dictionary<string, long>
            {
                ["objects_built"] = 3,      // rows, cols, the kinds seen
                ["trips"] = 2,              // cells_from_buffers, then the call
                ["cells_scanned"] = cells,
            };
        }

        // The path is prepared at registration, so a call looks nothing up by name and builds only
        // what carries its own arguments.
        [Fact]
        public void a_scalar_call_is_one_trip_and_two_objects()
        {
            Same(new Dictionary<string, long>
            {
                ["objects_built"] = 2,  // two numbers
                ["trips"] = 1,
            }, Counted(3.0, "Add", 1.0, 2.0));
        }

        [Fact]
        public void an_omitted_argument_is_carried_by_the_missing_held_since_start()
        {
            Same(new Dictionary<string, long>
            {
                ["objects_built"] = 1,  // the number; MISSING is neither built nor looked up
                ["trips"] = 1,
            }, Counted(5.0, "Times", 5.0, ExcelMissing.Value));
        }

        [Theory]
        [InlineData(1)]
        [InlineData(100)]
        [InlineData(10000)]
        public void a_warm_range_in_is_one_scan_three_objects_and_two_trips(int cells)
        {
            Same(RangeIn(cells), Counted((double)cells, "SumArray", Column(cells)));
        }

        [Fact]
        public void one_text_cell_keeps_the_range_budget()
        {
            const int cells = 10000;
            var column = Column(cells);
            column[cells - 1, 0] = "x";
            var expected = RangeIn(cells);
            expected["text_cells"] = 1;
            expected["texts_checked"] = 1;  // the one text looked at for NUL, since #189
            expected["objects_built"] = 4;  // and the text
            Same(expected, Counted("#ERROR SumArray: values cell (10000, 1) is text 'x', expected number", "SumArray", column));
        }

        // A mixed range crosses the host exactly as a range of numbers does. The host tells the
        // kinds apart and nothing else; which combinations a declared type allows is the bridge's
        // rule, so the counts differ only by the text these cells happen to hold.
        [Theory]
        [InlineData(1)]
        [InlineData(100)]
        [InlineData(10000)]
        public void a_mixed_range_in_costs_what_a_range_of_numbers_costs(int cells)
        {
            Same(RangeIn(cells), Counted((double)cells, "CountArray", Column(cells)));
            var expected = RangeIn(cells);
            expected["text_cells"] = MixedTexts(cells);
            expected["texts_checked"] = MixedTexts(cells);  // each text once, since #189
            expected["objects_built"] = 4;  // and the text, joined once for the whole range
            Same(expected, Counted((double)cells, "CountMixed", Mixed(cells)));
        }

        // A table is two ranges in, the header row and the body, each scanned and handed over as
        // any range is. The binding and the refining are the bridge's, so the host counts nothing
        // new: two hand-overs and the call, three integers and the text for each range, and the
        // cells and text cells of both.
        [Theory]
        [InlineData(1)]
        [InlineData(25)]
        [InlineData(2500)]
        public void a_table_in_costs_two_ranges(int rows)
        {
            Same(new Dictionary<string, long>
            {
                ["trips"] = 3,
                ["objects_built"] = 8,
                ["cells_scanned"] = 4 + 4L * rows,
                ["text_cells"] = 4 + rows,
                ["texts_checked"] = 4 + rows,
            }, Counted(Total(rows), "SumQuantity", Headers(), Trades(rows)));
        }

        // The buffers are kept between calls and grown only when a larger range comes: the first
        // range of a new largest size pays two buffers and the two addresses, the next does not.
        [Fact]
        public void a_larger_range_than_any_before_grows_the_buffers_once()
        {
            const int cells = 30000;  // larger than any other range in this process
            var prepared = Bridge.Prepare("SumArray");
            var grown = new WorkCounter();
            Assert.Equal((double)cells, Bridge.Call(grown, prepared, Column(cells)));
            var expected = RangeIn(cells);
            expected["buffers_allocated"] = 2;
            expected["buffer_bytes"] = 9L * cells;
            expected["objects_built"] = 5;  // the two addresses, then rows, cols, the kinds seen
            Same(expected, grown.Freeze());
            var again = new WorkCounter();
            Assert.Equal((double)cells, Bridge.Call(again, prepared, Column(cells)));
            Same(RangeIn(cells), again.Freeze());
        }

        [Fact]
        public void a_shape_rejection_still_pays_the_transport()
        {
            const int cells = 10000;
            Same(RangeIn(cells), Counted("#ERROR EchoRow: values is 10000x1 array, expected row of numbers", "EchoRow", Column(cells)));
        }

        [Fact]
        public void an_excel_error_stops_the_scan_and_makes_no_trip()
        {
            var column = Column(10000);
            column[4, 0] = ExcelError.ExcelErrorNA;
            Same(new Dictionary<string, long>
            {
                ["cells_scanned"] = 5,       // nothing is built or allocated: the buffers are kept
            }, Counted(ExcelError.ExcelErrorNA, "SumArray", column));
        }

        // Since #189, reject-nul-input-text.md: a text holding NUL (U+0000) stops the scan as an
        // Excel error does, where the pass reaches it. The cells up to it are visited and each text
        // reached is looked at once, the refused one included; nothing is built, allocated or
        // carried across, no trip is made, and the kept buffers serve the next call as before.
        [Fact]
        public void a_nul_in_a_text_cell_stops_the_scan_before_the_trip()
        {
            var column = Column(10000);
            column[2, 0] = "n2";
            column[4, 0] = "n\u00004";
            Same(new Dictionary<string, long>
            {
                ["cells_scanned"] = 5,
                ["text_cells"] = 1,      // the text before it, collected
                ["texts_checked"] = 2,   // both texts reached, the refused one included
            }, Counted("#ERROR host: SumArray argument 1 cell (5, 1) is text holding NUL (U+0000), expected text without it", "SumArray", column));
            Same(RangeIn(10000), Counted(10000.0, "SumArray", Column(10000)));
        }

        // A scalar text is checked at the same boundary: one look, no object built and no trip.
        [Fact]
        public void a_nul_in_a_scalar_text_is_one_check_and_no_trip()
        {
            Same(new Dictionary<string, long>
            {
                ["texts_checked"] = 1,
            }, Counted("#ERROR host: _ShowInstrument argument 1 is text holding NUL (U+0000), expected text without it", "_ShowInstrument", "fixed\u0000float"));
        }

        // Counted() compares the result with Assert.Equal, which a fresh double[,] never satisfies;
        // arrays are checked by shape here.
        private IReadOnlyDictionary<string, long> CountedArray(string name, int rows, int cols, params object[] args)
        {
            var prepared = Bridge.Prepare(name);
            Bridge.Call(prepared, args);
            var work = new WorkCounter();
            var array = Assert.IsType<double[,]>(Bridge.Call(work, prepared, args));
            Assert.Equal(rows, array.GetLength(0));
            Assert.Equal(cols, array.GetLength(1));
            var counts = work.Freeze();
            output.WriteLine(name + ": " + string.Join(", ", counts.OrderBy(pair => pair.Key).Select(pair => pair.Key + "=" + pair.Value)));
            return counts;
        }

        [Fact]
        public void an_array_out_from_nothing_in_is_one_buffer_and_one_copy()
        {
            Same(new Dictionary<string, long>
            {
                ["objects_built"] = 2,       // two numbers
                ["trips"] = 1,
                ["buffers_allocated"] = 1,   // the double[,] Excel receives, and nothing between
                ["buffer_bytes"] = 80000,    // 8 bytes per cell, once
                ["result_copies"] = 1,
                ["result_cells"] = 10000,
            }, CountedArray("Grid", 100, 100, 100.0, 100.0));
        }

        [Fact]
        public void one_answer_per_row_pays_a_range_in_and_an_array_out()
        {
            var expected = RangeIn(100);
            expected["buffers_allocated"] = 1;  // the array out, only
            expected["buffer_bytes"] = 8L * 10;
            expected["result_copies"] = 1;
            expected["result_cells"] = 10;
            Same(expected, CountedArray("RowSums", 10, 1, Grid(10, 10)));
        }

        // The mixed road out is checked by its cells; a fresh object[,] never satisfies Assert.Equal.
        private IReadOnlyDictionary<string, long> CountedObjects(string name, int rows, int cols, params object[] args)
        {
            var prepared = Bridge.Prepare(name);
            Bridge.Call(prepared, args);
            var work = new WorkCounter();
            var array = Assert.IsType<object[,]>(Bridge.Call(work, prepared, args));
            Assert.Equal(rows, array.GetLength(0));
            Assert.Equal(cols, array.GetLength(1));
            var counts = work.Freeze();
            output.WriteLine(name + ": " + string.Join(", ", counts.OrderBy(pair => pair.Key).Select(pair => pair.Key + "=" + pair.Value)));
            return counts;
        }

        // Every third cell of Mixed holds a number, counting from the second.
        private static int MixedNumbers(int cells) => (cells + 1) / 3;

        // A mixed array out is one array of references, a box per number cell and a string per
        // text cell, and no copy: Excel takes an array one tagged value per cell, so there is no
        // block of mixed cells to copy in one move. The booleans share two boxes made once.
        [Theory]
        [InlineData(1)]
        [InlineData(100)]
        [InlineData(10000)]
        public void a_mixed_array_out_is_one_array_a_box_per_number_and_a_string_per_text(int cells)
        {
            var expected = RangeIn(cells);
            expected["text_cells"] = MixedTexts(cells);
            expected["texts_checked"] = MixedTexts(cells);
            expected["objects_built"] = 4;  // and the text, joined once for the whole range
            expected["buffers_allocated"] = 1;
            expected["buffer_bytes"] = 8L * cells;
            expected["result_cells"] = cells;
            expected["result_texts"] = MixedTexts(cells);
            if (MixedNumbers(cells) > 0)
            {
                expected["result_boxes"] = MixedNumbers(cells);
            }
            Same(expected, CountedObjects("EchoMixed", cells, 1, Mixed(cells)));
        }

        // --- managed allocation, the CLR heap only: not Python, not numpy, not Excel-DNA ---------

        private static double BytesPerCall(Func<object> call, int calls)
        {
            for (var i = 0; i < 256; i++)
            {
                call();
            }
            object last = null;
            var before = GC.GetAllocatedBytesForCurrentThread();
            for (var i = 0; i < calls; i++)
            {
                last = call();
            }
            var bytes = (GC.GetAllocatedBytesForCurrentThread() - before) / (double)calls;
            GC.KeepAlive(last);
            return bytes;
        }

        // Measured 312 bytes on 2026-09-11 in Release, down from 440 when the path was looked up
        // by name on every call: two Python floats, the result, the boxed double, the argument
        // arrays and the pythonnet wrappers. The name string and the argument list are gone.
        [Fact]
        public void a_registered_scalar_call_allocates_under_384_managed_bytes()
        {
            var add = (Func<object, object, object>)Registration.MakeDelegate(Bridge.Prepare("Add"), 2);
            object first = 1.0, second = 2.0;  // Excel hands over boxed numbers
            var bytes = BytesPerCall(() => add(first, second), 10000);
            output.WriteLine("managed bytes per warm Add: " + bytes);
            Assert.InRange(bytes, 0, 384);
        }

        // The buffers are kept, so a warm range in allocates nothing per cell; the two sizes are
        // warmed first, so the larger has grown the buffers before either is metered.
        [Fact]
        public void a_warm_range_in_allocates_nothing_per_cell()
        {
            var sum = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("SumArray"), 1);
            object small = Column(1000), large = Column(10000);
            sum(large);
            var slope = (BytesPerCall(() => sum(large), 20) - BytesPerCall(() => sum(small), 20)) / 9000;
            output.WriteLine("managed bytes per added input cell: " + slope);
            Assert.InRange(Math.Abs(slope), 0, 2048.0 / 9000);
        }

        // Measured 496 bytes on 2026-09-11 in Release at one, a hundred, a thousand and ten
        // thousand cells alike: the three carriers, the Cells wrapper, the result and its box,
        // the argument array and the pythonnet wrappers. Nothing of it grows with the range.
        [Fact]
        public void a_warm_range_in_allocates_under_640_managed_bytes_whatever_its_size()
        {
            var sum = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("SumArray"), 1);
            object large = Column(10000);
            var bytes = BytesPerCall(() => sum(large), 1000);
            output.WriteLine("managed bytes per warm SumArray of ten thousand cells: " + bytes);
            Assert.InRange(bytes, 0, 640);
        }

        [Fact]
        public void an_array_out_allocates_eight_bytes_per_cell_and_nothing_else()
        {
            var grid = (Func<object, object, object>)Registration.MakeDelegate(Bridge.Prepare("Grid"), 2);
            object one = 1.0, small = 1000.0, large = 10000.0;
            var slope = (BytesPerCall(() => grid(large, one), 20) - BytesPerCall(() => grid(small, one), 20)) / 9000;
            output.WriteLine("managed bytes per added output cell: " + slope);
            Assert.InRange(slope, 0, 8 + 2048.0 / 9000);
        }

        // The mixed road pays per cell what its cells are: the reference slot for every cell, a
        // 24-byte box for every third cell, a string for every third, and the split that made the
        // strings. Measured 53 bytes per added cell on 2026-09-15 in Release over the mixed
        // column, against 8 on the numbers road; the ceiling holds the slope, not the small
        // objects of a call.
        [Fact]
        public void a_mixed_array_out_allocates_per_cell_what_its_cells_are()
        {
            var echo = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("EchoMixed"), 1);
            object small = Mixed(1000), large = Mixed(10000);
            echo(large);
            var slope = (BytesPerCall(() => echo(large), 20) - BytesPerCall(() => echo(small), 20)) / 9000;
            output.WriteLine("managed bytes per added mixed cell out: " + slope);
            Assert.InRange(slope, 0, 64 + 2048.0 / 9000);
        }
    }
}
