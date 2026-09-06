using System;
using System.Collections.Generic;
using System.IO;
using ExcelDna.Integration;
using Python.Runtime;

namespace Goosedove.Host
{
    /// <summary>Runs once when Excel loads the add-in: read config, start Python, import the bridge.</summary>
    public class AddIn : IExcelAddIn
    {
        public void AutoOpen()
        {
            try
            {
                var config = Config.Load();
                Runtime.PythonDLL = config["pythondll"];
                PythonEngine.Initialize();
                PythonEngine.BeginAllowThreads();
                using (Py.GIL())
                {
                    dynamic sys = Py.Import("sys");
                    sys.path.insert(0, config["pythonpath"]);
                    Bridge.Module = Py.Import("goosedove.excel.bridge");
                }
            }
            catch (Exception ex)
            {
                Bridge.StartupError = ex.ToString();
            }
        }

        public void AutoClose()
        {
            // Excel is exiting; the process ends and takes Python with it.
        }
    }

    /// <summary>The one place C# talks to Python: hand a name and arguments to bridge.call.</summary>
    public static class Bridge
    {
        public static PyObject Module;
        public static string StartupError;

        public static object Call(string name, params object[] args)
        {
            if (Module == null)
            {
                return "#ERROR python did not start: " + StartupError;
            }
            using (Py.GIL())
            {
                using (var pyName = new PyString(name))
                using (var pyArgs = new PyList())
                {
                    foreach (var arg in args)
                    {
                        using (var pyArg = arg.ToPython())
                        {
                            pyArgs.Append(pyArg);
                        }
                    }
                    using (var result = Module.InvokeMethod("call", pyName, pyArgs))
                    {
                        return result.AsManagedObject(typeof(object));
                    }
                }
            }
        }
    }

    /// <summary>Worksheet functions. Each one forwards to Python by name.</summary>
    public static class Functions
    {
        [ExcelFunction(Description = "Confirms which goosedove Excel is running.")]
        public static object Ping()
        {
            try
            {
                return Bridge.Call("Ping");
            }
            catch (Exception ex)
            {
                return "#ERROR host: " + ex.Message;
            }
        }
    }

    /// <summary>Reads key=value lines from goosedove.cfg beside the .xll.</summary>
    internal static class Config
    {
        public static Dictionary<string, string> Load()
        {
            var directory = Path.GetDirectoryName(ExcelDnaUtil.XllPath);
            var path = Path.Combine(directory, "goosedove.cfg");
            var values = new Dictionary<string, string>();
            foreach (var line in File.ReadAllLines(path))
            {
                var trimmed = line.Trim();
                if (trimmed.Length == 0 || trimmed.StartsWith("#")) continue;
                var split = trimmed.IndexOf('=');
                values[trimmed.Substring(0, split).Trim()] = trimmed.Substring(split + 1).Trim();
            }
            return values;
        }
    }
}
