using System.Collections.Generic;
using ExcelDna.Integration;
using Xunit;

namespace Goosedove.Host.Tests
{
    /// <summary>Whole calls through the host: the cell text or value Excel would show.</summary>
    [Collection("python")]
    public class CallTests
    {
        // The process ID that leads every handle: this test process's own, since Python runs inside it.
        private static readonly string Pid = System.Diagnostics.Process.GetCurrentProcess().Id.ToString();

        private static object[,] Column(params object[] cells)
        {
            var grid = new object[cells.Length, 1];
            for (var i = 0; i < cells.Length; i++)
            {
                grid[i, 0] = cells[i];
            }
            return grid;
        }

        // The index a calendar and futures fixings take: that schedule handle with that holiday
        // calendar handle, or none, over one set of conventions and specifications, since nothing
        // replayed here reads either.
        private static string Index(object schedule, object holidays, string name = "sample")
        {
            var conventions = Seam.Call("_CreateIndexConventions", "USD", "MMBTU", "USD", "ENERGY", "MMBTU");
            var specifications = Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0 } });
            var handle = (string)Seam.Call("_CreateIndex", name, schedule, conventions, specifications, holidays);
            Assert.StartsWith(Pid + ":index:" + name + ":", handle);
            return handle;
        }

        private static object[,] Row(params object[] cells)
        {
            var grid = new object[1, cells.Length];
            for (var i = 0; i < cells.Length; i++)
            {
                grid[0, i] = cells[i];
            }
            return grid;
        }

        // The toy table: a date, a text, a number and a flag per trade, three trades, with the
        // second quantity replaceable so one cell can be wrong.
        private static object[,] Trades(object secondQuantity = null)
        {
            return new object[,]
            {
                { 46276.0, "CL", 10.0, true },
                { 46277.0, "NG", secondQuantity ?? (object)3.5, false },
                { 46280.0, "CL", 7.0, true },
            };
        }

        // A curve's table: 11 to 13 September 2026 and a factor per day, the first replaceable.
        private static object[,] Curve(double first = 1.0)
        {
            return new object[,]
            {
                { 46276.0, first },
                { 46277.0, 0.9999 },
                { 46278.0, 0.9998 },
            };
        }

        private static object[,] FirstColumns(object[,] grid, int cols)
        {
            var narrow = new object[grid.GetLength(0), cols];
            for (var r = 0; r < grid.GetLength(0); r++)
            {
                for (var c = 0; c < cols; c++)
                {
                    narrow[r, c] = grid[r, c];
                }
            }
            return narrow;
        }

        // The rows of tools\excel_smoke.ps1, without Excel; the spilled ones are the tests below.
        public static IEnumerable<object[]> SmokeRows()
        {
            yield return new object[] { "Zero", new object[] { }, 0.0 };
            yield return new object[] { "Add", new object[] { 1.0, 2.0 }, 3.0 };
            yield return new object[] { "Add", new object[] { 1.0, ExcelMissing.Value }, "#ERROR Add: b is missing, expected number" };
            yield return new object[] { "Add", new object[] { 1.0, true }, "#ERROR Add: b is boolean TRUE, expected number" };
            yield return new object[] { "Times", new object[] { 5.0, ExcelMissing.Value }, 5.0 };
            yield return new object[] { "Times", new object[] { 5.0, 2.0 }, 10.0 };
            yield return new object[] { "Times", new object[] { 5.0, ExcelEmpty.Value }, "#ERROR Times: factor is blank, expected number" };
            yield return new object[] { "EchoText", new object[] { "x" }, "x" };
            yield return new object[] { "EchoText", new object[] { "" }, "#ERROR EchoText: label is empty text, expected text" };
            yield return new object[] { "EchoBoolean", new object[] { true }, true };
            yield return new object[] { "EchoBoolean", new object[] { 1.0 }, "#ERROR EchoBoolean: flag is number 1.0, expected boolean" };
            yield return new object[] { "SumArray", new object[] { Column(1.0, 2.0, 3.0) }, 6.0 };
            yield return new object[] { "SumArray", new object[] { 1.0 }, 1.0 };
            yield return new object[] { "SumArray", new object[] { Column("n/a", 2.0, 3.0) }, "#ERROR SumArray: values cell (1, 1) is text 'n/a', expected number" };
            yield return new object[] { "SumArray", new object[] { Column(1.0, ExcelEmpty.Value, 3.0) }, "#ERROR SumArray: values cell (2, 1) is blank, expected number" };
            yield return new object[] { "SumArray", new object[] { Column(1.0, ExcelError.ExcelErrorNA, 3.0) }, ExcelError.ExcelErrorNA };
            yield return new object[] { "SumArray", new object[] { Column("x", ExcelError.ExcelErrorNA) }, ExcelError.ExcelErrorNA };
            yield return new object[] { "SumArray", new object[] { Column(1.0, true) }, "#ERROR SumArray: values cell (2, 1) is boolean TRUE, expected number" };
            yield return new object[] { "CountArray", new object[] { Column(1.0, 2.0, 3.0) }, 3.0 };
            yield return new object[] { "CountArray", new object[] { Column("n/a", 2.0) }, "#ERROR CountArray: values cell (1, 1) is text 'n/a', expected number" };
            // A mixed range takes the three kinds that hold a value, in any combination.
            yield return new object[] { "CountMixed", new object[] { Column("CL", 46164.0, true) }, 3.0 };
            yield return new object[] { "CountMixed", new object[] { Column(1.0, 2.0) }, 2.0 };
            yield return new object[] { "CountMixed", new object[] { "CL" }, 1.0 };
            yield return new object[] { "CountMixed", new object[] { Column(1.0, ExcelEmpty.Value) }, "#ERROR CountMixed: values cell (2, 1) is blank, expected number, nonempty text or boolean" };
            yield return new object[] { "CountMixed", new object[] { Column("CL", "") }, "#ERROR CountMixed: values cell (2, 1) is empty text, expected number, nonempty text or boolean" };
            // An Excel error anywhere still wins, before the mixed rule ever runs.
            yield return new object[] { "CountMixed", new object[] { Column("CL", ExcelError.ExcelErrorNA) }, ExcelError.ExcelErrorNA };
            // A table: a header row and a mixed body, bound by name into typed columns.
            yield return new object[] { "SumQuantity", new object[] { Row("date", "product", "quantity", "cleared"), Trades() }, 20.5 };
            yield return new object[] { "SumQuantity", new object[] { Row("DATE", "PRODUCT", "QUANTITY", "CLEARED"), Trades() }, 20.5 };
            yield return new object[] { "SumQuantity", new object[] { Row("date", "ticker", "quantity", "cleared"), Trades() }, "#ERROR SumQuantity: header_row cell (1, 2) is text 'ticker', expected one of date, product, quantity or cleared" };
            yield return new object[] { "SumQuantity", new object[] { Row("date", "product", "quantity", "cleared"), FirstColumns(Trades(), 3) }, "#ERROR SumQuantity: header_row has 4 headers, expected 3, one per column of trades" };
            yield return new object[] { "SumQuantity", new object[] { Row("date", "product", "quantity", "cleared"), Trades("seven") }, "#ERROR SumQuantity: trades cell (2, 3) is text 'seven', expected number" };
            yield return new object[] { "Dot", new object[] { Column(1.0, 2.0, 3.0), Column(10.0, 20.0, 30.0) }, 140.0 };
            yield return new object[] { "Dot", new object[] { Column(1.0, 2.0, 3.0), Row(10.0, 20.0, 30.0) }, "#ERROR Dot: b is 1x3 array, expected column of numbers" };
            yield return new object[] { "Grid", new object[] { 2.5, 3.0 }, "#ERROR Grid: rows is number 2.5, expected whole number" };
            yield return new object[] { "Fail", new object[] { }, "#ERROR Fail: ValueError: as asked" };
            // Handles: a creator's own rule, a curve that cannot be made, and text naming no live object.
            yield return new object[] { "_CreateValuationDate", new object[] { 46276.0, 1.5 }, "#ERROR _CreateValuationDate: ValueError: day_fraction_elapsed is number 1.5, expected a number from 0 to 1" };
            yield return new object[] { "_CreateDiscountCurve", new object[] { Row("date", "discount_factor"), Curve(0.98) }, "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date" };
            // The curve from anchors: dates that run backwards are never sorted, and a span no sheet could show is refused.
            yield return new object[] { "_CreateDiscountCurve", new object[] { Row("date", "discount_factor"), new object[,] { { 46279.0, 1.0 }, { 46276.0, 0.9997 } } }, "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 2026-09-11, expected a date after row 1's 2026-09-14" };
            yield return new object[] { "_CreateDiscountCurve", new object[] { Row("date", "discount_factor"), new object[,] { { 46276.0, 1.0 }, { 1094850.0, 0.5 } } }, "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 4897-08-04, expected within 1048573 days of row 1's 2026-09-11" };
            yield return new object[] { "util_ReadHandle", new object[] { "x" }, "#ERROR util_ReadHandle: handle is text 'x' naming no live object, expected a handle" };
            yield return new object[] { "util_ReadHandle", new object[] { 46276.0 }, "#ERROR util_ReadHandle: handle is number 46276.0, expected a handle" };
            // The prompt reader: one calendar handle. Left out, a number and text naming no live object fail in the seam's words; the live calendars are in the calendar fact below.
            yield return new object[] { "util_ReadPrompt", new object[] { ExcelMissing.Value }, "#ERROR util_ReadPrompt: calendar is missing, expected calendar handle" };
            yield return new object[] { "util_ReadPrompt", new object[] { 46276.0 }, "#ERROR util_ReadPrompt: calendar is number 46276.0, expected calendar handle" };
            yield return new object[] { "util_ReadPrompt", new object[] { "x" }, "#ERROR util_ReadPrompt: calendar is text 'x' naming no live object, expected calendar handle" };
            // The two text helpers: a contract code in, text out. The next month in the exchanges' sequence, spelled as the code given, and the month as CME's feeds spell it; a strip, a four-digit year and December 2099 fail in the library's words, a number, a blank and empty text in the seam's.
            yield return new object[] { "util_NextFut", new object[] { "F26" }, "G26" };
            yield return new object[] { "util_NextFut", new object[] { "Z26" }, "F27" };
            yield return new object[] { "util_NextFut", new object[] { "m26" }, "n26" };
            yield return new object[] { "util_NextFut", new object[] { "Cal27" }, "#ERROR util_NextFut: ValueError: contract is 'Cal27', expected a month letter and a two-digit year, such as F26" };
            yield return new object[] { "util_NextFut", new object[] { "Z99" }, "#ERROR util_NextFut: ValueError: contract is 'Z99', expected a month before December 2099, the last a two-digit year can name" };
            yield return new object[] { "util_NextFut", new object[] { 26.0 }, "#ERROR util_NextFut: contract is number 26.0, expected text" };
            yield return new object[] { "util_NextFut", new object[] { ExcelEmpty.Value }, "#ERROR util_NextFut: contract is blank, expected text" };
            yield return new object[] { "util_FutToCme", new object[] { "F26" }, "202601" };
            yield return new object[] { "util_FutToCme", new object[] { "Z26" }, "202612" };
            yield return new object[] { "util_FutToCme", new object[] { "u26" }, "202609" };
            yield return new object[] { "util_FutToCme", new object[] { "F2026" }, "#ERROR util_FutToCme: ValueError: contract is 'F2026', expected a month letter and a two-digit year, such as F26" };
            yield return new object[] { "util_FutToCme", new object[] { "" }, "#ERROR util_FutToCme: contract is empty text, expected text" };
            yield return new object[] { "util_FutToCme", new object[] { ExcelMissing.Value }, "#ERROR util_FutToCme: contract is missing, expected text" };
            // The two date helpers: a day in and the code of its month out, in capitals; a code in and the first day of its month out, a serial. A day outside the years two digits name and a strip fail in the library's words, a serial with a time, text and a blank in the seam's.
            yield return new object[] { "util_DateToFut", new object[] { 46161.0 }, "K26" };
            yield return new object[] { "util_DateToFut", new object[] { 46387.0 }, "Z26" };
            yield return new object[] { "util_DateToFut", new object[] { 73051.0 }, "#ERROR util_DateToFut: ValueError: date is 2100-01-01, expected a day from 2000 to 2099, the years a two-digit code can name" };
            yield return new object[] { "util_DateToFut", new object[] { 46161.5 }, "#ERROR util_DateToFut: date is number 46161.5, expected date" };
            yield return new object[] { "util_DateToFut", new object[] { "19-May-2026" }, "#ERROR util_DateToFut: date is text '19-May-2026', expected date" };
            yield return new object[] { "util_DateToFut", new object[] { ExcelEmpty.Value }, "#ERROR util_DateToFut: date is blank, expected date" };
            yield return new object[] { "util_FutToDate", new object[] { "F26" }, 46023.0 };
            yield return new object[] { "util_FutToDate", new object[] { "n26" }, 46204.0 };
            yield return new object[] { "util_FutToDate", new object[] { "W29" }, "#ERROR util_FutToDate: ValueError: contract is 'W29', expected a month letter and a two-digit year, such as F26" };
            yield return new object[] { "util_FutToDate", new object[] { ExcelMissing.Value }, "#ERROR util_FutToDate: contract is missing, expected text" };
            // The two period functions: a contract or strip label in, in any case, and its first or last calendar day out as a serial; a month, a quarter, a year, a winter across the year end, a summer and a range. A malformed label and a reversed range fail in the library's words from either reader, a number and empty text in the seam's.
            yield return new object[] { "util_StartDate", new object[] { "f26" }, 46023.0 };
            yield return new object[] { "util_EndDate", new object[] { "f26" }, 46053.0 };
            yield return new object[] { "util_StartDate", new object[] { "1Q27" }, 46388.0 };
            yield return new object[] { "util_EndDate", new object[] { "1Q27" }, 46477.0 };
            yield return new object[] { "util_StartDate", new object[] { "cal28" }, 46753.0 };
            yield return new object[] { "util_EndDate", new object[] { "CAL28" }, 47118.0 };
            yield return new object[] { "util_StartDate", new object[] { "W29" }, 47423.0 };
            yield return new object[] { "util_EndDate", new object[] { "W29" }, 47573.0 };
            yield return new object[] { "util_StartDate", new object[] { "s28" }, 46844.0 };
            yield return new object[] { "util_EndDate", new object[] { "s28" }, 47057.0 };
            yield return new object[] { "util_StartDate", new object[] { "F26-Z28" }, 46023.0 };
            yield return new object[] { "util_EndDate", new object[] { "F26-Z28" }, 47118.0 };
            yield return new object[] { "util_EndDate", new object[] { "w28-w29" }, 47573.0 };
            yield return new object[] { "util_StartDate", new object[] { "W8-W9" }, "#ERROR util_StartDate: ValueError: period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_EndDate", new object[] { "W8-W9" }, "#ERROR util_EndDate: ValueError: period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_StartDate", new object[] { "Z28-F26" }, "#ERROR util_StartDate: ValueError: period is 'Z28-F26', expected range endpoints in chronological order" };
            yield return new object[] { "util_EndDate", new object[] { "CAL28-F28" }, "#ERROR util_EndDate: ValueError: period is 'CAL28-F28', expected range endpoints in chronological order" };
            yield return new object[] { "util_StartDate", new object[] { 46023.0 }, "#ERROR util_StartDate: period is number 46023.0, expected text" };
            yield return new object[] { "util_EndDate", new object[] { "" }, "#ERROR util_EndDate: period is empty text, expected text" };
            // The instrument catalog's show: one exact name in. Another case, a blank, a number and a left-out name fail, the name in the library's words and the rest in the seam's; the spills are in the catalog fact below.
            yield return new object[] { "_ShowInstrument", new object[] { "Future" }, "#ERROR _ShowInstrument: ValueError: instrument is 'Future', expected one of: 'future'" };
            yield return new object[] { "_ShowInstrument", new object[] { ExcelEmpty.Value }, "#ERROR _ShowInstrument: instrument is blank, expected text" };
            yield return new object[] { "_ShowInstrument", new object[] { 1.0 }, "#ERROR _ShowInstrument: instrument is number 1.0, expected text" };
            yield return new object[] { "_ShowInstrument", new object[] { ExcelMissing.Value }, "#ERROR _ShowInstrument: instrument is missing, expected text" };
            // A row or rows of an instrument's fields, through the two probes: the name in another case in the library's words, then the width, the headers in input order, exact, and the cells column by column, in the seam's; a handle cell naming no live object; two rows where one is wanted.
            yield return new object[] { "CountFieldRows", new object[] { "future", Row("quantity", "fixed_price"), new object[,] { { 1.0, 3.1 }, { 2.0, 3.2 }, { 3.0, 3.3 } } }, 3.0 };
            yield return new object[] { "EchoFieldRow", new object[] { "Future", Row("quantity"), 1.0 }, "#ERROR EchoFieldRow: ValueError: instrument is 'Future', expected one of: 'future'" };
            yield return new object[] { "EchoFieldRow", new object[] { "future", Row("quantity"), Row(1.0, 2.0) }, "#ERROR EchoFieldRow: fields has 1 headers, expected 2, one per column of values" };
            yield return new object[] { "EchoFieldRow", new object[] { "future", Row("Quantity"), 1.0 }, "#ERROR EchoFieldRow: fields cell (1, 1) is text 'Quantity', expected a field of future: trade_id, trade_date, contract_specification, contract_code, schedule_method, route, settlement_method, clearing_house, broker, quantity, quantity_unit, quantity_per, fixed_price, payment_time_lag, payment_holiday_calendar" };
            yield return new object[] { "EchoFieldRow", new object[] { "future", Row("quantity", "quantity"), Row(1.0, 2.0) }, "#ERROR EchoFieldRow: fields cell (1, 2) is text 'quantity', already given at cell (1, 1)" };
            yield return new object[] { "EchoFieldRow", new object[] { "future", Row("quantity", "fixed_price"), Row("ten", "eleven") }, "#ERROR EchoFieldRow: values cell (1, 1) is text 'ten', expected number" };
            yield return new object[] { "EchoFieldRow", new object[] { "future", Row("trade_date"), 46164.5 }, "#ERROR EchoFieldRow: values cell (1, 1) is number 46164.5, expected date" };
            yield return new object[] { "EchoFieldRow", new object[] { "future", Row("payment_holiday_calendar"), "x:holiday_calendar:9" }, "#ERROR EchoFieldRow: values cell (1, 1) is text 'x:holiday_calendar:9' naming no live object, expected holiday calendar handle" };
            yield return new object[] { "EchoFieldRow", new object[] { "future", Row("quantity"), Column(1.0, 2.0) }, "#ERROR EchoFieldRow: values is 2x1 array, expected one row of field values" };
            // The trade template: the name in another case in the library's words; two rows where one is wanted and a number where a code is expected in the seam's; a value against its field's own rule in the library's. The trades: the index and the template left out, and a text naming no live object, in the seam's words, before any binding; the batch itself is in the fact below.
            yield return new object[] { "_CreateTradeTemplate", new object[] { "Future", Row("quantity_unit"), "LOT" }, "#ERROR _CreateTradeTemplate: ValueError: instrument is 'Future', expected one of: 'future'" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "future", Row("quantity_unit"), Column("LOT", "LOT") }, "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "future", Row("quantity_unit"), 1.0 }, "#ERROR _CreateTradeTemplate: values cell (1, 1) is number 1.0, expected text" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "future", Row("quantity_unit", "schedule_method"), Row("LOT", "asian") }, "#ERROR _CreateTradeTemplate: ValueError: schedule_method is 'asian', expected lastday, the one method built" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "future", Row("payment_time_lag"), "+0bd" }, "#ERROR _CreateTradeTemplate: ValueError: payment_time_lag is '+0bd', expected a positive whole number of business days, such as +1bd" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "future", Row("quantity"), 1.5 }, "#ERROR _CreateTradeTemplate: ValueError: quantity is 1.5, expected a whole number of lots" };
            yield return new object[] { "_CreateTrades", new object[] { ExcelMissing.Value, Row("quantity"), 1.0, ExcelMissing.Value }, "#ERROR _CreateTrades: index is missing, expected index handle" };
            yield return new object[] { "_CreateTrades", new object[] { "x:index:gas:9", Row("quantity"), 1.0, "y:trade_template:9" }, "#ERROR _CreateTrades: index is text 'x:index:gas:9' naming no live object, expected index handle" };
            // The valuation path: the handles left out, naming nothing or of another kind, in the seam's words; the batch itself is in the fact below.
            yield return new object[] { "_PrepareTrades", new object[] { ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _PrepareTrades: trades is missing, expected trades handle" };
            yield return new object[] { "_PrepareTrades", new object[] { "x:trades:gas:9", "y:market_history:gas:9" }, "#ERROR _PrepareTrades: trades is text 'x:trades:gas:9' naming no live object, expected trades handle" };
            yield return new object[] { "_EvaluateTrades", new object[] { ExcelEmpty.Value, ExcelMissing.Value }, "#ERROR _EvaluateTrades: prepared is blank, expected prepared trades handle" };
            yield return new object[] { "_ReportValues", new object[] { 1.0 }, "#ERROR _ReportValues: results is number 1.0, expected trade results handle" };
            yield return new object[] { "_ReportRisk", new object[] { ExcelEmpty.Value }, "#ERROR _ReportRisk: results is blank, expected trade results handle" };
            // A creator's failure is relayed whole, and a relay of a relay shows the same text.
            yield return new object[] { "util_ReadHandle", new object[] { "#ERROR _CreateDiscountCurve: ValueError: x" }, "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" };
            yield return new object[] { "util_ReadHandle", new object[] { "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" }, "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" };
            // The futures schedule: a column of codes and up to two of dates, one row per code, the third column optional; a futures column one row short and a blank among the options.
            yield return new object[] { "_CreateFuturesSchedule", new object[] { Column("m26", "n26", "q26"), Column(46161.0, 46195.0), Column(46156.0, 46189.0, 46219.0) }, "#ERROR _CreateFuturesSchedule: ValueError: future_expiry has 2 dates, expected 3, one per contract_code" };
            yield return new object[] { "_CreateFuturesSchedule", new object[] { Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), Column(46156.0, ExcelEmpty.Value, 46219.0) }, "#ERROR _CreateFuturesSchedule: option_expiry cell (2, 1) is blank, expected date" };
            // The holiday calendar: one column of dates, a blank in it, and a row where a column is expected.
            yield return new object[] { "_CreateHolidayCalendar", new object[] { Column(46023.0, ExcelEmpty.Value, 46069.0) }, "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date" };
            yield return new object[] { "_CreateHolidayCalendar", new object[] { Row(46023.0, 46023.0) }, "#ERROR _CreateHolidayCalendar: holiday is 1x2 array, expected column of dates" };
            // The IFERC schedule: a last trading column one row short, the library's words; a blank among the publication dates, a number among the codes, the publication dates left out and a row where a column is expected, the seam's.
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", "X26", "Z26"), Column(46295.0, 46325.0), Column(46296.0, 46328.0, 46357.0) }, "#ERROR _CreateIfercSchedule: ValueError: last_trading_date has 2 dates, expected 3, one per contract_code" };
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", "X26"), Column(46295.0, 46325.0), Column(46296.0, ExcelEmpty.Value) }, "#ERROR _CreateIfercSchedule: publication_date cell (2, 1) is blank, expected date" };
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", 46023.0), Column(46295.0, 46325.0), Column(46296.0, 46328.0) }, "#ERROR _CreateIfercSchedule: contract_code cell (2, 1) is number 46023.0, expected text" };
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", "X26"), Column(46295.0, 46325.0), ExcelMissing.Value }, "#ERROR _CreateIfercSchedule: publication_date is missing, expected column of dates" };
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", "X26"), Row(46295.0, 46325.0), Column(46296.0, 46328.0) }, "#ERROR _CreateIfercSchedule: last_trading_date is 1x2 array, expected column of dates" };
            // The Gas Daily schedule: a first-date column one row short, the library's words; a blank among the last dates, a number among the codes, the last dates left out and a row where a column is expected, the seam's.
            yield return new object[] { "_CreateGasDailySchedule", new object[] { Column("U26", "V26", "X26"), Column(46266.0, 46296.0), Column(46295.0, 46326.0, 46356.0) }, "#ERROR _CreateGasDailySchedule: ValueError: first_date has 2 dates, expected 3, one per contract_code" };
            yield return new object[] { "_CreateGasDailySchedule", new object[] { Column("U26", "V26"), Column(46266.0, 46296.0), Column(46295.0, ExcelEmpty.Value) }, "#ERROR _CreateGasDailySchedule: last_date cell (2, 1) is blank, expected date" };
            yield return new object[] { "_CreateGasDailySchedule", new object[] { Column("U26", 46023.0), Column(46266.0, 46296.0), Column(46295.0, 46326.0) }, "#ERROR _CreateGasDailySchedule: contract_code cell (2, 1) is number 46023.0, expected text" };
            yield return new object[] { "_CreateGasDailySchedule", new object[] { Column("U26", "V26"), Column(46266.0, 46296.0), ExcelMissing.Value }, "#ERROR _CreateGasDailySchedule: last_date is missing, expected column of dates" };
            yield return new object[] { "_CreateGasDailySchedule", new object[] { Column("U26", "V26"), Row(46266.0, 46296.0), Column(46295.0, 46326.0) }, "#ERROR _CreateGasDailySchedule: first_date is 1x2 array, expected column of dates" };
            // The index conventions: five text scalars, a blank and a number where a code is expected, and a code left out.
            yield return new object[] { "_CreateIndexConventions", new object[] { "USD", "BBL", "USD", "VOLUME", ExcelEmpty.Value }, "#ERROR _CreateIndexConventions: quantity_unit is blank, expected text" };
            yield return new object[] { "_CreateIndexConventions", new object[] { "USD", "BBL", 1.0, "VOLUME", "BBL" }, "#ERROR _CreateIndexConventions: currency_unit is number 1.0, expected text" };
            yield return new object[] { "_CreateIndexConventions", new object[] { "USD", "BBL", "USD", "VOLUME", ExcelMissing.Value }, "#ERROR _CreateIndexConventions: quantity_unit is missing, expected text" };
            yield return new object[] { "_CreateIndexConventions", new object[] { "USD", "BBL", "USD", "Volume", "BBL" }, "#ERROR _CreateIndexConventions: ValueError: quantity_type is 'Volume', expected VOLUME, MASS or ENERGY" };
            yield return new object[] { "_CreateIndexConventions", new object[] { "USD", "MMBTU", "USD", "VOLUME", "BBL" }, "#ERROR _CreateIndexConventions: ValueError: quote_quantity_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3" };
            yield return new object[] { "_CreateIndexConventions", new object[] { "usd", "BBL", "USD", "VOLUME", "BBL" }, "#ERROR _CreateIndexConventions: ValueError: quote_currency_unit is 'usd', expected USD or CENT" };
            // The contract specifications: a header row and a table of words for a quantity; a lot size with a fraction, text where a fee is expected, a name given twice, and a unit that is no quantity unit.
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "usd", 3.0, 2.0 } } }, "#ERROR _CreateContractSpecifications: ValueError: lot_unit row 1 is 'usd', expected a VOLUME, MASS or ENERGY unit" };
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 2.5, "MMBTU", 3.0, 2.0 } } }, "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 2.5, expected a whole number" };
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "MMBTU", "three", 2.0 } } }, "#ERROR _CreateContractSpecifications: table cell (1, 4) is text 'three', expected number" };
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0 }, { "NYMEX NG", 2500.0, "MMBTU", 0.75, 0.5 } } }, "#ERROR _CreateContractSpecifications: ValueError: name row 2 is 'NYMEX NG', already given at row 1" };
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 0.0, "MMBTU", 3.0, 2.0 } } }, "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 0.0, expected 1 or more" };
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "MMBTU", -0.5, 2.0 } } }, "#ERROR _CreateContractSpecifications: ValueError: brokerage_rate_per_lot row 1 is -0.5, expected 0 or more" };
            // The index: text and four handles. A blank where the name should be, a number and text naming no live object where the schedule should be, and the specifications left out fail in the seam's words; the library's rules, which need live handles, are in the fact below.
            yield return new object[] { "_CreateIndex", new object[] { ExcelEmpty.Value, ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateIndex: name is blank, expected text" };
            yield return new object[] { "_CreateIndex", new object[] { "Henry Hub NYMEX", 46161.0, ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateIndex: schedule is number 46161.0, expected a handle" };
            yield return new object[] { "_CreateIndex", new object[] { "Henry Hub NYMEX", "x", ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateIndex: schedule is text 'x' naming no live object, expected a handle" };
            // The futures fixings: a column of days, a column of settles and the index by handle. The index left out, a number in its place and text naming no live object fail in the seam's words, as do a blank among the settles and a row where a column is expected; the library's rules, which need a live index, are in the fact below.
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Column(106.42, 101.94), ExcelMissing.Value }, "#ERROR _CreateFuturesFixings: index is missing, expected index handle" };
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Column(106.42, 101.94), 101.94 }, "#ERROR _CreateFuturesFixings: index is number 101.94, expected index handle" };
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Column(106.42, 101.94), "x" }, "#ERROR _CreateFuturesFixings: index is text 'x' naming no live object, expected index handle" };
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Column(106.42, ExcelEmpty.Value), "x" }, "#ERROR _CreateFuturesFixings: settle cell (2, 1) is blank, expected number" };
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Row(106.42, 101.94), "x" }, "#ERROR _CreateFuturesFixings: settle is 1x2 array, expected column of numbers" };
            // The IFERC fixings: a column of contract codes, a column of indices and the index by handle. A blank among the prices, a number among the codes, the prices left out, the index left out or a number in its place, and a row where a column is expected fail in the seam's words; the library's rules, which need a live index, are in the fact below.
            yield return new object[] { "_CreateIfercFixings", new object[] { Column("F26", "G26"), Column(1.85, 2.10), ExcelMissing.Value }, "#ERROR _CreateIfercFixings: index is missing, expected index handle" };
            yield return new object[] { "_CreateIfercFixings", new object[] { Column("F26", "G26"), Column(1.85, 2.10), 1.85 }, "#ERROR _CreateIfercFixings: index is number 1.85, expected index handle" };
            yield return new object[] { "_CreateIfercFixings", new object[] { Column("F26", "G26"), Column(1.85, ExcelEmpty.Value), ExcelMissing.Value }, "#ERROR _CreateIfercFixings: price cell (2, 1) is blank, expected number" };
            yield return new object[] { "_CreateIfercFixings", new object[] { Column("F26", 46027.0), Column(1.85, 2.10), ExcelMissing.Value }, "#ERROR _CreateIfercFixings: contract_code cell (2, 1) is number 46027.0, expected text" };
            yield return new object[] { "_CreateIfercFixings", new object[] { Column("F26", "G26"), ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateIfercFixings: price is missing, expected column of numbers" };
            yield return new object[] { "_CreateIfercFixings", new object[] { Column("F26", "G26"), Row(1.85, 2.10), ExcelMissing.Value }, "#ERROR _CreateIfercFixings: price is 1x2 array, expected column of numbers" };
            // The Gas Daily fixings: a column of flow days, a column of midpoints and the index by handle. A blank among the prices, text among the days, the prices left out, the index left out or a number in its place, and a row where a column is expected fail in the seam's words; the library's rules, which need a live index, are in the fact below.
            yield return new object[] { "_CreateGasDailyFixings", new object[] { Column(46270.0, 46269.0), Column(2.875, 2.93), ExcelMissing.Value }, "#ERROR _CreateGasDailyFixings: index is missing, expected index handle" };
            yield return new object[] { "_CreateGasDailyFixings", new object[] { Column(46270.0, 46269.0), Column(2.875, 2.93), 2.93 }, "#ERROR _CreateGasDailyFixings: index is number 2.93, expected index handle" };
            yield return new object[] { "_CreateGasDailyFixings", new object[] { Column(46270.0, 46269.0), Column(2.875, ExcelEmpty.Value), ExcelMissing.Value }, "#ERROR _CreateGasDailyFixings: price cell (2, 1) is blank, expected number" };
            yield return new object[] { "_CreateGasDailyFixings", new object[] { Column(46270.0, "x"), Column(2.875, 2.93), ExcelMissing.Value }, "#ERROR _CreateGasDailyFixings: flow_date cell (2, 1) is text 'x', expected date" };
            yield return new object[] { "_CreateGasDailyFixings", new object[] { Column(46270.0, 46269.0), ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateGasDailyFixings: price is missing, expected column of numbers" };
            yield return new object[] { "_CreateGasDailyFixings", new object[] { Column(46270.0, 46269.0), Row(2.875, 2.93), ExcelMissing.Value }, "#ERROR _CreateGasDailyFixings: price is 1x2 array, expected column of numbers" };
            // The calendar: two handles, the valuation date and the index. A number, a missing argument and text naming no live object where the valuation date should be fail in the seam's words; the library's rules and the wrong kinds, which need live handles, are in the fact below.
            yield return new object[] { "_CreateCalendar", new object[] { 46167.0, ExcelMissing.Value }, "#ERROR _CreateCalendar: valuation_date is number 46167.0, expected valuation date handle" };
            yield return new object[] { "_CreateCalendar", new object[] { ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateCalendar: valuation_date is missing, expected valuation date handle" };
            yield return new object[] { "_CreateCalendar", new object[] { "x", ExcelMissing.Value }, "#ERROR _CreateCalendar: valuation_date is text 'x' naming no live object, expected valuation date handle" };
            // The market history: two handles, the calendar and the fixings of its market, any handle. A number, a missing argument and text naming no live object where the calendar should be fail in the seam's words; the library's rules and the wrong kinds, which need live handles, are in the facts below.
            yield return new object[] { "_CreateMarketHistory", new object[] { 46168.0, ExcelMissing.Value }, "#ERROR _CreateMarketHistory: calendar is number 46168.0, expected calendar handle" };
            yield return new object[] { "_CreateMarketHistory", new object[] { ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateMarketHistory: calendar is missing, expected calendar handle" };
            yield return new object[] { "_CreateMarketHistory", new object[] { "x", ExcelMissing.Value }, "#ERROR _CreateMarketHistory: calendar is text 'x' naming no live object, expected calendar handle" };
            // The price vector: one column of numbers. A row where a column is expected, a header taken with the prices, numeric text, a boolean, a blank and the column left out fail in the seam's words; an Excel error in the column is passed through, as any is.
            yield return new object[] { "_CreatePriceVector", new object[] { "sample", Row(74.25, 0.0, -0.5) }, "#ERROR _CreatePriceVector: prices is 1x3 array, expected column of numbers" };
            yield return new object[] { "_CreatePriceVector", new object[] { "sample", Column("price", 74.25) }, "#ERROR _CreatePriceVector: prices cell (1, 1) is text 'price', expected number" };
            yield return new object[] { "_CreatePriceVector", new object[] { "sample", Column(74.25, "74.25") }, "#ERROR _CreatePriceVector: prices cell (2, 1) is text '74.25', expected number" };
            yield return new object[] { "_CreatePriceVector", new object[] { "sample", Column(74.25, true) }, "#ERROR _CreatePriceVector: prices cell (2, 1) is boolean TRUE, expected number" };
            yield return new object[] { "_CreatePriceVector", new object[] { "sample", Column(74.25, ExcelEmpty.Value) }, "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number" };
            yield return new object[] { "_CreatePriceVector", new object[] { "sample", ExcelMissing.Value }, "#ERROR _CreatePriceVector: prices is missing, expected column of numbers" };
            yield return new object[] { "_CreatePriceVector", new object[] { ExcelMissing.Value, Column(74.25) }, "#ERROR _CreatePriceVector: index_name is missing, expected text" };
            yield return new object[] { "_CreatePriceVector", new object[] { ExcelEmpty.Value, Column(74.25) }, "#ERROR _CreatePriceVector: index_name is blank, expected text" };
            yield return new object[] { "_CreatePriceVector", new object[] { "", Column(74.25) }, "#ERROR _CreatePriceVector: index_name is empty text, expected text" };
            yield return new object[] { "_CreatePriceVector", new object[] { 74.25, Column(74.25) }, "#ERROR _CreatePriceVector: index_name is number 74.25, expected text" };
            yield return new object[] { "_CreatePriceVector", new object[] { true, Column(74.25) }, "#ERROR _CreatePriceVector: index_name is boolean TRUE, expected text" };
            yield return new object[] { "_CreatePriceVector", new object[] { Column("WTI NYMEX", "Brent"), Column(74.25) }, "#ERROR _CreatePriceVector: index_name is 2x1 array, expected text" };
            yield return new object[] { "_CreatePriceVector", new object[] { "sample", Column(74.25, ExcelError.ExcelErrorNA) }, ExcelError.ExcelErrorNA };
            // The market: two handles, the market history and the price vector. A number, a missing argument and text naming no live object where the history should be fail in the seam's words; the library's rules and the wrong kinds, which need live handles, are in the fact below.
            yield return new object[] { "_CreateMarket", new object[] { 72.10, ExcelMissing.Value }, "#ERROR _CreateMarket: market_history is number 72.1, expected market history handle" };
            yield return new object[] { "_CreateMarket", new object[] { ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateMarket: market_history is missing, expected market history handle" };
            yield return new object[] { "_CreateMarket", new object[] { "x", ExcelMissing.Value }, "#ERROR _CreateMarket: market_history is text 'x' naming no live object, expected market history handle" };
        }

        // A futures schedule: three columns make one, two make one for an index without options,
        // and util_ReadHandle spills each back, the options last when the schedule has them; each
        // creator call publishes its own handle.
        [Fact]
        public void a_futures_schedule_is_created_with_and_without_options()
        {
            var codes = Column("m26", "n26", "q26");
            var futures = Column(46161.0, 46195.0, 46224.0);
            var options = Column(46156.0, 46189.0, 46219.0);
            var withOptions = (string)Seam.Call("_CreateFuturesSchedule", codes, futures, options);
            var withoutOptions = (string)Seam.Call("_CreateFuturesSchedule", codes, futures, ExcelMissing.Value);
            Assert.StartsWith(Pid + ":futures_schedule:", withOptions);
            Assert.StartsWith(Pid + ":futures_schedule:", withoutOptions);
            Assert.NotEqual(withOptions, withoutOptions);
            var spill = (object[,])Seam.Call("util_ReadHandle", withOptions);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(3, spill.GetLength(1));
            Assert.Equal("contract_code", spill[0, 0]);
            Assert.Equal("option_expiry", spill[0, 2]);
            Assert.Equal("datetime64[D]", spill[1, 2]);
            Assert.Equal(46219.0, spill[4, 2]);
            var plain = (object[,])Seam.Call("util_ReadHandle", withoutOptions);
            Assert.Equal(2, plain.GetLength(1));
            Assert.Equal("future_expiry", plain[0, 1]);
            Assert.Equal(46161.0, plain[2, 1]);
        }

        // A holiday calendar: a column of dates makes one, a single cell makes one of one day, and
        // A row of the future's fields bound against the instrument named: the holiday calendar cell
        // resolved to the object behind the handle and echoed as the words of its kind, the date as
        // its serial, the number as itself, under the field names in the sheet's order.
        [Fact]
        public void a_row_of_fields_is_bound_against_the_instrument_named_and_its_handle_cell_resolved()
        {
            var calendar = (string)Seam.Call("_CreateHolidayCalendar", 46023.0);
            var headers = Row("quantity_unit", "payment_holiday_calendar", "trade_date", "quantity");
            var spill = (object[,])Seam.Call("EchoFieldRow", "future", headers, Row("LOT", calendar, 46164.0, 10.0));
            Assert.Equal(2, spill.GetLength(0));
            Assert.Equal(4, spill.GetLength(1));
            Assert.Equal("payment_holiday_calendar", spill[0, 1]);
            Assert.Equal("LOT", spill[1, 0]);
            Assert.Equal("a holiday calendar", spill[1, 1]);
            Assert.Equal(46164.0, spill[1, 2]);
            Assert.Equal(10.0, spill[1, 3]);
            var date = (string)Seam.Call("_CreateValuationDate", 46276.0, 0.5);
            Assert.Equal("#ERROR EchoFieldRow: values cell (1, 1) is valuation date handle '" + date + "', expected holiday calendar handle", Seam.Call("EchoFieldRow", "future", Row("payment_holiday_calendar"), date));
        }

        // The instrument catalog: the list spills a header and a row per instrument, two text columns;
        // the shown future spills seven rows by sixteen columns, the labels down the first column, the
        // fields across the first row and the required row booleans, every other cell text.
        [Fact]
        public void the_instrument_catalog_is_listed_and_the_future_shown()
        {
            var listed = (object[,])Seam.Call("_ListInstruments");
            Assert.Equal(2, listed.GetLength(0));
            Assert.Equal(2, listed.GetLength(1));
            Assert.Equal("instrument", listed[0, 0]);
            Assert.Equal("description", listed[0, 1]);
            Assert.Equal("future", listed[1, 0]);
            var shown = (object[,])Seam.Call("_ShowInstrument", "future");
            Assert.Equal(7, shown.GetLength(0));
            Assert.Equal(16, shown.GetLength(1));
            Assert.Equal("field", shown[0, 0]);
            Assert.Equal("trade_id", shown[0, 1]);
            Assert.Equal("payment_holiday_calendar", shown[0, 15]);
            Assert.Equal("required", shown[2, 0]);
            Assert.Equal(false, shown[2, 1]);
            Assert.Equal(true, shown[2, 2]);
            Assert.Equal("route = cleared", shown[3, 8]);
            Assert.Equal("holiday calendar handle", shown[4, 15]);
            Assert.Equal("month, day", shown[5, 12]);
        }

        // The NG example of the trade-valuation pipeline: a template of the future's seven shared
        // fields, a batch of its five rows on the NG index, the codes in either case, the handle
        // named for the index, the spill one row per component with the kernel's numbers; a
        // template field repeated in the ticket refused, and a financial template whose strip
        // pays two business days after each expiry.
        [Fact]
        public void a_batch_of_trades_is_created_from_a_template_and_a_ticket_on_an_index()
        {
            var schedule = Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27"), Column(46323.0, 46351.0, 46385.0), ExcelMissing.Value);
            var holidays = Seam.Call("_CreateHolidayCalendar", Column(46352.0, 46381.0));
            var ng = Index(schedule, holidays, "Henry Hub NYMEX");
            var fields = Row("contract_specification", "quantity_unit", "quantity_per", "schedule_method", "route", "settlement_method", "clearing_house");
            var template = (string)Seam.Call("_CreateTradeTemplate", "future", fields, Row("NYMEX NG", "LOT", "month", "lastday", "cleared", "physical", "CME Clearing"));
            Assert.StartsWith(Pid + ":trade_template:", template);
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var rows = new object[,]
            {
                { "NG-001", 46289.0, "Z26", 10.0, 3.1 },
                { "NG-002", 46289.0, "z26", -4.0, 3.15 },
                { "NG-003", 46290.0, "F27", 7.0, 3.4 },
                { "NG-004", 46290.0, "F27", -12.0, 3.35 },
                { "NG-001", 46289.0, "Z26", 10.0, 3.1 },
            };
            var trades = (string)Seam.Call("_CreateTrades", ng, headers, rows, template);
            Assert.StartsWith(Pid + ":trades:Henry Hub NYMEX:", trades);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(7, spill.GetLength(0));
            Assert.Equal(16, spill.GetLength(1));
            Assert.Equal("row", spill[0, 0]);
            Assert.Equal("offset", spill[0, 15]);
            Assert.Equal(1.0, spill[2, 0]);
            Assert.Equal("Z26", spill[3, 4]);
            Assert.Equal("cleared", spill[2, 6]);
            Assert.Equal("physical", spill[2, 7]);
            Assert.Equal(100000.0, spill[2, 13]);
            Assert.Equal(-310000.0, spill[6, 15]);
            Assert.Equal("#ERROR _CreateTrades: ValueError: route is supplied by the template and by the ticket, expected by one of them", Seam.Call("_CreateTrades", ng, Row("trade_date", "contract_code", "quantity", "fixed_price", "route"), Row(46289.0, "Z26", 1.0, 3.0, "cleared"), template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: lots of trade 'a' at row 1 is 2.5, expected a whole number of lots", Seam.Call("_CreateTrades", ng, headers, Row("a", 46289.0, "Z26", 2.5, 3.0), template));
            Assert.Equal("#ERROR _CreateTrades: template is holiday calendar handle '" + holidays + "', expected trade template handle", Seam.Call("_CreateTrades", ng, headers, rows, holidays));
            var financial = (string)Seam.Call("_CreateTradeTemplate", "future", Row("contract_specification", "quantity_unit", "quantity_per", "schedule_method", "route", "settlement_method", "clearing_house", "payment_time_lag", "payment_holiday_calendar"), Row("NYMEX NG", "LOT", "month", "lastday", "cleared", "financial", "TEST", "+2bd", holidays));
            var strip = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateTrades", ng, Row("trade_date", "contract_code", "quantity", "fixed_price"), Row(46289.0, "Z26-F27", 3.0, 3.2), financial));
            Assert.Equal(4, strip.GetLength(0));
            Assert.Equal(17, strip.GetLength(1));
            Assert.Equal("payment_date", strip[0, 13]);
            Assert.Equal("+2bd", strip[2, 12]);
            Assert.Equal(46356.0, strip[2, 13]);
            Assert.Equal(46387.0, strip[3, 13]);
        }

        // The valuation path from the host's side: the market fact's chain, valued on 26 May 2026 with
        // n26 at 72.10 and q26 at 72.80, a batch of two lots of n26 at 70 and one lot sold of q26
        // at 72, prepared, evaluated and reported: a mark of 34,000 and no cash, a total delta of
        // 10,000 and a DV01 of zero, the readers' rows per slot; a tick making new results over the
        // same preparation while the first results stand.
        [Fact]
        public void a_batch_is_prepared_evaluated_and_reported()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46167.0);
            var index = Index(schedule, holidays);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46168.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46164.0, 46163.0, 46162.0), Column(71.25, 71.10, 70.85), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "sample", Column(72.10, 72.80)));
            var fields = Row("contract_specification", "quantity_unit", "quantity_per", "schedule_method", "route", "settlement_method", "clearing_house");
            var template = (string)Seam.Call("_CreateTradeTemplate", "future", fields, Row("NYMEX NG", "LOT", "month", "lastday", "cleared", "physical", "CME Clearing"));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var trades = (string)Seam.Call("_CreateTrades", index, headers, new object[,] { { "V1", 46153.0, "n26", 2.0, 70.0 }, { "V2", 46153.0, "q26", -1.0, 72.0 } }, template);
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            Assert.StartsWith(Pid + ":prepared_trades:sample:", prepared);
            var results = (string)Seam.Call("_EvaluateTrades", prepared, market);
            Assert.StartsWith(Pid + ":trade_results:sample:", results);
            var values = (object[,])Seam.Call("_ReportValues", results);
            Assert.Equal(3, values.GetLength(0));
            Assert.Equal(4, values.GetLength(1));
            Assert.Equal("cleared_mark", values[0, 0]);
            Assert.Equal("cleared_cash", values[0, 1]);
            Assert.Equal(34000.0, (double)values[2, 0], 6);
            Assert.Equal(0.0, values[2, 1]);
            Assert.Equal("USD", values[2, 2]);
            Assert.Equal(46168.0, values[2, 3]);
            var risk = (object[,])Seam.Call("_ReportRisk", results);
            Assert.Equal(5, risk.GetLength(1));
            Assert.Equal("delta_total", risk[0, 0]);
            Assert.Equal(10000.0, risk[2, 0]);
            Assert.Equal("USD per USD/MMBTU", risk[2, 1]);
            Assert.Equal(0.0, risk[2, 2]);
            Assert.Equal("USD per basis point", risk[2, 3]);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(4, slots.GetLength(0));
            Assert.Equal("live_exposure", slots[0, 4]);
            Assert.Equal("n26", slots[2, 0]);
            Assert.Equal(false, slots[2, 2]);
            Assert.Equal(20000.0, slots[2, 4]);
            Assert.Equal(-10000.0, slots[3, 4]);
            var contributions = (object[,])Seam.Call("util_ReadHandle", results);
            Assert.Equal("live_exposure", contributions[0, 3]);
            Assert.Equal("live_contribution", contributions[0, 4]);
            Assert.Equal("contract_delta", contributions[0, 5]);
            Assert.Equal(20000.0, contributions[2, 3]);
            Assert.Equal(1442000.0, (double)contributions[2, 4], 6);
            Assert.Equal(20000.0, contributions[2, 5]);
            var ticked = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "sample", Column(72.20, 72.80)));
            var later = (string)Seam.Call("_EvaluateTrades", prepared, ticked);
            Assert.NotEqual(results, later);
            Assert.Equal(36000.0, (double)((object[,])Seam.Call("_ReportValues", later))[2, 0], 6);
            Assert.Equal(34000.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            Assert.Equal("#ERROR _EvaluateTrades: prepared is trades handle '" + trades + "', expected prepared trades handle", Seam.Call("_EvaluateTrades", trades, market));
            Assert.Equal("#ERROR _ReportRisk: results is prepared trades handle '" + prepared + "', expected trade results handle", Seam.Call("_ReportRisk", prepared));
        }

        // util_ReadHandle spills it back, the header, the type, then a row per holiday.
        [Fact]
        public void a_holiday_calendar_is_created_from_a_column_and_read_back_through_its_handle()
        {
            var handle = (string)Seam.Call("_CreateHolidayCalendar", Column(46023.0, 46041.0, 46069.0));
            Assert.StartsWith(Pid + ":holiday_calendar:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(1, spill.GetLength(1));
            Assert.Equal("holiday", spill[0, 0]);
            Assert.Equal("datetime64[D]", spill[1, 0]);
            Assert.Equal(46041.0, spill[3, 0]);
            var oneDay = (string)Seam.Call("_CreateHolidayCalendar", 46023.0);
            Assert.NotEqual(handle, oneDay);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", oneDay)).GetLength(0));
        }

        // An IFERC schedule: three columns make one, three single cells make one of one contract
        // month, and util_ReadHandle spills it back, the three headers, the three types, then a
        // row per contract month, the code as text and both dates as serials.
        [Fact]
        public void an_iferc_schedule_is_created_from_three_columns_and_read_back_through_its_handle()
        {
            var handle = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46295.0, 46325.0, 46356.0), Column(46296.0, 46328.0, 46357.0));
            Assert.StartsWith(Pid + ":iferc_schedule:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(3, spill.GetLength(1));
            Assert.Equal("contract_code", spill[0, 0]);
            Assert.Equal("last_trading_date", spill[0, 1]);
            Assert.Equal("publication_date", spill[0, 2]);
            Assert.Equal("str", spill[1, 0]);
            Assert.Equal("datetime64[D]", spill[1, 1]);
            Assert.Equal("datetime64[D]", spill[1, 2]);
            Assert.Equal("V26", spill[2, 0]);
            Assert.Equal(46295.0, spill[2, 1]);
            Assert.Equal(46296.0, spill[2, 2]);
            Assert.Equal("Z26", spill[4, 0]);
            Assert.Equal(46356.0, spill[4, 1]);
            Assert.Equal(46357.0, spill[4, 2]);
            var one = (string)Seam.Call("_CreateIfercSchedule", "V26", 46295.0, 46296.0);
            Assert.NotEqual(handle, one);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", one)).GetLength(0));
        }

        // A Gas Daily schedule: three columns make one, three single cells make one of one contract
        // month, and util_ReadHandle spills it back, the three headers, the three types, then a
        // row per contract month, the code as text and both dates as serials.
        [Fact]
        public void a_gas_daily_schedule_is_created_from_three_columns_and_read_back_through_its_handle()
        {
            var handle = (string)Seam.Call("_CreateGasDailySchedule", Column("U26", "V26", "X26"), Column(46266.0, 46296.0, 46327.0), Column(46295.0, 46326.0, 46356.0));
            Assert.StartsWith(Pid + ":gas_daily_schedule:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(3, spill.GetLength(1));
            Assert.Equal("contract_code", spill[0, 0]);
            Assert.Equal("first_date", spill[0, 1]);
            Assert.Equal("last_date", spill[0, 2]);
            Assert.Equal("str", spill[1, 0]);
            Assert.Equal("datetime64[D]", spill[1, 1]);
            Assert.Equal("datetime64[D]", spill[1, 2]);
            Assert.Equal("U26", spill[2, 0]);
            Assert.Equal(46266.0, spill[2, 1]);
            Assert.Equal(46295.0, spill[2, 2]);
            Assert.Equal("X26", spill[4, 0]);
            Assert.Equal(46327.0, spill[4, 1]);
            Assert.Equal(46356.0, spill[4, 2]);
            var oneMonth = (string)Seam.Call("_CreateGasDailySchedule", "U26", 46266.0, 46295.0);
            Assert.NotEqual(handle, oneMonth);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", oneMonth)).GetLength(0));
        }

        // Index conventions: five codes make one, and util_ReadHandle spills them back, the five
        // headers, five types, then the codes as typed in one row; cents a gallon quoted and dollars
        // a barrel settled make one too, two units of one category in each pair. The library's
        // rules, a code in another case and a unit of another category, are rows of the theory.
        [Fact]
        public void index_conventions_are_created_from_five_codes_and_read_back_through_their_handle()
        {
            var handle = (string)Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "VOLUME", "BBL");
            Assert.StartsWith(Pid + ":index_conventions:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(3, spill.GetLength(0));
            Assert.Equal(5, spill.GetLength(1));
            Assert.Equal("quantity_type", spill[0, 3]);
            Assert.Equal("str", spill[1, 0]);
            Assert.Equal("VOLUME", spill[2, 3]);
            Assert.Equal("BBL", spill[2, 4]);
            var gasoline = (string)Seam.Call("_CreateIndexConventions", "CENT", "GAL", "USD", "VOLUME", "BBL");
            Assert.Equal("CENT", ((object[,])Seam.Call("util_ReadHandle", gasoline))[2, 0]);
        }

        // Contract specifications: a header row and two contracts make one, and util_ReadHandle spills them
        // back, the four headers, four types, then one row per contract, the name as text and the
        // lot size and fees as numbers.
        [Fact]
        public void contract_specifications_are_created_from_a_table_and_read_back_through_their_handle()
        {
            var handle = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0 }, { "ICE NG", 2500.0, "MMBTU", 0.75, 0.5 } });
            Assert.StartsWith(Pid + ":contract_specifications:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(4, spill.GetLength(0));
            Assert.Equal(5, spill.GetLength(1));
            Assert.Equal("lot_size", spill[0, 1]);
            Assert.Equal("lot_unit", spill[0, 2]);
            Assert.Equal("float64", spill[1, 1]);
            Assert.Equal("str", spill[1, 2]);
            Assert.Equal("ICE NG", spill[3, 0]);
            Assert.Equal(2500.0, spill[3, 1]);
            Assert.Equal("MMBTU", spill[3, 2]);
            Assert.Equal(0.75, spill[3, 3]);
        }

        // The index: a name, a futures schedule of three contracts, the conventions, the
        // specifications and a holiday calendar make one, and util_ReadHandle spills it back as one
        // row, the name, the kind, three contracts, two specifications and TRUE; an IFERC schedule
        // without a holiday calendar makes one whose row says IFERC and FALSE. The library's rules
        // answer through the same objects: the futures schedule without its holiday calendar, the
        // Gas Daily schedule with one, a holiday calendar where the schedule should be, and a handle
        // of another kind where the conventions should be.
        [Fact]
        public void an_index_is_created_from_text_and_four_handles_and_read_back_through_its_handle()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46167.0);
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "MMBTU", "USD", "ENERGY", "MMBTU");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0 }, { "ICE NG", 2500.0, "MMBTU", 0.75, 0.5 } });
            var handle = (string)Seam.Call("_CreateIndex", "Henry Hub NYMEX", schedule, conventions, specifications, holidays);
            Assert.StartsWith(Pid + ":index:Henry Hub NYMEX:", handle);
            // The lot units are units of the conventions' quantity type: the same MMBTU lots under volume conventions are refused, naming the row and the units that would have done.
            var volume = (string)Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "VOLUME", "BBL");
            Assert.Equal("#ERROR _CreateIndex: ValueError: specifications row 1 lot_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3", Seam.Call("_CreateIndex", "WTI NYMEX", schedule, volume, specifications, holidays));
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(3, spill.GetLength(0));
            Assert.Equal(5, spill.GetLength(1));
            Assert.Equal("kind", spill[0, 1]);
            Assert.Equal("int64", spill[1, 2]);
            Assert.Equal("Henry Hub NYMEX", spill[2, 0]);
            Assert.Equal("futures", spill[2, 1]);
            Assert.Equal(3.0, spill[2, 2]);
            Assert.Equal(2.0, spill[2, 3]);
            Assert.Equal(true, spill[2, 4]);
            var iferc = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46295.0, 46325.0, 46356.0), Column(46296.0, 46328.0, 46357.0));
            var monthly = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateIndex", "Henry Hub IFERC", iferc, conventions, specifications, ExcelMissing.Value));
            Assert.Equal("IFERC", monthly[2, 1]);
            Assert.Equal(false, monthly[2, 4]);
            Assert.Equal("#ERROR _CreateIndex: ValueError: holiday_calendar is missing, expected holiday calendar handle with a futures schedule", Seam.Call("_CreateIndex", "Henry Hub NYMEX", schedule, conventions, specifications, ExcelMissing.Value));
            var gasDaily = (string)Seam.Call("_CreateGasDailySchedule", Column("U26", "V26", "X26"), Column(46266.0, 46296.0, 46327.0), Column(46295.0, 46326.0, 46356.0));
            Assert.Equal("#ERROR _CreateIndex: ValueError: holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule", Seam.Call("_CreateIndex", "Henry Hub Gas Daily", gasDaily, conventions, specifications, holidays));
            Assert.Equal("#ERROR _CreateIndex: ValueError: schedule is a holiday calendar, expected a futures, IFERC or Gas Daily schedule", Seam.Call("_CreateIndex", "Henry Hub NYMEX", holidays, conventions, specifications, ExcelMissing.Value));
            Assert.Equal("#ERROR _CreateIndex: index_conventions is holiday calendar handle '" + holidays + "', expected index conventions handle", Seam.Call("_CreateIndex", "Henry Hub NYMEX", schedule, holidays, specifications, holidays));
        }

        // Futures fixings: a column of days, newest first, a column of settles and the index, holding
        // the market's holiday calendar, make one, two single cells make the fixings of one day, and
        // util_ReadHandle spills it back, the two headers, two types, then a row per day in the
        // order given, the date as a serial and the settle as a number; the spill's two columns
        // handed back to the creator make fixings that spill the same. With the index live, the
        // library's rules answer: a settle column one row short, the days oldest first, a business
        // day without a fixing, a Saturday, a listed holiday and an index of another kind; a handle
        // of another kind where the index should be fails in the seam's.
        [Fact]
        public void futures_fixings_are_created_from_two_columns_and_an_index_and_read_back_through_their_handle()
        {
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", Column(46023.0, 46041.0, 46069.0));
            var index = Index(Seam.Call("_CreateFuturesSchedule", Column("m26", "n26"), Column(46161.0, 46195.0), ExcelMissing.Value), holidays);
            var handle = (string)Seam.Call("_CreateFuturesFixings", Column(46146.0, 46143.0), Column(106.42, 101.94), index);
            Assert.StartsWith(Pid + ":futures_fixings:sample:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(4, spill.GetLength(0));
            Assert.Equal(2, spill.GetLength(1));
            Assert.Equal("settle", spill[0, 1]);
            Assert.Equal("datetime64[D]", spill[1, 0]);
            Assert.Equal(46146.0, spill[2, 0]);
            Assert.Equal(106.42, spill[2, 1]);
            Assert.Equal(46143.0, spill[3, 0]);
            Assert.Equal(101.94, spill[3, 1]);
            var again = (string)Seam.Call("_CreateFuturesFixings", Column(spill[2, 0], spill[3, 0]), Column(spill[2, 1], spill[3, 1]), index);
            Assert.NotEqual(handle, again);
            Assert.Equal(spill, (object[,])Seam.Call("util_ReadHandle", again));
            var oneDay = (string)Seam.Call("_CreateFuturesFixings", 46143.0, 101.94, index);
            Assert.NotEqual(handle, oneDay);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", oneDay)).GetLength(0));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: settle has 1 settle, expected 2, one per date", Seam.Call("_CreateFuturesFixings", Column(46146.0, 46143.0), Column(106.42), index));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-06, expected a date before row 1's 2026-05-05", Seam.Call("_CreateFuturesFixings", Column(46147.0, 46148.0), Column(102.27, 95.08), index));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-01, expected 2026-05-04, the business day before row 1's 2026-05-05", Seam.Call("_CreateFuturesFixings", Column(46147.0, 46143.0), Column(102.27, 101.94), index));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-05-02, a Saturday, expected a business day", Seam.Call("_CreateFuturesFixings", Column(46144.0, 46143.0), Column(100.0, 101.94), index));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-01-19, a holiday, expected a business day", Seam.Call("_CreateFuturesFixings", 46041.0, 100.0, index));
            var gasDaily = Index(Seam.Call("_CreateGasDailySchedule", Column("U26"), Column(46266.0), Column(46295.0)), ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: index is a Gas Daily index, expected a futures index", Seam.Call("_CreateFuturesFixings", 46143.0, 101.94, gasDaily));
            Assert.Equal("#ERROR _CreateFuturesFixings: index is futures fixings handle '" + handle + "', expected index handle", Seam.Call("_CreateFuturesFixings", 46143.0, 101.94, handle));
        }

        // The calendar: the valuation date and the index of a three-contract schedule with a one-day
        // holiday calendar make one, and util_ReadHandle spills it back, the four headers, the four
        // types, then a row per day, the date as a serial, the prompt contract as text and the two
        // flags as booleans. The library's rules answer through the same objects: an index of one
        // contract, a code given twice, expiries backwards and a span no sheet could show; a
        // calendar and a bare schedule where the index should be fail in the seam's. util_ReadPrompt
        // reads the contract of each calendar's first unfixed period as text, n26 on 25 May, U26 on
        // a Gas Daily calendar valued 25 September and Z26 on an IFERC one valued 15 November; a
        // calendar valued after its last day has none, the library's words, and a schedule where the
        // calendar should be fails in the seam's.
        [Fact]
        public void a_calendar_is_created_from_two_handles_and_read_back_through_its_handle()
        {
            var valuation = (string)Seam.Call("_CreateValuationDate", 46167.0, 0.5);
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46167.0);
            var index = Index(schedule, holidays);
            var handle = (string)Seam.Call("_CreateCalendar", valuation, index);
            Assert.StartsWith(Pid + ":calendar:sample:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(65, spill.GetLength(0));
            Assert.Equal(4, spill.GetLength(1));
            Assert.Equal("contract", spill[0, 1]);
            Assert.Equal("bool", spill[1, 3]);
            Assert.Equal(46162.0, spill[2, 0]);
            Assert.Equal("n26", spill[2, 1]);
            Assert.Equal(true, spill[2, 2]);
            Assert.Equal(true, spill[2, 3]);
            Assert.Equal(false, spill[5, 2]);
            Assert.Equal(false, spill[7, 2]);
            Assert.Equal(false, spill[7, 3]);
            Assert.Equal("q26", spill[36, 1]);
            Assert.Equal("q26", spill[64, 1]);
            var one = (string)Seam.Call("_CreateFuturesSchedule", Column("m26"), Column(46161.0), ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateCalendar: ValueError: index has 1 contract, expected at least 2", Seam.Call("_CreateCalendar", valuation, Index(one, holidays)));
            var twice = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "m26"), Column(46161.0, 46195.0), ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateCalendar: ValueError: contract_code row 2 is 'm26', already given at row 1", Seam.Call("_CreateCalendar", valuation, Index(twice, holidays)));
            var backwards = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26"), Column(46195.0, 46161.0), ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22", Seam.Call("_CreateCalendar", valuation, Index(backwards, holidays)));
            var tooLong = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26"), Column(46161.0, 1094736.0), ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19", Seam.Call("_CreateCalendar", valuation, Index(tooLong, holidays)));
            Assert.Equal("#ERROR _CreateCalendar: index is calendar handle '" + handle + "', expected index handle", Seam.Call("_CreateCalendar", valuation, handle));
            Assert.Equal("#ERROR _CreateCalendar: index is futures schedule handle '" + schedule + "', expected index handle", Seam.Call("_CreateCalendar", valuation, schedule));
            var gasDaily = (string)Seam.Call("_CreateGasDailySchedule", Column("U26", "V26", "X26"), Column(46266.0, 46296.0, 46327.0), Column(46295.0, 46326.0, 46356.0));
            var flowDays = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46290.0, 0.5), Index(gasDaily, ExcelMissing.Value)));
            Assert.Equal(93, flowDays.GetLength(0));
            Assert.Equal("U26", flowDays[2, 1]);
            Assert.Equal(true, flowDays[26, 3]);
            Assert.Equal(false, flowDays[27, 3]);
            Assert.Equal("X26", flowDays[92, 1]);
            var iferc = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46295.0, 46325.0, 46356.0), Column(46296.0, 46328.0, 46357.0));
            var months = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46341.0, 0.5), Index(iferc, ExcelMissing.Value)));
            Assert.Equal(5, months.GetLength(0));
            Assert.Equal(46328.0, months[3, 0]);
            Assert.Equal(true, months[3, 3]);
            Assert.Equal(false, months[4, 3]);
            Assert.Equal("n26", Seam.Call("util_ReadPrompt", handle));
            var gasCalendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46290.0, 0.5), Index(gasDaily, ExcelMissing.Value));
            Assert.Equal("U26", Seam.Call("util_ReadPrompt", gasCalendar));
            var ifercCalendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46341.0, 0.5), Index(iferc, ExcelMissing.Value));
            Assert.Equal("Z26", Seam.Call("util_ReadPrompt", ifercCalendar));
            var ended = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46225.0, 0.5), index);
            Assert.Equal("#ERROR util_ReadPrompt: ValueError: calendar has no unfixed period, expected at least one to quote", Seam.Call("util_ReadPrompt", ended));
            Assert.Equal("#ERROR util_ReadPrompt: calendar is futures schedule handle '" + schedule + "', expected calendar handle", Seam.Call("util_ReadPrompt", schedule));
        }

        // The market history: the calendar of the fact above valued a day later, on 26 May 2026
        // with the 25th a holiday, and the fixings on its three past business days make one, and
        // util_ReadHandle spills it back, the calendar's four columns and fixing_price, a number on
        // a fixed day, closed on the weekend and the holiday, unfixed on the valuation day and
        // after. The library's rules answer through the same objects: a fixing on the valuation
        // date, a fixed day without one, and fixings over another index of the same name; a handle of
        // another kind where the calendar should be, the seam's words, and a calendar where the
        // fixings should be, the library's.
        [Fact]
        public void a_market_history_is_created_from_two_handles_and_read_back_through_its_handle()
        {
            var valuation = (string)Seam.Call("_CreateValuationDate", 46168.0, 0.5);
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46167.0);
            var index = Index(schedule, holidays);
            var calendar = (string)Seam.Call("_CreateCalendar", valuation, index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46164.0, 46163.0, 46162.0), Column(71.25, 71.10, 70.85), index);
            var handle = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            Assert.StartsWith(Pid + ":market_history:sample:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(65, spill.GetLength(0));
            Assert.Equal(5, spill.GetLength(1));
            Assert.Equal("fixing_price", spill[0, 4]);
            Assert.Equal("float64", spill[1, 4]);
            Assert.Equal(46162.0, spill[2, 0]);
            Assert.Equal("n26", spill[2, 1]);
            Assert.Equal(true, spill[2, 3]);
            Assert.Equal(70.85, spill[2, 4]);
            Assert.Equal(71.25, spill[4, 4]);
            Assert.Equal("closed", spill[5, 4]);
            Assert.Equal("closed", spill[7, 4]);
            Assert.Equal(false, spill[8, 3]);
            Assert.Equal("unfixed", spill[8, 4]);
            Assert.Equal("unfixed", spill[64, 4]);
            var late = (string)Seam.Call("_CreateFuturesFixings", Column(46168.0, 46164.0, 46163.0, 46162.0), Column(71.5, 71.25, 71.10, 70.85), index);
            Assert.Equal("#ERROR _CreateMarketHistory: ValueError: fixings date 2026-05-26 is on or after valuation date 2026-05-26, expected dates before the valuation date", Seam.Call("_CreateMarketHistory", calendar, late));
            var twoDays = (string)Seam.Call("_CreateFuturesFixings", Column(46163.0, 46162.0), Column(71.10, 70.85), index);
            Assert.Equal("#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2026-05-22, expected a fixing for every fixed day in calendar", Seam.Call("_CreateMarketHistory", calendar, twoDays));
            var elsewhere = (string)Seam.Call("_CreateHolidayCalendar", 46023.0);
            var onTheHoliday = (string)Seam.Call("_CreateFuturesFixings", Column(46167.0, 46164.0, 46163.0, 46162.0), Column(71.4, 71.25, 71.10, 70.85), Index(schedule, elsewhere));
            Assert.Equal("#ERROR _CreateMarketHistory: ValueError: fixings is over another index, 'sample', expected the calendar's, 'sample'", Seam.Call("_CreateMarketHistory", calendar, onTheHoliday));
            Assert.Equal("#ERROR _CreateMarketHistory: calendar is futures fixings handle '" + fixings + "', expected calendar handle", Seam.Call("_CreateMarketHistory", fixings, fixings));
            Assert.Equal("#ERROR _CreateMarketHistory: ValueError: fixings is a calendar, expected futures, IFERC or Gas Daily fixings", Seam.Call("_CreateMarketHistory", calendar, calendar));
        }

        // The market history over the other two calendars: a Gas Daily calendar of September to
        // November 2026 valued on 11 September and a print on every flow day from the 11th back to
        // the 1st make one, every flow day through the valuation day priced and the next unfixed; an
        // IFERC calendar of October to December valued on 15 November and the indices of the two
        // published months, November's first, make one, the two priced in the calendar's order and
        // December unfixed. The library's rules answer through the same objects: a print for the
        // day after the valuation day, an index for a month not yet published, IFERC fixings over
        // another index than the Gas Daily calendar's, and a history where the fixings should be.
        [Fact]
        public void a_gas_daily_and_an_iferc_history_are_created_from_two_handles_each_and_read_back()
        {
            var gasDaily = (string)Seam.Call("_CreateGasDailySchedule", Column("U26", "V26", "X26"), Column(46266.0, 46296.0, 46327.0), Column(46295.0, 46326.0, 46356.0));
            var gasIndex = Index(gasDaily, ExcelMissing.Value, "Henry Hub Gas Daily");
            var september = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46276.0, 0.5), gasIndex);
            var prints = (string)Seam.Call("_CreateGasDailyFixings", Column(46276.0, 46275.0, 46274.0, 46273.0, 46272.0, 46271.0, 46270.0, 46269.0, 46268.0, 46267.0, 46266.0), Column(3.0, 2.95, 2.9, 2.875, 2.875, 2.875, 2.875, 2.93, 2.93, 2.92, 2.91), gasIndex);
            var daily = (string)Seam.Call("_CreateMarketHistory", september, prints);
            Assert.StartsWith(Pid + ":market_history:Henry Hub Gas Daily:", daily);
            var days = (object[,])Seam.Call("util_ReadHandle", daily);
            Assert.Equal(93, days.GetLength(0));
            Assert.Equal(5, days.GetLength(1));
            Assert.Equal(2.91, days[2, 4]);
            Assert.Equal(true, days[12, 3]);
            Assert.Equal(3.0, days[12, 4]);
            Assert.Equal(false, days[13, 3]);
            Assert.Equal("unfixed", days[13, 4]);
            Assert.Equal("unfixed", days[92, 4]);
            var iferc = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46295.0, 46325.0, 46356.0), Column(46296.0, 46328.0, 46357.0));
            var ifercIndex = Index(iferc, ExcelMissing.Value, "Henry Hub IFERC");
            var november = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46341.0, 0.5), ifercIndex);
            var indices = (string)Seam.Call("_CreateIfercFixings", Column("X26", "V26"), Column(2.10, 1.85), ifercIndex);
            var monthly = (string)Seam.Call("_CreateMarketHistory", november, indices);
            Assert.StartsWith(Pid + ":market_history:Henry Hub IFERC:", monthly);
            var months = (object[,])Seam.Call("util_ReadHandle", monthly);
            Assert.Equal(5, months.GetLength(0));
            Assert.Equal(46296.0, months[2, 0]);
            Assert.Equal("V26", months[2, 1]);
            Assert.Equal(1.85, months[2, 4]);
            Assert.Equal(2.10, months[3, 4]);
            Assert.Equal("unfixed", months[4, 4]);
            var earlier = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46275.0, 0.5), gasIndex);
            Assert.Equal("#ERROR _CreateMarketHistory: ValueError: fixings flow_date 2026-09-11 is after valuation date 2026-09-10, expected flow days on or before the valuation date", Seam.Call("_CreateMarketHistory", earlier, prints));
            var december = (string)Seam.Call("_CreateIfercFixings", Column("V26", "X26", "Z26"), Column(1.85, 2.10, 2.20), ifercIndex);
            Assert.Equal("#ERROR _CreateMarketHistory: ValueError: fixings contract_code 'Z26' is a month not yet fixed in calendar, expected an index for fixed months alone", Seam.Call("_CreateMarketHistory", november, december));
            Assert.Equal("#ERROR _CreateMarketHistory: ValueError: fixings is over another index, 'Henry Hub IFERC', expected the calendar's, 'Henry Hub Gas Daily'", Seam.Call("_CreateMarketHistory", september, indices));
            Assert.Equal("#ERROR _CreateMarketHistory: ValueError: fixings is a market history, expected futures, IFERC or Gas Daily fixings", Seam.Call("_CreateMarketHistory", september, daily));
        }

        // The price vector: the index's name and one column of prices make one, the name and a
        // single cell make one of one price, and util_ReadHandle spills it back, the header, the
        // type, then each price as a number, a zero and a negative price kept in their places and
        // no name; a second call over the same prices publishes its own handle, and the first
        // still reads the same.
        [Fact]
        public void a_price_vector_is_created_from_a_name_and_a_column_and_read_back_through_its_handle()
        {
            var handle = (string)Seam.Call("_CreatePriceVector", "WTI NYMEX", Column(74.25, 0.0, -0.5, 74.25));
            Assert.StartsWith(Pid + ":price_vector:WTI NYMEX:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(6, spill.GetLength(0));
            Assert.Equal(1, spill.GetLength(1));
            Assert.Equal("price", spill[0, 0]);
            Assert.Equal("float64", spill[1, 0]);
            Assert.Equal(74.25, spill[2, 0]);
            Assert.Equal(0.0, spill[3, 0]);
            Assert.Equal(-0.5, spill[4, 0]);
            Assert.Equal(74.25, spill[5, 0]);
            var one = (string)Seam.Call("_CreatePriceVector", "WTI NYMEX", 74.25);
            Assert.StartsWith(Pid + ":price_vector:WTI NYMEX:", one);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", one)).GetLength(0));
            var again = (string)Seam.Call("_CreatePriceVector", "WTI NYMEX", Column(74.25, 0.0, -0.5, 74.25));
            Assert.NotEqual(handle, again);
            Assert.Equal(-0.5, ((object[,])Seam.Call("util_ReadHandle", handle))[4, 0]);
        }

        // The market: the history of the market-history fact, valued on 26 May 2026 with the 25th
        // a holiday and the three past business days fixed, and a vector of two quotes, n26's and
        // q26's, named for the index, make one, and util_ReadHandle spills it back, the calendar's
        // four columns and price, a fixing on a past business day, closed on the weekend and the
        // holiday, n26's quote from the valuation day to its expiry and q26's from the day after.
        // The library's rules answer through the same objects: a vector named for another index,
        // refused before its count is looked at; the first quote alone, a vector that stops before
        // the schedule does, read back through n26's last day; one quote past the schedule; a
        // history valued before its calendar begins is a market from the calendar's first day;
        // and a handle of another kind in either slot.
        [Fact]
        public void a_market_is_created_from_two_handles_and_read_back_through_its_handle()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46167.0);
            var index = Index(schedule, holidays);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46168.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46164.0, 46163.0, 46162.0), Column(71.25, 71.10, 70.85), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var quotes = (string)Seam.Call("_CreatePriceVector", "sample", Column(72.10, 72.80));
            var handle = (string)Seam.Call("_CreateMarket", history, quotes);
            Assert.StartsWith(Pid + ":market:sample:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(65, spill.GetLength(0));
            Assert.Equal(5, spill.GetLength(1));
            Assert.Equal("price", spill[0, 4]);
            Assert.Equal("float64", spill[1, 4]);
            Assert.Equal(70.85, spill[2, 4]);
            Assert.Equal(71.25, spill[4, 4]);
            Assert.Equal("closed", spill[5, 4]);
            Assert.Equal("closed", spill[7, 4]);
            Assert.Equal(72.10, spill[8, 4]);
            Assert.Equal("n26", spill[35, 1]);
            Assert.Equal(72.10, spill[35, 4]);
            Assert.Equal("q26", spill[36, 1]);
            Assert.Equal(72.80, spill[36, 4]);
            Assert.Equal(72.80, spill[64, 4]);
            Assert.Equal("#ERROR _CreateMarket: ValueError: price_vector names index 'Brent', expected market_history's index 'sample'", Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "Brent", 72.10)));
            var alone = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "sample", 72.10));
            Assert.StartsWith(Pid + ":market:sample:", alone);
            var covered = (object[,])Seam.Call("util_ReadHandle", alone);
            Assert.Equal(36, covered.GetLength(0));
            Assert.Equal(70.85, covered[2, 4]);
            Assert.Equal("n26", covered[35, 1]);
            Assert.Equal(72.10, covered[35, 4]);
            Assert.Equal("#ERROR _CreateMarket: ValueError: price_vector has 3 prices, expected at most 2, one per contract from 'n26' through 'q26'", Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "sample", Column(72.10, 72.80, 73.0))));
            var early = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46161.0, 0.5), index);
            var earlyHistory = (string)Seam.Call("_CreateMarketHistory", early, (string)Seam.Call("_CreateFuturesFixings", 46160.0, 70.0, index));
            var earlyMarket = (string)Seam.Call("_CreateMarket", earlyHistory, quotes);
            Assert.StartsWith(Pid + ":market:sample:", earlyMarket);
            var earlySpill = (object[,])Seam.Call("util_ReadHandle", earlyMarket);
            Assert.Equal(46162.0, earlySpill[2, 0]);
            Assert.Equal(72.10, earlySpill[2, 4]);
            Assert.Equal(72.80, earlySpill[36, 4]);
            Assert.Equal("#ERROR _CreateMarket: market_history is price vector handle '" + quotes + "', expected market history handle", Seam.Call("_CreateMarket", quotes, quotes));
            Assert.Equal("#ERROR _CreateMarket: price_vector is market history handle '" + history + "', expected price vector handle", Seam.Call("_CreateMarket", history, history));
        }

        // The market over the other two histories: the Gas Daily history of September to November
        // 2026 valued on 11 September with the prints through the 11th, and three quotes, the
        // balance of September, October and November, make one, and util_ReadHandle spills it back,
        // the print on the valuation day, the balance-of-month quote the day after, October's quote
        // on its first day and November's on the last; the IFERC history of October to December
        // valued on 15 November with two months published, and one quote, December's, make one,
        // the two indices and the quote on their rows, each vector named for its index. The
        // library's rules answer through the same objects: the IFERC vector given with the Gas
        // Daily history, named for the other index; one quote of the three months, a vector that
        // stops before the schedule does, read back through September's last day; a fourth quote,
        // one past the schedule; and a history with no unfixed period, the IFERC calendar valued
        // on 15 December with all three indices.
        [Fact]
        public void a_gas_daily_and_an_iferc_market_are_created_from_two_handles_each_and_read_back()
        {
            var gasDaily = (string)Seam.Call("_CreateGasDailySchedule", Column("U26", "V26", "X26"), Column(46266.0, 46296.0, 46327.0), Column(46295.0, 46326.0, 46356.0));
            var gasIndex = Index(gasDaily, ExcelMissing.Value, "Henry Hub Gas Daily");
            var september = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46276.0, 0.5), gasIndex);
            var prints = (string)Seam.Call("_CreateGasDailyFixings", Column(46276.0, 46275.0, 46274.0, 46273.0, 46272.0, 46271.0, 46270.0, 46269.0, 46268.0, 46267.0, 46266.0), Column(3.0, 2.95, 2.9, 2.875, 2.875, 2.875, 2.875, 2.93, 2.93, 2.92, 2.91), gasIndex);
            var daily = (string)Seam.Call("_CreateMarketHistory", september, prints);
            var threeQuotes = (string)Seam.Call("_CreatePriceVector", "Henry Hub Gas Daily", Column(2.95, 3.10, 3.40));
            var dailyMarket = (string)Seam.Call("_CreateMarket", daily, threeQuotes);
            Assert.StartsWith(Pid + ":market:Henry Hub Gas Daily:", dailyMarket);
            var days = (object[,])Seam.Call("util_ReadHandle", dailyMarket);
            Assert.Equal(93, days.GetLength(0));
            Assert.Equal(5, days.GetLength(1));
            Assert.Equal("price", days[0, 4]);
            Assert.Equal(2.91, days[2, 4]);
            Assert.Equal(3.0, days[12, 4]);
            Assert.Equal(2.95, days[13, 4]);
            Assert.Equal(2.95, days[31, 4]);
            Assert.Equal("V26", days[32, 1]);
            Assert.Equal(3.10, days[32, 4]);
            Assert.Equal(3.40, days[63, 4]);
            Assert.Equal(3.40, days[92, 4]);
            var iferc = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46295.0, 46325.0, 46356.0), Column(46296.0, 46328.0, 46357.0));
            var ifercIndex = Index(iferc, ExcelMissing.Value, "Henry Hub IFERC");
            var november = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46341.0, 0.5), ifercIndex);
            var monthly = (string)Seam.Call("_CreateMarketHistory", november, (string)Seam.Call("_CreateIfercFixings", Column("X26", "V26"), Column(2.10, 1.85), ifercIndex));
            var oneQuote = (string)Seam.Call("_CreatePriceVector", "Henry Hub IFERC", 2.20);
            var monthlyMarket = (string)Seam.Call("_CreateMarket", monthly, oneQuote);
            Assert.StartsWith(Pid + ":market:Henry Hub IFERC:", monthlyMarket);
            var months = (object[,])Seam.Call("util_ReadHandle", monthlyMarket);
            Assert.Equal(5, months.GetLength(0));
            Assert.Equal(1.85, months[2, 4]);
            Assert.Equal(2.10, months[3, 4]);
            Assert.Equal(46357.0, months[4, 0]);
            Assert.Equal(2.20, months[4, 4]);
            Assert.Equal("#ERROR _CreateMarket: ValueError: price_vector names index 'Henry Hub IFERC', expected market_history's index 'Henry Hub Gas Daily'", Seam.Call("_CreateMarket", daily, oneQuote));
            var balance = (string)Seam.Call("_CreateMarket", daily, (string)Seam.Call("_CreatePriceVector", "Henry Hub Gas Daily", 2.20));
            Assert.StartsWith(Pid + ":market:Henry Hub Gas Daily:", balance);
            var throughSeptember = (object[,])Seam.Call("util_ReadHandle", balance);
            Assert.Equal(32, throughSeptember.GetLength(0));
            Assert.Equal(3.0, throughSeptember[12, 4]);
            Assert.Equal(2.20, throughSeptember[13, 4]);
            Assert.Equal("U26", throughSeptember[31, 1]);
            Assert.Equal(2.20, throughSeptember[31, 4]);
            Assert.Equal("#ERROR _CreateMarket: ValueError: price_vector has 4 prices, expected at most 3, one per contract from 'U26' through 'X26'", Seam.Call("_CreateMarket", daily, (string)Seam.Call("_CreatePriceVector", "Henry Hub Gas Daily", Column(2.95, 3.10, 3.40, 3.50))));
            var december = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46371.0, 0.5), ifercIndex);
            var published = (string)Seam.Call("_CreateMarketHistory", december, (string)Seam.Call("_CreateIfercFixings", Column("V26", "X26", "Z26"), Column(1.85, 2.10, 2.20), ifercIndex));
            Assert.Equal("#ERROR _CreateMarket: ValueError: market_history has no unfixed period, expected at least one to quote", Seam.Call("_CreateMarket", published, oneQuote));
        }

        // IFERC fixings: a column of contract codes, a column of indices and the index of those
        // months make one, two single cells make the fixings of one month, and util_ReadHandle
        // spills it back, the two headers, the text type over the number type, then a row per
        // month in the order typed, here the newest first over a schedule that runs the other way,
        // the code as text and the index as a number; the spill's two columns handed back to the
        // creator make fixings that spill the same. With the index live, the library's rules
        // answer: a price column one row short, a code given twice, a code the index does not
        // hold, and a futures index where the IFERC index should be; a handle of another kind where
        // the index should be fails in the seam's.
        [Fact]
        public void iferc_fixings_are_created_from_two_columns_and_an_index_and_read_back_through_their_handle()
        {
            var schedule = (string)Seam.Call("_CreateIfercSchedule", Column("F26", "G26", "H26", "J26"), Column(46022.0, 46052.0, 46080.0, 46112.0), Column(46027.0, 46055.0, 46083.0, 46113.0));
            var index = Index(schedule, ExcelMissing.Value, "Waha IFERC");
            var handle = (string)Seam.Call("_CreateIfercFixings", Column("J26", "H26", "G26", "F26"), Column(1.60, 1.95, 2.10, 1.85), index);
            Assert.StartsWith(Pid + ":iferc_fixings:Waha IFERC:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(6, spill.GetLength(0));
            Assert.Equal(2, spill.GetLength(1));
            Assert.Equal("contract_code", spill[0, 0]);
            Assert.Equal("price", spill[0, 1]);
            Assert.Equal("str", spill[1, 0]);
            Assert.Equal("float64", spill[1, 1]);
            Assert.Equal("J26", spill[2, 0]);
            Assert.Equal(1.60, spill[2, 1]);
            Assert.Equal("F26", spill[5, 0]);
            Assert.Equal(1.85, spill[5, 1]);
            var again = (string)Seam.Call("_CreateIfercFixings", Column(spill[2, 0], spill[3, 0], spill[4, 0], spill[5, 0]), Column(spill[2, 1], spill[3, 1], spill[4, 1], spill[5, 1]), index);
            Assert.NotEqual(handle, again);
            Assert.Equal(spill, (object[,])Seam.Call("util_ReadHandle", again));
            var oneMonth = (string)Seam.Call("_CreateIfercFixings", "F26", 1.85, index);
            Assert.NotEqual(handle, oneMonth);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", oneMonth)).GetLength(0));
            Assert.Equal("#ERROR _CreateIfercFixings: ValueError: price has 2 prices, expected 3, one per contract_code", Seam.Call("_CreateIfercFixings", Column("F26", "G26", "H26"), Column(1.85, 2.10), index));
            Assert.Equal("#ERROR _CreateIfercFixings: ValueError: contract_code row 2 is 'F26', already given at row 1", Seam.Call("_CreateIfercFixings", Column("F26", "F26"), Column(1.85, 2.10), index));
            Assert.Equal("#ERROR _CreateIfercFixings: ValueError: contract_code row 2 is 'K26', expected one of the index's months", Seam.Call("_CreateIfercFixings", Column("F26", "K26"), Column(1.85, 2.10), index));
            var futures = Index(Seam.Call("_CreateFuturesSchedule", Column("m26", "n26"), Column(46161.0, 46195.0), ExcelMissing.Value), Seam.Call("_CreateHolidayCalendar", 46167.0));
            Assert.Equal("#ERROR _CreateIfercFixings: ValueError: index is a futures index, expected an IFERC index", Seam.Call("_CreateIfercFixings", "F26", 1.85, futures));
            Assert.Equal("#ERROR _CreateIfercFixings: index is iferc schedule handle '" + schedule + "', expected index handle", Seam.Call("_CreateIfercFixings", "F26", 1.85, schedule));
        }

        // Gas Daily fixings: a column of flow days, newest first, a column of midpoints and the index
        // of their month make one, two single cells make the fixings of one day, and util_ReadHandle
        // spills it back, the two headers, the day type over the number type, then a row per flow
        // day in the order given, the weekend rows among them; the spill's two columns handed back
        // to the creator make fixings that spill the same. With the index live, the library's rules
        // answer: a price column one row short, a day skipped, the days oldest first, and an IFERC
        // index where the Gas Daily index should be; a handle of another kind where the index
        // should be fails in the seam's.
        [Fact]
        public void gas_daily_fixings_are_created_from_two_columns_and_an_index_and_read_back_through_their_handle()
        {
            var schedule = (string)Seam.Call("_CreateGasDailySchedule", "U26", 46266.0, 46295.0);
            var index = Index(schedule, ExcelMissing.Value, "Henry Hub Gas Daily");
            var handle = (string)Seam.Call("_CreateGasDailyFixings", Column(46272.0, 46271.0, 46270.0, 46269.0), Column(2.875, 2.875, 2.875, 2.93), index);
            Assert.StartsWith(Pid + ":gas_daily_fixings:Henry Hub Gas Daily:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(6, spill.GetLength(0));
            Assert.Equal(2, spill.GetLength(1));
            Assert.Equal("flow_date", spill[0, 0]);
            Assert.Equal("price", spill[0, 1]);
            Assert.Equal("datetime64[D]", spill[1, 0]);
            Assert.Equal("float64", spill[1, 1]);
            Assert.Equal(46272.0, spill[2, 0]);
            Assert.Equal(2.875, spill[2, 1]);
            Assert.Equal(46269.0, spill[5, 0]);
            Assert.Equal(2.93, spill[5, 1]);
            var again = (string)Seam.Call("_CreateGasDailyFixings", Column(spill[2, 0], spill[3, 0], spill[4, 0], spill[5, 0]), Column(spill[2, 1], spill[3, 1], spill[4, 1], spill[5, 1]), index);
            Assert.NotEqual(handle, again);
            Assert.Equal(spill, (object[,])Seam.Call("util_ReadHandle", again));
            var oneDay = (string)Seam.Call("_CreateGasDailyFixings", 46269.0, 2.93, index);
            Assert.NotEqual(handle, oneDay);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", oneDay)).GetLength(0));
            Assert.Equal("#ERROR _CreateGasDailyFixings: ValueError: price has 2 prices, expected 3, one per flow_date", Seam.Call("_CreateGasDailyFixings", Column(46271.0, 46270.0, 46269.0), Column(2.875, 2.93), index));
            Assert.Equal("#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-04, expected 2026-09-05, the day before row 1's 2026-09-06", Seam.Call("_CreateGasDailyFixings", Column(46271.0, 46269.0), Column(2.875, 2.93), index));
            Assert.Equal("#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-05, expected 2026-09-03, the day before row 1's 2026-09-04", Seam.Call("_CreateGasDailyFixings", Column(46269.0, 46270.0), Column(2.93, 2.875), index));
            var iferc = Index(Seam.Call("_CreateIfercSchedule", "F26", 46022.0, 46027.0), ExcelMissing.Value, "Waha IFERC");
            Assert.Equal("#ERROR _CreateGasDailyFixings: ValueError: index is an IFERC index, expected a Gas Daily index", Seam.Call("_CreateGasDailyFixings", 46269.0, 2.93, iferc));
            Assert.Equal("#ERROR _CreateGasDailyFixings: index is gas daily schedule handle '" + schedule + "', expected index handle", Seam.Call("_CreateGasDailyFixings", 46269.0, 2.93, schedule));
        }

        // The mixed road out: a rectangle of three kinds comes back one tagged value per cell.
        [Fact]
        public void a_mixed_array_out_keeps_each_cell_as_it_was()
        {
            var array = (object[,])Seam.Call("EchoMixed", new object[,] { { "CL", 46164.0 }, { true, 2.5 } });
            Assert.Equal(2, array.GetLength(0));
            Assert.Equal(2, array.GetLength(1));
            Assert.Equal("CL", array[0, 0]);
            Assert.Equal(46164.0, array[0, 1]);
            Assert.Equal(true, array[1, 0]);
            Assert.Equal(2.5, array[1, 1]);
        }

        // A curve from anchors: three anchors over eleven days make eleven days, and util_ReadHandle
        // spills them all, the anchors exactly and a day between on the straight line.
        [Fact]
        public void a_curve_from_anchors_spills_every_day_between_them()
        {
            var anchors = new object[,] { { 46276.0, 1.0 }, { 46279.0, 0.9997 }, { 46286.0, 0.999 } };
            var handle = (string)Seam.Call("_CreateDiscountCurve", Row("date", "discount_factor"), anchors);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(13, spill.GetLength(0));
            Assert.Equal(46276.0, spill[2, 0]);
            Assert.Equal(1.0, spill[2, 1]);
            Assert.Equal(0.9997, spill[5, 1]);
            Assert.Equal(46286.0, spill[12, 0]);
            Assert.Equal(0.999, spill[12, 1]);
            Assert.Equal(0.9998, (double)spill[4, 1], 12);
        }

        // A handle: the creator's text stands for the curve, util_ReadHandle spills the curve's table
        // back through it, headers, types, then a row per day, and the headers bind by name in
        // either order.
        [Fact]
        public void a_curve_is_created_as_a_handle_and_read_back_through_it()
        {
            var handle = (string)Seam.Call("_CreateDiscountCurve", Row("date", "discount_factor"), Curve());
            Assert.StartsWith(Pid + ":discount_curve:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(2, spill.GetLength(1));
            Assert.Equal("date", spill[0, 0]);
            Assert.Equal("float64", spill[1, 1]);
            Assert.Equal(46277.0, spill[3, 0]);
            Assert.Equal(0.9999, spill[3, 1]);
            var swapped = new object[,] { { 1.0, 46276.0 }, { 0.9999, 46277.0 }, { 0.9998, 46278.0 } };
            var reversed = (string)Seam.Call("_CreateDiscountCurve", Row("discount_factor", "date"), swapped);
            Assert.NotEqual(handle, reversed);
            var again = (object[,])Seam.Call("util_ReadHandle", reversed);
            Assert.Equal(0.9998, again[4, 1]);
        }

        [Theory]
        [MemberData(nameof(SmokeRows))]
        public void the_smoke_rows_hold(string name, object[] args, object shown)
        {
            Assert.Equal(shown, Seam.Call(name, args));
        }

        [Fact]
        public void ping_says_which_goosedove_is_running()
        {
            Assert.Contains("goosedove", (string)Seam.Call("Ping"));
        }

        // Arrays come back as plain doubles: no boxing, and no NaN, because the seam fails the call first.
        [Fact]
        public void a_grid_result_counts_across_then_down()
        {
            var array = (double[,])Seam.Call("Grid", 2.0, 3.0);
            Assert.Equal(2, array.GetLength(0));
            Assert.Equal(3, array.GetLength(1));
            Assert.Equal(1.0, array[0, 0]);
            Assert.Equal(4.0, array[1, 0]);
            Assert.Equal(6.0, array[1, 2]);
        }

        [Fact]
        public void a_column_result_spills_down()
        {
            var array = (double[,])Seam.Call("EchoColumn", Column(1.0, 2.0, 3.0));
            Assert.Equal(3, array.GetLength(0));
            Assert.Equal(1, array.GetLength(1));
            Assert.Equal(3.0, array[2, 0]);
        }

        [Fact]
        public void a_row_result_spills_across()
        {
            var array = (double[,])Seam.Call("EchoRow", Row(1.0, 2.0, 3.0));
            Assert.Equal(1, array.GetLength(0));
            Assert.Equal(3, array.GetLength(1));
            Assert.Equal(3.0, array[0, 2]);
        }

        [Fact]
        public void a_single_cell_is_a_column_of_one()
        {
            var array = (double[,])Seam.Call("EchoColumn", 5.0);
            Assert.Equal(1, array.GetLength(0));
            Assert.Equal(1, array.GetLength(1));
            Assert.Equal(5.0, array[0, 0]);
        }

        [Fact]
        public void a_grid_in_gives_one_number_per_row_out()
        {
            var grid = new object[,] { { 1.0, 2.0 }, { 3.0, 4.0 }, { 5.0, 6.0 } };
            var array = (double[,])Seam.Call("RowSums", grid);
            Assert.Equal(3, array.GetLength(0));
            Assert.Equal(1, array.GetLength(1));
            Assert.Equal(7.0, array[1, 0]);
            Assert.Equal(11.0, array[2, 0]);
        }
    }
}
