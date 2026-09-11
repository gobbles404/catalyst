// Warm timings through the host, one probe at a time, with Python started the way the
// add-in starts it and no Excel. Run:
//   dotnet run --project tools/performance/Goosedove.Host.Measure -c Release
// The clock includes the registered delegate: argument marshaling, the trip into Python,
// validation, the probe, result conversion, and the way back to a .NET value. It excludes
// Excel and Excel-DNA. Two stage scenarios time the way in and the way out alone, with the
// GIL held outside the clock. Each row of batches.csv is one batch of calibrated length;
// per_call_us is that batch's mean. Results are checked outside the clock. Timings choose
// experiments; nothing gates on them.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Python.Runtime;

namespace Goosedove.Host.Measure
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            try
            {
                if (args.Length != 0 && (args.Length != 2 || args[0] != "--output"))
                {
                    Console.Error.WriteLine("usage: Goosedove.Host.Measure [--output DIRECTORY]   (default: profiles/host-measure)");
                    return 2;
                }
                var root = RepoRoot();
                var output = args.Length == 0 ? Path.Combine(root, "profiles", "host-measure") : Path.GetFullPath(args[1]);
                var python = Ask(root, "import sys, sysconfig; print(sys.base_prefix); print(sysconfig.get_paths()['purelib']); print(f'python{sys.version_info.major}{sys.version_info.minor}.dll'); print(sys.version.split()[0])");
                Bridge.Start(Path.Combine(python[0], python[2]), new[] { Path.Combine(root, "src"), python[1] });
                var measurements = new Measurements();
                Scenarios.Run(measurements);
                Directory.CreateDirectory(output);
                measurements.Write(output);
                File.WriteAllText(Path.Combine(output, "environment.json"), Environment(root, python[3]));
                Console.WriteLine("Results: " + output);
                return 0;
            }
            catch (Exception failure)
            {
                Console.Error.WriteLine(failure);
                return 1;
            }
        }

        private static string Environment(string root, string pythonVersion)
        {
            string numpyVersion;
            using (Py.GIL())
            using (var numpy = Py.Import("numpy"))
            using (var version = numpy.GetAttr("__version__"))
            {
                numpyVersion = version.As<string>();
            }
            var fields = new List<KeyValuePair<string, string>>
            {
                Pair("timestamp_utc", DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture)),
                Pair("revision", Git(root, "rev-parse HEAD")),
                Pair("host_sha256", Sha256(typeof(Bridge).Assembly.Location)),
                Pair("bridge_sha256", Sha256(Path.Combine(root, "src", "goosedove", "excel", "bridge.py"))),
                Pair("probes_sha256", Sha256(Path.Combine(root, "src", "goosedove", "excel", "probes.py"))),
                Pair("configuration", Configuration()),
                Pair("python", pythonVersion),
                Pair("numpy", numpyVersion),
                Pair("pythonnet", typeof(PyObject).Assembly.GetName().Version.ToString()),
                Pair("exceldna_integration", typeof(ExcelDna.Integration.ExcelFunctionAttribute).Assembly.GetName().Version.ToString()),
                Pair("runtime", System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription),
                Pair("logical_processors", System.Environment.ProcessorCount.ToString(CultureInfo.InvariantCulture)),
                Pair("batch_target_ms", Measurements.BatchMilliseconds.ToString(CultureInfo.InvariantCulture)),
                Pair("batches", Measurements.Batches.ToString(CultureInfo.InvariantCulture)),
                Pair("timed_scope", "The registered delegate, Excel's path minus Excel-DNA: marshaling, the trip, validation, the probe, result conversion. Two stage rows, 'way in' and 'way out', time Marshal.ToPython and Marshal.FromPython alone with the GIL held outside the clock. Excludes Excel and building inputs. per_call_us is a batch mean."),
                Pair("allocation_scope", "GC.GetAllocatedBytesForCurrentThread over the batch, divided by calls: managed bytes on this thread only, not Python, numpy, or Excel-DNA."),
            };
            var json = new StringBuilder("{\n");
            for (var i = 0; i < fields.Count; i++)
            {
                json.Append("  \"").Append(fields[i].Key).Append("\": \"").Append(Escape(fields[i].Value)).Append('"');
                json.Append(i + 1 < fields.Count ? ",\n" : "\n");
            }
            return json.Append("}\n").ToString();
        }

        private static KeyValuePair<string, string> Pair(string key, string value)
        {
            return new KeyValuePair<string, string>(key, value);
        }

        private static string Escape(string value)
        {
            return value.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n");
        }

        private static string Configuration()
        {
#if DEBUG
            return "Debug";
#else
            return "Release";
#endif
        }

        private static string Sha256(string path)
        {
            using (var sha = SHA256.Create())
            using (var stream = File.OpenRead(path))
            {
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
            }
        }

        private static string Git(string root, string arguments)
        {
            return Run(root, "git", arguments).Trim();
        }

        private static string RepoRoot()
        {
            var directory = new DirectoryInfo(AppContext.BaseDirectory);
            while (directory != null && !File.Exists(Path.Combine(directory.FullName, "pyproject.toml")))
            {
                directory = directory.Parent;
            }
            if (directory == null)
            {
                throw new InvalidOperationException("no pyproject.toml above " + AppContext.BaseDirectory);
            }
            return directory.FullName;
        }

        // The project's own Python, found the way the host tests find it.
        private static string[] Ask(string root, string code)
        {
            return Run(root, "uv", "run python -c \"" + code + "\"").Trim().Split('\n').Select(line => line.Trim()).ToArray();
        }

        private static string Run(string root, string program, string arguments)
        {
            var start = new ProcessStartInfo(program, arguments)
            {
                WorkingDirectory = root,
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            using (var process = Process.Start(start))
            {
                var output = process.StandardOutput.ReadToEnd();
                process.WaitForExit();
                if (process.ExitCode != 0)
                {
                    throw new InvalidOperationException(program + " " + arguments + " failed: " + output);
                }
                return output;
            }
        }
    }
}
