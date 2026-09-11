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
            var zero = (Func<object>)Registration.MakeDelegate("Zero", 0);
            var add = (Func<object, object, object>)Registration.MakeDelegate("Add", 2);
            var times = (Func<object, object, object>)Registration.MakeDelegate("Times", 2);
            var dot = (Func<object, object, object>)Registration.MakeDelegate("Dot", 2);
            var sum = (Func<object, object>)Registration.MakeDelegate("SumArray", 1);
            var echoColumn = (Func<object, object>)Registration.MakeDelegate("EchoColumn", 1);
            var echoRow = (Func<object, object>)Registration.MakeDelegate("EchoRow", 1);
            var rowSums = (Func<object, object>)Registration.MakeDelegate("RowSums", 1);
            var grid = (Func<object, object, object>)Registration.MakeDelegate("Grid", 2);
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
                measurements.Run("Dot", "two ranges in", 2 * n, 1, () => dot(column, weights), Equal(total), Counted("Dot", column, weights));
                measurements.Run("EchoColumn", "round trip", n, n, () => echoColumn(column), Block(n, 1, total), Counted("EchoColumn", column));
                object rows = (double)n;
                var counted = (double)n * (n + 1) / 2;  // 1 + 2 + ... + n, in doubles before it overflows an int
                measurements.Run("Grid", "cells out", 2, n, () => grid(rows, one), Block(n, 1, counted), Counted("Grid", rows, one));
                if (n >= 10)
                {
                    var wide = Grid(n / 10, 10);
                    measurements.Run("RowSums", "one answer per row", n, n / 10, () => rowSums(wide), Block(n / 10, 1, total), Counted("RowSums", wide));
                }

                // The way in alone: scan, pin, hand over, own. The GIL is held outside the clock.
                using (Py.GIL())
                {
                    measurements.Run("Marshal.Append", "way in alone", n, 0,
                        () => { using (var args = new PyList()) { return Marshal.Append(args, column); } },
                        Equal(null),
                        () => { var work = new WorkCounter(); using (var args = new PyList()) { Marshal.Append(args, column, work); } return work.Freeze(); });

                    // The way out alone: a block Python already holds, read into double[,].
                    using (var name = new PyString("Grid"))
                    using (var args = new PyList())
                    using (var pyRows = new PyInt(n))
                    using (var pyCols = new PyInt(1))
                    {
                        args.Append(pyRows);
                        args.Append(pyCols);
                        using (var block = Bridge.Module.InvokeMethod("call", name, args))
                        {
                            measurements.Run("Marshal.FromPython", "way out alone", 0, n,
                                () => Marshal.FromPython(block, "Grid"),
                                Block(n, 1, counted),
                                () => { var work = new WorkCounter(); Marshal.FromPython(block, "Grid", work); return work.Freeze(); });
                        }
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
        }

        private static Func<IReadOnlyDictionary<string, long>> Counted(string name, params object[] args)
        {
            return () =>
            {
                var work = new WorkCounter();
                Bridge.Call(work, name, args);
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

        private static Action<object> Block(int rows, int cols, double total)
        {
            return actual =>
            {
                if (!(actual is double[,] block) || block.GetLength(0) != rows || block.GetLength(1) != cols)
                {
                    throw new InvalidOperationException("got " + (actual ?? "null") + ", expected a " + rows + "x" + cols + " block");
                }
                var sum = 0.0;
                foreach (var value in block)
                {
                    sum += value;
                }
                if (sum != total)
                {
                    throw new InvalidOperationException("block sums to " + sum + ", expected " + total);
                }
            };
        }
    }
}
