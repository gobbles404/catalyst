using System.Collections.Generic;
using ExcelDna.Integration;
using Xunit;

namespace Goosedove.Host.Tests
{
    /// <summary>Whole calls through the host: the cell text or value Excel would show.</summary>
    [Collection("python")]
    public class CallTests
    {
        private static object[,] Column(params object[] cells)
        {
            var grid = new object[cells.Length, 1];
            for (var i = 0; i < cells.Length; i++)
            {
                grid[i, 0] = cells[i];
            }
            return grid;
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
            // A creator's failure is relayed whole, and a relay of a relay shows the same text.
            yield return new object[] { "util_ReadHandle", new object[] { "#ERROR _CreateDiscountCurve: ValueError: x" }, "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" };
            yield return new object[] { "util_ReadHandle", new object[] { "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" }, "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" };
            // The expiry schedule: a column of codes and up to three of dates, one row per code, the third and fourth columns optional; a futures column one row short, a blank among the options, a publication column one row short and a blank among the publication dates with the options left out.
            yield return new object[] { "_CreateExpirySchedule", new object[] { Column("m26", "n26", "q26"), Column(46161.0, 46195.0), Column(46156.0, 46189.0, 46219.0), ExcelMissing.Value }, "#ERROR _CreateExpirySchedule: ValueError: future_expiry has 2 dates, expected 3, one per future_code" };
            yield return new object[] { "_CreateExpirySchedule", new object[] { Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), Column(46156.0, ExcelEmpty.Value, 46219.0), ExcelMissing.Value }, "#ERROR _CreateExpirySchedule: option_expiry cell (2, 1) is blank, expected date" };
            yield return new object[] { "_CreateExpirySchedule", new object[] { Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), Column(46156.0, 46189.0, 46219.0), Column(46162.0, 46196.0) }, "#ERROR _CreateExpirySchedule: ValueError: publication_date has 2 dates, expected 3, one per future_code" };
            yield return new object[] { "_CreateExpirySchedule", new object[] { Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value, Column(46162.0, ExcelEmpty.Value, 46225.0) }, "#ERROR _CreateExpirySchedule: publication_date cell (2, 1) is blank, expected date" };
            // The holiday calendar: one column of dates, a blank in it, and a row where a column is expected.
            yield return new object[] { "_CreateHolidayCalendar", new object[] { Column(46023.0, ExcelEmpty.Value, 46069.0) }, "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date" };
            yield return new object[] { "_CreateHolidayCalendar", new object[] { Row(46023.0, 46023.0) }, "#ERROR _CreateHolidayCalendar: holiday is 1x2 array, expected column of dates" };
            // The index conventions: five text scalars, a blank and a number where a code is expected, and a code left out.
            yield return new object[] { "_CreateIndexConventions", new object[] { "USD", "BBL", "USD", "volume", ExcelEmpty.Value }, "#ERROR _CreateIndexConventions: quantity_unit is blank, expected text" };
            yield return new object[] { "_CreateIndexConventions", new object[] { "USD", "BBL", 1.0, "volume", "BBL" }, "#ERROR _CreateIndexConventions: currency_unit is number 1.0, expected text" };
            yield return new object[] { "_CreateIndexConventions", new object[] { "USD", "BBL", "USD", "volume", ExcelMissing.Value }, "#ERROR _CreateIndexConventions: quantity_unit is missing, expected text" };
            // The contract specifications: a header row and a table of contracts; a lot size with a fraction, text where a fee is expected, and a name given twice.
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 2.5, 3.0, 2.0 } } }, "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 2.5, expected a whole number" };
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "three", 2.0 } } }, "#ERROR _CreateContractSpecifications: table cell (1, 3) is text 'three', expected number" };
            yield return new object[] { "_CreateContractSpecifications", new object[] { Row("name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, 3.0, 2.0 }, { "NYMEX NG", 2500.0, 0.75, 0.5 } } }, "#ERROR _CreateContractSpecifications: ValueError: name row 2 is 'NYMEX NG', already given at row 1" };
            // The futures curve: a column of codes and a column of prices, one row per code; a blank among the prices, and the prices left out.
            yield return new object[] { "_CreateFuturesCurve", new object[] { Column("M26", "N26", "Q26"), Column(71.25, 71.4) }, "#ERROR _CreateFuturesCurve: ValueError: price has 2 prices, expected 3, one per future_code" };
            yield return new object[] { "_CreateFuturesCurve", new object[] { Column("M26", "N26", "Q26"), Column(71.25, ExcelEmpty.Value, 71.1) }, "#ERROR _CreateFuturesCurve: price cell (2, 1) is blank, expected number" };
            yield return new object[] { "_CreateFuturesCurve", new object[] { Column("M26", "N26", "Q26"), ExcelMissing.Value }, "#ERROR _CreateFuturesCurve: price is missing, expected column of numbers" };
            // The daily fixings: a header row, a body of dates and settles and the market's calendar by handle. The calendar left out, a number in its place and text naming no live object fail in the seam's words, and the seam says so before it looks at the table, so every row that expects the table's words, and the library's rules, which need a live calendar, are in the fact below.
            yield return new object[] { "_CreateDailyFixings", new object[] { Row("date", "settle"), new object[,] { { 46143.0, 101.94 }, { 46146.0, 106.42 } }, ExcelMissing.Value }, "#ERROR _CreateDailyFixings: holiday_calendar is missing, expected holiday calendar handle" };
            yield return new object[] { "_CreateDailyFixings", new object[] { Row("date", "settle"), new object[,] { { 46143.0, 101.94 }, { 46146.0, 106.42 } }, 101.94 }, "#ERROR _CreateDailyFixings: holiday_calendar is number 101.94, expected holiday calendar handle" };
            yield return new object[] { "_CreateDailyFixings", new object[] { Row("date", "settle"), new object[,] { { 46143.0, 101.94 }, { 46146.0, 106.42 } }, "x" }, "#ERROR _CreateDailyFixings: holiday_calendar is text 'x' naming no live object, expected holiday calendar handle" };
            // The monthly fixings: a column of publication days, a column of prices and the index's schedule by handle. Text among the days and a blank among the prices fail before the schedule is looked at; the schedule left out and a number in its place fail in the seam's words. The library's rules, which need a live schedule, are in the fact below.
            yield return new object[] { "_CreateMonthlyFixings", new object[] { Column("Jan-26", 46055.0), Column(1.85, 2.10), ExcelMissing.Value }, "#ERROR _CreateMonthlyFixings: publication_date cell (1, 1) is text 'Jan-26', expected date" };
            yield return new object[] { "_CreateMonthlyFixings", new object[] { Column(46027.0, 46055.0), Column(1.85, ExcelEmpty.Value), ExcelMissing.Value }, "#ERROR _CreateMonthlyFixings: price cell (2, 1) is blank, expected number" };
            yield return new object[] { "_CreateMonthlyFixings", new object[] { Column(46027.0, 46055.0), Column(1.85, 2.10), ExcelMissing.Value }, "#ERROR _CreateMonthlyFixings: expiry_schedule is missing, expected expiry schedule handle" };
            yield return new object[] { "_CreateMonthlyFixings", new object[] { Column(46027.0, 46055.0), Column(1.85, 2.10), 2.86 }, "#ERROR _CreateMonthlyFixings: expiry_schedule is number 2.86, expected expiry schedule handle" };
            // The calendar: three handles, the valuation date, the expiry schedule and the holiday calendar. A number, a missing argument and text naming no live object where the valuation date should be fail in the seam's words; the library's rules and the wrong kinds, which need live handles, are in the fact below.
            yield return new object[] { "_CreateCalendar", new object[] { 46167.0, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateCalendar: valuation_date is number 46167.0, expected valuation date handle" };
            yield return new object[] { "_CreateCalendar", new object[] { ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateCalendar: valuation_date is missing, expected valuation date handle" };
            yield return new object[] { "_CreateCalendar", new object[] { "x", ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateCalendar: valuation_date is text 'x' naming no live object, expected valuation date handle" };
        }

        // An expiry schedule: three columns make one, two make one for an index without options,
        // four make one with the publication dates, and the publication dates with the options
        // left out make one whose spill puts them last; each creator call publishes its own handle.
        [Fact]
        public void an_expiry_schedule_is_created_with_and_without_options_and_publication_dates()
        {
            var codes = Column("m26", "n26", "q26");
            var futures = Column(46161.0, 46195.0, 46224.0);
            var options = Column(46156.0, 46189.0, 46219.0);
            var publications = Column(46162.0, 46196.0, 46225.0);
            var withOptions = (string)Seam.Call("_CreateExpirySchedule", codes, futures, options, ExcelMissing.Value);
            var withoutOptions = (string)Seam.Call("_CreateExpirySchedule", codes, futures, ExcelMissing.Value, ExcelMissing.Value);
            var withPublications = (string)Seam.Call("_CreateExpirySchedule", codes, futures, options, publications);
            var publishedWithoutOptions = (string)Seam.Call("_CreateExpirySchedule", codes, futures, ExcelMissing.Value, publications);
            Assert.StartsWith("expiry_schedule:", withOptions);
            Assert.StartsWith("expiry_schedule:", withoutOptions);
            Assert.StartsWith("expiry_schedule:", withPublications);
            Assert.StartsWith("expiry_schedule:", publishedWithoutOptions);
            Assert.NotEqual(withOptions, withoutOptions);
            Assert.NotEqual(withPublications, publishedWithoutOptions);
            var spill = (object[,])Seam.Call("util_ReadHandle", withPublications);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(4, spill.GetLength(1));
            Assert.Equal("publication_date", spill[0, 3]);
            Assert.Equal("datetime64[D]", spill[1, 3]);
            Assert.Equal(46225.0, spill[4, 3]);
            var published = (object[,])Seam.Call("util_ReadHandle", publishedWithoutOptions);
            Assert.Equal(3, published.GetLength(1));
            Assert.Equal("publication_date", published[0, 2]);
            Assert.Equal(46162.0, published[2, 2]);
        }

        // A holiday calendar: a column of dates makes one, a single cell makes one of one day, and
        // util_ReadHandle spills it back, the header, the type, then a row per holiday.
        [Fact]
        public void a_holiday_calendar_is_created_from_a_column_and_read_back_through_its_handle()
        {
            var handle = (string)Seam.Call("_CreateHolidayCalendar", Column(46023.0, 46041.0, 46069.0));
            Assert.StartsWith("holiday_calendar:", handle);
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

        // Index conventions: five codes make one, and util_ReadHandle spills them back, the five
        // headers, five types, then the codes as typed in one row.
        [Fact]
        public void index_conventions_are_created_from_five_codes_and_read_back_through_their_handle()
        {
            var handle = (string)Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "volume", "BBL");
            Assert.StartsWith("index_conventions:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(3, spill.GetLength(0));
            Assert.Equal(5, spill.GetLength(1));
            Assert.Equal("quantity_type", spill[0, 3]);
            Assert.Equal("str", spill[1, 0]);
            Assert.Equal("volume", spill[2, 3]);
            Assert.Equal("BBL", spill[2, 4]);
        }

        // Contract specifications: a header row and two contracts make one, and util_ReadHandle spills them
        // back, the four headers, four types, then one row per contract, the name as text and the
        // lot size and fees as numbers.
        [Fact]
        public void contract_specifications_are_created_from_a_table_and_read_back_through_their_handle()
        {
            var handle = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, 3.0, 2.0 }, { "ICE NG", 2500.0, 0.75, 0.5 } });
            Assert.StartsWith("contract_specifications:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(4, spill.GetLength(0));
            Assert.Equal(4, spill.GetLength(1));
            Assert.Equal("lot_size", spill[0, 1]);
            Assert.Equal("float64", spill[1, 1]);
            Assert.Equal("ICE NG", spill[3, 0]);
            Assert.Equal(2500.0, spill[3, 1]);
            Assert.Equal(0.75, spill[3, 2]);
        }

        // A futures curve: two columns make one, and util_ReadHandle spills it back, the two
        // headers, two types, then a row per contract, the code as text and the price as a number.
        [Fact]
        public void a_futures_curve_is_created_from_two_columns_and_read_back_through_its_handle()
        {
            var handle = (string)Seam.Call("_CreateFuturesCurve", Column("M26", "N26", "Q26"), Column(71.25, 71.4, 71.1));
            Assert.StartsWith("futures_curve:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(2, spill.GetLength(1));
            Assert.Equal("price", spill[0, 1]);
            Assert.Equal("float64", spill[1, 1]);
            Assert.Equal("M26", spill[2, 0]);
            Assert.Equal(71.4, spill[3, 1]);
        }

        // Daily fixings: a header row, a body and the market's calendar make one, and util_ReadHandle
        // spills it back, the two headers, two types, then a row per day, the date as a serial and
        // the settle as a number. With the calendar live, the table's faults say so, text where a
        // settle is expected and a header the table does not have, and the library's rules answer:
        // the days newest first, a business day without a fixing, a Saturday, a listed holiday, and
        // a handle of another kind where the calendar should be.
        [Fact]
        public void daily_fixings_are_created_from_a_table_and_a_calendar_and_read_back_through_their_handle()
        {
            var headers = Row("date", "settle");
            var calendar = (string)Seam.Call("_CreateHolidayCalendar", Column(46023.0, 46041.0, 46069.0));
            var handle = (string)Seam.Call("_CreateDailyFixings", headers, new object[,] { { 46143.0, 101.94 }, { 46146.0, 106.42 } }, calendar);
            Assert.StartsWith("daily_fixings:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(4, spill.GetLength(0));
            Assert.Equal(2, spill.GetLength(1));
            Assert.Equal("settle", spill[0, 1]);
            Assert.Equal("datetime64[D]", spill[1, 0]);
            Assert.Equal(46143.0, spill[2, 0]);
            Assert.Equal(106.42, spill[3, 1]);
            Assert.Equal("#ERROR _CreateDailyFixings: table cell (1, 2) is text 'x', expected number", Seam.Call("_CreateDailyFixings", headers, new object[,] { { 46143.0, "x" }, { 46146.0, 106.42 } }, calendar));
            Assert.Equal("#ERROR _CreateDailyFixings: header_row cell (1, 2) is text 'price', expected one of date or settle", Seam.Call("_CreateDailyFixings", Row("date", "price"), new object[,] { { 46143.0, 101.94 } }, calendar));
            Assert.Equal("#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-05, expected a date after row 1's 2026-05-06", Seam.Call("_CreateDailyFixings", headers, new object[,] { { 46148.0, 95.08 }, { 46147.0, 102.27 } }, calendar));
            Assert.Equal("#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-05, expected 2026-05-04, the business day after row 1's 2026-05-01", Seam.Call("_CreateDailyFixings", headers, new object[,] { { 46143.0, 101.94 }, { 46147.0, 102.27 } }, calendar));
            Assert.Equal("#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-02, a Saturday, expected a business day", Seam.Call("_CreateDailyFixings", headers, new object[,] { { 46143.0, 101.94 }, { 46144.0, 100.0 } }, calendar));
            Assert.Equal("#ERROR _CreateDailyFixings: ValueError: date row 1 is 2026-01-19, a holiday, expected a business day", Seam.Call("_CreateDailyFixings", headers, new object[,] { { 46041.0, 100.0 } }, calendar));
            Assert.Equal("#ERROR _CreateDailyFixings: holiday_calendar is daily fixings handle '" + handle + "', expected holiday calendar handle", Seam.Call("_CreateDailyFixings", headers, new object[,] { { 46143.0, 101.94 } }, handle));
        }

        // The calendar: the valuation date, a three-contract schedule and a one-day holiday calendar
        // make one, and util_ReadHandle spills it back, the four headers, the four types, then a row
        // per day, the date as a serial, the prompt contract as text and the two flags as booleans.
        // The library's rules answer through the same objects: a schedule of one contract, a code
        // given twice, expiries backwards and a span no sheet could show; and a handle of another
        // kind where the holiday calendar should be.
        [Fact]
        public void a_calendar_is_created_from_three_handles_and_read_back_through_its_handle()
        {
            var valuation = (string)Seam.Call("_CreateValuationDate", 46167.0, 0.5);
            var schedule = (string)Seam.Call("_CreateExpirySchedule", Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value, ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46167.0);
            var handle = (string)Seam.Call("_CreateCalendar", valuation, schedule, holidays);
            Assert.StartsWith("calendar:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(65, spill.GetLength(0));
            Assert.Equal(4, spill.GetLength(1));
            Assert.Equal("prompt_contract", spill[0, 1]);
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
            var one = (string)Seam.Call("_CreateExpirySchedule", Column("m26"), Column(46161.0), ExcelMissing.Value, ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateCalendar: ValueError: expiry_schedule has 1 contract, expected at least 2", Seam.Call("_CreateCalendar", valuation, one, holidays));
            var twice = (string)Seam.Call("_CreateExpirySchedule", Column("m26", "m26"), Column(46161.0, 46195.0), ExcelMissing.Value, ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateCalendar: ValueError: future_code row 2 is 'm26', already given at row 1", Seam.Call("_CreateCalendar", valuation, twice, holidays));
            var backwards = (string)Seam.Call("_CreateExpirySchedule", Column("m26", "n26"), Column(46195.0, 46161.0), ExcelMissing.Value, ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22", Seam.Call("_CreateCalendar", valuation, backwards, holidays));
            var tooLong = (string)Seam.Call("_CreateExpirySchedule", Column("m26", "n26"), Column(46161.0, 1094736.0), ExcelMissing.Value, ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19", Seam.Call("_CreateCalendar", valuation, tooLong, holidays));
            Assert.Equal("#ERROR _CreateCalendar: holiday_calendar is calendar handle '" + handle + "', expected holiday calendar handle", Seam.Call("_CreateCalendar", valuation, schedule, handle));
        }

        // Monthly fixings: a column of publication days, a column of prices and the index's schedule
        // make one, and util_ReadHandle spills it back, the two headers, the day type over the price
        // type, then a row per fixing. With the schedule live, the library's rules answer: a price
        // column one row short, a day the schedule does not publish on, the days backwards, a
        // publication skipped, and a schedule built without publication dates.
        [Fact]
        public void monthly_fixings_are_created_from_two_columns_and_a_schedule_and_read_back_through_their_handle()
        {
            var codes = Column("F26", "G26", "H26");
            var futures = Column(46022.0, 46052.0, 46080.0);
            var schedule = (string)Seam.Call("_CreateExpirySchedule", codes, futures, ExcelMissing.Value, Column(46027.0, 46055.0, 46083.0));
            var handle = (string)Seam.Call("_CreateMonthlyFixings", Column(46027.0, 46055.0), Column(1.85, 2.10), schedule);
            Assert.StartsWith("monthly_fixings:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(4, spill.GetLength(0));
            Assert.Equal(2, spill.GetLength(1));
            Assert.Equal("publication_date", spill[0, 0]);
            Assert.Equal("datetime64[D]", spill[1, 0]);
            Assert.Equal(46027.0, spill[2, 0]);
            Assert.Equal(2.10, spill[3, 1]);
            Assert.Equal("#ERROR _CreateMonthlyFixings: ValueError: price has 1 price, expected 2, one per publication_date", Seam.Call("_CreateMonthlyFixings", Column(46027.0, 46055.0), Column(1.85), schedule));
            Assert.Equal("#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-01-06, expected one of the schedule's publication dates", Seam.Call("_CreateMonthlyFixings", Column(46027.0, 46028.0), Column(1.85, 2.10), schedule));
            Assert.Equal("#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-01-05, expected a date after row 1's 2026-02-02", Seam.Call("_CreateMonthlyFixings", Column(46055.0, 46027.0), Column(2.10, 1.85), schedule));
            Assert.Equal("#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-03-02, expected 2026-02-02, the schedule's publication after row 1's 2026-01-05", Seam.Call("_CreateMonthlyFixings", Column(46027.0, 46083.0), Column(1.85, 1.95), schedule));
            var unpublished = (string)Seam.Call("_CreateExpirySchedule", codes, futures, ExcelMissing.Value, ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateMonthlyFixings: ValueError: expiry_schedule has no publication dates, expected a schedule with one per contract", Seam.Call("_CreateMonthlyFixings", Column(46027.0, 46055.0), Column(1.85, 2.10), unpublished));
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
            Assert.StartsWith("discount_curve:", handle);
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
