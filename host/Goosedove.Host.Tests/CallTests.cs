using System.Collections.Generic;
using ExcelDna.Integration;
using Xunit;

namespace Goosedove.Host.Tests
{
    /// <summary>Whole calls through the host: the cell text or value Excel would show.</summary>
    [Collection("python")]
    public class CallTests
    {
        private static object[,] Column(params object[] cells)
        {
            var grid = new object[cells.Length, 1];
            for (var i = 0; i < cells.Length; i++)
            {
                grid[i, 0] = cells[i];
            }
            return grid;
        }

        // The rows of tools\excel_smoke.ps1, without Excel.
        public static IEnumerable<object[]> SmokeRows()
        {
            yield return new object[] { "Add", new object[] { 1.0, 2.0 }, 3.0 };
            yield return new object[] { "Add", new object[] { 1.0, ExcelMissing.Value }, "#ERROR Add: b is missing, expected number" };
            yield return new object[] { "Add", new object[] { 1.0, true }, "#ERROR Add: b is boolean TRUE, expected number" };
            yield return new object[] { "SumColumn", new object[] { Column(1.0, 2.0, 3.0) }, 6.0 };
            yield return new object[] { "SumColumn", new object[] { 1.0 }, 1.0 };
            yield return new object[] { "SumColumn", new object[] { Column("n/a", 2.0, 3.0) }, "#ERROR SumColumn: values cell (1, 1) is text 'n/a', expected number" };
            yield return new object[] { "SumColumn", new object[] { Column(1.0, ExcelEmpty.Value, 3.0) }, "#ERROR SumColumn: values cell (2, 1) is blank, expected number" };
            yield return new object[] { "SumColumn", new object[] { Column(1.0, ExcelError.ExcelErrorNA, 3.0) }, ExcelError.ExcelErrorNA };
            yield return new object[] { "SumColumn", new object[] { Column("x", ExcelError.ExcelErrorNA) }, ExcelError.ExcelErrorNA };
            yield return new object[] { "SumColumn", new object[] { Column(1.0, true) }, "#ERROR SumColumn: values cell (2, 1) is boolean TRUE, expected number" };
            yield return new object[] { "SumRow", new object[] { Column(1.0, 2.0, 3.0) }, "#ERROR SumRow: values is 3x1 array, expected row of numbers" };
            yield return new object[] { "JoinColumn", new object[] { Column("x", "y") }, "x, y" };
            yield return new object[] { "JoinColumn", new object[] { Column("x", "") }, "#ERROR JoinColumn: names cell (2, 1) is empty text, expected text" };
            yield return new object[] { "DateText", new object[] { 46164.0 }, "2026-05-22" };
        }

        [Theory]
        [MemberData(nameof(SmokeRows))]
        public void the_smoke_rows_hold(string name, object[] args, object shown)
        {
            Assert.Equal(shown, Bridge.Call(name, args));
        }

        [Fact]
        public void ping_says_which_goosedove_is_running()
        {
            Assert.Contains("goosedove", (string)Bridge.Call("Ping"));
        }

        [Fact]
        public void a_grid_result_becomes_cells_with_na_for_nan()
        {
            var block = (object[,])Bridge.Call("TestGrid", 2.0);
            Assert.Equal(2, block.GetLength(0));
            Assert.Equal(2, block.GetLength(1));
            Assert.Equal(ExcelError.ExcelErrorNA, block[0, 0]);
            Assert.Equal(1.0, block[0, 1]);
            Assert.Equal(3.0, block[1, 1]);
        }

        [Fact]
        public void a_nothing_result_is_an_empty_cell()
        {
            Assert.Null(Bridge.Call("TestNothing"));
        }

        // Today's truth, not the intent: a one-column result has no way back to the sheet yet.
        // The way-out change replaces this test.
        [Fact]
        public void a_one_column_result_fails_in_the_host_today()
        {
            var shown = Assert.IsType<string>(Bridge.Call("TestVector", 3.0));
            Assert.StartsWith("#ERROR host:", shown);
        }
    }
}
