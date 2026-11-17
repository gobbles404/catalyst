using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using ExcelDna.Integration;
using Xunit;

[assembly: CollectionBehavior(DisableTestParallelization = true)]

namespace Catalyst.Host.Tests
{
    /// <summary>
    /// Starts Python once for every test, the way the add-in does, minus Excel, in the add-in's own
    /// two steps: the bridge first, as an end user's build stops, then the probes' package, as a
    /// build whose config names it goes on. What Excel would be told between the two is kept.
    /// </summary>
    public sealed class PythonFixture
    {
        /// <summary>Each function an end user's Excel is told of, and whether it is hidden.</summary>
        public IReadOnlyList<(string Name, bool Hidden)> EndUserFunctions { get; }

        public PythonFixture()
        {
            var root = RepoRoot();
            var python = Ask(root, "import sys, sysconfig; print(sys.base_prefix); print(sysconfig.get_paths()['purelib']); print(f'python{sys.version_info.major}{sys.version_info.minor}.dll')");
            Bridge.Start(Path.Combine(python[0], python[2]), new[] { Path.Combine(root, "src"), Path.Combine(root, "test_support"), python[1] });
            EndUserFunctions = Told();
            Bridge.LoadProbes("catalyst_probes");
        }

        /// <summary>The names and hidden flags registration would hand Excel now.</summary>
        internal static List<(string Name, bool Hidden)> Told()
        {
            return Registration.Describe().Attributes.Cast<ExcelFunctionAttribute>().Select(a => (a.Name, a.IsHidden)).ToList();
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

        // The project's own Python, found the way tools\excel_smoke.ps1 finds it.
        private static string[] Ask(string root, string code)
        {
            var start = new ProcessStartInfo("uv", "run python -c \"" + code + "\"")
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
                    throw new InvalidOperationException("uv run python failed: " + output);
                }
                return output.Trim().Split('\n').Select(line => line.Trim()).ToArray();
            }
        }
    }

    [CollectionDefinition("python")]
    public sealed class PythonCollection : ICollectionFixture<PythonFixture>
    {
    }

    /// <summary>The seam by name, for tests: prepare the path, then call it, the way a registered delegate does.</summary>
    internal static class Seam
    {
        public static object Call(string name, params object[] args)
        {
            return Bridge.Call(Bridge.Prepare(name), args);
        }
    }
}
