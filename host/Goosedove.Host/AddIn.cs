using System;
using System.Collections.Generic;
using System.IO;
using ExcelDna.Integration;
using ExcelDna.IntelliSense;
using Python.Runtime;
using System.Linq.Expressions;
using System.Runtime.CompilerServices;

[assembly: InternalsVisibleTo("Goosedove.Host.Tests")]
[assembly: InternalsVisibleTo("Goosedove.Host.Measure")]

namespace Goosedove.Host
{
    /// <summary>Runs once when Excel loads the add-in: read config, start Python, import the bridge.</summary>
    public class AddIn : IExcelAddIn
    {
        private static bool helpShown;
        private static bool preparedToQuit;

        public void AutoOpen()
        {
            try
            {
                var config = Config.Load(Path.Combine(Path.GetDirectoryName(ExcelDnaUtil.XllPath), "goosedove.cfg"));
                Bridge.Start(config["pythondll"], config["pythonpath"].Split(';'));
                Registration.RegisterAll();
                // The help beside the formula as a person types it, from what was just registered. Excel's
                // own fx dialog reads the same registration and needs nothing more.
                IntelliSenseServer.Install();
                helpShown = true;
            }
            catch (Exception ex)
            {
                Bridge.StartupError = ex.ToString();
            }
        }

        public void AutoClose()
        {
            // Excel-DNA calls this on explicit add-in removal, not when Excel quits.
            StopHelp();
        }

        private static void StopHelp()
        {
            if (helpShown)
            {
                IntelliSenseServer.Uninstall();
                helpShown = false;
            }
        }

        /// <summary>
        /// Terminal cleanup for a hidden automation session. Its owner calls this after closing
        /// its workbooks, then quits Excel; it must make no further calls to the add-in.
        /// </summary>
        [ExcelCommand(Description = "Prepares this Excel process to quit after a hidden automation run.")]
        public static void GoosedovePrepareToQuit()
        {
            if (preparedToQuit) return;
            StopHelp();
            // IntelliSense obtained Excel-DNA's cached Application wrapper. Releasing the script's
            // COM objects cannot release this in-process reference, which keeps automated Excel
            // alive after Quit. Release it only on this terminal path, never on ordinary removal.
            System.Runtime.InteropServices.Marshal.ReleaseComObject(ExcelDnaUtil.Application);
            preparedToQuit = true;
            // Collect the event sinks detached by Uninstall inside Excel's own CLR.
            GC.Collect();
            GC.WaitForPendingFinalizers();
        }
    }

    /// <summary>
    /// The one place C# talks to Python. Each function's path is prepared once, at registration:
    /// the seam's entry for it, fetched by name and kept with the registered delegate. A call
    /// hands that entry the arguments and nothing else. What every call shares, MISSING, the
    /// range builder and the empty text, is fetched or made once at start.
    /// </summary>
    internal static class Bridge
    {
        public static PyObject Module;
        public static PyObject BoolType;
        public static PyObject Missing;
        public static PyObject CellsFromBuffers;
        public static PyObject EmptyText;
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
                Missing = Module.GetAttr("MISSING");
                CellsFromBuffers = Module.GetAttr("cells_from_buffers");
                EmptyText = new PyString("");  // what a range with no text cells carries as its text
                using (var builtins = Py.Import("builtins"))
                {
                    BoolType = builtins.GetAttr("bool");
                }
            }
        }

        /// <summary>A function's prepared path, fetched from the seam once, by name, at registration.</summary>
        public static Prepared Prepare(string name)
        {
            using (Py.GIL())
            using (var pyName = new PyString(name))
            {
                return new Prepared(name, Module.InvokeMethod("entry", pyName));
            }
        }

        /// <summary>The worksheet path: what every registered delegate calls, with no counter.</summary>
        public static object Call(Prepared prepared, params object[] args)
        {
            return Call(null, prepared, args);
        }

        /// <summary>The same call, reporting what it did to the observer's counter.</summary>
        internal static object Call(WorkCounter work, Prepared prepared, params object[] args)
        {
            if (Module == null)
            {
                return "#ERROR python did not start: " + StartupError;
            }
            try
            {
                using (Py.GIL())
                {
                    var pyArgs = new PyObject[args.Length];
                    try
                    {
                        for (var i = 0; i < args.Length; i++)
                        {
                            // An Excel error in any argument is the result, unchanged. Excel's own
                            // functions do the same, and it keeps an error from pricing as a blank.
                            object inputError;
                            pyArgs[i] = Marshal.ToPython(args[i], out inputError, work);
                            if (inputError != null)
                            {
                                return inputError;
                            }
                        }
                        work?.Hit("trips");
                        using (var result = prepared.Entry.Invoke(pyArgs))
                        {
                            return Marshal.FromPython(result, prepared.Name, work);
                        }
                    }
                    finally
                    {
                        foreach (var arg in pyArgs)
                        {
                            Marshal.Release(arg);
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

    /// <summary>One registered function's prepared path: its name, for messages, and the seam's entry for it.</summary>
    internal sealed class Prepared
    {
        public readonly string Name;
        public readonly PyObject Entry;

        public Prepared(string name, PyObject entry)
        {
            Name = name;
            Entry = entry;
        }
    }

    /// <summary>Excel-DNA values to Python and back: blanks to None, omitted arguments to MISSING, every range to one table of cells; a result read by its type, never asked about.</summary>
    internal static class Marshal
    {
        /// <summary>One argument as Python sees it, or null with the Excel error it holds. Release it with Release.</summary>
        public static PyObject ToPython(object value, out object error, WorkCounter work = null)
        {
            error = null;
            if (value is ExcelError)
            {
                error = value;
                return null;
            }
            if (value is object[,] rect)
            {
                return Range(rect, out error, work);
            }
            if (value is ExcelMissing)
            {
                return Bridge.Missing;  // held since start: never built, never released
            }
            work?.Hit("objects_built");
            return value == null || value is ExcelEmpty ? PyObject.None : value.ToPython();
        }

        /// <summary>Lets go of whatever ToPython returned: a built value is disposed, the shared MISSING and a null stay.</summary>
        public static void Release(PyObject value)
        {
            if (value != null && !ReferenceEquals(value, Bridge.Missing))
            {
                value.Dispose();
            }
        }

        // The codes of the seam's Kind enum, and the bit each sets in the summary of kinds seen.
        private const byte Number = 0, Text = 1, Boolean = 2, Blank = 3, Missing = 4;
        private const byte NumberSeen = 1 << Number, TextSeen = 1 << Text, BooleanSeen = 1 << Boolean, BlankSeen = 1 << Blank, MissingSeen = 1 << Missing;

        // The two buffers a range crosses in, kept between calls and grown only when a larger
        // range comes. They are pinned for as long as they live, and the two Python integers
        // that carry their addresses are built when they are. One set per thread: Excel calls
        // these functions on one thread, and the host runner and the tests each on their own.
        [ThreadStatic] private static byte[] kindsBuffer;
        [ThreadStatic] private static double[] numbersBuffer;
        [ThreadStatic] private static System.Runtime.InteropServices.GCHandle kindsHandle;
        [ThreadStatic] private static System.Runtime.InteropServices.GCHandle numbersHandle;
        [ThreadStatic] private static PyObject kindsAddress;
        [ThreadStatic] private static PyObject numbersAddress;
        [ThreadStatic] private static List<string> textCells;

        // Room for a range of this many cells: the buffers already there, or larger ones. The new
        // set is whole before the old one goes, so a failure to grow leaves the old buffers pinned
        // and the next range as safe as before.
        private static void Reserve(int cells, WorkCounter work)
        {
            if (kindsBuffer != null && kindsBuffer.Length >= cells)
            {
                return;
            }
            var newKinds = new byte[cells];
            var newNumbers = new double[cells];
            var newKindsHandle = System.Runtime.InteropServices.GCHandle.Alloc(newKinds, System.Runtime.InteropServices.GCHandleType.Pinned);
            var newNumbersHandle = System.Runtime.InteropServices.GCHandle.Alloc(newNumbers, System.Runtime.InteropServices.GCHandleType.Pinned);
            PyObject newKindsAddress = null, newNumbersAddress = null;
            try
            {
                newKindsAddress = new PyInt(newKindsHandle.AddrOfPinnedObject().ToInt64());
                newNumbersAddress = new PyInt(newNumbersHandle.AddrOfPinnedObject().ToInt64());
            }
            catch
            {
                newKindsAddress?.Dispose();
                newKindsHandle.Free();
                newNumbersHandle.Free();
                throw;
            }
            if (kindsBuffer != null)
            {
                kindsHandle.Free();
                numbersHandle.Free();
                kindsAddress.Dispose();
                numbersAddress.Dispose();
            }
            kindsBuffer = newKinds;
            numbersBuffer = newNumbers;
            kindsHandle = newKindsHandle;
            numbersHandle = newNumbersHandle;
            kindsAddress = newKindsAddress;
            numbersAddress = newNumbersAddress;
            work?.Hit("buffers_allocated", 2);
            work?.Hit("buffer_bytes", 9L * cells);
            work?.Hit("objects_built", 2);
        }

        // One pass over the cells, in sheet order, into the kept buffers. An Excel error
        // anywhere is returned and nothing is built. Every other range ships the same way: one
        // kind code per cell, one number per cell (NaN where there is none), the text cells
        // joined with NUL, and one bit per kind that occurred, so the seam learns "all numbers"
        // from this pass and takes no look of its own. Python copies the buffers before it
        // returns, so the next range may overwrite them.
        private static PyObject Range(object[,] rect, out object error, WorkCounter work)
        {
            error = null;
            int rows = rect.GetLength(0), cols = rect.GetLength(1);
            Reserve(rows * cols, work);
            var kinds = kindsBuffer;
            var numbers = numbersBuffer;
            var texts = textCells ?? (textCells = new List<string>());
            texts.Clear();
            byte seen = 0;
            var i = 0;
            for (var r = 0; r < rows; r++)
            {
                for (var c = 0; c < cols; c++)
                {
                    var cell = rect[r, c];
                    if (cell is ExcelError)
                    {
                        work?.Hit("cells_scanned", i + 1);
                        work?.Hit("text_cells", texts.Count);
                        error = cell;
                        return null;
                    }
                    if (cell is double d)
                    {
                        kinds[i] = Number;
                        numbers[i] = d;
                        seen |= NumberSeen;
                    }
                    else if (cell is string s)
                    {
                        kinds[i] = Text;
                        numbers[i] = double.NaN;
                        texts.Add(s);
                        seen |= TextSeen;
                    }
                    else if (cell is bool b)
                    {
                        kinds[i] = Boolean;
                        numbers[i] = b ? 1.0 : 0.0;
                        seen |= BooleanSeen;
                    }
                    else if (cell == null || cell is ExcelEmpty)
                    {
                        kinds[i] = Blank;
                        numbers[i] = double.NaN;
                        seen |= BlankSeen;
                    }
                    else if (cell is ExcelMissing)
                    {
                        kinds[i] = Missing;
                        numbers[i] = double.NaN;
                        seen |= MissingSeen;
                    }
                    else
                    {
                        throw new InvalidOperationException("a cell holds a " + cell.GetType().Name);
                    }
                    i++;
                }
            }
            work?.Hit("cells_scanned", i);
            work?.Hit("text_cells", texts.Count);
            return CellsFromBuffers(rows, cols, texts.Count == 0 ? null : string.Join("\0", texts), seen, work);
        }

        // The seam sends one of four things: a number, text, a boolean, or a two-dimensional array
        // of doubles. Each is read by its type at the C level, with no trip into Python. Anything
        // else is the seam's promise broken, and says so in the cell.
        public static object FromPython(PyObject value, string name, WorkCounter work = null)
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
                    return "#ERROR host: " + name + " returned a buffer that is not an array of doubles";
                }
                var rows = (int)buffer.Shape[0];
                var cols = (int)buffer.Shape[1];
                var bytes = (long)rows * cols * sizeof(double);
                if (buffer.Length != bytes)
                {
                    return "#ERROR host: " + name + " returned a buffer of " + buffer.Length + " bytes for " + rows + "x" + cols + " doubles";
                }
                // One copy, straight from Python's buffer into the array Excel receives; the array
                // is pinned only for the length of the copy.
                var array = new double[rows, cols];
                if (bytes > 0)
                {
                    unsafe
                    {
                        fixed (double* destination = array)
                        {
                            Buffer.MemoryCopy((void*)buffer.Buffer, destination, bytes, bytes);
                        }
                    }
                    work?.Hit("result_copies");
                }
                work?.Hit("buffers_allocated");
                work?.Hit("buffer_bytes", bytes);
                work?.Hit("result_cells", rows * cols);
                return array;
            }
        }

        // Let Python copy the kept buffers from their addresses, with the shape, the kinds seen,
        // and the text if there is any beside them; without text the shared empty string crosses.
        private static PyObject CellsFromBuffers(int rows, int cols, string text, byte seen, WorkCounter work)
        {
            using (var pyRows = new PyInt(rows))
            using (var pyCols = new PyInt(cols))
            using (var pySeen = new PyInt(seen))
            {
                work?.Hit("objects_built", 3);
                work?.Hit("trips");
                if (text == null)
                {
                    return Bridge.CellsFromBuffers.Invoke(kindsAddress, numbersAddress, pyRows, pyCols, Bridge.EmptyText, pySeen);
                }
                using (var pyText = new PyString(text))
                {
                    work?.Hit("objects_built");
                    return Bridge.CellsFromBuffers.Invoke(kindsAddress, numbersAddress, pyRows, pyCols, pyText, pySeen);
                }
            }
        }
    }

    /// <summary>Asks Python which functions exist and registers each one with Excel; a probe is registered hidden from the function wizard.</summary>
    internal static class Registration
    {
        public static void RegisterAll()
        {
            var (delegates, attributes, argumentAttributes) = Describe();
            ExcelIntegration.RegisterDelegates(delegates, attributes, argumentAttributes);
        }

        /// <summary>
        /// What Excel is told about each function: one delegate, its name, description and hidden flag, and
        /// one attribute per argument carrying the label Excel shows, [factor] for an optional argument, and
        /// its help. The bridge prepared all of it once at import; nothing here is read again per call.
        /// </summary>
        internal static (List<Delegate> Delegates, List<object> Attributes, List<List<object>> ArgumentAttributes) Describe()
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
                    var arguments = new List<object>();
                    foreach (PyObject argument in new PyList(spec[2]))
                    {
                        arguments.Add(new ExcelArgumentAttribute { Name = argument[0].As<string>(), Description = argument[1].As<string>() });
                    }
                    var hidden = spec[3].As<bool>();

                    delegates.Add(MakeDelegate(Bridge.Prepare(name), arguments.Count));
                    attributes.Add(new ExcelFunctionAttribute { Name = name, Description = description, IsHidden = hidden });
                    argumentAttributes.Add(arguments);
                }
            }

            return (delegates, attributes, argumentAttributes);
        }

        // Excel-DNA needs a delegate with one typed parameter per argument. Build one that packs
        // its arguments into an array and hands them to the function's prepared path.
        internal static Delegate MakeDelegate(Prepared prepared, int parameterCount)
        {
            var parameters = new ParameterExpression[parameterCount];
            for (var i = 0; i < parameterCount; i++)
            {
                parameters[i] = Expression.Parameter(typeof(object), "arg" + i);
            }
            var call = Expression.Call(
                typeof(Bridge).GetMethod(nameof(Bridge.Call), new[] { typeof(Prepared), typeof(object[]) }),
                Expression.Constant(prepared),
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

    /// <summary>
    /// The floor under every probe: a function with the host's argument shape and no Python, so
    /// what Excel and Excel-DNA charge for a call is measured beside what the seam adds. Hidden
    /// from the function wizard like the probes.
    /// </summary>
    public static class Floor
    {
        [ExcelFunction(IsHidden = true, Description = "Probe: a number in and out with no Python; the Excel-DNA floor.")]
        public static object HostAdd(object a, object b)
        {
            return (double)a + (double)b;
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
