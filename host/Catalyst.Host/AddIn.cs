using System;
using System.Collections.Generic;
using System.IO;
using ExcelDna.Integration;
using ExcelDna.IntelliSense;
using Python.Runtime;
using System.Linq.Expressions;
using System.Reflection;
using System.Runtime.CompilerServices;

[assembly: InternalsVisibleTo("Catalyst.Host.Tests")]
[assembly: InternalsVisibleTo("Catalyst.Host.Measure")]

namespace Catalyst.Host
{
    /// <summary>
    /// Runs once when Excel loads the add-in: read config, start Python, import the bridge. A config
    /// that names the probes' package under <c>probes</c> has them imported too, a test or a
    /// measurement build; an end user's config has no such line, and its Excel knows no probe.
    /// </summary>
    public class AddIn : IExcelAddIn
    {
        private static bool helpShown;
        private static bool preparedToQuit;

        public void AutoOpen()
        {
            try
            {
                var config = Config.Load(Path.Combine(Path.GetDirectoryName(ExcelDnaUtil.XllPath), "catalyst.cfg"));
                Bridge.Start(config["pythondll"], config["pythonpath"].Split(';'));
                if (config.TryGetValue("probes", out var probes)) Bridge.LoadProbes(probes);
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
            // Excel-DNA calls this on explicit add-in removal, not when Excel quits. A release
            // that arrives after this is skipped: the process is on its way out.
            Lifetime.Closing = true;
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
        public static void CatalystPrepareToQuit()
        {
            if (preparedToQuit) return;
            Lifetime.Closing = true;
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
        public static bool ProbesLoaded;

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
                Module = Py.Import("catalyst.excel.bridge");
                Missing = Module.GetAttr("MISSING");
                CellsFromBuffers = Module.GetAttr("cells_from_buffers");
                EmptyText = new PyString("");  // what a range with no text cells carries as its text
                using (var builtins = Py.Import("builtins"))
                {
                    BoolType = builtins.GetAttr("bool");
                }
            }
        }

        /// <summary>
        /// Import the probes' package, which registers each probe with the bridge as any worksheet
        /// function is registered. The package is test support and no part of the library: it is on
        /// the path only where a config put it. Called once, after Start and before registration.
        /// </summary>
        public static void LoadProbes(string package)
        {
            using (Py.GIL())
            {
                Py.Import(package).Dispose();
            }
            ProbesLoaded = true;
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

        /// <summary>A creator's prepared path for the observed delegate, fetched from the seam once, by name.</summary>
        public static Prepared PreparePublisher(string name)
        {
            using (Py.GIL())
            using (var pyName = new PyString(name))
            {
                return new Prepared(name, Module.InvokeMethod("publisher", pyName));
            }
        }

        /// <summary>The worksheet path: what every registered delegate calls, with no counter.</summary>
        public static object Call(Prepared prepared, params object[] args)
        {
            return Call(null, prepared, args);
        }

        /// <summary>
        /// The observed path a creator's publication takes: the cell's value and whether this call
        /// published it, as the seam says in one result. An Excel error in any argument is the
        /// value, unchanged and owning nothing, as on the plain path.
        /// </summary>
        public static Outcome Publish(Prepared prepared, params object[] args)
        {
            if (Module == null)
            {
                return new Outcome("#ERROR python did not start: " + StartupError, false);
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
                            object inputError;
                            pyArgs[i] = Marshal.ToPython(args[i], prepared.Name, i + 1, out inputError);
                            if (inputError != null)
                            {
                                return new Outcome(inputError, false);
                            }
                        }
                        using (var pair = prepared.Entry.Invoke(pyArgs))
                        using (var value = pair[0])
                        using (var owned = pair[1])
                        {
                            return new Outcome(Marshal.FromPython(value, prepared.Name), owned.As<bool>());
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
                return new Outcome("#ERROR host: " + ex.Message, false);
            }
        }

        /// <summary>
        /// Lets one publication go when Excel has disconnected its last subscriber: released, or
        /// missing when the seam found no entry. Skipped once the add-in is closing or Python is
        /// gone; a call into a finalized interpreter is never made.
        /// </summary>
        public static Release Release(string text)
        {
            if (Lifetime.Closing || Module == null || !PythonEngine.IsInitialized)
            {
                return Catalyst.Host.Release.Skipped;
            }
            using (Py.GIL())
            using (var pyText = new PyString(text))
            using (var result = Module.InvokeMethod("release", pyText))
            {
                return result.As<bool>() ? Catalyst.Host.Release.Released : Catalyst.Host.Release.Missing;
            }
        }

        /// <summary>The store's live count and the bytes of prices its live vectors hold: a diagnostic read.</summary>
        public static (long Live, long PriceBytes) LiveHandles()
        {
            if (Module == null)
            {
                return (-1, -1);
            }
            using (Py.GIL())
            using (var pair = Module.InvokeMethod("live_handles"))
            using (var live = pair[0])
            using (var bytes = pair[1])
            {
                return (live.As<long>(), bytes.As<long>());
            }
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
                            // Since #189 a text holding NUL is the result too, the host's own refusal,
                            // found in the same left-to-right pass and never sent across.
                            object inputError;
                            pyArgs[i] = Marshal.ToPython(args[i], prepared.Name, i + 1, out inputError, work);
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
        /// <summary>
        /// One argument as Python sees it, or null with what refuses it: the Excel error it holds,
        /// unchanged, or since #189 the host's own text for a text holding NUL (U+0000), the
        /// character that separates a range's texts on their way across, named by the function
        /// and the argument's one-based position. Release it with Release.
        /// </summary>
        public static PyObject ToPython(object value, string function, int position, out object error, WorkCounter work = null)
        {
            error = null;
            if (value is ExcelError)
            {
                error = value;
                return null;
            }
            if (value is object[,] rect)
            {
                return Range(rect, function, position, out error, work);
            }
            if (value is ExcelMissing)
            {
                return Bridge.Missing;  // held since start: never built, never released
            }
            if (value is string text)
            {
                // A scalar text is checked at the same boundary as a range's cells, so the rule
                // does not depend on the shape the text arrives in.
                work?.Hit("texts_checked");
                if (text.IndexOf('\0') >= 0)
                {
                    error = NulRefusal(function, position, 0, 0);
                    return null;
                }
            }
            work?.Hit("objects_built");
            return value == null || value is ExcelEmpty ? PyObject.None : value.ToPython();
        }

        // The host's refusal of a text holding NUL (U+0000), since #189: the function, the argument's
        // one-based position and, inside a range, the cell's one-based row and column within the
        // range supplied; never the text itself, which would put the character in the message.
        internal static string NulRefusal(string function, int position, int row, int column)
        {
            var where = row == 0 ? "" : " cell (" + row + ", " + column + ")";
            return "#ERROR host: " + function + " argument " + position + where + " is text holding NUL (U+0000), expected text without it";
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
        // anywhere is returned and nothing is built, and since #189 so is a text holding NUL, the
        // separator of the texts below, refused where the pass reaches it. Every other range ships the same way: one
        // kind code per cell, one number per cell (NaN where there is none), the text cells
        // joined with NUL, and one bit per kind that occurred, so the seam learns "all numbers"
        // from this pass and takes no look of its own. Python copies the buffers before it
        // returns, so the next range may overwrite them.
        private static PyObject Range(object[,] rect, string function, int position, out object error, WorkCounter work)
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
                        // Each text reached is looked at once, the refused one included: joined,
                        // a text holding NUL would split into two cells on the other side and
                        // move text into another field, so it stops the scan as an error does.
                        work?.Hit("texts_checked");
                        if (s.IndexOf('\0') >= 0)
                        {
                            work?.Hit("cells_scanned", i + 1);
                            work?.Hit("text_cells", texts.Count);
                            error = NulRefusal(function, position, r + 1, c + 1);
                            return null;
                        }
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

        // The seam sends one of five things: a number, text, a boolean, a two-dimensional array of
        // doubles, or a tuple carrying a rectangle of numbers, text and booleans. Each is read by
        // its type at the C level, with no trip into Python. Anything else is the seam's promise
        // broken, and says so in the cell.
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
            if (PyTuple.IsTupleType(value))
            {
                return MixedOut(value, name, work);
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

        private static readonly object TrueBox = true, FalseBox = false;  // shared, never made per cell

        // The mixed road out: a rectangle of numbers, text and booleans, laid out cell by cell from
        // the kinds, the mirror of the way in. The seam sends three things by position: the kinds,
        // one byte per cell; the numbers, eight bytes per cell, 1.0 or 0.0 for a boolean and a
        // placeholder where a cell holds text; and the text cells joined with NUL in sheet order.
        // Every number cell is boxed and every text cell is its own string, because Excel receives
        // an array as one tagged value per cell and there is no block of mixed cells to copy in one
        // move; a boolean cell is one of two boxes made once.
        private static object MixedOut(PyObject tuple, string name, WorkCounter work)
        {
            using (var kindsObject = tuple[0])
            using (var numbersObject = tuple[1])
            using (var textObject = tuple[2])
            {
                PyBuffer kinds;
                try
                {
                    kinds = kindsObject.GetBuffer(PyBUF.CONTIG_RO);
                }
                catch (PythonException)
                {
                    return "#ERROR host: " + name + " returned a mixed array whose kinds give no buffer";
                }
                using (kinds)
                {
                    if (kinds.Dimensions != 2 || kinds.ItemSize != sizeof(byte))
                    {
                        return "#ERROR host: " + name + " returned a mixed array whose kinds are not bytes in two dimensions";
                    }
                    var rows = (int)kinds.Shape[0];
                    var cols = (int)kinds.Shape[1];
                    var cells = (long)rows * cols;
                    PyBuffer numbers;
                    try
                    {
                        numbers = numbersObject.GetBuffer(PyBUF.CONTIG_RO);
                    }
                    catch (PythonException)
                    {
                        return "#ERROR host: " + name + " returned a mixed array whose numbers give no buffer";
                    }
                    using (numbers)
                    {
                        if (numbers.Dimensions != 2 || numbers.ItemSize != sizeof(double) || numbers.Length != cells * sizeof(double))
                        {
                            return "#ERROR host: " + name + " returned a mixed array whose numbers are not " + rows + "x" + cols + " doubles";
                        }
                        var joined = textObject.As<string>();
                        var texts = joined.Length == 0 ? Array.Empty<string>() : joined.Split('\0');
                        var array = new object[rows, cols];
                        var text = 0;
                        long boxed = 0;
                        unsafe
                        {
                            var kind = (byte*)kinds.Buffer;
                            var number = (double*)numbers.Buffer;
                            var i = 0;
                            for (var r = 0; r < rows; r++)
                            {
                                for (var c = 0; c < cols; c++, i++)
                                {
                                    switch (kind[i])
                                    {
                                        case Number:
                                            array[r, c] = number[i];
                                            boxed++;
                                            break;
                                        case Text:
                                            if (text == texts.Length)
                                            {
                                                return "#ERROR host: " + name + " returned a mixed array with " + texts.Length + " texts for more text cells";
                                            }
                                            array[r, c] = texts[text++];
                                            break;
                                        case Boolean:
                                            array[r, c] = number[i] != 0.0 ? TrueBox : FalseBox;
                                            break;
                                        default:
                                            return "#ERROR host: " + name + " returned a mixed array with kind " + kind[i] + " at cell (" + (r + 1) + ", " + (c + 1) + ")";
                                    }
                                }
                            }
                        }
                        if (text != texts.Length)
                        {
                            return "#ERROR host: " + name + " returned a mixed array with " + texts.Length + " texts for " + text + " text cells";
                        }
                        work?.Hit("buffers_allocated");
                        work?.Hit("buffer_bytes", 8 * cells);  // the array of references, one slot per cell
                        work?.Hit("result_cells", cells);
                        work?.Hit("result_texts", text);
                        work?.Hit("result_boxes", boxed);
                        return array;
                    }
                }
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
            if (Bridge.ProbesLoaded) RegisterFloor();
        }

        // The floor is a probe, written here because it has no Python: Excel is told of it where
        // the probes were loaded and nowhere else, as a method, the way a marked one is exported.
        private static void RegisterFloor()
        {
            ExcelIntegration.RegisterMethods(
                new List<MethodInfo> { typeof(Floor).GetMethod(nameof(Floor.HostAdd)) },
                new List<object> { new ExcelFunctionAttribute { Name = nameof(Floor.HostAdd), IsHidden = true, Description = Floor.Description } },
                new List<List<object>> { new List<object> { new ExcelArgumentAttribute { Name = "a" }, new ExcelArgumentAttribute { Name = "b" } } });
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
                    var publishes = spec[4].As<bool>();

                    // A creator's call is observed, so Excel's live-data subscription owns its
                    // publication; every other function takes the plain path.
                    delegates.Add(publishes
                        ? MakeObservedDelegate(Bridge.PreparePublisher(name), arguments.Count)
                        : MakeDelegate(Bridge.Prepare(name), arguments.Count));
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

        // The same delegate for a creator, handing its arguments to the observed path.
        internal static Delegate MakeObservedDelegate(Prepared prepared, int parameterCount)
        {
            var parameters = new ParameterExpression[parameterCount];
            for (var i = 0; i < parameterCount; i++)
            {
                parameters[i] = Expression.Parameter(typeof(object), "arg" + i);
            }
            var call = Expression.Call(
                typeof(Lifetime).GetMethod(nameof(Lifetime.Observe), new[] { typeof(Prepared), typeof(object[]) }),
                Expression.Constant(prepared),
                Expression.NewArrayInit(typeof(object), parameters));
            return Expression.Lambda(call, parameters).Compile();
        }
    }

    /// <summary>Always registered, even when Python failed to start, so the failure is visible.</summary>
    public static class Status
    {
        [ExcelFunction(Description = "Reports whether Python started, and the error if it did not.")]
        public static string CatalystStatus()
        {
            return Bridge.StartupError ?? "ok: python started and functions registered";
        }

        [ExcelFunction(IsHidden = true, Description = "Reports the handle store's live count and what the observed path did: published, reused, released.")]
        public static string CatalystHandles()
        {
            var (live, priceBytes) = Bridge.LiveHandles();
            return Lifetime.Report(live, priceBytes);
        }
    }

    /// <summary>
    /// The floor under every probe: a function with the host's argument shape and no Python, so
    /// what Excel and Excel-DNA charge for a call is measured beside what the seam adds. Hidden
    /// from the function wizard like the probes, and like them no part of an end user's build:
    /// it carries no export mark, so only the registration that follows the probes names it.
    /// </summary>
    public static class Floor
    {
        public const string Description = "Probe: a number in and out with no Python; the Excel-DNA floor.";

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
