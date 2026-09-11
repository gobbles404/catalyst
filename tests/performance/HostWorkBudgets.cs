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

        private static Dictionary<string, long> RangeIn(int cells)
        {
            return new Dictionary<string, long>
            {
                ["objects_built"] = 6,      // the six values that carry a range, the kinds seen among them
                ["trips"] = 2,              // cells_from_buffers, then the call
                ["cells_scanned"] = cells,
                ["buffers_allocated"] = 2,  // kinds and numbers
                ["buffer_bytes"] = 9L * cells,
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
        public void a_range_in_is_one_scan_two_buffers_and_two_trips(int cells)
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
            Same(expected, Counted("#ERROR SumArray: values cell (10000, 1) is text 'x', expected number", "SumArray", column));
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
                ["cells_scanned"] = 5,       // nothing is built before the first argument is read
                ["buffers_allocated"] = 2,   // allocated before the scan, and wasted
                ["buffer_bytes"] = 90000,
            }, Counted(ExcelError.ExcelErrorNA, "SumArray", column));
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
        public void an_array_out_from_nothing_in_is_two_buffers_and_two_copies()
        {
            Same(new Dictionary<string, long>
            {
                ["objects_built"] = 2,       // two numbers
                ["trips"] = 1,
                ["buffers_allocated"] = 2,   // doubles[], then double[,]
                ["buffer_bytes"] = 160000,   // 8 bytes per cell, twice
                ["result_copies"] = 2,
                ["result_cells"] = 10000,
            }, CountedArray("Grid", 100, 100, 100.0, 100.0));
        }

        [Fact]
        public void one_answer_per_row_pays_a_range_in_and_an_array_out()
        {
            var expected = RangeIn(100);
            expected["buffers_allocated"] = 4;
            expected["buffer_bytes"] = 9L * 100 + 16L * 10;
            expected["result_copies"] = 2;
            expected["result_cells"] = 10;
            Same(expected, CountedArray("RowSums", 10, 1, Grid(10, 10)));
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

        [Fact]
        public void a_range_in_allocates_nine_bytes_per_cell_and_nothing_else()
        {
            var sum = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("SumArray"), 1);
            object small = Column(1000), large = Column(10000);
            var slope = (BytesPerCall(() => sum(large), 20) - BytesPerCall(() => sum(small), 20)) / 9000;
            output.WriteLine("managed bytes per added input cell: " + slope);
            Assert.InRange(slope, 0, 9 + 2048.0 / 9000);
        }

        [Fact]
        public void an_array_out_allocates_sixteen_bytes_per_cell_and_nothing_else()
        {
            var grid = (Func<object, object, object>)Registration.MakeDelegate(Bridge.Prepare("Grid"), 2);
            object one = 1.0, small = 1000.0, large = 10000.0;
            var slope = (BytesPerCall(() => grid(large, one), 20) - BytesPerCall(() => grid(small, one), 20)) / 9000;
            output.WriteLine("managed bytes per added output cell: " + slope);
            Assert.InRange(slope, 0, 16 + 2048.0 / 9000);
        }
    }
}
