using System;
using System.Collections.Generic;
using System.IO;
using ExcelDna.Integration;
using Python.Runtime;
using System.Linq.Expressions;
using System.Runtime.CompilerServices;

[assembly: InternalsVisibleTo("Goosedove.Host.Tests")]

namespace Goosedove.Host
{
    /// <summary>Runs once when Excel loads the add-in: read config, start Python, import the bridge.</summary>
    public class AddIn : IExcelAddIn
    {
        public void AutoOpen()
        {
            try
            {
                var config = Config.Load(Path.Combine(Path.GetDirectoryName(ExcelDnaUtil.XllPath), "goosedove.cfg"));
                Bridge.Start(config["pythondll"], config["pythonpath"].Split(';'));
                Registration.RegisterAll();
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
    internal static class Bridge
    {
        public static PyObject Module;
        public static PyObject BoolType;
        public static string StartupError;

        /// <summary>Start Python once, put the package on its path, and import the bridge.</summary>
        public static void Start(string pythonDll, string[] pythonPath)
        {
            Runtime.PythonDLL = pythonDll;
            PythonEngine.Initialize();
            PythonEngine.BeginAllowThreads();
            using (Py.GIL())
            {
                dynamic sys = Py.Import("sys");
                for (var i = pythonPath.Length - 1; i >= 0; i--)
                {
                    sys.path.insert(0, pythonPath[i].Trim());
                }
                Module = Py.Import("goosedove.excel.bridge");
                using (var builtins = Py.Import("builtins"))
                {
                    BoolType = builtins.GetAttr("bool");
                }
            }
        }

        public static object Call(string name, params object[] args)
        {
            if (Module == null)
            {
                return "#ERROR python did not start: " + StartupError;
            }
            try
            {
                using (Py.GIL())
                {
                    using (var pyName = new PyString(name))
                    using (var pyArgs = new PyList())
                    {
                        foreach (var arg in args)
                        {
                            // An Excel error in any argument is the result, unchanged. Excel's own
                            // functions do the same, and it keeps an error from pricing as a blank.
                            var inputError = Marshal.Append(pyArgs, arg);
                            if (inputError != null)
                            {
                                return inputError;
                            }
                        }
                        using (var result = Module.InvokeMethod("call", pyName, pyArgs))
                        {
                            return Marshal.FromPython(result, name);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                return "#ERROR host: " + ex.Message;
            }
        }
    }

    /// <summary>Excel-DNA values to Python and back: blanks to None, omitted arguments to MISSING, every range to one table of cells; a result read by its type, never asked about.</summary>
    internal static class Marshal
    {
        /// <summary>Appends one argument to the call. Returns the Excel error it holds, if any, and then appends nothing.</summary>
        public static object Append(PyList args, object value)
        {
            if (value is ExcelError)
            {
                return value;
            }
            if (value is object[,] rect)
            {
                object error;
                var range = Range(rect, out error);
                if (error != null)
                {
                    return error;
                }
                using (range)
                {
                    args.Append(range);
                }
                return null;
            }
            using (var scalar = Scalar(value))
            {
                args.Append(scalar);
            }
            return null;
        }

        private static PyObject Scalar(object value)
        {
            if (value == null || value is ExcelEmpty)
            {
                return PyObject.None;
            }
            if (value is ExcelMissing)
            {
                return Bridge.Module.GetAttr("MISSING");
            }
            return value.ToPython();
        }

        // The codes of the seam's Kind enum.
        private const byte Number = 0, Text = 1, Boolean = 2, Blank = 3, Missing = 4;

        // One pass over the cells, in sheet order. An Excel error anywhere is returned and
        // nothing is built. Every other range ships the same way: one kind code per cell,
        // one number per cell (NaN where there is none), and the text cells joined with NUL.
        private static PyObject Range(object[,] rect, out object error)
        {
            error = null;
            int rows = rect.GetLength(0), cols = rect.GetLength(1);
            var kinds = new byte[rows * cols];
            var numbers = new double[rows * cols];
            var texts = new List<string>();
            var i = 0;
            foreach (var cell in rect)
            {
                if (cell is ExcelError)
                {
                    error = cell;
                    return null;
                }
                if (cell is double d)
                {
                    kinds[i] = Number;
                    numbers[i] = d;
                }
                else if (cell is string s)
                {
                    kinds[i] = Text;
                    numbers[i] = double.NaN;
                    texts.Add(s);
                }
                else if (cell is bool b)
                {
                    kinds[i] = Boolean;
                    numbers[i] = b ? 1.0 : 0.0;
                }
                else if (cell == null || cell is ExcelEmpty)
                {
                    kinds[i] = Blank;
                    numbers[i] = double.NaN;
                }
                else if (cell is ExcelMissing)
                {
                    kinds[i] = Missing;
                    numbers[i] = double.NaN;
                }
                else
                {
                    throw new InvalidOperationException("a cell holds a " + cell.GetType().Name);
                }
                i++;
            }
            return CellsBlock(kinds, numbers, rows, cols, string.Join("\0", texts));
        }

        // The seam sends one of four things: a number, text, a boolean, or a two-dimensional block
        // of doubles. Each is read by its type at the C level, with no trip into Python. Anything
        // else is the seam's promise broken, and says so in the cell.
        public static object FromPython(PyObject value, string name)
        {
            if (PyFloat.IsFloatType(value))
            {
                return value.As<double>();
            }
            if (PyString.IsStringType(value))
            {
                return value.As<string>();
            }
            if (value.IsInstance(Bridge.BoolType))
            {
                return value.As<bool>();
            }
            PyBuffer buffer;
            try
            {
                // Never PyBUF.FORMATS: pythonnet 3.1.0 crashes on it (its issue 2371). CONTIG_RO
                // carries the dimensions, the shape, the item size, and the pointer.
                buffer = value.GetBuffer(PyBUF.CONTIG_RO);
            }
            catch (PythonException)
            {
                return "#ERROR host: " + name + " returned a " + value.GetPythonType().Name + ", which the host cannot show";
            }
            using (buffer)
            {
                if (buffer.Dimensions != 2 || buffer.ItemSize != sizeof(double))
                {
                    return "#ERROR host: " + name + " returned a buffer that is not a block of doubles";
                }
                var rows = (int)buffer.Shape[0];
                var cols = (int)buffer.Shape[1];
                var doubles = new double[rows * cols];
                System.Runtime.InteropServices.Marshal.Copy(buffer.Buffer, doubles, 0, doubles.Length);
                var block = new double[rows, cols];
                Buffer.BlockCopy(doubles, 0, block, 0, doubles.Length * sizeof(double));
                return block;
            }
        }

        // Pin the buffers and let Python copy them from pointers.
        private static PyObject CellsBlock(byte[] kinds, double[] numbers, int rows, int cols, string text)
        {
            var kindsHandle = System.Runtime.InteropServices.GCHandle.Alloc(kinds, System.Runtime.InteropServices.GCHandleType.Pinned);
            var numbersHandle = System.Runtime.InteropServices.GCHandle.Alloc(numbers, System.Runtime.InteropServices.GCHandleType.Pinned);
            try
            {
                using (var pyKinds = new PyInt(kindsHandle.AddrOfPinnedObject().ToInt64()))
                using (var pyNumbers = new PyInt(numbersHandle.AddrOfPinnedObject().ToInt64()))
                using (var pyRows = new PyInt(rows))
                using (var pyCols = new PyInt(cols))
                using (var pyText = new PyString(text))
                {
                    return Bridge.Module.InvokeMethod("cells_block", pyKinds, pyNumbers, pyRows, pyCols, pyText);
                }
            }
            finally
            {
                kindsHandle.Free();
                numbersHandle.Free();
            }
        }
    }

    /// <summary>Asks Python which functions exist and registers each one with Excel; a probe is registered hidden from the function wizard.</summary>
    internal static class Registration
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
                    var hidden = spec[3].As<bool>();

                    delegates.Add(MakeDelegate(name, parameters.Count));
                    attributes.Add(new ExcelFunctionAttribute { Name = name, Description = description, IsHidden = hidden });
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
        internal static Delegate MakeDelegate(string name, int parameterCount)
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

    /// <summary>Reads key=value lines from a config file; the add-in keeps its own beside the .xll.</summary>
    internal static class Config
    {
        public static Dictionary<string, string> Load(string path)
        {
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
