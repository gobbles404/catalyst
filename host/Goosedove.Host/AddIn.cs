using System;
using System.Collections.Generic;
using System.IO;
using ExcelDna.Integration;
using Python.Runtime;
using System.Linq.Expressions;

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
                    var paths = config["pythonpath"].Split(';');
                    for (var i = paths.Length - 1; i >= 0; i--)
                    {
                        sys.path.insert(0, paths[i].Trim());
                    }
                    Bridge.Module = Py.Import("goosedove.excel.bridge");
                    Registration.RegisterAll();
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
                        using (var pyArg = Marshal.ToPython(arg))
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

        /// <summary>Excel-DNA values to Python values: blanks to None, ranges to rows.</summary>
    public static class Marshal
    {
        public static PyObject ToPython(object value)
        {
            if (value == null || value is ExcelEmpty || value is ExcelMissing || value is ExcelError)
            {
                return PyObject.None;
            }
            if (value is object[,] rect)
            {
                if (IsNumeric(rect))
                {
                    return NumericBlock(rect);
                }
                var rows = new PyList();
                for (var r = 0; r < rect.GetLength(0); r++)
                {
                    using (var row = new PyList())
                    {
                        for (var c = 0; c < rect.GetLength(1); c++)
                        {
                            using (var cell = ToPython(rect[r, c]))
                            {
                                row.Append(cell);
                            }
                        }
                        rows.Append(row);
                    }
                }
                return rows;
            }
            return value.ToPython();
        }

                // True when every cell is a number or blank; those ranges take the fast path.
        private static bool IsNumeric(object[,] rect)
        {
            foreach (var cell in rect)
            {
                if (!(cell is double || cell == null || cell is ExcelEmpty))
                {
                    return false;
                }
            }
            return true;
        }

        // Unbox into one double[] (NaN for blanks) and let Python copy it from a pointer.
        private static PyObject NumericBlock(object[,] rect)
        {
            int rows = rect.GetLength(0), cols = rect.GetLength(1);
            var block = new double[rows * cols];
            var i = 0;
            for (var r = 0; r < rows; r++)
            {
                for (var c = 0; c < cols; c++)
                {
                    block[i++] = rect[r, c] is double d ? d : double.NaN;
                }
            }
            var handle = System.Runtime.InteropServices.GCHandle.Alloc(block, System.Runtime.InteropServices.GCHandleType.Pinned);
            try
            {
                using (var ptr = new PyInt(handle.AddrOfPinnedObject().ToInt64()))
                using (var pyRows = new PyInt(rows))
                using (var pyCols = new PyInt(cols))
                {
                    return Bridge.Module.InvokeMethod("numeric_block", ptr, pyRows, pyCols);
                }
            }
            finally
            {
                handle.Free();
            }
        }
    }

    /// <summary>Asks Python which functions exist and registers each one with Excel.</summary>
    public static class Registration
    {
        public static void RegisterAll()
        {
            var delegates = new List<Delegate>();
            var attributes = new List<object>();
            var argumentAttributes = new List<List<object>>();

            using (Py.GIL())
            using (var specs = Bridge.Module.InvokeMethod("function_specs"))
            {
                foreach (PyObject spec in new PyList(specs))
                {
                    var name = spec[0].As<string>();
                    var description = spec[1].As<string>();
                    var parameters = new List<string>();
                    foreach (PyObject p in new PyList(spec[2]))
                    {
                        parameters.Add(p.As<string>());
                    }

                    delegates.Add(MakeDelegate(name, parameters.Count));
                    attributes.Add(new ExcelFunctionAttribute { Name = name, Description = description });
                    var args = new List<object>();
                    foreach (var p in parameters)
                    {
                        args.Add(new ExcelArgumentAttribute { Name = p });
                    }
                    argumentAttributes.Add(args);
                }
            }

            ExcelIntegration.RegisterDelegates(delegates, attributes, argumentAttributes);
        }

        // Excel-DNA needs a delegate with one typed parameter per argument.
        // Build one that packs its arguments into an array and forwards by name.
        private static Delegate MakeDelegate(string name, int parameterCount)
        {
            var parameters = new ParameterExpression[parameterCount];
            for (var i = 0; i < parameterCount; i++)
            {
                parameters[i] = Expression.Parameter(typeof(object), "arg" + i);
            }
            var call = Expression.Call(
                typeof(Bridge).GetMethod(nameof(Bridge.Call)),
                Expression.Constant(name),
                Expression.NewArrayInit(typeof(object), parameters));
            return Expression.Lambda(call, parameters).Compile();
        }
    }

    /// <summary>Always registered, even when Python failed to start, so the failure is visible.</summary>
    public static class Status
    {
        [ExcelFunction(Description = "Reports whether Python started, and the error if it did not.")]
        public static string GoosedoveStatus()
        {
            return Bridge.StartupError ?? "ok: python started and functions registered";
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
