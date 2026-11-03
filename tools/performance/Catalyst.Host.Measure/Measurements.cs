using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;

namespace Catalyst.Host.Measure
{
    /// <summary>Warm, calibrate, time in batches, check outside the clock, and remember every batch.</summary>
    internal sealed class Measurements
    {
        internal const double BatchMilliseconds = 50;
        internal const int Batches = 5;
        private const long MostIterations = 1_000_000;

        private readonly List<string[]> batches = new List<string[]>();
        private readonly List<string[]> work = new List<string[]>();

        internal void Run(string probe, string scenario, int cellsIn, int cellsOut,
            Func<object> operation, Action<object> check, Func<IReadOnlyDictionary<string, long>> counted)
        {
            check(operation());
            long iterations = 1;
            while (true)
            {
                var watch = Stopwatch.StartNew();
                for (long i = 0; i < iterations; i++)
                {
                    operation();
                }
                watch.Stop();
                if (watch.Elapsed.TotalMilliseconds >= BatchMilliseconds || iterations >= MostIterations)
                {
                    break;
                }
                iterations *= 2;
            }
            var means = new List<double>();
            for (var batch = 1; batch <= Batches; batch++)
            {
                int gc0 = GC.CollectionCount(0), gc1 = GC.CollectionCount(1), gc2 = GC.CollectionCount(2);
                var bytesBefore = GC.GetAllocatedBytesForCurrentThread();
                object last = null;
                var watch = Stopwatch.StartNew();
                for (long i = 0; i < iterations; i++)
                {
                    last = operation();
                }
                watch.Stop();
                var bytes = GC.GetAllocatedBytesForCurrentThread() - bytesBefore;
                check(last);
                var elapsed = watch.Elapsed.TotalMilliseconds;
                var perCall = elapsed * 1000 / iterations;
                means.Add(perCall);
                batches.Add(new[]
                {
                    "host", probe, scenario, "1", Text(cellsIn), Text(cellsOut), Text(batch), Text(iterations),
                    elapsed.ToString("F3", CultureInfo.InvariantCulture), perCall.ToString("F3", CultureInfo.InvariantCulture),
                    ((double)bytes / iterations).ToString("F1", CultureInfo.InvariantCulture),
                    Text(GC.CollectionCount(0) - gc0), Text(GC.CollectionCount(1) - gc1), Text(GC.CollectionCount(2) - gc2),
                });
            }
            if (counted != null)
            {
                foreach (var pair in counted().OrderBy(pair => pair.Key))
                {
                    work.Add(new[] { probe, scenario, Text(cellsIn), Text(cellsOut), pair.Key, Text(pair.Value) });
                }
            }
            means.Sort();
            Console.WriteLine(
                probe.PadRight(12) + " " + scenario.PadRight(22) + " " + Text(cellsIn).PadLeft(7) + " in " + Text(cellsOut).PadLeft(7) + " out" +
                "  median " + means[means.Count / 2].ToString("F3", CultureInfo.InvariantCulture).PadLeft(10) + " us" +
                "  (" + means[0].ToString("F3", CultureInfo.InvariantCulture) + ".." + means[means.Count - 1].ToString("F3", CultureInfo.InvariantCulture) + ")");
        }

        internal void Write(string directory)
        {
            using (var writer = new StreamWriter(Path.Combine(directory, "batches.csv")))
            {
                writer.WriteLine("layer,probe,scenario,calls,cells_in,cells_out,batch,iterations,elapsed_ms,per_call_us,managed_bytes_per_call,gc0,gc1,gc2");
                foreach (var row in batches)
                {
                    writer.WriteLine(Csv(row));
                }
            }
            using (var writer = new StreamWriter(Path.Combine(directory, "work.csv")))
            {
                writer.WriteLine("probe,scenario,cells_in,cells_out,counter,count");
                foreach (var row in work)
                {
                    writer.WriteLine(Csv(row));
                }
            }
        }

        // One row as the comma-separated line its readers expect. A field that holds a comma, a
        // quote or a line break goes in quotes, with a quote of its own doubled, as Python's csv
        // module and Export-Csv write the other two layers' files: a scenario named
        // "round trip, numbers" is one field in all three, and the readers join rows by it.
        private static readonly char[] NeedsQuotes = { ',', '"', '\r', '\n' };

        private static string Csv(string[] row)
        {
            return string.Join(",", row.Select(Field));
        }

        private static string Field(string value)
        {
            return value.IndexOfAny(NeedsQuotes) < 0 ? value : "\"" + value.Replace("\"", "\"\"") + "\"";
        }

        private static string Text(long value)
        {
            return value.ToString(CultureInfo.InvariantCulture);
        }
    }
}
