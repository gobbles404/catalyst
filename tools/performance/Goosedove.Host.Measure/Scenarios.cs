using System;
using System.Collections.Generic;
using ExcelDna.Integration;
using Python.Runtime;

namespace Goosedove.Host.Measure
{
    /// <summary>Every timed case through the host, its inputs built before any clock starts.</summary>
    internal static class Scenarios
    {
        private static readonly int[] Sizes = { 1, 100, 1_000, 10_000, 100_000 };  // 100 works; 100,000 controls

        internal static void Run(Measurements measurements)
        {
            var zero = (Func<object>)Registration.MakeDelegate(Bridge.Prepare("Zero"), 0);
            var add = (Func<object, object, object>)Registration.MakeDelegate(Bridge.Prepare("Add"), 2);
            var times = (Func<object, object, object>)Registration.MakeDelegate(Bridge.Prepare("Times"), 2);
            var dot = (Func<object, object, object>)Registration.MakeDelegate(Bridge.Prepare("Dot"), 2);
            var sum = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("SumArray"), 1);
            var countArray = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("CountArray"), 1);
            var countMixed = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("CountMixed"), 1);
            var sumQuantity = (Func<object, object, object>)Registration.MakeDelegate(Bridge.Prepare("SumQuantity"), 2);
            var echoColumn = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("EchoColumn"), 1);
            var echoRow = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("EchoRow"), 1);
            var rowSums = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("RowSums"), 1);
            var grid = (Func<object, object, object>)Registration.MakeDelegate(Bridge.Prepare("Grid"), 2);
            var gridPath = Bridge.Prepare("Grid");
            var echoMixed = (Func<object, object>)Registration.MakeDelegate(Bridge.Prepare("EchoMixed"), 1);
            var echoMixedPath = Bridge.Prepare("EchoMixed");
            object one = 1.0, two = 2.0, five = 5.0, missing = ExcelMissing.Value;

            measurements.Run("Zero", "scalar", 0, 1, () => zero(), Equal(0.0), Counted("Zero"));
            measurements.Run("Add", "scalar", 2, 1, () => add(one, two), Equal(3.0), Counted("Add", one, two));
            measurements.Run("Times", "missing", 1, 1, () => times(five, missing), Equal(5.0), Counted("Times", five, missing));

            foreach (var n in Sizes)
            {
                var column = Column(n);
                var weights = Filled(n, 1.0);
                var total = Total(n);
                measurements.Run("SumArray", "cells in", n, 1, () => sum(column), Equal(total), Counted("SumArray", column));
                // The same count three ways. The first two differ only in the rule, over the very
                // same cells, so what lies between them is the mixed rule alone. The third sends
                // text as well, which the host must collect, join and hand over and Python must
                // split, so what lies between it and the second is the text, not the rule.
                var mixed = Mixed(n);
                measurements.Run("CountArray", "cells in", n, 1, () => countArray(column), Equal((double)n), Counted("CountArray", column));
                measurements.Run("CountMixed", "mixed: no text", n, 1, () => countMixed(column), Equal((double)n), Counted("CountMixed", column));
                measurements.Run("CountMixed", "cells in", n, 1, () => countMixed(mixed), Equal((double)n), Counted("CountMixed", mixed));
                measurements.Run("Dot", "two ranges in", 2 * n, 1, () => dot(column, weights), Equal(total), Counted("Dot", column, weights));
                measurements.Run("EchoColumn", "round trip", n, n, () => echoColumn(column), ArrayOf(n, 1, total), Counted("EchoColumn", column));
                // The mixed road out, twice: over the numbers alone, so what lies between this row
                // and EchoColumn's is the road, a box per cell instead of one copy; and over the
                // mixed column, so what lies between the two is the text, a string per text cell.
                measurements.Run("EchoMixed", "round trip, numbers", n, n, () => echoMixed(column), MixedOf(n), Counted("EchoMixed", column));
                measurements.Run("EchoMixed", "round trip, mixed", n, n, () => echoMixed(mixed), MixedOf(n), Counted("EchoMixed", mixed));
                object rows = (double)n;
                var counted = (double)n * (n + 1) / 2;  // 1 + 2 + ... + n, in doubles before it overflows an int
                measurements.Run("Grid", "cells out", 2, n, () => grid(rows, one), ArrayOf(n, 1, counted), Counted("Grid", rows, one));
                if (n >= 10)
                {
                    var wide = Grid(n / 10, 10);
                    measurements.Run("RowSums", "one answer per row", n, n / 10, () => rowSums(wide), ArrayOf(n / 10, 1, total), Counted("RowSums", wide));
                }

                // The way in alone: scan into the kept buffers, hand over, own. The GIL is held outside the clock.
                // The stage rows are named for the stage, not the method, so a rename never splits
                // their history.
                using (Py.GIL())
                {
                    measurements.Run("way in", "alone", n, 0,
                        () => { object error; Marshal.Release(Marshal.ToPython(column, out error)); return error; },
                        Equal(null),
                        () => { var work = new WorkCounter(); object error; Marshal.Release(Marshal.ToPython(column, out error, work)); return work.Freeze(); });

                    // The way out alone: an array Python already holds, read into double[,].
                    using (var pyRows = new PyInt(n))
                    using (var pyCols = new PyInt(1))
                    {
                        using (var array = gridPath.Entry.Invoke(pyRows, pyCols))
                        {
                            measurements.Run("way out", "alone", 0, n,
                                () => Marshal.FromPython(array, "Grid"),
                                ArrayOf(n, 1, counted),
                                () => { var work = new WorkCounter(); Marshal.FromPython(array, "Grid", work); return work.Freeze(); });
                        }
                    }

                    // The way out alone on the mixed road: the tuple Python already holds for the mixed
                    // column, laid out cell by cell into the array Excel receives.
                    object mixedError;
                    var pyMixed = Marshal.ToPython(mixed, out mixedError);
                    try
                    {
                        using (var record = echoMixedPath.Entry.Invoke(pyMixed))
                        {
                            measurements.Run("way out", "mixed", 0, n,
                                () => Marshal.FromPython(record, "EchoMixed"),
                                MixedOf(n),
                                () => { var work = new WorkCounter(); Marshal.FromPython(record, "EchoMixed", work); return work.Freeze(); });
                        }
                    }
                    finally
                    {
                        Marshal.Release(pyMixed);
                    }
                }
            }

            const int size = 10_000;
            var shape = Column(size);
            measurements.Run("EchoRow", "rejected: shape", size, 0, () => echoRow(shape),
                Equal("#ERROR EchoRow: values is 10000x1 array, expected row of numbers"), Counted("EchoRow", shape));
            var textFirst = Column(size);
            textFirst[0, 0] = "x";
            measurements.Run("SumArray", "rejected: text first", size, 0, () => sum(textFirst),
                Equal("#ERROR SumArray: values cell (1, 1) is text 'x', expected number"), Counted("SumArray", textFirst));
            var textLast = Column(size);
            textLast[size - 1, 0] = "x";
            measurements.Run("SumArray", "rejected: text last", size, 0, () => sum(textLast),
                Equal("#ERROR SumArray: values cell (10000, 1) is text 'x', expected number"), Counted("SumArray", textLast));
            var blankDeep = Column(size);
            blankDeep[5_000, 0] = ExcelEmpty.Value;
            measurements.Run("SumArray", "rejected: blank deep", size, 0, () => sum(blankDeep),
                Equal("#ERROR SumArray: values cell (5001, 1) is blank, expected number"), Counted("SumArray", blankDeep));
            var errorFirst = Column(size);
            errorFirst[0, 0] = ExcelError.ExcelErrorNA;
            measurements.Run("SumArray", "excel error first", size, 0, () => sum(errorFirst),
                Equal(ExcelError.ExcelErrorNA), Counted("SumArray", errorFirst));
            var errorLast = Column(size);
            errorLast[size - 1, 0] = ExcelError.ExcelErrorNA;
            measurements.Run("SumArray", "excel error last", size, 0, () => sum(errorLast),
                Equal(ExcelError.ExcelErrorNA), Counted("SumArray", errorLast));

            // A table in: the header row and a body of four columns, one of each column type, with
            // as many rows as make n cells. The host carries two ranges as it always has; the
            // binding and the refining are the bridge's, and these rows time them. They run after
            // every other row, so the rows above meet the heap they met before the table existed:
            // what a scenario allocates changes where the next scenario's input lies in memory, and
            // that moved the ten-thousand-cell rows by a few percent when the table ran among them.
            foreach (var n in Sizes)
            {
                var tableRows = Math.Max(1, n / 4);
                var headers = Headers();
                var trades = Trades(tableRows);
                measurements.Run("SumQuantity", "cells in", 4 * tableRows, 1, () => sumQuantity(headers, trades), Equal(Total(tableRows)), Counted("SumQuantity", headers, trades));
            }
        }

        private static Func<IReadOnlyDictionary<string, long>> Counted(string name, params object[] args)
        {
            var prepared = Bridge.Prepare(name);
            return () =>
            {
                var work = new WorkCounter();
                Bridge.Call(work, prepared, args);
                return work.Freeze();
            };
        }

        private static object[,] Column(int cells)
        {
            var column = new object[cells, 1];
            for (var i = 0; i < cells; i++)
            {
                column[i, 0] = (double)i;
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

        private static object[,] Filled(int cells, double value)
        {
            var column = new object[cells, 1];
            for (var i = 0; i < cells; i++)
            {
                column[i, 0] = value;
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
                    grid[r, c] = (double)(r * cols + c);
                }
            }
            return grid;
        }

        private static double Total(int n)
        {
            return (double)n * (n - 1) / 2;
        }

        private static Action<object> Equal(object expected)
        {
            return actual =>
            {
                if (!Equals(expected, actual))
                {
                    throw new InvalidOperationException("got " + (actual ?? "null") + ", expected " + (expected ?? "null"));
                }
            };
        }

        private static Action<object> MixedOf(int rows)
        {
            return actual =>
            {
                if (!(actual is object[,] array) || array.GetLength(0) != rows || array.GetLength(1) != 1)
                {
                    throw new InvalidOperationException("got " + (actual ?? "null") + ", expected a " + rows + "x1 mixed array");
                }
            };
        }

        private static Action<object> ArrayOf(int rows, int cols, double total)
        {
            return actual =>
            {
                if (!(actual is double[,] array) || array.GetLength(0) != rows || array.GetLength(1) != cols)
                {
                    throw new InvalidOperationException("got " + (actual ?? "null") + ", expected a " + rows + "x" + cols + " array");
                }
                var sum = 0.0;
                foreach (var value in array)
                {
                    sum += value;
                }
                if (sum != total)
                {
                    throw new InvalidOperationException("array sums to " + sum + ", expected " + total);
                }
            };
        }
    }
}
