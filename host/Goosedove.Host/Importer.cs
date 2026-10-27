using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using ExcelDna.Integration;

namespace Goosedove.Host
{
    /// <summary>
    /// The import command, GoosedoveImportTrades on Ctrl+Shift+F, docs/library/importer/import-trades.md,
    /// built from the ticket import-cleared-futures.md as its first slice. On Excel's main thread,
    /// in the command's own macro context, it reads the active workbook's configuration through the
    /// object model: the Tables import_settings and import_destinations, the trade_id column of
    /// every Table the destinations name, and the named cell import_status. It then hands the
    /// endpoint, the filter and the IDs beside their Tables' names to the seam's one entry for it,
    /// _ImportTradeIds, on a thread of its own, so Excel stays free while the request waits, and
    /// writes what comes back into the status cell through QueueAsMacro, the one way back onto
    /// Excel's thread. Its own refusals, a name missing or a cell it will not hand over, are
    /// written in the form a cell shows a failure, "#ERROR GoosedoveImportTrades: ..."; with the
    /// status cell itself missing, or refusing a write, a protected sheet say, the one line goes
    /// to Excel's status bar, the cause after it in the second case and cut to the 255 characters
    /// the bar takes, so no run ends in silence. The host checks no meaning: it tells one kind of
    /// cell from another, as its scan does, and the seam and the library judge the rest.
    /// </summary>
    public static class Importer
    {
        public const string Command = "GoosedoveImportTrades";
        public const string Entry = "_ImportTradeIds";
        public const string SettingsTable = "import_settings";
        public const string DestinationsTable = "import_destinations";
        public const string StatusName = "import_status";
        public const string IdColumn = "trade_id";

        /// <summary>The seam's entry, fetched once at start as every function's path is.</summary>
        internal static Prepared Path;

        private static int running;  // 1 from a run's first write to its last

        /// <summary>
        /// Ctrl+Shift+F: Excel's own key notation in the attribute, the caret for Ctrl and the
        /// capital for Shift, as Excel-DNA's template binds Ctrl+Shift+D with "^D".
        /// </summary>
        [ExcelCommand(ShortCut = "^F", Description = "Asks the API named in import_settings for today's cleared futures and writes in import_status what a run would fetch and where the walk stopped; Ctrl+Shift+F.")]
        public static void GoosedoveImportTrades()
        {
            dynamic application = ExcelDnaUtil.Application;
            dynamic status = null;
            try
            {
                dynamic book = application.ActiveWorkbook;
                if (book == null)
                {
                    throw new Refusal("no workbook is open");
                }
                status = StatusCell(book);
                if (Path == null)
                {
                    Write(application, status, "#ERROR python did not start: " + Bridge.StartupError, "nothing was fetched");
                    return;
                }
                var request = Read(book);
                if (Interlocked.CompareExchange(ref running, 1, 0) != 0)
                {
                    throw new Refusal("a run is in progress; its line replaces this one when it ends");
                }
                try
                {
                    // The progress text first: a cell that will not take it, a protected sheet
                    // say, stops the run here, before any request, the cause on the status bar.
                    if (!Write(application, status, "fetching trade IDs from " + request.Endpoint + " ...", "nothing was fetched"))
                    {
                        Volatile.Write(ref running, 0);
                        return;
                    }
                    Start(request, application, status);
                }
                catch
                {
                    Volatile.Write(ref running, 0);
                    throw;
                }
            }
            catch (Refusal refusal)
            {
                var text = "#ERROR " + Command + ": " + refusal.Message;
                Write(application, status, text, "the refusal: " + text);
            }
            catch (Exception failure)
            {
                // Excel's object model refusing something on the way: reported where every run
                // reports, never swallowed, since a command has no cell of its own to fail into.
                var text = "#ERROR host: " + failure.Message;
                Write(application, status, text, "the failure: " + text);
            }
        }

        /// <summary>What one run hands the seam: the two settings as their cells hold them, and the IDs beside their Tables' names.</summary>
        internal sealed class Request
        {
            public object Endpoint;
            public object Filter;
            public readonly List<double> Ids = new List<double>();
            public readonly List<string> Tables = new List<string>();
        }

        /// <summary>The host's own refusal, in words for the status cell.</summary>
        internal sealed class Refusal : Exception
        {
            public Refusal(string message) : base(message)
            {
            }
        }

        // The named cell the run writes into: one cell, by the workbook-level name.
        private static dynamic StatusCell(dynamic book)
        {
            dynamic name;
            try
            {
                name = book.Names.Item(StatusName);
            }
            catch (Exception)
            {
                throw new Refusal("the workbook has no name " + StatusName);
            }
            dynamic range;
            try
            {
                range = name.RefersToRange;
            }
            catch (Exception)
            {
                throw new Refusal(StatusName + " does not refer to a cell");
            }
            int count = range.Count;
            if (count != 1)
            {
                throw new Refusal(StatusName + " refers to " + count + " cells, expected one");
            }
            return range;
        }

        // The text into the status cell, true when the cell took it. Onto Excel's status bar when
        // there is no cell to take it, the name missing, or when the cell will not, a protected
        // sheet say, then with the words given for what the text was and the cause, so that no run
        // ends in silence and no progress text stands for a result unexplained.
        private static bool Write(dynamic application, dynamic status, string text, string otherwise)
        {
            if (status == null)
            {
                StatusBar(application, text);
                return true;
            }
            try
            {
                status.Value2 = text;
                return true;
            }
            catch (Exception failure)
            {
                StatusBar(application, Unwritten(otherwise, failure.Message));
                return false;
            }
        }

        /// <summary>Excel's status bar takes 255 characters and refuses a longer text.</summary>
        internal const int StatusBarLimit = 255;

        // Onto Excel's status bar, within what it takes: a longer text is cut there and the cut
        // marked, since the bar refusing it would leave a run's last word unsaid, and from the
        // callback on Excel's thread unsaid to anyone.
        private static void StatusBar(dynamic application, string text)
        {
            application.StatusBar = Bounded(text);
        }

        internal static string Bounded(string text)
        {
            return text.Length <= StatusBarLimit ? text : text.Substring(0, StatusBarLimit - 3) + "...";
        }

        /// <summary>
        /// The status bar's line for a cell that would not take a write: the failure, then what the
        /// text was, the run's line say, then Excel's cause, so that the cut the bar's limit makes
        /// takes the cause's tail before anything a person needs.
        /// </summary>
        internal static string Unwritten(string otherwise, string cause)
        {
            return "#ERROR " + Command + ": " + StatusName + " could not be written; " + otherwise + "; the cause: " + cause;
        }

        // The configuration off the active workbook's Tables, each read once, in the order the
        // destinations name them.
        internal static Request Read(dynamic book)
        {
            var request = new Request();
            dynamic settings = Table(book, SettingsTable, "the workbook has no Table " + SettingsTable);
            Settings(request, Headers(settings), Body(settings));
            dynamic destinations = Table(book, DestinationsTable, "the workbook has no Table " + DestinationsTable);
            foreach (var name in Destinations(Headers(destinations), Body(destinations)))
            {
                dynamic table = Table(book, name.Table, DestinationsTable + " row " + name.Row + " names " + name.Table + ", which is not a Table in this workbook");
                TradeIds(name.Table, Headers(table), Body(table), request.Ids, request.Tables);
            }
            return request;
        }

        private static dynamic Table(dynamic book, string name, string refusal)
        {
            dynamic sheets = book.Worksheets;
            int count = sheets.Count;
            for (var s = 1; s <= count; s++)
            {
                dynamic tables = sheets.Item(s).ListObjects;
                int held = tables.Count;
                for (var t = 1; t <= held; t++)
                {
                    dynamic table = tables.Item(t);
                    if ((string)table.Name == name)
                    {
                        return table;
                    }
                }
            }
            throw new Refusal(refusal);
        }

        private static object[,] Headers(dynamic table)
        {
            return Grid(table.HeaderRowRange.Value2);
        }

        // The Table's rows, or null for a Table with none: Excel has no body range then.
        private static object[,] Body(dynamic table)
        {
            dynamic body = table.DataBodyRange;
            return body == null ? null : Grid(body.Value2);
        }

        // Excel hands one cell's value as the value itself and several as a rectangle, and the
        // object model's rectangle counts from 1 where Excel-DNA's arguments count from 0; every
        // reader here takes a rectangle counted from 0, so the one from 1 is copied once.
        internal static object[,] Grid(object value)
        {
            if (value is object[,] grid)
            {
                var firstRow = grid.GetLowerBound(0);
                var firstColumn = grid.GetLowerBound(1);
                if (firstRow == 0 && firstColumn == 0)
                {
                    return grid;
                }
                var rows = grid.GetLength(0);
                var columns = grid.GetLength(1);
                var fromZero = new object[rows, columns];
                for (var r = 0; r < rows; r++)
                {
                    for (var c = 0; c < columns; c++)
                    {
                        fromZero[r, c] = grid[r + firstRow, c + firstColumn];
                    }
                }
                return fromZero;
            }
            var one = new object[1, 1];
            one[0, 0] = value;
            return one;
        }

        /// <summary>
        /// import_settings: the columns setting and value exactly, and one row each for endpoint
        /// and filter, whose values cross as their cells hold them for the seam to judge; an Excel
        /// error, which the object model hands over as a number, is refused here by name.
        /// </summary>
        internal static void Settings(Request request, object[,] headers, object[,] body)
        {
            var columns = Columns(SettingsTable, headers, "setting", "value");
            if (body == null)
            {
                throw new Refusal(SettingsTable + " has no rows, expected endpoint and filter");
            }
            var seen = new HashSet<string>();
            for (var r = 0; r < body.GetLength(0); r++)
            {
                var setting = body[r, columns[0]] as string;
                if (setting != "endpoint" && setting != "filter")
                {
                    throw new Refusal(SettingsTable + " row " + (r + 1) + " has setting " + Shown(body[r, columns[0]]) + ", expected endpoint or filter");
                }
                if (!seen.Add(setting))
                {
                    throw new Refusal(SettingsTable + " names " + setting + " twice, expected once");
                }
                var value = body[r, columns[1]];
                if (value is int)
                {
                    throw new Refusal(SettingsTable + " value of " + setting + " is an Excel error, expected text");
                }
                if (setting == "endpoint")
                {
                    request.Endpoint = value;
                }
                else
                {
                    request.Filter = value;
                }
            }
            foreach (var required in new[] { "endpoint", "filter" })
            {
                if (!seen.Contains(required))
                {
                    throw new Refusal(SettingsTable + " has no row " + required + ", expected endpoint and filter");
                }
            }
        }

        /// <summary>One row of import_destinations: the Table it names and its row, for the refusal.</summary>
        internal struct Destination
        {
            public int Row;
            public string Table;
        }

        /// <summary>
        /// import_destinations: the columns index, clearing_house and table exactly, and in each row
        /// the Table's name as text; the index and the clearing house are the second slice's to read.
        /// A Table named by two rows is read once, in the order of its first.
        /// </summary>
        internal static List<Destination> Destinations(object[,] headers, object[,] body)
        {
            var columns = Columns(DestinationsTable, headers, "index", "clearing_house", "table");
            if (body == null)
            {
                throw new Refusal(DestinationsTable + " has no rows, expected one per index and clearing house");
            }
            var names = new List<Destination>();
            var seen = new HashSet<string>();
            for (var r = 0; r < body.GetLength(0); r++)
            {
                var table = body[r, columns[2]] as string;
                if (string.IsNullOrEmpty(table))
                {
                    throw new Refusal(DestinationsTable + " row " + (r + 1) + " has table " + Shown(body[r, columns[2]]) + ", expected a Table's name");
                }
                if (seen.Add(table))
                {
                    names.Add(new Destination { Row = r + 1, Table = table });
                }
            }
            return names;
        }

        /// <summary>
        /// A participating Table's trade_id column, read cell by cell into the IDs and, beside each,
        /// the Table's name: a number crosses, a blank holds no trade and is passed over, and a text,
        /// a boolean or an Excel error is refused by the Table and the row, since the column of
        /// every Table crosses as one and the seam's own words could name no Table.
        /// </summary>
        internal static void TradeIds(string name, object[,] headers, object[,] body, List<double> ids, List<string> tables)
        {
            var column = -1;
            for (var c = 0; c < headers.GetLength(1); c++)
            {
                if (Equals(headers[0, c], IdColumn))
                {
                    column = c;
                }
            }
            if (column < 0)
            {
                throw new Refusal(name + " has no column " + IdColumn);
            }
            if (body == null)
            {
                return;
            }
            for (var r = 0; r < body.GetLength(0); r++)
            {
                var cell = body[r, column];
                if (cell == null)
                {
                    continue;
                }
                if (cell is double number)
                {
                    ids.Add(number);
                    tables.Add(name);
                    continue;
                }
                throw new Refusal(name + " row " + (r + 1) + " " + IdColumn + " is " + Shown(cell) + ", expected number");
            }
        }

        // Each wanted header's column, the headers being exactly the wanted ones in any order.
        private static int[] Columns(string table, object[,] headers, params string[] wanted)
        {
            var found = new int[wanted.Length];
            var names = new List<string>();
            for (var c = 0; c < headers.GetLength(1); c++)
            {
                names.Add(headers[0, c] as string ?? Shown(headers[0, c]));
            }
            var exact = names.Count == wanted.Length;
            for (var w = 0; w < wanted.Length; w++)
            {
                found[w] = names.IndexOf(wanted[w]);
                exact &= found[w] >= 0;
            }
            if (!exact)
            {
                throw new Refusal(table + " has headers " + string.Join(", ", names) + ", expected " + Listed(wanted));
            }
            return found;
        }

        private static string Listed(string[] names)
        {
            return names.Length == 2
                ? names[0] + " and " + names[1]
                : string.Join(", ", names, 0, names.Length - 1) + " and " + names[names.Length - 1];
        }

        // A cell's kind and value in the seam's words, for a refusal; an Excel error arrives from
        // the object model as a number of the Int32 kind, which no cell's number ever is.
        internal static string Shown(object cell)
        {
            switch (cell)
            {
                case null:
                    return "blank";
                case string text:
                    return text.Length == 0 ? "empty text" : "text '" + text + "'";
                case double number:
                    return "number " + number.ToString("R", CultureInfo.InvariantCulture);
                case bool flag:
                    return "boolean " + (flag ? "TRUE" : "FALSE");
                case int _:
                    return "an Excel error";
                default:
                    return "a " + cell.GetType().Name;
            }
        }

        // The request on a thread of its own: the seam's entry takes Python's lock in turn with
        // any recalculation and lets it go while the network waits; the answer goes back onto
        // Excel's thread as a macro, the one place a cell may be written.
        private static void Start(Request request, dynamic application, dynamic status)
        {
            var thread = new Thread(() =>
            {
                string line;
                try
                {
                    line = Run(request);
                }
                catch (Exception failure)
                {
                    line = "#ERROR host: " + failure.Message;
                }
                try
                {
                    ExcelAsyncUtil.QueueAsMacro(() =>
                    {
                        // On Excel's thread, later: the cell, or the status bar with the line and
                        // the cause when the cell will not take the line now, within what the bar
                        // takes; nothing thrown here reaches anyone, and the run is over either way.
                        try
                        {
                            Write(application, status, line, "the run's line: " + line);
                        }
                        catch (Exception)
                        {
                        }
                        finally
                        {
                            Volatile.Write(ref running, 0);
                        }
                    });
                }
                catch (Exception)
                {
                    // Excel on its way out, or its queue gone: there is nowhere left to write.
                    Volatile.Write(ref running, 0);
                }
            })
            {
                IsBackground = true,
                Name = Command,
            };
            thread.Start();
        }

        /// <summary>
        /// The worker's work: the seam's line for the request, and this thread's set of the host's
        /// kept buffers let go once it is done, so a run leaves nothing pinned behind, however many
        /// run; a thread that ended without letting go would keep its set alive.
        /// </summary>
        internal static string Run(Request request)
        {
            try
            {
                return Line(request);
            }
            finally
            {
                Marshal.ReleaseBuffers();
            }
        }

        /// <summary>
        /// The seam's line for one request: the entry called as a worksheet function is, the two
        /// columns handed over as ranges or left out together when no Table holds an ID, and the
        /// text it returns, the run's line or its refusal in the form a cell shows.
        /// </summary>
        internal static string Line(Request request)
        {
            object ids = request.Ids.Count == 0 ? ExcelMissing.Value : Column(request.Ids);
            object tables = request.Tables.Count == 0 ? ExcelMissing.Value : Column(request.Tables);
            var result = Bridge.Call(Path, request.Endpoint, request.Filter, ids, tables);
            return result as string ?? "#ERROR host: " + Entry + " returned a " + result.GetType().Name + ", expected text";
        }

        private static object[,] Column<T>(List<T> cells)
        {
            var column = new object[cells.Count, 1];
            for (var i = 0; i < cells.Count; i++)
            {
                column[i, 0] = cells[i];
            }
            return column;
        }
    }
}
