using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using ExcelDna.Integration;
using Xunit;

namespace Goosedove.Host.Tests
{
    /// <summary>
    /// The import command's pieces that need no Excel, import-cleared-futures.md: the readers of
    /// the configuration Tables and of a participating Table's trade_id column, each refusal in
    /// its words, and the seam's line for a request, through the host's path against a stand-in
    /// answering on the loopback interface and against a port nobody listens on. The entry is
    /// prepared for the host and never told to Excel. Reading the Tables off a workbook and
    /// writing the status cell need Excel: tools/excel_lifetime.ps1, the import group.
    /// </summary>
    [Collection("python")]
    public class ImporterTests
    {
        public ImporterTests()
        {
            if (Importer.Path == null)
            {
                Importer.Path = Bridge.Prepare(Importer.Entry);
            }
        }

        private static object[,] Row(params object[] cells)
        {
            var row = new object[1, cells.Length];
            for (var i = 0; i < cells.Length; i++)
            {
                row[0, i] = cells[i];
            }
            return row;
        }

        private static object[,] Rows(int width, params object[] cells)
        {
            var grid = new object[cells.Length / width, width];
            for (var i = 0; i < cells.Length; i++)
            {
                grid[i / width, i % width] = cells[i];
            }
            return grid;
        }

        private static string Refused(Action action)
        {
            return Assert.Throws<Importer.Refusal>(action).Message;
        }

        [Fact]
        public void the_entry_is_prepared_for_the_host_and_never_told_to_excel()
        {
            var (_, attributes, _) = Registration.Describe();
            Assert.DoesNotContain(attributes, a => ((ExcelFunctionAttribute)a).Name == Importer.Entry);
            Assert.NotNull(Importer.Path);
        }

        // --- import_settings ----------------------------------------------------------------

        [Fact]
        public void the_settings_cross_as_their_cells_hold_them_in_any_row_order()
        {
            var request = new Importer.Request();
            Importer.Settings(request, Row("setting", "value"), Rows(2, "filter", "today", "endpoint", "http://api/ids"));
            Assert.Equal("http://api/ids", request.Endpoint);
            Assert.Equal("today", request.Filter);
            // A number or a blank crosses as it is, for the seam to refuse in its own words.
            Importer.Settings(request, Row("value", "setting"), Rows(2, 5.0, "endpoint", null, "filter"));
            Assert.Equal(5.0, request.Endpoint);
            Assert.Null(request.Filter);
        }

        [Fact]
        public void the_settings_refusals_name_the_table_the_row_and_what_was_expected()
        {
            var request = new Importer.Request();
            Assert.Equal("import_settings has headers setting, valeur, expected setting and value",
                Refused(() => Importer.Settings(request, Row("setting", "valeur"), Rows(2, "endpoint", "x"))));
            Assert.Equal("import_settings has headers setting, value, note, expected setting and value",
                Refused(() => Importer.Settings(request, Row("setting", "value", "note"), Rows(3, "endpoint", "x", "y"))));
            Assert.Equal("import_settings has no rows, expected endpoint and filter",
                Refused(() => Importer.Settings(request, Row("setting", "value"), null)));
            Assert.Equal("import_settings row 2 has setting text 'filtre', expected endpoint or filter",
                Refused(() => Importer.Settings(request, Row("setting", "value"), Rows(2, "endpoint", "x", "filtre", "y"))));
            Assert.Equal("import_settings row 1 has setting blank, expected endpoint or filter",
                Refused(() => Importer.Settings(request, Row("setting", "value"), Rows(2, null, "x"))));
            Assert.Equal("import_settings row 1 has setting number 3, expected endpoint or filter",
                Refused(() => Importer.Settings(request, Row("setting", "value"), Rows(2, 3.0, "x"))));
            Assert.Equal("import_settings names endpoint twice, expected once",
                Refused(() => Importer.Settings(request, Row("setting", "value"), Rows(2, "endpoint", "x", "endpoint", "y"))));
            Assert.Equal("import_settings has no row filter, expected endpoint and filter",
                Refused(() => Importer.Settings(request, Row("setting", "value"), Rows(2, "endpoint", "x"))));
            Assert.Equal("import_settings value of endpoint is an Excel error, expected text",
                Refused(() => Importer.Settings(request, Row("setting", "value"), Rows(2, "endpoint", -2146826246, "filter", "y"))));
        }

        // --- import_destinations ------------------------------------------------------------

        [Fact]
        public void the_destinations_name_each_table_once_in_the_order_of_its_first_row()
        {
            var names = Importer.Destinations(Row("index", "clearing_house", "table"),
                Rows(3, "WTI", "NYMEX", "Trades_NYMEX", "NG", "NYMEX", "Trades_NG", "WTI", "ICE", "Trades_NYMEX"));
            Assert.Equal(new[] { "Trades_NYMEX", "Trades_NG" }, names.ConvertAll(n => n.Table));
            Assert.Equal(new[] { 1, 2 }, names.ConvertAll(n => n.Row));
            var reordered = Importer.Destinations(Row("table", "index", "clearing_house"), Rows(3, "T", "WTI", "NYMEX"));
            Assert.Equal("T", reordered[0].Table);
        }

        [Fact]
        public void the_destinations_refusals_name_the_table_the_row_and_what_was_expected()
        {
            Assert.Equal("import_destinations has headers index, table, expected index, clearing_house and table",
                Refused(() => Importer.Destinations(Row("index", "table"), Rows(2, "WTI", "T"))));
            Assert.Equal("import_destinations has no rows, expected one per index and clearing house",
                Refused(() => Importer.Destinations(Row("index", "clearing_house", "table"), null)));
            Assert.Equal("import_destinations row 2 has table blank, expected a Table's name",
                Refused(() => Importer.Destinations(Row("index", "clearing_house", "table"), Rows(3, "WTI", "NYMEX", "T", "NG", "NYMEX", null))));
            Assert.Equal("import_destinations row 1 has table number 7, expected a Table's name",
                Refused(() => Importer.Destinations(Row("index", "clearing_house", "table"), Rows(3, "WTI", "NYMEX", 7.0))));
            Assert.Equal("import_destinations row 1 has table empty text, expected a Table's name",
                Refused(() => Importer.Destinations(Row("index", "clearing_house", "table"), Rows(3, "WTI", "NYMEX", ""))));
        }

        // --- a participating Table's trade_id column ------------------------------------------

        [Fact]
        public void the_ids_cross_beside_their_tables_name_with_blanks_passed_over()
        {
            var ids = new List<double>();
            var tables = new List<string>();
            Importer.TradeIds("Trades_NYMEX", Row("quantity", "trade_id"), Rows(2, 10.0, 104.0, 5.0, null, 7.0, 90.0), ids, tables);
            Importer.TradeIds("Trades_NG", Row("trade_id"), null, ids, tables);
            Importer.TradeIds("Trades_ICE", Row("trade_id"), Rows(1, new object[] { null }), ids, tables);
            Importer.TradeIds("Trades_CME", Row("trade_id"), Rows(1, 105.0), ids, tables);
            Assert.Equal(new[] { 104.0, 90.0, 105.0 }, ids);
            Assert.Equal(new[] { "Trades_NYMEX", "Trades_NYMEX", "Trades_CME" }, tables);
        }

        [Fact]
        public void a_cell_that_is_no_number_and_no_blank_is_refused_by_its_table_and_row()
        {
            var ids = new List<double>();
            var tables = new List<string>();
            Assert.Equal("Trades_NYMEX has no column trade_id",
                Refused(() => Importer.TradeIds("Trades_NYMEX", Row("id", "quantity"), Rows(2, 1.0, 2.0), ids, tables)));
            Assert.Equal("Trades_NYMEX row 2 trade_id is text 'abc', expected number",
                Refused(() => Importer.TradeIds("Trades_NYMEX", Row("trade_id"), Rows(1, 104.0, "abc"), ids, tables)));
            Assert.Equal("Trades_NYMEX row 1 trade_id is boolean TRUE, expected number",
                Refused(() => Importer.TradeIds("Trades_NYMEX", Row("trade_id"), Rows(1, true), ids, tables)));
            Assert.Equal("Trades_NYMEX row 3 trade_id is an Excel error, expected number",
                Refused(() => Importer.TradeIds("Trades_NYMEX", Row("trade_id"), Rows(1, 1.0, 2.0, -2146826246), ids, tables)));
            Assert.Equal("Trades_NYMEX row 1 trade_id is empty text, expected number",
                Refused(() => Importer.TradeIds("Trades_NYMEX", Row("trade_id"), Rows(1, ""), ids, tables)));
        }

        // --- the seam's line ---------------------------------------------------------------

        private static Importer.Request Request(string endpoint, params (double id, string table)[] held)
        {
            var request = new Importer.Request { Endpoint = endpoint, Filter = "today" };
            foreach (var (id, table) in held)
            {
                request.Ids.Add(id);
                request.Tables.Add(table);
            }
            return request;
        }

        [Fact]
        public void the_line_for_the_issues_table_through_the_hosts_path()
        {
            using (var standIn = new StandIn("[103, 105, 104]"))
            {
                var line = Importer.Line(Request(standIn.Address, (104.0, "Trades_NYMEX"), (90.0, "Trades_NYMEX")));
                Assert.Equal("3 IDs returned, 1 to fetch: 105; stopped at 104, held by Trades_NYMEX", line);
                Assert.StartsWith("POST /ids HTTP/1.1\r\n", standIn.Request);
                Assert.EndsWith("\r\n\r\ntoday", standIn.Request);
            }
            using (var standIn = new StandIn("[103, 105, 104]"))
            {
                Assert.Equal("3 IDs returned, 3 to fetch: 105, 104, 103; none held", Importer.Line(Request(standIn.Address)));
            }
        }

        [Fact]
        public void the_seams_and_the_librarys_refusals_come_back_as_the_line()
        {
            using (var standIn = new StandIn("[105, 104, 104]"))
            {
                Assert.Equal("#ERROR _ImportTradeIds: ValueError: the filter returned 104 more than once, expected each trade ID once",
                    Importer.Line(Request(standIn.Address)));
            }
            Assert.Equal("#ERROR _ImportTradeIds: endpoint is number 5.0, expected text", Importer.Line(new Importer.Request { Endpoint = 5.0, Filter = "today" }));
            Assert.Equal("#ERROR _ImportTradeIds: filter is blank, expected text", Importer.Line(new Importer.Request { Endpoint = "http://127.0.0.1:1/ids", Filter = null }));
            using (var standIn = new StandIn("[103, 105, 104]"))
            {
                Assert.Equal("#ERROR _ImportTradeIds: ValueError: Trades_NYMEX trade_id 2 is 90.5, expected a whole number of at most 15 digits",
                    Importer.Line(Request(standIn.Address, (104.0, "Trades_NYMEX"), (90.5, "Trades_NYMEX"))));
            }
        }

        [Fact]
        public void nobody_listening_is_the_line_too_with_the_address_and_the_cause()
        {
            // A port the system handed out and took back: nothing listens on it now.
            var probe = new TcpListener(IPAddress.Loopback, 0);
            probe.Start();
            var port = ((IPEndPoint)probe.LocalEndpoint).Port;
            probe.Stop();
            var endpoint = "http://127.0.0.1:" + port + "/ids";
            Assert.StartsWith("#ERROR _ImportTradeIds: ValueError: the filter request to " + endpoint + " failed: ", Importer.Line(Request(endpoint)));
        }

        // Excel's object model hands a range's values as a rectangle counted from 1, and one
        // cell's value as the value itself; the readers take a rectangle counted from 0.
        [Fact]
        public void a_rectangle_from_the_object_model_is_read_from_zero()
        {
            var fromOne = (object[,])Array.CreateInstance(typeof(object), new[] { 2, 2 }, new[] { 1, 1 });
            fromOne[1, 1] = "setting";
            fromOne[1, 2] = "value";
            fromOne[2, 1] = "endpoint";
            fromOne[2, 2] = "http://api/ids";
            var grid = Importer.Grid(fromOne);
            Assert.Equal(0, grid.GetLowerBound(0));
            Assert.Equal("http://api/ids", grid[1, 1]);
            Assert.Equal("setting", grid[0, 0]);
            var one = Importer.Grid(104.0);
            Assert.Equal(104.0, one[0, 0]);
            var fromZero = Row("a", "b");
            Assert.Same(fromZero, Importer.Grid(fromZero));
        }

        [Fact]
        public void a_cells_kind_in_the_seams_words()
        {
            Assert.Equal("blank", Importer.Shown(null));
            Assert.Equal("text 'x'", Importer.Shown("x"));
            Assert.Equal("empty text", Importer.Shown(""));
            Assert.Equal("number 2.5", Importer.Shown(2.5));
            Assert.Equal("boolean FALSE", Importer.Shown(false));
            Assert.Equal("an Excel error", Importer.Shown(-2146826281));
        }
    }

    /// <summary>
    /// A stand-in for the desk's API on the loopback interface: one connection, the request kept
    /// whole for the test to read, and one answer with the status and the JSON given.
    /// </summary>
    internal sealed class StandIn : IDisposable
    {
        private static readonly Regex Length = new Regex(@"Content-Length:\s*(\d+)", RegexOptions.IgnoreCase);
        private readonly TcpListener listener;
        private readonly string answer;
        public volatile string Request;

        public StandIn(string answer)
        {
            this.answer = answer;
            listener = new TcpListener(IPAddress.Loopback, 0);
            listener.Start();
            Address = "http://127.0.0.1:" + ((IPEndPoint)listener.LocalEndpoint).Port + "/ids";
            new Thread(Serve) { IsBackground = true }.Start();
        }

        public string Address { get; }

        private void Serve()
        {
            try
            {
                using (var client = listener.AcceptTcpClient())
                using (var stream = client.GetStream())
                {
                    var received = new MemoryStream();
                    var buffer = new byte[65536];
                    while (true)
                    {
                        var count = stream.Read(buffer, 0, buffer.Length);
                        if (count <= 0)
                        {
                            return;
                        }
                        received.Write(buffer, 0, count);
                        var text = Encoding.UTF8.GetString(received.ToArray());
                        var headersEnd = text.IndexOf("\r\n\r\n", StringComparison.Ordinal);
                        if (headersEnd < 0)
                        {
                            continue;
                        }
                        var length = Length.Match(text.Substring(0, headersEnd));
                        var body = length.Success ? int.Parse(length.Groups[1].Value) : 0;
                        if (received.Length >= headersEnd + 4 + body)
                        {
                            Request = text;
                            break;
                        }
                    }
                    var bytes = Encoding.UTF8.GetBytes(answer);
                    var head = Encoding.ASCII.GetBytes("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + bytes.Length + "\r\nConnection: close\r\n\r\n");
                    stream.Write(head, 0, head.Length);
                    stream.Write(bytes, 0, bytes.Length);
                }
            }
            catch (Exception)
            {
                // The listener stopped, or the client went: nothing more to serve.
            }
        }

        public void Dispose()
        {
            listener.Stop();
        }
    }
}
