using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using Xunit;

[assembly: CollectionBehavior(DisableTestParallelization = true)]

namespace Goosedove.Host.Tests
{
    /// <summary>Starts Python once for every test, the way the add-in does, minus Excel.</summary>
    public sealed class PythonFixture
    {
        public PythonFixture()
        {
            var root = RepoRoot();
            var python = Ask(root, "import sys, sysconfig; print(sys.base_prefix); print(sysconfig.get_paths()['purelib']); print(f'python{sys.version_info.major}{sys.version_info.minor}.dll')");
            Bridge.Start(Path.Combine(python[0], python[2]), new[] { Path.Combine(root, "src"), python[1] });
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
}
