using System.Collections.Generic;
using ExcelDna.Integration;
using Xunit;

namespace Catalyst.Host.Tests
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
            var handle = (string)Seam.Call("_CreateIndex", name, name + " index", schedule, conventions, specifications, holidays, "NYMEX NG");
            Assert.StartsWith(Pid + ":index:" + name + ":", handle);
            return handle;
        }

        // The column of a readback under a heading, or -1 when no column carries it.
        private static int Heading(object[,] grid, string name)
        {
            for (var j = 0; j < grid.GetLength(1); j++)
            {
                if (Equals(grid[0, j], name))
                {
                    return j;
                }
            }
            return -1;
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
            yield return new object[] { "_CreateDiscountCurve", new object[] { "SOFR", Row("date", "discount_factor"), Curve(0.98) }, "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date" };
            // The curve from anchors: dates that run backwards are never sorted, and a span no sheet could show is refused.
            yield return new object[] { "_CreateDiscountCurve", new object[] { "SOFR", Row("date", "discount_factor"), new object[,] { { 46279.0, 1.0 }, { 46276.0, 0.9997 } } }, "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 2026-09-11, expected a date after row 1's 2026-09-14" };
            yield return new object[] { "_CreateDiscountCurve", new object[] { "SOFR", Row("date", "discount_factor"), new object[,] { { 46276.0, 1.0 }, { 1094850.0, 0.5 } } }, "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 4897-08-04, expected within 1048573 days of row 1's 2026-09-11" };
            yield return new object[] { "_CreateDiscountCurve", new object[] { "SOFR ", Row("date", "discount_factor"), Curve() }, "#ERROR _CreateDiscountCurve: ValueError: name is 'SOFR ', expected a name with no whitespace around it" };
            yield return new object[] { "_CreateDiscountCurve", new object[] { "", Row("date", "discount_factor"), Curve() }, "#ERROR _CreateDiscountCurve: name is empty text, expected text" };
            yield return new object[] { "_CreateDiscountCurve", new object[] { Row("date", "discount_factor"), Row("date", "discount_factor"), Curve() }, "#ERROR _CreateDiscountCurve: name is 1x2 array, expected text" };
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
            // Contract prices interpolated between anchors: the index handle first, missing or naming no live object, in the seam's words; the live index and the library's rules are in the fact below.
            yield return new object[] { "util_InterpolateContracts", new object[] { ExcelMissing.Value, Column("J27", "M27"), Column(70.0, 76.0) }, "#ERROR util_InterpolateContracts: index is missing, expected index handle" };
            yield return new object[] { "util_InterpolateContracts", new object[] { "x", Column("J27", "M27"), Column(70.0, 76.0) }, "#ERROR util_InterpolateContracts: index is text 'x' naming no live object, expected index handle" };
            // Cashflows: the template handle last and required, missing in the seam's words; the evaluator's handles missing or naming nothing; the live batch and the library's rules are in the fact below.
            yield return new object[] { "_CreateCashflows", new object[] { Row("trade_date"), Row(46391.0), ExcelMissing.Value }, "#ERROR _CreateCashflows: template is missing, expected trade template handle" };
            yield return new object[] { "_EvaluateCashflows", new object[] { ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _EvaluateCashflows: cashflows is missing, expected cashflows handle" };
            yield return new object[] { "_EvaluateCashflows", new object[] { "x", ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _EvaluateCashflows: cashflows is text 'x' naming no live object, expected cashflows handle" };
            // A discount curve bumped by basis points: the curve first, missing, text naming nothing or a number, in the seam's words; the live curve and the library's rule are in the fact below.
            yield return new object[] { "util_BumpDiscountCurve", new object[] { ExcelMissing.Value, 1.0 }, "#ERROR util_BumpDiscountCurve: curve is missing, expected discount curve handle" };
            yield return new object[] { "util_BumpDiscountCurve", new object[] { "x", 1.0 }, "#ERROR util_BumpDiscountCurve: curve is text 'x' naming no live object, expected discount curve handle" };
            yield return new object[] { "util_BumpDiscountCurve", new object[] { 46276.0, 1.0 }, "#ERROR util_BumpDiscountCurve: curve is number 46276.0, expected discount curve handle" };
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
            yield return new object[] { "util_StartDate", new object[] { "f26", ExcelMissing.Value }, 46023.0 };
            yield return new object[] { "util_EndDate", new object[] { "f26", ExcelMissing.Value }, 46053.0 };
            yield return new object[] { "util_StartDate", new object[] { "1Q27", ExcelMissing.Value }, 46388.0 };
            yield return new object[] { "util_EndDate", new object[] { "1Q27", ExcelMissing.Value }, 46477.0 };
            yield return new object[] { "util_StartDate", new object[] { "cal28", ExcelMissing.Value }, 46753.0 };
            yield return new object[] { "util_EndDate", new object[] { "CAL28", ExcelMissing.Value }, 47118.0 };
            yield return new object[] { "util_StartDate", new object[] { "W29", ExcelMissing.Value }, 47423.0 };
            yield return new object[] { "util_EndDate", new object[] { "W29", ExcelMissing.Value }, 47573.0 };
            yield return new object[] { "util_StartDate", new object[] { "s28", ExcelMissing.Value }, 46844.0 };
            yield return new object[] { "util_EndDate", new object[] { "s28", ExcelMissing.Value }, 47057.0 };
            yield return new object[] { "util_StartDate", new object[] { "F26-Z28", ExcelMissing.Value }, 46023.0 };
            yield return new object[] { "util_EndDate", new object[] { "F26-Z28", ExcelMissing.Value }, 47118.0 };
            yield return new object[] { "util_EndDate", new object[] { "w28-w29", ExcelMissing.Value }, 47573.0 };
            // Half-year strips, half-year-strips.md: 1H27 January to June and 2H27 July to December in either case, H27 March as it was, the ranges of halves, a leap first half; a zeroth and a third half, a one-digit and a four-digit year refused by the grammar, a reversed range by its order.
            yield return new object[] { "util_StartDate", new object[] { "1h27", ExcelMissing.Value }, 46388.0 };
            yield return new object[] { "util_EndDate", new object[] { "1H27", ExcelMissing.Value }, 46568.0 };
            yield return new object[] { "util_StartDate", new object[] { "2H27", ExcelMissing.Value }, 46569.0 };
            yield return new object[] { "util_EndDate", new object[] { "2h27", ExcelMissing.Value }, 46752.0 };
            yield return new object[] { "util_StartDate", new object[] { "H27", ExcelMissing.Value }, 46447.0 };
            yield return new object[] { "util_EndDate", new object[] { "1H27-2H27", ExcelMissing.Value }, 46752.0 };
            yield return new object[] { "util_StartDate", new object[] { "2H27-1H28", ExcelMissing.Value }, 46569.0 };
            yield return new object[] { "util_EndDate", new object[] { "2H27-1H28", ExcelMissing.Value }, 46934.0 };
            yield return new object[] { "util_EndDate", new object[] { "1H28", ExcelMissing.Value }, 46934.0 };
            yield return new object[] { "util_StartDate", new object[] { "0H27", ExcelMissing.Value }, "#ERROR util_StartDate: ValueError: period is '0H27', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_EndDate", new object[] { "3H27", ExcelMissing.Value }, "#ERROR util_EndDate: ValueError: period is '3H27', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_StartDate", new object[] { "1H7", ExcelMissing.Value }, "#ERROR util_StartDate: ValueError: period is '1H7', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_EndDate", new object[] { "1H2027", ExcelMissing.Value }, "#ERROR util_EndDate: ValueError: period is '1H2027', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_StartDate", new object[] { "2H27-1H27", ExcelMissing.Value }, "#ERROR util_StartDate: ValueError: period is '2H27-1H27', expected range endpoints in chronological order" };
            yield return new object[] { "util_StartDate", new object[] { "W8-W9", ExcelMissing.Value }, "#ERROR util_StartDate: ValueError: period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_EndDate", new object[] { "W8-W9", ExcelMissing.Value }, "#ERROR util_EndDate: ValueError: period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_StartDate", new object[] { "Z28-F26", ExcelMissing.Value }, "#ERROR util_StartDate: ValueError: period is 'Z28-F26', expected range endpoints in chronological order" };
            yield return new object[] { "util_EndDate", new object[] { "CAL28-F28", ExcelMissing.Value }, "#ERROR util_EndDate: ValueError: period is 'CAL28-F28', expected range endpoints in chronological order" };
            yield return new object[] { "util_StartDate", new object[] { 46023.0, ExcelMissing.Value }, "#ERROR util_StartDate: period is number 46023.0, expected text" };
            yield return new object[] { "util_EndDate", new object[] { "", ExcelMissing.Value }, "#ERROR util_EndDate: period is empty text, expected text" };
            // The balance of a period, date-helper-inputs.md: the second argument is a valuation-date handle since #173, so a raw date, a blank, a text and a fraction of a day fail in the seam's words whatever the label, a BAL label without one in the library's, and a malformed or reversed label under the prefix as any label does; the balances themselves are a fact below, their handles made at run time.
            yield return new object[] { "util_StartDate", new object[] { "BALZ26", ExcelMissing.Value }, "#ERROR util_StartDate: ValueError: valuation_date is missing, expected a valuation-date handle with 'BALZ26', whose day starts the balance of a period" };
            yield return new object[] { "util_EndDate", new object[] { "BALZ26", ExcelMissing.Value }, "#ERROR util_EndDate: ValueError: valuation_date is missing, expected a valuation-date handle with 'BALZ26', whose day starts the balance of a period" };
            yield return new object[] { "util_StartDate", new object[] { "BALZ26", 46371.0 }, "#ERROR util_StartDate: valuation_date is number 46371.0, expected valuation date handle" };
            yield return new object[] { "util_StartDate", new object[] { "Z26", 46371.0 }, "#ERROR util_StartDate: valuation_date is number 46371.0, expected valuation date handle" };
            yield return new object[] { "util_StartDate", new object[] { "BALZ26", ExcelEmpty.Value }, "#ERROR util_StartDate: valuation_date is blank, expected valuation date handle" };
            yield return new object[] { "util_StartDate", new object[] { "BALZ26", "15-Dec-2026" }, "#ERROR util_StartDate: valuation_date is text '15-Dec-2026' naming no live object, expected valuation date handle" };
            yield return new object[] { "util_EndDate", new object[] { "BALZ26", 46371.5 }, "#ERROR util_EndDate: valuation_date is number 46371.5, expected valuation date handle" };
            yield return new object[] { "util_StartDate", new object[] { "BALBALZ26", ExcelMissing.Value }, "#ERROR util_StartDate: ValueError: period is 'BALBALZ26', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28" };
            yield return new object[] { "util_EndDate", new object[] { "BALZ28-F26", ExcelMissing.Value }, "#ERROR util_EndDate: ValueError: period is 'BALZ28-F26', expected range endpoints in chronological order" };
            // A date shifted by a text offset, the calendar left out: the ticket's table, Friday 9 October 2026 at 46304, the Saturday at 46305 and the Sunday at 46306; the month ends through a leap February; the library's words for no offset, a result past the sheet's calendar and a count of too many digits; the seam's for the date, the offset and a blank where the calendar should be, a blank being no omission.
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+1bd", ExcelMissing.Value }, 46307.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46305.0, "+1bd", ExcelMissing.Value }, 46307.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46306.0, "-1bd", ExcelMissing.Value }, 46304.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46305.0, "+0bd", ExcelMissing.Value }, 46305.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+7cd", ExcelMissing.Value }, 46311.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "-7cd", ExcelMissing.Value }, 46297.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+0em", ExcelMissing.Value }, 46326.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+1em", ExcelMissing.Value }, 46356.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "-1em", ExcelMissing.Value }, 46295.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46783.0, "+1em", ExcelMissing.Value }, 46812.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46371.0, "+1em", ExcelMissing.Value }, 46418.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+001cD", ExcelMissing.Value }, 46305.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 2958465.0, "+0em", ExcelMissing.Value }, 2958465.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "1bd", ExcelMissing.Value }, "#ERROR util_ShiftDate: ValueError: offset is '1bd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd" };
            // Since #181 a chain, compound-date-offsets.md: the requested chain from 12 August 2026 without a calendar, 25 December; the order the rule and no roll at the end; a chain malformed late, one leaving the sheet at its first instruction and too many digits in a later one.
            yield return new object[] { "util_ShiftDate", new object[] { 46246.0, "+3em+25cd-1bd+1bd", ExcelMissing.Value }, 46381.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46246.0, "+003EM+025cD-01BD+001bd", ExcelMissing.Value }, 46381.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "-1bd+1bd", ExcelMissing.Value }, 46304.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46305.0, "-1bd+1bd", ExcelMissing.Value }, 46307.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46052.0, "+1cd+0em", ExcelMissing.Value }, 46053.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46052.0, "+0em+1cd", ExcelMissing.Value }, 46054.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46783.0, "+1em+1cd", ExcelMissing.Value }, 46813.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46305.0, "+0bd+0cd", ExcelMissing.Value }, 46305.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+1cd", ExcelMissing.Value }, 46305.0 };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+1bd+2xd", ExcelMissing.Value }, "#ERROR util_ShiftDate: ValueError: offset is '+1bd+2xd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd; from character 5, '+2xd' begins with no instruction" };
            yield return new object[] { "util_ShiftDate", new object[] { 2958465.0, "+1cd-1cd", ExcelMissing.Value }, "#ERROR util_ShiftDate: ValueError: date 9999-12-31 shifted by '+1cd-1cd' is 10000-01-01 at instruction 1, '+1cd', outside the sheet's calendar, 1900-03-01 to 9999-12-31" };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+1bd+99999999cd", ExcelMissing.Value }, "#ERROR util_ShiftDate: ValueError: offset has a count of 8 digits in instruction 2, '+99999999cd', expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31" };
            yield return new object[] { "util_ShiftDate", new object[] { 2958465.0, "+1cd", ExcelMissing.Value }, "#ERROR util_ShiftDate: ValueError: date 9999-12-31 shifted by '+1cd' is 10000-01-01, outside the sheet's calendar, 1900-03-01 to 9999-12-31" };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+99999999cd", ExcelMissing.Value }, "#ERROR util_ShiftDate: ValueError: offset has a count of 8 digits, expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31" };
            yield return new object[] { "util_ShiftDate", new object[] { ExcelMissing.Value, "+1bd", ExcelMissing.Value }, "#ERROR util_ShiftDate: date is missing, expected date" };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.5, "+1bd", ExcelMissing.Value }, "#ERROR util_ShiftDate: date is number 46304.5, expected date" };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, ExcelEmpty.Value, ExcelMissing.Value }, "#ERROR util_ShiftDate: offset is blank, expected text" };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, 1.0, ExcelMissing.Value }, "#ERROR util_ShiftDate: offset is number 1.0, expected text" };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+1bd", ExcelEmpty.Value }, "#ERROR util_ShiftDate: holiday_calendar is blank, expected holiday calendar handle" };
            yield return new object[] { "util_ShiftDate", new object[] { 46304.0, "+7cd", "x:holiday_calendar:9" }, "#ERROR util_ShiftDate: holiday_calendar is text 'x:holiday_calendar:9' naming no live object, expected holiday calendar handle" };
            // The instrument catalog's show: one exact name in. Another case, a blank, a number and a left-out name fail, the name in the library's words and the rest in the seam's; the spills are in the catalog fact below.
            yield return new object[] { "_ShowInstrument", new object[] { "Future" }, "#ERROR _ShowInstrument: ValueError: instrument is 'Future', expected one of: 'fixed_float', 'cashflow'" };
            yield return new object[] { "_ShowInstrument", new object[] { "future" }, "#ERROR _ShowInstrument: ValueError: instrument is 'future', expected one of: 'fixed_float', 'cashflow'" };  // the name until #174
            yield return new object[] { "_ShowInstrument", new object[] { ExcelEmpty.Value }, "#ERROR _ShowInstrument: instrument is blank, expected text" };
            yield return new object[] { "_ShowInstrument", new object[] { 1.0 }, "#ERROR _ShowInstrument: instrument is number 1.0, expected text" };
            yield return new object[] { "_ShowInstrument", new object[] { ExcelMissing.Value }, "#ERROR _ShowInstrument: instrument is missing, expected text" };
            // A row or rows of an instrument's fields, through the two probes: the name in another case in the library's words, then the width, the headers in input order, exact, and the cells column by column, in the seam's; a handle cell naming no live object; two rows where one is wanted.
            yield return new object[] { "CountFieldRows", new object[] { "fixed_float", Row("quantity", "fixed_price"), new object[,] { { 1.0, 3.1 }, { 2.0, 3.2 }, { 3.0, 3.3 } } }, 3.0 };
            yield return new object[] { "EchoFieldRow", new object[] { "Future", Row("quantity"), 1.0 }, "#ERROR EchoFieldRow: ValueError: instrument is 'Future', expected one of: 'fixed_float', 'cashflow'" };
            yield return new object[] { "EchoFieldRow", new object[] { "fixed_float", Row("quantity"), Row(1.0, 2.0) }, "#ERROR EchoFieldRow: fields has 1 headers, expected 2, one per column of values" };
            yield return new object[] { "EchoFieldRow", new object[] { "fixed_float", Row("Quantity"), 1.0 }, "#ERROR EchoFieldRow: fields cell (1, 1) is text 'Quantity', expected a field of fixed_float: trade_id, trade_date, contract_code, start_date, end_date, schedule_method, route, settlement_method, clearing_house, counterparty, discount_curve_key, broker, quantity, quantity_unit, quantity_per, fixed_price, second_schedule_method, payment_day, payment_holiday_calendar, marketing_reserve, cva_reserve, settlement_frequency, nearby" };
            yield return new object[] { "EchoFieldRow", new object[] { "fixed_float", Row("quantity", "quantity"), Row(1.0, 2.0) }, "#ERROR EchoFieldRow: fields cell (1, 2) is text 'quantity', already given at cell (1, 1)" };
            yield return new object[] { "EchoFieldRow", new object[] { "fixed_float", Row("quantity", "fixed_price"), Row("ten", "eleven") }, "#ERROR EchoFieldRow: values cell (1, 1) is text 'ten', expected number" };
            yield return new object[] { "EchoFieldRow", new object[] { "fixed_float", Row("trade_date"), 46164.5 }, "#ERROR EchoFieldRow: values cell (1, 1) is number 46164.5, expected date" };
            yield return new object[] { "EchoFieldRow", new object[] { "fixed_float", Row("payment_holiday_calendar"), "x:holiday_calendar:9" }, "#ERROR EchoFieldRow: values cell (1, 1) is text 'x:holiday_calendar:9' naming no live object, expected holiday calendar handle" };
            yield return new object[] { "EchoFieldRow", new object[] { "fixed_float", Row("quantity"), Column(1.0, 2.0) }, "#ERROR EchoFieldRow: values is 2x1 array, expected one row of field values" };
            // The trade template: the name in another case in the library's words; two rows where one is wanted, the extra row filled or blank, and a number where text is expected in the seam's; a value against its field's own rule in the library's. The trades: the index and the template left out, and a text naming no live object, in the seam's words, before any binding; the batch itself is in the fact below.
            yield return new object[] { "_CreateTradeTemplate", new object[] { "Future", Row("quantity_unit"), "NYMEX NG" }, "#ERROR _CreateTradeTemplate: ValueError: instrument is 'Future', expected one of: 'fixed_float', 'cashflow'" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "fixed_float", Row("quantity_unit"), Column("NYMEX NG", "NYMEX NG") }, "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "fixed_float", Row("quantity_unit"), Column("NYMEX NG", ExcelEmpty.Value) }, "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "fixed_float", Row("quantity_unit"), 1.0 }, "#ERROR _CreateTradeTemplate: values cell (1, 1) is number 1.0, expected text" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "fixed_float", Row("quantity_unit", "schedule_method"), Row("NYMEX NG", "Asian") }, "#ERROR _CreateTradeTemplate: ValueError: schedule_method is 'Asian', expected lastday, penultimate, last3day or asian" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "fixed_float", Row("payment_day"), "2bd" }, "#ERROR _CreateTradeTemplate: ValueError: payment_day is '2bd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "fixed_float", Row("payment_day"), "+1bd+2xd" }, "#ERROR _CreateTradeTemplate: ValueError: payment_day is '+1bd+2xd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd; from character 5, '+2xd' begins with no instruction" };
            yield return new object[] { "_CreateTradeTemplate", new object[] { "fixed_float", Row("quantity"), 1.5 }, "#ERROR _CreateTradeTemplate: ValueError: quantity is 1.5, expected a whole number" };
            // The quote template, template-based-quoting.md: a booking field and a blank period header refused by name, the cashflow refused as no instrument a quote prices, a value by the trade template's rule; and the quote's arguments in the seam's words, the market left out or naming nothing.
            yield return new object[] { "_CreateQuoteTemplate", new object[] { "fixed_float", Row("route", "quantity"), Row("cleared", 10.0) }, "#ERROR _CreateQuoteTemplate: ValueError: quantity is a field of booking alone, expected one a quote template holds: schedule_method, route, settlement_method, discount_curve_key, quantity_per, payment_day, payment_holiday_calendar, settlement_frequency, nearby" };
            yield return new object[] { "_CreateQuoteTemplate", new object[] { "fixed_float", Row("contract_code", "route"), Row(ExcelEmpty.Value, "cleared") }, "#ERROR _CreateQuoteTemplate: ValueError: contract_code is a field of booking alone, expected one a quote template holds: schedule_method, route, settlement_method, discount_curve_key, quantity_per, payment_day, payment_holiday_calendar, settlement_frequency, nearby" };
            yield return new object[] { "_CreateQuoteTemplate", new object[] { "cashflow", Row("currency"), "USD" }, "#ERROR _CreateQuoteTemplate: ValueError: instrument is 'cashflow', expected one a quote prices: 'fixed_float'" };
            yield return new object[] { "_CreateQuoteTemplate", new object[] { "fixed_float", Row("route"), "Cleared" }, "#ERROR _CreateQuoteTemplate: ValueError: route is 'Cleared', expected cleared or bilateral" };
            yield return new object[] { "_Quote", new object[] { ExcelMissing.Value, "F27", ExcelMissing.Value, "flat", ExcelMissing.Value }, "#ERROR _Quote: market is missing, expected market handle" };
            yield return new object[] { "_Quote", new object[] { "x:market:gas:9", "F27", "y:quote_template:9", "flat", ExcelMissing.Value }, "#ERROR _Quote: market is text 'x:market:gas:9' naming no live object, expected market handle" };
            yield return new object[] { "_QuoteByDates", new object[] { ExcelMissing.Value, 46168.0, 46198.0, ExcelMissing.Value, "flat", ExcelMissing.Value }, "#ERROR _QuoteByDates: market is missing, expected market handle" };
            yield return new object[] { "_QuoteByDates", new object[] { "x:market:gas:9", "26-May-2026", 46198.0, "y:quote_template:9", "flat", ExcelMissing.Value }, "#ERROR _QuoteByDates: market is text 'x:market:gas:9' naming no live object, expected market handle" };
            yield return new object[] { "_CreateRFQ", new object[] { ExcelMissing.Value, Row("contract_code", "quantity"), Row("F27", 1.0), ExcelMissing.Value }, "#ERROR _CreateRFQ: index is missing, expected index handle" };
            yield return new object[] { "_CreateRFQ", new object[] { "x:index:gas:9", Row("contract_code", "quantity"), Row("F27", 1.0), "y:quote_template:9" }, "#ERROR _CreateRFQ: index is text 'x:index:gas:9' naming no live object, expected index handle" };
            yield return new object[] { "_QuoteRFQ", new object[] { ExcelMissing.Value, "x:rfq:gas:9", "flat", ExcelMissing.Value }, "#ERROR _QuoteRFQ: market is missing, expected market handle" };
            yield return new object[] { "_QuoteRFQ", new object[] { "x:market:gas:9", "x:rfq:gas:9", "flat", ExcelMissing.Value }, "#ERROR _QuoteRFQ: market is text 'x:market:gas:9' naming no live object, expected market handle" };
            yield return new object[] { "_QuoteFTCPrices", new object[] { ExcelMissing.Value, "x:rfq:gas:9", 3.95, 2.0 }, "#ERROR _QuoteFTCPrices: market is missing, expected market handle" };
            yield return new object[] { "_QuoteFTCPrices", new object[] { "x:market:gas:9", "x:rfq:gas:9", 3.95, 2.0 }, "#ERROR _QuoteFTCPrices: market is text 'x:market:gas:9' naming no live object, expected market handle" };
            yield return new object[] { "_CreateTrades", new object[] { ExcelMissing.Value, Row("quantity"), 1.0, ExcelMissing.Value }, "#ERROR _CreateTrades: indexes is missing, expected index handles in a cell, a row or a column" };
            yield return new object[] { "_CreateTrades", new object[] { "x:index:gas:9", Row("quantity"), 1.0, "y:trade_template:9" }, "#ERROR _CreateTrades: indexes is text 'x:index:gas:9' naming no live object, expected index handle" };
            // The valuation path: the handles left out, naming nothing or of another kind, in the seam's words; the batch itself is in the fact below.
            yield return new object[] { "_PrepareTrades", new object[] { ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _PrepareTrades: trades is missing, expected trades handle" };
            yield return new object[] { "_PrepareTrades", new object[] { "x:trades:gas:9", "y:market_history:gas:9" }, "#ERROR _PrepareTrades: trades is text 'x:trades:gas:9' naming no live object, expected trades handle" };
            yield return new object[] { "_EvaluateTrades", new object[] { ExcelEmpty.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _EvaluateTrades: prepared is blank, expected prepared trades handle" };
            yield return new object[] { "_ReportValues", new object[] { 1.0 }, "#ERROR _ReportValues: results is number 1.0, expected trade results or cashflow results handle" };
            yield return new object[] { "_ReportRisk", new object[] { ExcelEmpty.Value, "all", "day" }, "#ERROR _ReportRisk: results is blank, expected trade results or aggregate results or cashflow results handle" };
            yield return new object[] { "_ReportReserves", new object[] { ExcelEmpty.Value }, "#ERROR _ReportReserves: results is blank, expected trade results handle" };
            // The collector, since #180: the vector left out, a scalar that is no text, a true array, and a cell naming nothing, in the seam's words.
            yield return new object[] { "_AggregateResults", new object[] { ExcelMissing.Value }, "#ERROR _AggregateResults: result_handles is missing, expected trade results or cashflow results handles in a cell, a row or a column" };
            yield return new object[] { "_AggregateResults", new object[] { 1.0 }, "#ERROR _AggregateResults: result_handles is number 1.0, expected trade results or cashflow results handles in a cell, a row or a column" };
            yield return new object[] { "_AggregateResults", new object[] { new object[,] { { "a", "b" }, { "c", "d" } } }, "#ERROR _AggregateResults: result_handles is 2x2 array, expected one cell, one row or one column of trade results or cashflow results handles" };
            yield return new object[] { "_AggregateResults", new object[] { Column("x:trade_results:gas:9", ExcelEmpty.Value) }, "#ERROR _AggregateResults: result_handles cell (1, 1) is text 'x:trade_results:gas:9' naming no live object, expected trade results or cashflow results handle" };
            // A creator's failure is relayed whole, and a relay of a relay shows the same text.
            yield return new object[] { "util_ReadHandle", new object[] { "#ERROR _CreateDiscountCurve: ValueError: x" }, "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" };
            yield return new object[] { "util_ReadHandle", new object[] { "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" }, "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: x" };
            // The futures schedule: a column of codes and up to two of dates, one row per code, the third column optional; a futures column one row short and a blank among the options.
            yield return new object[] { "_CreateFuturesSchedule", new object[] { Column("m26", "n26", "q26"), Column(46161.0, 46195.0), Column(46156.0, 46189.0, 46219.0) }, "#ERROR _CreateFuturesSchedule: ValueError: future_expiry has 2 dates, expected 3, one per contract_code" };
            yield return new object[] { "_CreateFuturesSchedule", new object[] { Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), Column(46156.0, ExcelEmpty.Value, 46219.0) }, "#ERROR _CreateFuturesSchedule: option_expiry cell (2, 1) is blank, expected date" };
            // The holiday calendar: one column of dates, a blank in it, and a row where a column is expected.
            yield return new object[] { "_CreateHolidayCalendar", new object[] { Column(46023.0, ExcelEmpty.Value, 46069.0) }, "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date" };
            yield return new object[] { "_CreateHolidayCalendar", new object[] { Row(46023.0, 46023.0) }, "#ERROR _CreateHolidayCalendar: holiday is 1x2 array, expected column of dates" };
            // The IFERC schedule: a publication column one row short, the library's words; a blank among the publication dates, a number among the codes, the publication dates left out and a row where a column is expected, the seam's.
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", "X26", "Z26"), Column(46296.0, 46328.0) }, "#ERROR _CreateIfercSchedule: ValueError: publication_date has 2 dates, expected 3, one per contract_code" };
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", "X26"), Column(46296.0, ExcelEmpty.Value) }, "#ERROR _CreateIfercSchedule: publication_date cell (2, 1) is blank, expected date" };
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", 46023.0), Column(46296.0, 46328.0) }, "#ERROR _CreateIfercSchedule: contract_code cell (2, 1) is number 46023.0, expected text" };
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", "X26"), ExcelMissing.Value }, "#ERROR _CreateIfercSchedule: publication_date is missing, expected column of dates" };
            yield return new object[] { "_CreateIfercSchedule", new object[] { Column("V26", "X26"), Row(46296.0, 46328.0) }, "#ERROR _CreateIfercSchedule: publication_date is 1x2 array, expected column of dates" };
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
            // The index: two texts and four handles. A blank where the name should be, a number and text naming no live object where the schedule should be, and the specifications left out fail in the seam's words; the library's rules, which need live handles, are in the fact below.
            yield return new object[] { "_CreateIndex", new object[] { ExcelEmpty.Value, "Henry Hub natural gas - NYMEX", ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateIndex: name is blank, expected text" };
            yield return new object[] { "_CreateIndex", new object[] { "Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", 46161.0, ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateIndex: schedule is number 46161.0, expected a handle" };
            yield return new object[] { "_CreateIndex", new object[] { "Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", "x", ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value, ExcelMissing.Value }, "#ERROR _CreateIndex: schedule is text 'x' naming no live object, expected a handle" };
            // The futures fixings: a column of days, a column of settles and the index by handle. The index left out, a number in its place and text naming no live object fail in the seam's words, as do a blank among the settles and a row where a column is expected; the library's rules, which need a live index, are in the fact below.
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Column(106.42, 101.94), ExcelMissing.Value }, "#ERROR _CreateFuturesFixings: index is missing, expected index handle" };
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Column(106.42, 101.94), 101.94 }, "#ERROR _CreateFuturesFixings: index is number 101.94, expected index handle" };
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Column(106.42, 101.94), "x" }, "#ERROR _CreateFuturesFixings: index is text 'x' naming no live object, expected index handle" };
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), Column(106.42, ExcelEmpty.Value), "x" }, "#ERROR _CreateFuturesFixings: settle cell (2, 1) is blank, expected number" };
            yield return new object[] { "_CreateFuturesFixings", new object[] { Column(46146.0, 46143.0), new object[,] { { 106.42, "x" }, { 101.94, 102.5 } }, "x" }, "#ERROR _CreateFuturesFixings: settle cell (1, 2) is text 'x', expected number" };
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

        // Contract prices interpolated between anchors, interpolate-contract-prices.md: the ticket's
        // CL-style index, J27, K27 and M27 expiring 22 March, 20 April and 20 May 2027, quoted 70 in
        // April as CME spells it and 76 in June by code, spills the three months under two heading
        // rows, their expiries as serials and May 29 of 59 days along. Anchors out of order and a
        // schedule missing a month are refused in the library's words, a numeric month in the seam's.
        [Fact]
        public void contract_prices_are_interpolated_between_anchors_on_the_index_schedule()
        {
            var holidays = Seam.Call("_CreateHolidayCalendar", Column(47484.0));
            var index = Index(Seam.Call("_CreateFuturesSchedule", Column("J27", "K27", "M27"), Column(46468.0, 46497.0, 46527.0), ExcelMissing.Value), holidays, "CL");
            var spill = (object[,])Seam.Call("util_InterpolateContracts", index, Column("202704", "M27"), Column(70.0, 76.0));
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(3, spill.GetLength(1));
            Assert.Equal("contract_code", spill[0, 0]);
            Assert.Equal("future_expiry", spill[0, 1]);
            Assert.Equal("price", spill[0, 2]);
            Assert.Equal("str", spill[1, 0]);
            Assert.Equal("datetime64[D]", spill[1, 1]);
            Assert.Equal("float64", spill[1, 2]);
            Assert.Equal("J27", spill[2, 0]);
            Assert.Equal("K27", spill[3, 0]);
            Assert.Equal("M27", spill[4, 0]);
            Assert.Equal(46468.0, spill[2, 1]);
            Assert.Equal(46497.0, spill[3, 1]);
            Assert.Equal(46527.0, spill[4, 1]);
            Assert.Equal(70.0, spill[2, 2]);
            Assert.Equal(72.94915254237289, (double)spill[3, 2], 12);
            Assert.Equal(76.0, spill[4, 2]);
            Assert.Equal("#ERROR util_InterpolateContracts: ValueError: anchor_contracts row 2 is 'J27', 2027-04, expected a month after row 1's 'M27', 2027-06", Seam.Call("util_InterpolateContracts", index, Column("M27", "J27"), Column(76.0, 70.0)));
            Assert.Equal("#ERROR util_InterpolateContracts: anchor_contracts cell (1, 1) is number 202704.0, expected text", Seam.Call("util_InterpolateContracts", index, Column(202704.0, 202706.0), Column(70.0, 76.0)));
            var gapped = Index(Seam.Call("_CreateFuturesSchedule", Column("J27", "M27"), Column(46468.0, 46527.0), ExcelMissing.Value), holidays, "GAP");
            Assert.Equal("#ERROR util_InterpolateContracts: ValueError: the index's schedule has no contract for 2027-05, K27, expected every month from 2027-04 to 2027-06, the anchors' range", Seam.Call("util_InterpolateContracts", gapped, Column("J27", "M27"), Column(70.0, 76.0)));
        }

        // A discount curve bumped by basis points, bump-discount-curve.md: the three-day curve a
        // basis point up is a new curve of the same days, its first factor 1 and the others moved by
        // exp(-0.0001 tau), tau the days from the start over 365; a bump of nothing moves nothing;
        // text where the bump should be is the seam's refusal, and a curve of ones bumped down the
        // library's, by the row that rose.
        [Fact]
        public void a_discount_curve_is_bumped_by_basis_points_into_an_ordinary_curve()
        {
            var curve = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), Curve());
            var bumped = (string)Seam.Call("util_BumpDiscountCurve", curve, 1.0);
            Assert.StartsWith(Pid + ":discount_curve:SOFR:", bumped);
            Assert.NotEqual(curve, bumped);
            var spill = (object[,])Seam.Call("util_ReadHandle", bumped);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(3, spill.GetLength(1));
            Assert.Equal("SOFR", spill[2, 2]);
            Assert.Equal("date", spill[0, 0]);
            Assert.Equal("discount_factor", spill[0, 1]);
            Assert.Equal("float64", spill[1, 1]);
            Assert.Equal(46276.0, spill[2, 0]);
            Assert.Equal(46278.0, spill[4, 0]);
            Assert.Equal(1.0, spill[2, 1]);
            Assert.Equal(0.9998997260548321, (double)spill[3, 1], 15);
            Assert.Equal(0.9997994521645337, (double)spill[4, 1], 15);
            var still = (object[,])Seam.Call("util_ReadHandle", Seam.Call("util_BumpDiscountCurve", curve, 0.0));
            Assert.Equal(0.9998, still[4, 1]);
            Assert.Equal("#ERROR util_BumpDiscountCurve: bump_bps is text '1bp', expected number", Seam.Call("util_BumpDiscountCurve", curve, "1bp"));
            var ones = Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), new object[,] { { 46276.0, 1.0 }, { 46277.0, 1.0 }, { 46278.0, 1.0 } });
            Assert.Equal("#ERROR util_BumpDiscountCurve: ValueError: discount_factor rises at row 2, from 1.0 to 1.0000002739726404", Seam.Call("util_BumpDiscountCurve", ones, -1.0));
        }

        // Named curves and their collection, named-curves-slice-1.md: a curve is created under its
        // name, SOFR, carried in its handle and on every row of its readback, last; a bump keeps it;
        // _CollectDiscountCurves gathers curves into a compact set handle whose readback is one row
        // per curve, the name, the span and the days, in the order given; each name once, two
        // snapshots of FFOIS refused by the library, a valuation date and a nested collection by the
        // seam at their cells; and the name's own refusals, whitespace around it, whitespace alone,
        // a number and the argument left out.
        [Fact]
        public void discount_curves_are_named_and_collected_each_name_once()
        {
            var sofr = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), Curve());
            Assert.StartsWith(Pid + ":discount_curve:SOFR:", sofr);
            var ffois = (string)Seam.Call("_CreateDiscountCurve", "FFOIS", Row("date", "discount_factor"), new object[,] { { 46276.0, 1.0 }, { 46279.0, 0.9997 } });
            Assert.StartsWith(Pid + ":discount_curve:FFOIS:", ffois);
            var spill = (object[,])Seam.Call("util_ReadHandle", sofr);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(3, spill.GetLength(1));
            Assert.Equal("name", spill[0, 2]);
            Assert.Equal("str", spill[1, 2]);
            Assert.Equal("SOFR", spill[2, 2]);
            Assert.Equal("SOFR", spill[4, 2]);
            Assert.Equal(0.9998, spill[4, 1]);
            var bumped = (string)Seam.Call("util_BumpDiscountCurve", ffois, 1.0);
            Assert.StartsWith(Pid + ":discount_curve:FFOIS:", bumped);
            Assert.Equal("FFOIS", ((object[,])Seam.Call("util_ReadHandle", bumped))[3, 2]);
            var both = (string)Seam.Call("_CollectDiscountCurves", Column(sofr, ffois));
            Assert.StartsWith(Pid + ":discount_curve_set:", both);
            var table = (object[,])Seam.Call("util_ReadHandle", both);
            Assert.Equal(4, table.GetLength(0));
            Assert.Equal(4, table.GetLength(1));
            Assert.Equal("name", table[0, 0]);
            Assert.Equal("start_date", table[0, 1]);
            Assert.Equal("end_date", table[0, 2]);
            Assert.Equal("days", table[0, 3]);
            Assert.Equal("str", table[1, 0]);
            Assert.Equal("datetime64[D]", table[1, 2]);
            Assert.Equal("int64", table[1, 3]);
            Assert.Equal("SOFR", table[2, 0]);
            Assert.Equal(46276.0, table[2, 1]);
            Assert.Equal(46278.0, table[2, 2]);
            Assert.Equal(3.0, table[2, 3]);
            Assert.Equal("FFOIS", table[3, 0]);
            Assert.Equal(46279.0, table[3, 2]);
            Assert.Equal(4.0, table[3, 3]);
            var row = (string)Seam.Call("_CollectDiscountCurves", Row(bumped, sofr));
            Assert.StartsWith(Pid + ":discount_curve_set:", row);
            Assert.NotEqual(both, row);
            Assert.Equal("FFOIS", ((object[,])Seam.Call("util_ReadHandle", row))[2, 0]);
            var one = (string)Seam.Call("_CollectDiscountCurves", sofr);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", one)).GetLength(0));
            Assert.Equal("#ERROR _CollectDiscountCurves: ValueError: curve_handles cell 1 and cell 2 are both named 'FFOIS', expected each name once", Seam.Call("_CollectDiscountCurves", Column(ffois, bumped)));
            var date = (string)Seam.Call("_CreateValuationDate", 46276.0, 0.5);
            Assert.Equal("#ERROR _CollectDiscountCurves: curve_handles cell (2, 1) is valuation date handle '" + date + "', expected discount curve handle", Seam.Call("_CollectDiscountCurves", Column(sofr, date)));
            Assert.Equal("#ERROR _CollectDiscountCurves: curve_handles is discount curve set handle '" + both + "', expected discount curve handle", Seam.Call("_CollectDiscountCurves", both));
            Assert.Equal("#ERROR _CollectDiscountCurves: curve_handles is missing, expected discount curve handles in a cell, a row or a column", Seam.Call("_CollectDiscountCurves", ExcelMissing.Value));
            Assert.Equal("#ERROR _CreateDiscountCurve: ValueError: name is ' SOFR', expected a name with no whitespace around it", Seam.Call("_CreateDiscountCurve", " SOFR", Row("date", "discount_factor"), Curve()));
            Assert.Equal("#ERROR _CreateDiscountCurve: ValueError: name is '  ', expected a name, not whitespace alone", Seam.Call("_CreateDiscountCurve", "  ", Row("date", "discount_factor"), Curve()));
            Assert.Equal("#ERROR _CreateDiscountCurve: name is number 1.0, expected text", Seam.Call("_CreateDiscountCurve", 1.0, Row("date", "discount_factor"), Curve()));
            Assert.Equal("#ERROR _CreateDiscountCurve: name is missing, expected text", Seam.Call("_CreateDiscountCurve", ExcelMissing.Value, Row("date", "discount_factor"), Curve()));
        }

        // Trades and cashflows in one collection, named-curves-slice-2.md, from the host's side:
        // a batch of cashflows collected alone reports its own DV01 under its curve's name and
        // refuses the commodity selectors in the cashflow result's words; the same batch on two
        // curves makes two columns under the curves' names; the membership readback shows a
        // cashflow row with cashflow under the route, its curve's word, its currency and its DV01,
        // and a dash where a batch of cashflows has no number; and a cashflows handle among the
        // results is refused at its cell naming both kinds.
        [Fact]
        public void cashflows_collect_alone_and_beside_each_other_under_their_curves_names()
        {
            var template = (string)Seam.Call("_CreateTradeTemplate", "cashflow", Row("currency"), Row("USD"));
            var fields = Row("trade_id", "trade_date", "amount", "payment_date");
            var rows = new object[,] { { 1.0, 46391.0, 10000.0, 46756.0 }, { 2.0, 46391.0, -10000.0, 47121.0 }, { 3.0, 46391.0, 250.0, 46390.0 } };
            var batch = (string)Seam.Call("_CreateCashflows", fields, rows, template);
            var date = Seam.Call("_CreateValuationDate", 46391.0, 0.5);
            var sofr = Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), new object[,] { { 46391.0, 1.0 }, { 46756.0, 0.95 }, { 47121.0, 0.9 } });
            var ffois = Seam.Call("_CreateDiscountCurve", "FFOIS", Row("date", "discount_factor"), new object[,] { { 46391.0, 1.0 }, { 46756.0, 0.96 }, { 47121.0, 0.92 } });
            var onSofr = (string)Seam.Call("_EvaluateCashflows", batch, date, sofr);
            var onFfois = (string)Seam.Call("_EvaluateCashflows", batch, date, ffois);
            var alone = (string)Seam.Call("_AggregateResults", onSofr);
            Assert.StartsWith(Pid + ":aggregate_results:", alone);
            var own = (object[,])Seam.Call("_ReportRisk", onSofr, "dv01", "year");
            var collected = (object[,])Seam.Call("_ReportRisk", alone, "dv01", "year");
            Assert.Equal(own.GetLength(0), collected.GetLength(0));
            Assert.Equal("SOFR USD dv01 [USD per basis point]", collected[1, 1]);
            Assert.Equal(0.85, (double)collected[3, 1], 12);
            Assert.Equal((double)own[5, 1], (double)collected[5, 1], 12);
            Assert.Equal(-0.95, (double)collected[5, 1], 12);
            Assert.Equal("#ERROR _ReportRisk: ValueError: risk is 'delta', expected dv01 or all for a collection of cashflows alone, which has no commodity risk", Seam.Call("_ReportRisk", alone, "delta", "day"));
            var both = (string)Seam.Call("_AggregateResults", Column(onSofr, onFfois));
            var two = (object[,])Seam.Call("_ReportRisk", both, "dv01", "year");
            Assert.Equal(3, two.GetLength(1));
            Assert.Equal("FFOIS USD dv01 [USD per basis point]", two[1, 2]);
            Assert.Equal(0.85, (double)two[3, 1], 12);
            Assert.Equal(0.88, (double)two[3, 2], 12);
            var members = (object[,])Seam.Call("util_ReadHandle", both);
            Assert.Equal(4, members.GetLength(0));
            Assert.Equal(12, members.GetLength(1));
            Assert.Equal("-", members[2, 1]);
            Assert.Equal("-", members[2, 2]);
            Assert.Equal("cashflow", members[2, 3]);
            Assert.Equal("SOFR", members[2, 4]);
            Assert.Equal("FFOIS", members[3, 4]);
            Assert.Equal("USD", members[2, 5]);
            Assert.Equal("-", members[2, 6]);
            Assert.Equal("-", members[2, 7]);
            Assert.Equal(0.85, (double)members[2, 8], 12);
            Assert.Equal(46391.0, members[2, 9]);
            Assert.Equal("-", members[2, 10]);
            Assert.Equal("-", members[2, 11]);
            Assert.Equal("#ERROR _AggregateResults: result_handles cell (2, 1) is cashflows handle '" + batch + "', expected trade results or cashflow results handle", Seam.Call("_AggregateResults", Column(onSofr, batch)));
        }

        // The cashflow instrument, cashflow-instrument.md: a template of USD and Firm A, the
        // ticket's three payments, valued on 4 January 2027 over the curve 1, 0.95 and 0.90: 500 of
        // mark, 250 of cash and 0.85 of DV01, the handles named for the currency; the values and
        // the risk reports, the readback with its totals once and the batch's rows; delta refused by
        // name; a fixed_float template refused at the ticket's first cashflow header and, with a
        // ticket of the shared fields, by name.
        [Fact]
        public void cashflows_are_booked_from_a_template_and_a_ticket_and_valued_on_a_curve()
        {
            var template = (string)Seam.Call("_CreateTradeTemplate", "cashflow", Row("currency", "counterparty"), Row("USD", "Firm A"));
            Assert.StartsWith(Pid + ":trade_template:", template);
            var fields = Row("trade_id", "trade_date", "amount", "payment_date", "description");
            var rows = new object[,] { { 1.0, 46391.0, 10000.0, 46756.0, "Receivable" }, { 2.0, 46391.0, -10000.0, 47121.0, "Payable" }, { 3.0, 46391.0, 250.0, 46390.0, "Earlier rebate" } };
            var batch = (string)Seam.Call("_CreateCashflows", fields, rows, template);
            Assert.StartsWith(Pid + ":cashflows:USD:", batch);
            var date = Seam.Call("_CreateValuationDate", 46391.0, 0.5);
            var curve = Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), new object[,] { { 46391.0, 1.0 }, { 46756.0, 0.95 }, { 47121.0, 0.9 } });
            var results = (string)Seam.Call("_EvaluateCashflows", batch, date, curve);
            Assert.StartsWith(Pid + ":cashflow_results:USD:", results);
            var values = (object[,])Seam.Call("_ReportValues", results);
            Assert.Equal("cashflow_mark", values[0, 0]);
            Assert.Equal("cashflow_cash", values[0, 1]);
            Assert.Equal(500.0, (double)values[2, 0], 9);
            Assert.Equal(250.0, values[2, 1]);
            Assert.Equal("USD", values[2, 2]);
            Assert.Equal(46391.0, values[2, 3]);
            var risk = (object[,])Seam.Call("_ReportRisk", results, "dv01", "year");
            Assert.Equal(7, risk.GetLength(0));
            Assert.Equal(2, risk.GetLength(1));
            Assert.Equal("SOFR USD dv01 [USD per basis point]", risk[1, 1]);
            Assert.Equal("Total", risk[3, 0]);
            Assert.Equal(0.85, (double)risk[3, 1], 12);
            Assert.Equal(46753.0, risk[5, 0]);
            Assert.Equal(-0.95, (double)risk[5, 1], 12);
            Assert.Equal(1.8, (double)risk[6, 1], 12);
            var read = (object[,])Seam.Call("util_ReadHandle", results);
            Assert.Equal(5, read.GetLength(0));
            Assert.Equal(12, read.GetLength(1));
            Assert.Equal("cashflow_mark", read[0, 9]);
            Assert.Equal(500.0, (double)read[2, 9], 9);
            Assert.Equal("-", read[3, 9]);
            var booked = (object[,])Seam.Call("util_ReadHandle", batch);
            Assert.Equal(5, booked.GetLength(0));
            Assert.Equal(7, booked.GetLength(1));
            Assert.Equal("Firm A", booked[2, 5]);
            Assert.Equal("#ERROR _ReportRisk: ValueError: risk is 'delta', expected dv01 or all for a batch of cashflows, which has no commodity risk", Seam.Call("_ReportRisk", results, "delta", "day"));
            var fixedFloat = Seam.Call("_CreateTradeTemplate", "fixed_float", Row("route"), Row("cleared"));
            Assert.Equal("#ERROR _CreateCashflows: fields cell (1, 3) is text 'amount', expected a field of fixed_float: trade_id, trade_date, contract_code, start_date, end_date, schedule_method, route, settlement_method, clearing_house, counterparty, discount_curve_key, broker, quantity, quantity_unit, quantity_per, fixed_price, second_schedule_method, payment_day, payment_holiday_calendar, marketing_reserve, cva_reserve, settlement_frequency, nearby", Seam.Call("_CreateCashflows", fields, rows, fixedFloat));
            Assert.Equal("#ERROR _CreateCashflows: ValueError: template is of instrument 'fixed_float', expected cashflow, the one instrument whose cashflows are built", Seam.Call("_CreateCashflows", Row("trade_date"), Row(46391.0), fixedFloat));
        }

        // A row of the fixed_float's fields bound against the instrument named: the holiday calendar cell
        // resolved to the object behind the handle and echoed as the words of its kind, the date as
        // its serial, the number as itself, under the field names in the sheet's order.
        [Fact]
        public void a_row_of_fields_is_bound_against_the_instrument_named_and_its_handle_cell_resolved()
        {
            var calendar = (string)Seam.Call("_CreateHolidayCalendar", 46023.0);
            var headers = Row("quantity_unit", "payment_holiday_calendar", "trade_date", "quantity");
            var spill = (object[,])Seam.Call("EchoFieldRow", "fixed_float", headers, Row("LOT", calendar, 46164.0, 10.0));
            Assert.Equal(2, spill.GetLength(0));
            Assert.Equal(4, spill.GetLength(1));
            Assert.Equal("payment_holiday_calendar", spill[0, 1]);
            Assert.Equal("LOT", spill[1, 0]);
            Assert.Equal("a holiday calendar", spill[1, 1]);
            Assert.Equal(46164.0, spill[1, 2]);
            Assert.Equal(10.0, spill[1, 3]);
            var date = (string)Seam.Call("_CreateValuationDate", 46276.0, 0.5);
            Assert.Equal("#ERROR EchoFieldRow: values cell (1, 1) is valuation date handle '" + date + "', expected holiday calendar handle", Seam.Call("EchoFieldRow", "fixed_float", Row("payment_holiday_calendar"), date));
        }

        // A pair of indexes, two-index-fixed-float.md and two-index-one-price.md: A a futures index
        // and B an IFERC one over the one NYMEX NG specification, booked as one row at the outright
        // 3.00, the histories and the markets handed as a column and a row in either order: the
        // ticket's hand table, 950 of mark and -0.095 of DV01 on SOFR at 0.95 a year on, each leg a
        // lot; the risk report two commodity groups and one DV01 column; the readbacks naming each
        // leg and showing one price and no leg value; a column of one history, a grid of handles, the
        // second leg's method on one index and a second price refused, the seam's words and the
        // kernel's.
        [Fact]
        public void a_pair_of_indexes_is_booked_prepared_and_valued_as_one_payment()
        {
            var a = Index((string)Seam.Call("_CreateFuturesSchedule", Column("F27", "G27", "H27"), Column(46385.0, 46414.0, 46442.0), ExcelMissing.Value), (string)Seam.Call("_CreateHolidayCalendar", 46388.0), "A");
            var b = Index((string)Seam.Call("_CreateIfercSchedule", Column("Z26", "F27", "G27", "H27"), Column(46357.0, 46391.0, 46419.0, 46447.0)), ExcelMissing.Value, "B");
            var date = (string)Seam.Call("_CreateValuationDate", 46391.0, 0.5);
            var historyA = (string)Seam.Call("_CreateMarketHistory", (string)Seam.Call("_CreateCalendar", date, a), (string)Seam.Call("_CreateFuturesFixings", Column(46387.0, 46386.0), Column(3.60, 3.58), a));
            var historyB = (string)Seam.Call("_CreateMarketHistory", (string)Seam.Call("_CreateCalendar", date, b), (string)Seam.Call("_CreateIfercFixings", Column("Z26"), Column(-0.30), b));
            var marketA = (string)Seam.Call("_CreateMarket", historyA, (string)Seam.Call("_CreatePriceVector", "A", Column(3.50, 3.60)));
            var marketB = (string)Seam.Call("_CreateMarket", historyB, (string)Seam.Call("_CreatePriceVector", "B", Column(-0.38, -0.40, -0.42)));
            var curves = (string)Seam.Call("_CollectDiscountCurves", (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), new object[,] { { 46391.0, 1.0 }, { 46756.0, 0.95 } }));
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "second_schedule_method", "route", "settlement_method", "counterparty", "discount_curve_key", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "month", "monthly", 1.0, "lastday", "lastday", "bilateral", "financial", "ACME Trading", "SOFR", 46756.0, (string)Seam.Call("_CreateHolidayCalendar", 46388.0)));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var row = Row(1.0, 46371.0, "G27", 1.0, 3.00);
            var trades = (string)Seam.Call("_CreateTrades", Column(a, b), headers, row, template);
            Assert.StartsWith(Pid + ":trades:A+B:", trades);
            var prepared = (string)Seam.Call("_PrepareTrades", trades, Column(historyB, historyA));
            Assert.StartsWith(Pid + ":prepared_trades:A+B:", prepared);
            var results = (string)Seam.Call("_EvaluateTrades", prepared, Row(marketA, marketB), curves);
            Assert.StartsWith(Pid + ":trade_results:A+B:", results);
            var values = (object[,])Seam.Call("_ReportValues", results);
            Assert.Equal("bilateral_mark", values[0, 0]);
            Assert.Equal(950.0, (double)values[2, 0], 9);
            Assert.Equal(0.0, values[2, 1]);
            var risk = (object[,])Seam.Call("_ReportRisk", results, "all", "day");
            Assert.Equal(8, risk.GetLength(1));
            Assert.Equal("A nominal_delta [NYMEX NG]", risk[1, 1]);
            Assert.Equal("B delta [NYMEX NG]", risk[1, 4]);
            Assert.Equal("SOFR USD dv01 [USD per basis point]", risk[1, 5]);
            Assert.Equal("A SOFR cross_gamma [NYMEX NG per basis point]", risk[1, 6]);
            Assert.Equal("Total", risk[3, 0]);
            Assert.Equal(1.0, (double)risk[3, 1], 12);
            Assert.Equal(0.95, (double)risk[3, 4], 12);
            Assert.Equal(-0.095, (double)risk[3, 5], 12);
            var read = (object[,])Seam.Call("util_ReadHandle", results);
            Assert.Equal(4, read.GetLength(0));
            Assert.Equal("leg", read[0, 0]);
            Assert.Equal("index", read[0, 1]);
            Assert.Equal(1.0, read[2, 0]);
            Assert.Equal("A", read[2, 1]);
            Assert.Equal("B", read[3, 1]);
            var booked = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(3, booked.GetLength(0));
            var price = Heading(booked, "fixed_price");
            Assert.True(price > 0);
            Assert.Equal(3.0, (double)booked[2, price], 12);
            Assert.Equal(-30000.0, (double)booked[2, Heading(booked, "offset")], 9);  // the trade's fixed leg, once
            Assert.Equal(-1, Heading(booked, "second_fixed_price"));  // no field since two-index-one-price.md
            Assert.Equal(-1, Heading(read, "leg_dv01"));  // no value is a leg's
            // cva-reserve.md: a CVA column on the pair's row books its signed amount once, though the row has two
            // legs, the bilateral unbrokered template charging no fee.
            var pairCva = (string)Seam.Call("_CreateTrades", Column(a, b), Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "cva_reserve"), Row(1.0, 46371.0, "G27", 1.0, 3.00, -40.0), template);
            var pairReserves = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", pairCva, Column(historyA, historyB)), Row(marketA, marketB), curves));
            Assert.Equal(5, pairReserves.GetLength(1));
            Assert.Equal(0.0, (double)pairReserves[2, 0], 9);
            Assert.Equal(-40.0, (double)pairReserves[2, 3], 9);
            Assert.Equal("USD", pairReserves[2, 4]);
            Assert.Equal("#ERROR _PrepareTrades: ValueError: histories are 1, expected 2, one per leg of the trades", Seam.Call("_PrepareTrades", trades, historyA));
            Assert.Equal("#ERROR _EvaluateTrades: ValueError: market 2 is over the history of index 'A' as market 1 is, expected one market per history of the trades", Seam.Call("_EvaluateTrades", prepared, Column(marketA, marketA), curves));
            Assert.StartsWith("#ERROR _CreateTrades: indexes is 2x2 array, expected one cell, one row or one column of index handles", (string)Seam.Call("_CreateTrades", new object[,] { { a, b }, { a, b } }, headers, row, template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: second_schedule_method is 'lastday', expected none unless two indexes", Seam.Call("_CreateTrades", a, headers, row, template));
            Assert.StartsWith("#ERROR _CreateTrades: fields cell (1, 6) is text 'second_fixed_price', expected a field of fixed_float: trade_id,", (string)Seam.Call("_CreateTrades", Column(a, b), Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "second_fixed_price"), Row(1.0, 46371.0, "G27", 1.0, 3.30, -0.30), template));
        }

        // The instrument catalog: the list spills a header and a row per instrument, two text columns;
        // the shown fixed_float spills ten rows by twenty-three columns, the seven rows of booking and since
        // template-based-quoting.md the three of quoting, the labels down the first column, the fields across
        // the first row and the required, quote_allowed and quote_required rows booleans, every other cell text.
        [Fact]
        public void the_instrument_catalog_is_listed_and_the_future_shown()
        {
            var listed = (object[,])Seam.Call("_ListInstruments");
            Assert.Equal(3, listed.GetLength(0));
            Assert.Equal(2, listed.GetLength(1));
            Assert.Equal("instrument", listed[0, 0]);
            Assert.Equal("description", listed[0, 1]);
            Assert.Equal("fixed_float", listed[1, 0]);
            Assert.Equal("cashflow", listed[2, 0]);
            Assert.Equal(8, ((object[,])Seam.Call("_ShowInstrument", "cashflow")).GetLength(1));
            var shown = (object[,])Seam.Call("_ShowInstrument", "fixed_float");
            Assert.Equal(10, shown.GetLength(0));
            Assert.Equal(24, shown.GetLength(1));  // twenty-three fields, nearby last since nearby-selection.md
            Assert.Equal("field", shown[0, 0]);
            Assert.Equal("trade_id", shown[0, 1]);
            Assert.Equal("start_date", shown[0, 4]);
            Assert.Equal("counterparty", shown[0, 10]);
            Assert.Equal("discount_curve_key", shown[0, 11]);  // after the counterparty, since named-curves-slice-3.md
            Assert.Equal("route = bilateral", shown[3, 11]);
            Assert.Equal("second_schedule_method", shown[0, 17]);  // the second leg's one field since two-index-one-price.md
            Assert.Equal("two indexes", shown[3, 17]);
            Assert.Equal("payment_holiday_calendar", shown[0, 19]);
            Assert.Equal("marketing_reserve", shown[0, 20]);
            Assert.Equal("cva_reserve", shown[0, 21]);  // signed, since cva-reserve.md
            Assert.Equal("settlement_frequency", shown[0, 22]);  // since onetime-averaging.md
            Assert.Equal("nearby", shown[0, 23]);  // last, since nearby-selection.md
            Assert.Equal("required", shown[2, 0]);
            Assert.Equal(false, shown[2, 1]);
            Assert.Equal(true, shown[2, 2]);
            Assert.Equal(false, shown[2, 3]);
            Assert.Equal("no start_date and end_date on the row", shown[3, 3]);
            Assert.Equal("no contract_code on the row, or with start_date", shown[3, 5]);
            Assert.Equal("route = cleared", shown[3, 9]);
            Assert.Equal("route = bilateral", shown[3, 10]);
            Assert.Equal("a finite amount of zero or more", shown[5, 20]);
            Assert.Equal("holiday calendar handle", shown[4, 19]);
            Assert.Equal("the index's specification names", shown[5, 14]);
            Assert.Equal("month, calday, period", shown[5, 15]);
            Assert.Equal("quote_allowed", shown[7, 0]);
            Assert.Equal("quote_required", shown[8, 0]);
            Assert.Equal("quote_required_when", shown[9, 0]);
            Assert.Equal(false, shown[7, 1]);  // trade_id: a booking fact no quote template holds
            Assert.Equal(true, shown[7, 6]);  // schedule_method: held and always required
            Assert.Equal(true, shown[8, 6]);
            Assert.Equal(true, shown[7, 19]);  // payment_day: held, required with a financial settlement
            Assert.Equal(false, shown[8, 19]);
            Assert.Equal("settlement_method = financial", shown[9, 19]);
            Assert.Equal("route = bilateral", shown[9, 11]);
            Assert.Equal("none", shown[9, 1]);
        }

        // The NG example of the trade-valuation pipeline: a template of the fixed_float's six shared
        // fields, a batch of its five rows and a sixth kept ready at nothing on the NG index, the
        // codes in either case, the handle named for the index, the spill one row per component
        // with the kernel's numbers; a template field repeated in the ticket refused, and a
        // financial template whose strip pays two business days after each expiry.
        [Fact]
        public void a_batch_of_trades_is_created_from_a_template_and_a_ticket_on_an_index()
        {
            var schedule = Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27"), Column(46323.0, 46351.0, 46385.0), ExcelMissing.Value);
            var holidays = Seam.Call("_CreateHolidayCalendar", Column(46352.0, 46381.0));
            var ng = Index(schedule, holidays, "Henry Hub NYMEX");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "month", "monthly", 1.0, "lastday", "cleared", "physical", "CME Clearing"));
            Assert.StartsWith(Pid + ":trade_template:", template);
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var rows = new object[,]
            {
                { 1001.0, 46289.0, "Z26", 10.0, 3.1 },
                { 1002.0, 46289.0, "z26", -4.0, 3.15 },
                { 1003.0, 46290.0, "F27", 7.0, 3.4 },
                { 1004.0, 46290.0, "F27", -12.0, 3.35 },
                { 1001.0, 46289.0, "Z26", 10.0, 3.1 },
                { 1000.0, 46289.0, "F27", 0.0, 3.3 },
            };
            var trades = (string)Seam.Call("_CreateTrades", ng, headers, rows, template);
            Assert.StartsWith(Pid + ":trades:Henry Hub NYMEX:", trades);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(8, spill.GetLength(0));
            Assert.Equal(22, spill.GetLength(1));  // settlement_frequency, then nearby last since nearby-selection.md
            Assert.Equal("row", spill[0, 0]);
            Assert.Equal("covered_days", spill[0, 15]);
            Assert.Equal("component_quantity", spill[0, 16]);
            Assert.Equal("entered_contract_code", spill[0, 12]);
            Assert.Equal("start_date", spill[0, 13]);
            Assert.Equal("offset", spill[0, 19]);
            Assert.Equal(1.0, spill[2, 0]);
            Assert.Equal("Z26", spill[3, 3]);
            Assert.Equal("cleared", spill[2, 5]);
            Assert.Equal("physical", spill[2, 6]);
            Assert.Equal("quantity_unit", spill[0, 9]);
            Assert.Equal("NYMEX NG", spill[2, 9]);
            Assert.Equal("Z26", spill[2, 12]);  // the code as the ticket typed it, since #172
            Assert.Equal("z26", spill[3, 12]);
            Assert.Equal(46357.0, spill[2, 13]);
            Assert.Equal(46387.0, spill[2, 14]);
            Assert.Equal(31.0, spill[2, 15]);
            Assert.Equal(10.0, spill[2, 16]);
            Assert.Equal(100000.0, spill[2, 17]);
            Assert.Equal(-310000.0, spill[6, 19]);
            Assert.Equal(1000.0, spill[7, 1]);
            Assert.Equal(1001.0, spill[2, 1]);  // the source system's number, read back as one
            Assert.Equal("int64", spill[1, 1]);
            Assert.Equal(0.0, spill[7, 8]);
            Assert.Equal(0.0, spill[7, 17]);
            Assert.Equal(0.0, spill[7, 19]);
            Assert.Equal("#ERROR _CreateTrades: ValueError: route is supplied by the template and by the ticket, expected by one of them", Seam.Call("_CreateTrades", ng, Row("trade_date", "contract_code", "quantity", "fixed_price", "route"), Row(46289.0, "Z26", 1.0, 3.0, "cleared"), template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: quantity of trade 1 at row 1 is 2.5, expected a whole number", Seam.Call("_CreateTrades", ng, headers, Row(1.0, 46289.0, "Z26", 2.5, 3.0), template));
            Assert.Equal("#ERROR _CreateTrades: template is holiday calendar handle '" + holidays + "', expected trade template handle", Seam.Call("_CreateTrades", ng, headers, rows, holidays));
            var financial = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar"), Row("NYMEX NG", "month", "monthly", 1.0, "lastday", "cleared", "financial", "TEST", "+2bd", holidays));
            var strip = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateTrades", ng, Row("trade_date", "contract_code", "quantity", "fixed_price"), Row(46289.0, "Z26-F27", 3.0, 3.2), financial));
            Assert.Equal(4, strip.GetLength(0));
            Assert.Equal(23, strip.GetLength(1));
            Assert.Equal("payment_date", strip[0, 12]);
            Assert.Equal("+2bd", strip[2, 11]);
            Assert.Equal(46356.0, strip[2, 12]);
            Assert.Equal(46387.0, strip[3, 12]);
            Assert.Equal("#ERROR _CreateTrades: ValueError: quantity_unit is 'ICE PHH', expected one of the index's specifications: 'NYMEX NG'", Seam.Call("_CreateTrades", ng, headers, rows, (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("ICE PHH", "month", "monthly", 1.0, "lastday", "cleared", "physical", "CME Clearing"))));
        }

        // The whole-period average, onetime-averaging.md's third slice: the WTI trade month of 26 May
        // to 25 June 2026 as one onetime row of 2,200 barrels at 71 paying 29 June, on a CL-like index
        // whose N26 expires 22 June, closed on Memorial Day, Juneteenth and 3 July, a barrel its one
        // specification; valued on 23 April, the one fixed day settled, with M26 at 69, N26 at 70 and
        // Q26 at 72: one component reading back its two dates under booked_period, its 31 days and
        // 2,200 barrels, onetime and period as entered, paying 29 June; 22 slots each labelled by the
        // window, N26's nineteen then Q26's three; a mark of -1,600 and no cash, 2,200 barrels of
        // delta; a lastday row under onetime refused by name before any period is built.
        [Fact]
        public void a_onetime_window_is_one_average_one_quantity_and_one_payment()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("K26", "M26", "N26", "Q26", "U26"), Column(46133.0, 46161.0, 46195.0, 46224.0, 46254.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", Column(46167.0, 46192.0, 46206.0));
            var conventions = Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "VOLUME", "BBL");
            var specifications = Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "BBL", 1.0, "BBL", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "CL", "CL index", schedule, conventions, specifications, holidays, "BBL");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("BBL", "period", "onetime", 1.0, "asian", "cleared", "financial", "CME Clearing", 46202.0, holidays));
            var headers = Row("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price");
            var booking = Row(1.0, 46157.0, 46168.0, 46198.0, 2200.0, 71.0);
            var trades = (string)Seam.Call("_CreateTrades", index, headers, booking, template);
            Assert.StartsWith(Pid + ":trades:CL:", trades);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(3, spill.GetLength(0));
            Assert.Equal("booked_period", spill[0, 3]);
            Assert.Equal("2026-05-26 to 2026-06-25", spill[2, 3]);
            Assert.Equal("period", spill[2, Heading(spill, "quantity_per")]);
            Assert.Equal("onetime", spill[2, Heading(spill, "settlement_frequency")]);
            Assert.Equal(46168.0, spill[2, Heading(spill, "start_date")]);
            Assert.Equal(46198.0, spill[2, Heading(spill, "end_date")]);
            Assert.Equal(31.0, spill[2, Heading(spill, "covered_days")]);
            Assert.Equal(2200.0, spill[2, Heading(spill, "component_quantity")]);
            Assert.Equal(46202.0, spill[2, Heading(spill, "payment_date")]);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46135.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46134.0), Column(69.0), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "CL", Column(69.0, 70.0, 72.0, 74.0)));
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(24, slots.GetLength(0));
            Assert.Equal("booked_period", slots[0, 1]);
            Assert.Equal("2026-05-26 to 2026-06-25", slots[2, 1]);
            Assert.Equal("2026-05-26 to 2026-06-25", slots[23, 1]);
            Assert.Equal("N26", slots[2, 0]);
            Assert.Equal("N26", slots[20, 0]);
            Assert.Equal("Q26", slots[21, 0]);
            Assert.Equal(46168.0, slots[2, 2]);
            Assert.Equal(46198.0, slots[23, 2]);
            Assert.Equal(46202.0, slots[2, 3]);
            Assert.Equal(100.0, (double)slots[2, 6], 6);
            var results = (string)Seam.Call("_EvaluateTrades", prepared, market, ExcelMissing.Value);
            var values = (object[,])Seam.Call("_ReportValues", results);
            Assert.Equal(-1600.0, (double)values[2, 0], 6);
            Assert.Equal(0.0, values[2, 1]);
            var risk = (object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year");
            Assert.Equal(2200.0, (double)risk[3, 1], 6);
            var lastday = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("BBL", "period", "onetime", 1.0, "lastday", "cleared", "financial", "CME Clearing", 46202.0, holidays));
            Assert.Equal("#ERROR _CreateTrades: ValueError: schedule_method of trade 1 at row 1 is 'lastday', expected 'asian' under settlement_frequency = onetime; a onetime period averages every pricing day it covers, and the expiry-based methods take their contract's month", Seam.Call("_CreateTrades", index, headers, booking, lastday));
        }

        // The quote by dates, dated-quotes.md: the onetime fact's index and market, valued 23 April 2026
        // with N26 at 70 and Q26 at 72, the trade month 26 May to 25 June under a onetime quote template
        // one average of 22 fixings, (19 * 70 + 3 * 72) / 22, and under a monthly one a dated strip,
        // May's four days at 70 and June's eighteen at 70.333333 in equal quantities; the window booked
        // at its quote marks zero; the dates reversed and a text date refused in the seam's words, and a
        // label under the onetime template in the library's, naming the function that prices a window.
        [Fact]
        public void a_window_is_quoted_by_its_dates_under_the_templates_frequency()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("K26", "M26", "N26", "Q26", "U26"), Column(46133.0, 46161.0, 46195.0, 46224.0, 46254.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", Column(46167.0, 46192.0, 46206.0));
            var conventions = Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "VOLUME", "BBL");
            var specifications = Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "BBL", 1.0, "BBL", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "CL", "CL index", schedule, conventions, specifications, holidays, "BBL");
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46135.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46134.0), Column(69.0), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "CL", Column(69.0, 70.0, 72.0, 74.0)));
            var fields = Row("route", "settlement_method", "schedule_method", "quantity_per", "payment_day", "payment_holiday_calendar", "settlement_frequency", "nearby");
            var onetime = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", fields, Row("cleared", "financial", "asian", "period", 46202.0, holidays, "onetime", 1.0));
            var monthly = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", fields, Row("cleared", "financial", "asian", "month", 46202.0, holidays, "monthly", 1.0));
            var window = (double)Seam.Call("_QuoteByDates", market, 46168.0, 46198.0, onetime, "flat", ExcelMissing.Value);
            Assert.Equal((19 * 70.0 + 3 * 72.0) / 22, window, 12);
            Assert.Equal((70.0 + (15 * 70.0 + 3 * 72.0) / 18) / 2, (double)Seam.Call("_QuoteByDates", market, 46168.0, 46198.0, monthly, "flat", ExcelMissing.Value), 12);
            // Since fit-to-curve-price.md the pricing: a cleared strip and one window are each the same under ftc.
            Assert.Equal((70.0 + (15 * 70.0 + 3 * 72.0) / 18) / 2, (double)Seam.Call("_QuoteByDates", market, 46168.0, 46198.0, monthly, "ftc", ExcelMissing.Value), 12);
            Assert.Equal(window, (double)Seam.Call("_QuoteByDates", market, 46168.0, 46198.0, onetime, "ftc", ExcelMissing.Value), 12);
            Assert.Equal("#ERROR _QuoteByDates: ValueError: pricing is 'Flat', expected flat or ftc", Seam.Call("_QuoteByDates", market, 46168.0, 46198.0, monthly, "Flat", ExcelMissing.Value));
            var booking = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", booking, Row("BBL", "period", "onetime", 1.0, "asian", "cleared", "financial", "CME Clearing", 46202.0, holidays));
            var trades = (string)Seam.Call("_CreateTrades", index, Row("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price"), Row(1.0, 46157.0, 46168.0, 46198.0, 2200.0, window), template);
            var results = (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", trades, history), market, ExcelMissing.Value);
            Assert.Equal(0.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            Assert.Equal("#ERROR _QuoteByDates: ValueError: end_date is 2026-05-26, expected a day on or after start_date, 2026-06-25", Seam.Call("_QuoteByDates", market, 46198.0, 46168.0, onetime, "flat", ExcelMissing.Value));
            Assert.Equal("#ERROR _QuoteByDates: start_date is text '26-May-2026', expected date", Seam.Call("_QuoteByDates", market, "26-May-2026", 46198.0, onetime, "flat", ExcelMissing.Value));
            Assert.Equal("#ERROR _Quote: ValueError: settlement_frequency is 'onetime', expected 'monthly'; a quote by contract code prices by the month, and _QuoteByDates prices a onetime period across two dates", Seam.Call("_Quote", market, "K26-M26", onetime, "flat", ExcelMissing.Value));
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
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "month", "monthly", 1.0, "lastday", "cleared", "physical", "CME Clearing"));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var trades = (string)Seam.Call("_CreateTrades", index, headers, new object[,] { { 1.0, 46153.0, "n26", 2.0, 70.0 }, { 2.0, 46153.0, "q26", -1.0, 72.0 } }, template);
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            Assert.StartsWith(Pid + ":prepared_trades:sample:", prepared);
            var results = (string)Seam.Call("_EvaluateTrades", prepared, market, ExcelMissing.Value);
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
            var risk = (object[,])Seam.Call("_ReportRisk", results, "all", "year");
            Assert.Equal(5, risk.GetLength(0));
            Assert.Equal(5, risk.GetLength(1));  // since #197 the cross-gamma's column last
            Assert.Equal("sample cleared cross_gamma [NYMEX NG per basis point]", risk[1, 4]);
            Assert.Equal(0.0, risk[3, 4]);
            Assert.Equal(0.0, risk[4, 4]);
            Assert.Equal("as_of", risk[0, 0]);
            Assert.Equal(46168.0, risk[0, 1]);
            Assert.Equal("-", risk[0, 3]);
            Assert.Equal("period", risk[1, 0]);
            Assert.Equal("sample nominal_delta [NYMEX NG]", risk[1, 1]);
            Assert.Equal("sample delta [NYMEX NG]", risk[1, 2]);
            Assert.Equal("cleared USD dv01 [USD per basis point]", risk[1, 3]);
            Assert.Equal("str | datetime64[D]", risk[2, 0]);
            Assert.Equal("float64", risk[2, 1]);
            Assert.Equal("Total", risk[3, 0]);
            Assert.Equal(1.0, risk[3, 1]);
            Assert.Equal(1.0, risk[3, 2]);
            Assert.Equal(0.0, risk[3, 3]);
            Assert.Equal(46023.0, risk[4, 0]);
            Assert.Equal(1.0, risk[4, 1]);
            var dv01 = (object[,])Seam.Call("_ReportRisk", results, "dv01", "day");
            Assert.Equal(4, dv01.GetLength(0));  // cleared: a Total of nothing over no dated row
            Assert.Equal(0.0, dv01[3, 1]);
            // Since #197 the cross-gamma alone: a cleared batch's known zero on the delta's rows.
            var cross = (object[,])Seam.Call("_ReportRisk", results, "cross_gamma", "year");
            Assert.Equal(5, cross.GetLength(0));
            Assert.Equal(2, cross.GetLength(1));
            Assert.Equal("sample cleared cross_gamma [NYMEX NG per basis point]", cross[1, 1]);
            Assert.Equal(0.0, cross[3, 1]);
            Assert.Equal(46023.0, cross[4, 0]);
            Assert.Equal(0.0, cross[4, 1]);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(4, slots.GetLength(0));
            Assert.Equal("live_coefficient", slots[0, 5]);
            Assert.Equal("live_lots", slots[0, 6]);
            Assert.Equal("n26", slots[2, 0]);
            Assert.Equal(false, slots[2, 3]);
            Assert.Equal(20000.0, slots[2, 5]);
            Assert.Equal(-10000.0, slots[3, 5]);
            Assert.Equal(2.0, slots[2, 6]);
            Assert.Equal(-1.0, slots[3, 6]);
            var contributions = (object[,])Seam.Call("util_ReadHandle", results);
            Assert.Equal("live_coefficient", contributions[0, 4]);
            Assert.Equal("live_lots", contributions[0, 5]);
            Assert.Equal("live_contribution", contributions[0, 6]);
            Assert.Equal("contract_sensitivity", contributions[0, 7]);
            Assert.Equal("contract_discounted_sensitivity", contributions[0, 8]);
            Assert.Equal("contract_nominal_delta", contributions[0, 9]);
            Assert.Equal("contract_delta", contributions[0, 10]);
            Assert.Equal(20000.0, contributions[2, 4]);
            Assert.Equal(2.0, contributions[2, 5]);
            Assert.Equal(1442000.0, (double)contributions[2, 6], 6);
            Assert.Equal(20000.0, contributions[2, 7]);
            Assert.Equal(20000.0, contributions[2, 8]);  // the discounted twin, the nominal for a cleared batch
            Assert.Equal(2.0, contributions[2, 9]);
            Assert.Equal(2.0, contributions[2, 10]);
            Assert.Equal("sensitivity_unit", contributions[0, 11]);
            Assert.Equal("USD per USD/MMBTU", contributions[2, 11]);
            Assert.Equal("lot_unit", contributions[0, 12]);
            Assert.Equal("lots of NYMEX NG (10000 MMBTU)", contributions[2, 12]);
            Assert.Equal("payment_factor", contributions[0, 13]);
            Assert.Equal("group_dv01", contributions[0, 16]);
            Assert.Equal("-", contributions[2, 13]);  // a cleared batch retains no payment facts
            Assert.Equal("brokerage_reserve", contributions[0, 17]);
            Assert.Equal(30, contributions.GetLength(1));  // since #197 the contract's cross-gamma and its unit, since named-curves-slice-3.md the key and the curve, since observation-prices-readback.md the four price columns, last, since cva-reserve.md the CVA reserve among the reserves
            Assert.Equal("observation_coefficient", contributions[0, 26]);
            Assert.Equal(20000.0, contributions[2, 26]);
            Assert.Equal(72.1, (double)contributions[2, 27], 9);  // the live quote the contribution was made of
            Assert.Equal("USD/MMBTU", contributions[2, 28]);
            Assert.Equal(1442000.0, (double)contributions[2, 29], 6);
            Assert.Equal("contract_cross_gamma", contributions[0, 22]);
            Assert.Equal("cross_gamma_unit", contributions[0, 23]);
            Assert.Equal(0.0, contributions[2, 22]);
            Assert.Equal("lots of NYMEX NG (10000 MMBTU) per basis point", contributions[2, 23]);
            var ticked = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "sample", Column(72.20, 72.80)));
            var later = (string)Seam.Call("_EvaluateTrades", prepared, ticked, ExcelMissing.Value);
            Assert.NotEqual(results, later);
            Assert.Equal(36000.0, (double)((object[,])Seam.Call("_ReportValues", later))[2, 0], 6);
            Assert.Equal(34000.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            Assert.Equal("#ERROR _EvaluateTrades: prepared is trades handle '" + trades + "', expected prepared trades handle", Seam.Call("_EvaluateTrades", trades, market, ExcelMissing.Value));
            Assert.Equal("#ERROR _ReportRisk: results is prepared trades handle '" + prepared + "', expected trade results or aggregate results or cashflow results handle", Seam.Call("_ReportRisk", prepared, "all", "day"));
            // Since #180, aggregate-risk-excel-integration.md: the results collected twice down a column,
            // one collection handle of its own kind, and the same reader over it, every Total doubled on
            // the same axis under the same labels; one result alone collected as itself; the readback's
            // membership rows; and the refusals in the seam's and the library's words, nothing collected
            // across a price tick, nothing read by the value readers.
            var collection = (string)Seam.Call("_AggregateResults", Column(results, results));
            Assert.StartsWith(Pid + ":aggregate_results:", collection);
            var doubled = (object[,])Seam.Call("_ReportRisk", collection, "all", "year");
            Assert.Equal(5, doubled.GetLength(0));
            Assert.Equal(5, doubled.GetLength(1));  // since #197 the one cleared pair's column of nothing
            Assert.Equal("sample cleared cross_gamma [NYMEX NG per basis point]", doubled[1, 4]);
            Assert.Equal(0.0, doubled[3, 4]);
            Assert.Equal(46168.0, doubled[0, 1]);
            Assert.Equal("sample nominal_delta [NYMEX NG]", doubled[1, 1]);
            Assert.Equal("sample delta [NYMEX NG]", doubled[1, 2]);
            Assert.Equal("cleared USD dv01 [USD per basis point]", doubled[1, 3]);
            Assert.Equal("Total", doubled[3, 0]);
            Assert.Equal(2.0, doubled[3, 1]);
            Assert.Equal(2.0, doubled[3, 2]);
            Assert.Equal(0.0, doubled[3, 3]);
            Assert.Equal(46023.0, doubled[4, 0]);
            Assert.Equal(2.0, doubled[4, 1]);
            var rate = (object[,])Seam.Call("_ReportRisk", collection, "dv01", "day");
            Assert.Equal(4, rate.GetLength(0));  // all cleared: a Total of nothing per currency over no dated row
            Assert.Equal("cleared USD dv01 [USD per basis point]", rate[1, 1]);
            Assert.Equal(0.0, rate[3, 1]);
            var alone = (string)Seam.Call("_AggregateResults", results);
            Assert.StartsWith(Pid + ":aggregate_results:", alone);
            Assert.Equal(1.0, ((object[,])Seam.Call("_ReportRisk", alone, "nominal_delta", "year"))[3, 1]);
            var members = (object[,])Seam.Call("util_ReadHandle", collection);
            Assert.Equal(4, members.GetLength(0));
            Assert.Equal(12, members.GetLength(1));  // since #197 each source's cross-gamma and its unit
            Assert.Equal("cross_gamma", members[0, 10]);
            Assert.Equal("cross_gamma_unit", members[0, 11]);
            Assert.Equal(0.0, members[2, 10]);
            Assert.Equal("lots of NYMEX NG (10000 MMBTU) per basis point", members[3, 11]);
            Assert.Equal("position", members[0, 0]);
            Assert.Equal("curve", members[0, 4]);
            Assert.Equal("as_of", members[0, 9]);
            Assert.Equal("int64", members[1, 0]);
            Assert.Equal(1.0, members[2, 0]);
            Assert.Equal(2.0, members[3, 0]);
            Assert.Equal("sample", members[2, 1]);
            Assert.Equal("NYMEX NG", members[2, 2]);
            Assert.Equal("cleared", members[2, 3]);
            Assert.Equal("-", members[2, 4]);
            Assert.Equal("USD", members[2, 5]);
            Assert.Equal(1.0, members[2, 6]);
            Assert.Equal(1.0, members[3, 7]);
            Assert.Equal(0.0, members[3, 8]);
            Assert.Equal(46168.0, members[3, 9]);
            Assert.Equal("#ERROR _AggregateResults: ValueError: results 2 is on index 'sample' quoted off another price vector than results 1, expected one price vector for one index", Seam.Call("_AggregateResults", Row(results, later)));
            Assert.Equal("#ERROR _AggregateResults: result_handles cell (2, 1) is blank, expected trade results or cashflow results handle", Seam.Call("_AggregateResults", Column(results, ExcelEmpty.Value)));
            Assert.Equal("#ERROR _AggregateResults: result_handles is prepared trades handle '" + prepared + "', expected trade results or cashflow results handle", Seam.Call("_AggregateResults", prepared));
            Assert.Equal("#ERROR _ReportValues: results is aggregate results handle '" + collection + "', expected trade results or cashflow results handle", Seam.Call("_ReportValues", collection));
            Assert.Equal("#ERROR _ReportReserves: results is aggregate results handle '" + collection + "', expected trade results handle", Seam.Call("_ReportReserves", collection));
            // A failed evaluation in a cell fails the collection behind the cell's name, the creator's text
            // whole, and the reader over the failed collection shows that text once behind its own wrapper.
            var broken = (string)Seam.Call("_AggregateResults", Column(results, "#ERROR _EvaluateTrades: ValueError: x"));
            Assert.Equal("#ERROR _AggregateResults: result_handles cell (2, 1) is the creator's failure, expected trade results or cashflow results handle: #ERROR _EvaluateTrades: ValueError: x", broken);
            Assert.Equal("#ERROR _ReportRisk: results is the creator's failure, expected trade results or aggregate results or cashflow results handle: #ERROR _EvaluateTrades: ValueError: x", Seam.Call("_ReportRisk", broken, "all", "day"));
        }

        // Combined holiday calendars, combine-holiday-calendars.md: the ticket's calendars A, listing
        // 14 October 2026 twice around the 12th, and B, the 13th and the 14th, combine into the 12th,
        // the 13th and the 14th once each in order, in a column as in a row, one calendar alone into its
        // own distinct days; from Friday the 9th +1bd is the 15th and +2bd the 16th, from the 15th -1bd
        // the 9th; a trade anchored on the 9th pays the 15th; the seam's refusals at their cells, and a
        // failed source carried whole.
        [Fact]
        public void combined_holiday_calendars_close_every_day_any_source_closes()
        {
            var a = (string)Seam.Call("_CreateHolidayCalendar", Column(46309.0, 46307.0, 46309.0));
            var b = (string)Seam.Call("_CreateHolidayCalendar", Column(46308.0, 46309.0));
            var combined = (string)Seam.Call("_CombineHolidayCalendars", Column(a, b));
            Assert.Matches(@"^\d+:holiday_calendar:\d+$", combined);
            var days = (object[,])Seam.Call("util_ReadHandle", combined);
            Assert.Equal(5, days.GetLength(0));
            Assert.Equal("holiday", days[0, 0]);
            Assert.Equal(46307.0, days[2, 0]);
            Assert.Equal(46308.0, days[3, 0]);
            Assert.Equal(46309.0, days[4, 0]);
            var inRow = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CombineHolidayCalendars", Row(b, a)));
            Assert.Equal(days, inRow);
            var alone = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CombineHolidayCalendars", a));
            Assert.Equal(4, alone.GetLength(0));
            Assert.Equal(46307.0, alone[2, 0]);
            Assert.Equal(46309.0, alone[3, 0]);
            Assert.Equal(46310.0, Seam.Call("util_ShiftDate", 46304.0, "+1bd", combined));
            Assert.Equal(46311.0, Seam.Call("util_ShiftDate", 46304.0, "+2bd", combined));
            Assert.Equal(46304.0, Seam.Call("util_ShiftDate", 46310.0, "-1bd", combined));
            Assert.Equal(46308.0, Seam.Call("util_ShiftDate", 46304.0, "+1bd", a));
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("U26", "V26", "X26"), Column(46261.0, 46293.0, 46304.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 47484.0);
            var anchored = Index(schedule, holidays, "ANCHORED");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "month", "monthly", 1.0, "lastday", "cleared", "financial", "Prototype Clearing", "+1bd", combined));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var trade = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateTrades", anchored, headers, Row(4001.0, 46296.0, "X26", 1.0, 3.0), template));
            Assert.Equal("payment_date", trade[0, 13]);
            Assert.Equal(46310.0, trade[2, 13]);
            Assert.Equal("#ERROR _CombineHolidayCalendars: calendar_handles is 2x2 array, expected one cell, one row or one column of holiday calendar handles", Seam.Call("_CombineHolidayCalendars", new object[,] { { a, b }, { b, a } }));
            Assert.Equal("#ERROR _CombineHolidayCalendars: calendar_handles cell (2, 1) is blank, expected holiday calendar handle", Seam.Call("_CombineHolidayCalendars", Column(a, ExcelEmpty.Value)));
            Assert.Equal("#ERROR _CombineHolidayCalendars: calendar_handles cell (1, 2) is number 46307.0, expected holiday calendar handle", Seam.Call("_CombineHolidayCalendars", Row(a, 46307.0)));
            Assert.Equal($"#ERROR _CombineHolidayCalendars: calendar_handles cell (2, 1) is futures schedule handle '{schedule}', expected holiday calendar handle", Seam.Call("_CombineHolidayCalendars", Column(a, schedule)));
            Assert.Equal("#ERROR _CombineHolidayCalendars: calendar_handles is text 'x' naming no live object, expected holiday calendar handle", Seam.Call("_CombineHolidayCalendars", "x"));
            Assert.Equal("#ERROR _CombineHolidayCalendars: calendar_handles is missing, expected holiday calendar handles in a cell, a row or a column", Seam.Call("_CombineHolidayCalendars", ExcelMissing.Value));
            var failed = (string)Seam.Call("_CreateHolidayCalendar", Column(46023.0, ExcelEmpty.Value));
            var broken = (string)Seam.Call("_CombineHolidayCalendars", Column(a, failed));
            Assert.Equal($"#ERROR _CombineHolidayCalendars: calendar_handles cell (2, 1) is the creator's failure, expected holiday calendar handle: {failed}", broken);
            Assert.Equal($"#ERROR util_ShiftDate: holiday_calendar is the creator's failure, expected holiday calendar handle: {failed}", Seam.Call("util_ShiftDate", 46304.0, "+1bd", broken));
        }

        // A half-year strip, half-year-strips.md: on an index of nine months, X26 the boundary and N27
        // last, 1h27 resolves to F27 through M27, six components on one occurrence, the entered code
        // kept as typed, each paying two business days after its expiry as the F27-M27 strip's do; the
        // balance of a half from a valuation day inside it; a zeroth half refused by the grammar.
        [Fact]
        public void a_half_year_strip_resolves_to_its_six_months_as_the_strip_of_them_does()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27", "G27", "H27", "J27", "K27", "M27", "N27"), Column(46351.0, 46385.0, 46414.0, 46442.0, 46475.0, 46505.0, 46533.0, 46566.0, 46596.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 47484.0);
            var half = Index(schedule, holidays, "HALF");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "month", "monthly", 1.0, "lastday", "cleared", "financial", "Prototype Clearing", "+2bd", holidays));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var one = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateTrades", half, headers, Row(3001.0, 46357.0, "1h27", 1.0, 3.0), template));
            var strip = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateTrades", half, headers, Row(3002.0, 46357.0, "F27-M27", 1.0, 3.0), template));
            Assert.Equal(8, one.GetLength(0));
            Assert.Equal(8, strip.GetLength(0));
            Assert.Equal("payment_date", one[0, 13]);
            Assert.Equal("entered_contract_code", one[0, 14]);
            var months = new[] { "F27", "G27", "H27", "J27", "K27", "M27" };
            var pays = new[] { 46416.0, 46444.0, 46477.0, 46507.0, 46535.0, 46568.0 };
            for (var k = 0; k < 6; k++)
            {
                Assert.Equal(1.0, one[2 + k, 0]);
                Assert.Equal(months[k], one[2 + k, 3]);
                Assert.Equal("1h27", one[2 + k, 14]);
                Assert.Equal(pays[k], one[2 + k, 13]);
                Assert.Equal(strip[2 + k, 13], one[2 + k, 13]);
                Assert.Equal(strip[2 + k, 19], one[2 + k, 19]);  // quote_quantity
            }
            var midMarch = (string)Seam.Call("_CreateValuationDate", 46461.0, 0.0);
            Assert.Equal(46461.0, Seam.Call("util_StartDate", "BAL1H27", midMarch));
            Assert.Equal(46568.0, Seam.Call("util_EndDate", "bal1h27", midMarch));
            Assert.Equal("#ERROR _CreateTrades: ValueError: contract_code row 1 is '0H27', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28", Seam.Call("_CreateTrades", half, headers, Row(3003.0, 46357.0, "0H27", 1.0, 3.0), template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: contract_code row 1 is '2H27', expected months the index's schedule has a contract for; it has none for 2027-08", Seam.Call("_CreateTrades", half, headers, Row(3003.0, 46357.0, "2H27", 1.0, 3.0), template));
        }

        // A quote, template-based-quoting.md: the ticket's strip on an index of Z26 bounding the calendar
        // and F27 and G27 month-matching, closed on weekends and New Year's Day, valued 31 December 2026
        // with both months live at 30 and 60; a bilateral and a cleared quote template over the fields a
        // quote may hold, SOFR 0.99 on 1 February and 0.98 on 1 March, the two payment days of +1bd on a
        // weekend-only calendar; the month and calendar-day prices by hand, January alone 30, the strip's
        // balance the strip with both months ahead and the balance of a month gone refused, since
        // balance-of-period-quotes.md; the
        // template's readback; a trade template and a blank fourth cell refused by the seam, a left-out or
        // a surplus collection by the library, and the quote template refused where a trade template is taken.
        [Fact]
        public void a_quote_prices_the_tickets_strip_cleared_and_bilateral()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("Z26", "F27", "G27"), Column(46371.0, 46416.0, 46444.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46388.0);
            var index = Index(schedule, holidays, "STRIP");
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46387.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46386.0, 46385.0, 46384.0, 46381.0, 46380.0, 46379.0, 46378.0, 46377.0, 46374.0, 46373.0, 46372.0), Column(3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "STRIP", Column(30.0, 60.0)));
            var weekends = (string)Seam.Call("_CreateHolidayCalendar", 47484.0);
            var fields = Row("route", "settlement_method", "schedule_method", "quantity_per", "payment_day", "payment_holiday_calendar", "discount_curve_key", "settlement_frequency", "nearby");
            var otc = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", fields, Row("bilateral", "financial", "asian", "month", "+1bd", weekends, "SOFR", "monthly", 1.0));
            var cleared = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", Row("route", "settlement_method", "schedule_method", "quantity_per", "payment_day", "payment_holiday_calendar", "settlement_frequency", "nearby"), Row("cleared", "financial", "asian", "calday", "+1bd", weekends, "monthly", 1.0));
            Assert.StartsWith(Pid + ":quote_template:", otc);
            var sofr = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), new object[,] { { 46387.0, 1.0 }, { 46419.0, 0.99 }, { 46447.0, 0.98 } });
            var rates = (string)Seam.Call("_CollectDiscountCurves", sofr);
            Assert.Equal(44.23728813559322, (double)Seam.Call("_Quote", market, "F27-G27", cleared, "flat", ExcelMissing.Value), 12);
            Assert.Equal(44.923857868020306, (double)Seam.Call("_Quote", market, "F27-G27", otc, "flat", rates), 12);
            Assert.Equal(30.0, (double)Seam.Call("_Quote", market, "F27", otc, "flat", rates), 12);
            // Since fit-to-curve-price.md the pricing: ftc weighs the months by quantity alone, 45 where the
            // flat bilateral price is 44.92; one month and a cleared quote are the same under either.
            Assert.Equal(45.0, (double)Seam.Call("_Quote", market, "F27-G27", otc, "ftc", rates), 12);
            Assert.Equal(30.0, (double)Seam.Call("_Quote", market, "F27", otc, "ftc", rates), 12);
            Assert.Equal(44.23728813559322, (double)Seam.Call("_Quote", market, "F27-G27", cleared, "ftc", ExcelMissing.Value), 12);
            Assert.Equal(44.23728813559322, (double)Seam.Call("_Quote", market, "BALF27-G27", cleared, "flat", ExcelMissing.Value), 12);
            Assert.Equal("#ERROR _Quote: ValueError: valuation_date is 2026-12-31, after 'BALX26' ended on 2026-11-30, expected a valuation day on or before the period's last day", Seam.Call("_Quote", market, "BALX26", cleared, "flat", ExcelMissing.Value));
            var shown = (object[,])Seam.Call("util_ReadHandle", otc);
            Assert.Equal(3, shown.GetLength(0));
            Assert.Equal(10, shown.GetLength(1));  // settlement_frequency since onetime-averaging.md, nearby since nearby-selection.md
            Assert.Equal("instrument", shown[0, 0]);
            Assert.Equal("fixed_float", shown[2, 0]);
            Assert.Equal("a holiday calendar", shown[2, 6]);
            Assert.Equal("discount_curve_key", shown[0, 7]);
            Assert.Equal("SOFR", shown[2, 7]);
            var trade = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("route"), "cleared");
            Assert.Equal($"#ERROR _Quote: template is trade template handle '{trade}', expected quote template handle", Seam.Call("_Quote", market, "F27", trade, "flat", ExcelMissing.Value));
            Assert.Equal("#ERROR _Quote: discount_curve_set is blank, expected discount curve set handle", Seam.Call("_Quote", market, "F27", otc, "flat", ExcelEmpty.Value));
            Assert.Equal("#ERROR _Quote: pricing is blank, expected text", Seam.Call("_Quote", market, "F27", otc, ExcelEmpty.Value, rates));
            Assert.Equal("#ERROR _Quote: pricing is missing, expected text", Seam.Call("_Quote", market, "F27", otc, ExcelMissing.Value, rates));
            Assert.Equal("#ERROR _Quote: ValueError: pricing is 'FTC', expected flat or ftc", Seam.Call("_Quote", market, "F27", otc, "FTC", rates));
            // A formula written before the argument existed has its curve where the pricing now goes.
            Assert.Equal($"#ERROR _Quote: ValueError: pricing is '{rates}', expected flat or ftc", Seam.Call("_Quote", market, "F27", otc, rates, ExcelMissing.Value));
            Assert.Equal("#ERROR _Quote: ValueError: discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, under flat and ftc alike", Seam.Call("_Quote", market, "F27", otc, "ftc", ExcelMissing.Value));
            Assert.Equal("#ERROR _Quote: ValueError: discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, under flat and ftc alike", Seam.Call("_Quote", market, "F27", otc, "flat", ExcelMissing.Value));
            Assert.Equal("#ERROR _Quote: ValueError: discount_curve_set is a collection of 1 curve, expected none with route = cleared; a cleared quote discounts nothing", Seam.Call("_Quote", market, "F27", cleared, "flat", rates));
            Assert.Equal($"#ERROR _CreateTrades: template is quote template handle '{otc}', expected trade template handle", Seam.Call("_CreateTrades", index, Row("quantity"), 1.0, otc));
        }

        // A request for quote, rfq-quoting.md and dated-quotes.md, on the quote fact's strip as a ticket's
        // rows: F27 at 100,000 and G27 at 300,000 under the bilateral +1bd template paying 1 February at
        // 0.99 and 1 March at 0.98, 20,610,000 over 393,000; the request's own 8 February, 46426,
        // interpolated to 0.9875, and 1 March, 20,602,500 over 392,750; the cleared calendar-day template,
        // 3,100,000 and 8,400,000 a month, 597 over 11.5; the readback's rows, periods, sources and days;
        // two windows by their dates under a onetime template, 11 January to 26 February at 47.142857 and
        // 1 to 12 February at 60 paying 1 March at 0.98 and 15 February at 0.985, 22,350,000 over
        // 393,500; a booking header, a text quantity, a rule in the payment column, a bad code, a date on
        // a month's last observation and the template's kind refused in the seam's words and the
        // library's, and a market over another index refused before any data is gathered.
        [Fact]
        public void a_request_for_quote_is_saved_and_priced_on_the_strip()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("Z26", "F27", "G27"), Column(46371.0, 46416.0, 46444.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46388.0);
            var index = Index(schedule, holidays, "STRIP");
            var date = (string)Seam.Call("_CreateValuationDate", 46387.0, 0.5);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46386.0, 46385.0, 46384.0, 46381.0, 46380.0, 46379.0, 46378.0, 46377.0, 46374.0, 46373.0, 46372.0), Column(3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0), index);
            var history = (string)Seam.Call("_CreateMarketHistory", (string)Seam.Call("_CreateCalendar", date, index), fixings);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "STRIP", Column(30.0, 60.0)));
            var weekends = (string)Seam.Call("_CreateHolidayCalendar", 47484.0);
            var fields = Row("route", "settlement_method", "schedule_method", "quantity_per", "payment_day", "payment_holiday_calendar", "discount_curve_key", "settlement_frequency", "nearby");
            var otc = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", fields, Row("bilateral", "financial", "asian", "month", "+1bd", weekends, "SOFR", "monthly", 1.0));
            var cleared = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", Row("route", "settlement_method", "schedule_method", "quantity_per", "payment_day", "payment_holiday_calendar", "settlement_frequency", "nearby"), Row("cleared", "financial", "asian", "calday", "+1bd", weekends, "monthly", 1.0));
            var sofr = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), new object[,] { { 46387.0, 1.0 }, { 46419.0, 0.99 }, { 46447.0, 0.98 } });
            var rates = (string)Seam.Call("_CollectDiscountCurves", sofr);
            var byCode = Row("contract_code", "quantity");
            var ticket = new object[,] { { "F27", 100000.0 }, { "G27", 300000.0 } };
            var saved = (string)Seam.Call("_CreateRFQ", index, byCode, ticket, otc);
            Assert.StartsWith(Pid + ":rfq:STRIP:", saved);
            var withDays = Row("contract_code", "quantity", "payment_day");
            var dated = (string)Seam.Call("_CreateRFQ", index, withDays, new object[,] { { "F27", 100000.0, 46426.0 }, { "G27", 300000.0, 46447.0 } }, otc);
            Assert.StartsWith(Pid + ":rfq:STRIP:", dated);
            var daily = (string)Seam.Call("_CreateRFQ", index, byCode, ticket, cleared);
            Assert.Equal(20610000.0 / 393000.0, (double)Seam.Call("_QuoteRFQ", market, saved, "flat", rates), 12);
            Assert.Equal(20602500.0 / 392750.0, (double)Seam.Call("_QuoteRFQ", market, dated, "flat", rates), 12);
            Assert.Equal(597.0 / 11.5, (double)Seam.Call("_QuoteRFQ", market, daily, "flat", ExcelMissing.Value), 12);
            // Since fit-to-curve-price.md the same saved requests under ftc: the quantities alone, 21,000,000
            // over 400,000, whichever days they pay on; the cleared one the same under either.
            Assert.Equal(52.5, (double)Seam.Call("_QuoteRFQ", market, saved, "ftc", rates), 12);
            Assert.Equal(52.5, (double)Seam.Call("_QuoteRFQ", market, dated, "ftc", rates), 12);
            Assert.Equal(597.0 / 11.5, (double)Seam.Call("_QuoteRFQ", market, daily, "ftc", ExcelMissing.Value), 12);
            // Since ftc-monthly-prices.md the months' fixed prices from one agreed price: agreed at 52.63
            // against the quote of 52.5 each month takes 13 cents, 30.13 and 60.13, which round at one
            // decimal to 30.1 and 60.1 and come back to 21,040,000 over 400,000, 52.6, three cents under;
            // the check's three rows, a dash in their spare cells, over the header, the types and a row a
            // month. At the quote's own cell nothing moves and the difference is zero exactly.
            var prices = (object[,])Seam.Call("_QuoteFTCPrices", market, saved, 52.63, 1.0);
            Assert.Equal(7, prices.GetLength(0));
            Assert.Equal(4, prices.GetLength(1));
            Assert.Equal("agreed_price", prices[0, 0]);
            Assert.Equal(52.63, prices[0, 1]);
            Assert.Equal("-", prices[0, 2]);
            Assert.Equal("-", prices[0, 3]);
            Assert.Equal("average_fixed_price", prices[1, 0]);
            Assert.Equal(52.6, (double)prices[1, 1], 12);
            Assert.Equal("difference", prices[2, 0]);
            Assert.Equal(-0.03, (double)prices[2, 1], 12);
            Assert.Equal("period", prices[3, 0]);
            Assert.Equal("fixed_price", prices[3, 3]);
            Assert.Equal("str", prices[4, 0]);
            Assert.Equal("float64", prices[4, 3]);
            Assert.Equal("F27", prices[5, 0]);
            Assert.Equal(100000.0, prices[5, 1]);
            Assert.Equal(30.0, (double)prices[5, 2], 12);
            Assert.Equal(30.1, prices[5, 3]);
            Assert.Equal("G27", prices[6, 0]);
            Assert.Equal(300000.0, prices[6, 1]);
            Assert.Equal(60.1, prices[6, 3]);
            var quoted = (double)Seam.Call("_QuoteRFQ", market, daily, "ftc", ExcelMissing.Value);
            var atQuote = (object[,])Seam.Call("_QuoteFTCPrices", market, daily, quoted, 0.0);
            Assert.Equal(0.0, atQuote[2, 1]);
            Assert.Equal(3100000.0, atQuote[5, 1]);
            Assert.Equal(30.0, atQuote[5, 3]);
            Assert.Equal(60.0, atQuote[6, 3]);
            Assert.Equal("#ERROR _QuoteFTCPrices: decimals is number 2.5, expected whole number", Seam.Call("_QuoteFTCPrices", market, saved, 52.63, 2.5));
            Assert.Equal("#ERROR _QuoteFTCPrices: ValueError: decimals is 16, expected a whole number from 0 to 15, the decimals a fixed price may hold", Seam.Call("_QuoteFTCPrices", market, saved, 52.63, 16.0));
            Assert.Equal("#ERROR _QuoteFTCPrices: price is text 'flat', expected number", Seam.Call("_QuoteFTCPrices", market, saved, "flat", 2.0));
            Assert.Equal("#ERROR _QuoteFTCPrices: decimals is missing, expected whole number", Seam.Call("_QuoteFTCPrices", market, saved, 52.63, ExcelMissing.Value));
            Assert.Equal($"#ERROR _QuoteFTCPrices: rfq is market handle '{market}', expected rfq handle", Seam.Call("_QuoteFTCPrices", market, market, 52.63, 2.0));
            var shown = (object[,])Seam.Call("util_ReadHandle", dated);
            Assert.Equal(4, shown.GetLength(0));
            Assert.Equal(15, shown.GetLength(1));  // nearby last, since nearby-selection.md
            Assert.Equal("row", shown[0, 0]);
            Assert.Equal("period", shown[0, 1]);
            Assert.Equal("payment_source", shown[0, 5]);
            Assert.Equal("datetime64[D]", shown[1, 6]);
            Assert.Equal("F27", shown[2, 1]);
            Assert.Equal(300000.0, shown[3, 2]);
            Assert.Equal("request", shown[2, 5]);
            Assert.Equal(46426.0, shown[2, 6]);
            Assert.Equal(46447.0, shown[3, 6]);
            Assert.Equal("STRIP", shown[2, 7]);
            Assert.Equal("SOFR", shown[2, 12]);
            Assert.Equal("monthly", shown[2, 13]);
            var byTemplate = (object[,])Seam.Call("util_ReadHandle", saved);
            Assert.Equal("template", byTemplate[2, 5]);
            Assert.Equal(46419.0, byTemplate[2, 6]);
            Assert.Equal(3100000.0, ((object[,])Seam.Call("util_ReadHandle", daily))[2, 4]);
            var onetime = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", fields, Row("bilateral", "financial", "asian", "period", "+1bd", weekends, "SOFR", "onetime", 1.0));
            var windows = (string)Seam.Call("_CreateRFQ", index, Row("start_date", "end_date", "quantity", "payment_day"), new object[,] { { 46398.0, 46444.0, 100000.0, 46447.0 }, { 46419.0, 46430.0, 300000.0, 46433.0 } }, onetime);
            Assert.Equal(22350000.0 / 393500.0, (double)Seam.Call("_QuoteRFQ", market, windows, "flat", rates), 9);
            Assert.Equal((100000.0 * 1650.0 / 35.0 + 300000.0 * 60.0) / 400000.0, (double)Seam.Call("_QuoteRFQ", market, windows, "ftc", rates), 9);
            var byDates = (object[,])Seam.Call("util_ReadHandle", windows);
            Assert.Equal("2027-01-11 to 2027-02-26", byDates[2, 1]);
            Assert.Equal("2027-02-01 to 2027-02-12", byDates[3, 1]);
            Assert.Equal("onetime", byDates[3, 13]);
            Assert.Equal("#ERROR _CreateRFQ: ValueError: trade_id is a field of booking alone, expected one a request's rows hold: contract_code, start_date, end_date, quantity, payment_day", Seam.Call("_CreateRFQ", index, Row("trade_id", "quantity"), Row(1.0, 100000.0), otc));
            Assert.Equal("#ERROR _CreateRFQ: ValueError: nearby is a field of the quote template, expected one a request's rows hold: contract_code, start_date, end_date, quantity, payment_day; supply nearby on the quote template", Seam.Call("_CreateRFQ", index, Row("contract_code", "quantity", "nearby"), Row("F27", 100000.0, 2.0), otc));
            Assert.Equal("#ERROR _CreateRFQ: rows cell (2, 2) is text 'ten', expected number", Seam.Call("_CreateRFQ", index, byCode, new object[,] { { "F27", 1.0 }, { "G27", "ten" } }, otc));
            Assert.Equal($"#ERROR _CreateRFQ: template is market handle '{market}', expected quote template handle", Seam.Call("_CreateRFQ", index, byCode, ticket, market));
            Assert.Equal("#ERROR _CreateRFQ: ValueError: payment_day row 1 is '+2bd', expected a date; a request's rows pay on dates, and a rule is the template's to hold", Seam.Call("_CreateRFQ", index, withDays, Row("F27", 100000.0, "+2bd"), otc));
            Assert.Equal("#ERROR _CreateRFQ: ValueError: contract_code row 2 is 'H27', expected months the index's schedule has a contract for; it has none for 2027-03", Seam.Call("_CreateRFQ", index, byCode, new object[,] { { "F27", 1.0 }, { "H27", 1.0 } }, otc));
            Assert.Equal("#ERROR _CreateRFQ: ValueError: F27 of row 1 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, when its final price exists", Seam.Call("_CreateRFQ", index, withDays, Row("F27", 100000.0, 46416.0), otc));
            Assert.Equal("#ERROR _QuoteRFQ: ValueError: discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, under flat and ftc alike", Seam.Call("_QuoteRFQ", market, saved, "flat", ExcelMissing.Value));
            Assert.Equal($"#ERROR _QuoteRFQ: rfq is quote template handle '{otc}', expected rfq handle", Seam.Call("_QuoteRFQ", market, otc, "flat", rates));
            Assert.Equal("#ERROR _QuoteRFQ: ValueError: pricing is 'both', expected flat or ftc", Seam.Call("_QuoteRFQ", market, saved, "both", rates));
            Assert.Equal($"#ERROR _QuoteRFQ: ValueError: pricing is '{rates}', expected flat or ftc", Seam.Call("_QuoteRFQ", market, saved, rates, ExcelMissing.Value));
            var other = Index(schedule, holidays, "OTHER");
            var elsewhere = (string)Seam.Call("_CreateMarket", (string)Seam.Call("_CreateMarketHistory", (string)Seam.Call("_CreateCalendar", date, other), (string)Seam.Call("_CreateFuturesFixings", Column(46386.0, 46385.0, 46384.0, 46381.0, 46380.0, 46379.0, 46378.0, 46377.0, 46374.0, 46373.0, 46372.0), Column(3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0), other)), (string)Seam.Call("_CreatePriceVector", "OTHER", Column(30.0, 60.0)));
            Assert.StartsWith("#ERROR _QuoteRFQ: ValueError: market is over another index, 'OTHER', expected the request's, 'STRIP'", (string)Seam.Call("_QuoteRFQ", elsewhere, saved, "flat", rates));
        }

        // Since payment-day-date-or-rule.md the payment field holds a date or a rule: the ticket's two
        // bilateral rows on a synthetic index, F27 expiring Friday 29 January 2027, 46416, 10,000 MMBtu at
        // 2.65 each, F27 quoted 3.10 on 15 December 2026, 46371; one pays +2bd, Tuesday 2 February, 46420,
        // and one on Thursday 25 February, 46443, entered as a date: 4,455 on SOFR 0.990 and 4,432.50 on
        // 0.985, 8,887.50 in all and no cash. The readback holds the rule as text and the date as a date
        // under one header typed `date or text`, beside the day each resolved to; a date on the expiry is
        // refused by its trade, a boolean by the seam, and the old header is a field of nothing.
        [Fact]
        public void a_payment_day_is_a_date_or_a_rule_and_reads_back_as_entered()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27", "G27"), Column(46323.0, 46351.0, 46416.0, 46444.0), ExcelMissing.Value);
            var weekends = (string)Seam.Call("_CreateHolidayCalendar", 47484.0);
            var conventions = Seam.Call("_CreateIndexConventions", "USD", "MMBTU", "USD", "ENERGY", "MMBTU");
            var specifications = Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "MMBTU", 1.0, "MMBTU", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "SYN", "Synthetic gas index for the payment-day example", schedule, conventions, specifications, weekends, "MMBTU");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "counterparty", "discount_curve_key", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("MMBTU", "month", "monthly", 1.0, "lastday", "bilateral", "financial", "ACME Trading", "SOFR", weekends));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "payment_day");
            var rows = new object[,] { { 1001.0, 46371.0, "F27", 10000.0, 2.65, "+2bd" }, { 1002.0, 46371.0, "F27", 10000.0, 2.65, 46443.0 } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            var batch = (object[,])Seam.Call("util_ReadHandle", trades);
            var at = -1;
            for (var c = 0; c < batch.GetLength(1); c++) { if (Equals(batch[0, c], "payment_day")) { at = c; } }
            Assert.True(at >= 0);
            Assert.Equal("date or text", batch[1, at]);
            Assert.Equal("+2bd", batch[2, at]);
            Assert.Equal(46443.0, batch[3, at]);
            Assert.Equal("payment_date", batch[0, at + 1]);
            Assert.Equal(46420.0, batch[2, at + 1]);
            Assert.Equal(46443.0, batch[3, at + 1]);
            // The calendar runs from the day after X26 expires, Thursday 29 October 2026, 46324; every
            // fixed business day before the valuation day holds a settle of 3, newest first.
            var days = new List<object>();
            var settles = new List<object>();
            for (var d = 46370.0; d >= 46324.0; d--) { if (d % 7 >= 2 && d % 7 <= 6) { days.Add(d); settles.Add(3.0); } }
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(days.ToArray()), Column(settles.ToArray()), index);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46371.0, 0.5), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "SYN", Column(3.10)));
            var sofr = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), new object[,] { { 46371.0, 1.0 }, { 46420.0, 0.990 }, { 46443.0, 0.985 } });
            var rates = (string)Seam.Call("_CollectDiscountCurves", sofr);
            var results = (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", trades, history), market, rates);
            var values = (object[,])Seam.Call("_ReportValues", results);
            Assert.Equal(8887.5, (double)values[2, 0], 6);
            Assert.Equal(0.0, values[2, 1]);
            Assert.Equal("#ERROR _CreateTrades: ValueError: trade 1002 at row 2 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, when its final price exists", Seam.Call("_CreateTrades", index, headers, new object[,] { { 1001.0, 46371.0, "F27", 10000.0, 2.65, "+2bd" }, { 1002.0, 46371.0, "F27", 10000.0, 2.65, 46416.0 } }, template));
            Assert.Equal("#ERROR _CreateTrades: trade_rows cell (2, 6) is boolean TRUE, expected date or text", Seam.Call("_CreateTrades", index, headers, new object[,] { { 1001.0, 46371.0, "F27", 10000.0, 2.65, "+2bd" }, { 1002.0, 46371.0, "F27", 10000.0, 2.65, true } }, template));
            Assert.StartsWith("#ERROR _CreateTradeTemplate: fields cell (1, 1) is text 'payment_time_lag', expected a field of fixed_float: ", (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("payment_time_lag"), "+2bd"));
        }

        // The penultimate method on the host's chain: a financial template paying one business day
        // after the pen day on the chain's holiday calendar, the same two trades under it. n26
        // expires Monday 22 June 2026, so its pen day is Friday the 19th, 46192, and it pays on
        // the 22nd, 46195; q26 expires Tuesday 21 July, observes Monday the 20th and pays on the
        // 21st, 46224. Both live on 26 May, the batch marks the lastday batch's 34,000; a physical
        // penultimate template makes no batch, and an unbuilt method is refused by name.
        [Fact]
        public void a_penultimate_batch_observes_the_day_before_expiry_and_pays_after_it()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46167.0);
            var index = Index(schedule, holidays);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46168.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46164.0, 46163.0, 46162.0), Column(71.25, 71.10, 70.85), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "sample", Column(72.10, 72.80)));
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "month", "monthly", 1.0, "penultimate", "cleared", "financial", "ICE Clear Europe", "+1bd", holidays));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var rows = new object[,] { { 1.0, 46153.0, "n26", 2.0, 70.0 }, { 2.0, 46153.0, "q26", -1.0, 72.0 } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(24, spill.GetLength(1));
            Assert.Equal("penultimate", spill[2, 4]);
            Assert.Equal("payment_date", spill[0, 13]);
            Assert.Equal(46195.0, spill[2, 13]);
            Assert.Equal(46224.0, spill[3, 13]);
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal("observation_date", slots[0, 2]);
            Assert.Equal("payment_date", slots[0, 3]);
            Assert.Equal(46192.0, slots[2, 2]);
            Assert.Equal(46223.0, slots[3, 2]);
            Assert.Equal(46195.0, slots[2, 3]);
            Assert.Equal(46224.0, slots[3, 3]);
            Assert.Equal(false, slots[2, 4]);
            var values = (object[,])Seam.Call("_ReportValues", (string)Seam.Call("_EvaluateTrades", prepared, market, ExcelMissing.Value));
            Assert.Equal(34000.0, (double)values[2, 0], 6);
            Assert.Equal(0.0, values[2, 1]);
            var physical = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house"), Row("NYMEX NG", "month", "monthly", 1.0, "penultimate", "cleared", "physical", "CME Clearing"));
            Assert.Equal("#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the penultimate method of trade 1 at row 1; a penultimate future is cash settled on the business day before its contract's expiry", Seam.Call("_CreateTrades", index, headers, rows, physical));
        }

        // The last three pricing days, last3day-trades.md: the synthetic index of X26, Z26 and F27,
        // 46356, 46363 and 46394, closed on 4 December, 46360, one specification UNIT of one MMBTU;
        // the template last3day, cleared, financial, paying two weekdays after the last observation;
        // A, 60 of Z26 at 70, and B, -30 at 72. The batch observes the 2nd, 3rd and 7th, 46358,
        // 46359 and 46363, a third each, and pays the 9th, 46365; on 3 December, the 2nd fixed at
        // 71, the mark is 150, the cash 0 and the delta 20; a tick to 75 marks 170 on the same
        // preparation while the first results stand; a physical last3day template makes no batch.
        [Fact]
        public void a_last3day_batch_observes_three_days_a_third_each_and_pays_after_the_last()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27"), Column(46356.0, 46363.0, 46394.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46360.0);
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "MMBTU", "USD", "ENERGY", "MMBTU");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), Row("UNIT", 1.0, "MMBTU", 0.0, 0.0));
            var index = (string)Seam.Call("_CreateIndex", "SYN", "Synthetic gas index for the last3day example", schedule, conventions, specifications, holidays, "UNIT");
            var weekdays = (string)Seam.Call("_CreateHolidayCalendar", 46023.0);
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("UNIT", "month", "monthly", 1.0, "last3day", "cleared", "financial", "Prototype Clearing", "+2bd", weekdays));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var rows = new object[,] { { 1.0, 46346.0, "Z26", 60.0, 70.0 }, { 2.0, 46346.0, "Z26", -30.0, 72.0 } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal("last3day", spill[2, 4]);
            Assert.Equal(46365.0, spill[2, 13]);
            Assert.Equal(46365.0, spill[3, 13]);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46359.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46358.0, 46357.0), Column(71.0, 70.0), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(5, slots.GetLength(0));
            Assert.Equal(46358.0, slots[2, 2]);
            Assert.Equal(46359.0, slots[3, 2]);
            Assert.Equal(46363.0, slots[4, 2]);
            Assert.Equal(46365.0, slots[2, 3]);
            Assert.Equal(true, slots[2, 4]);
            Assert.Equal(false, slots[3, 4]);
            Assert.Equal(0.0, slots[2, 6]);
            Assert.Equal(10.0, (double)slots[4, 6], 6);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "SYN", Column(74.0, 80.0)));
            var results = (string)Seam.Call("_EvaluateTrades", prepared, market, ExcelMissing.Value);
            var values = (object[,])Seam.Call("_ReportValues", results);
            Assert.Equal(150.0, (double)values[2, 0], 6);
            Assert.Equal(0.0, values[2, 1]);
            Assert.Equal(20.0, (double)((object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year"))[3, 1], 6);
            var ticked = (string)Seam.Call("_EvaluateTrades", prepared, (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "SYN", Column(75.0, 80.0))), ExcelMissing.Value);
            Assert.Equal(170.0, (double)((object[,])Seam.Call("_ReportValues", ticked))[2, 0], 6);
            Assert.Equal(150.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            var physical = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house"), Row("UNIT", "month", "monthly", 1.0, "last3day", "cleared", "physical", "Prototype Clearing"));
            Assert.Equal("#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the last3day method of trade 1 at row 1; a last3day future is cash settled on the average of its last three pricing days", Seam.Call("_CreateTrades", index, headers, rows, physical));
        }

        // Calendar month Asian trades, asian-trades.md: the synthetic ethane index of X26, Z26, F27
        // and G27, 46356, 46387, 46416 and 46444, closed on 25 December and 1 January, 46381 and
        // 46388, one specification GAL of one gallon; the template asian, cleared, financial, paying
        // two weekdays after the month's last pricing day on a calendar closed on 1 January; A,
        // 4,400 gallons of Z26 at 0.25, and B, -2,200 at 0.26. The batch observes December's 22
        // pricing days, the 1st, 46357, to the 31st, 46387, and pays 5 January, 46392; on 2 December,
        // the 1st fixed at 0.24 and the rest live at the projection of 0.28, the mark is 84, the
        // cash 0 and the delta 2,100 to that projection; a tick to 0.29 marks 105 on the same
        // preparation while the first results stand; a physical asian template makes no batch.
        [Fact]
        public void an_asian_batch_observes_every_pricing_day_of_its_month_and_pays_after_the_last()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27", "G27"), Column(46356.0, 46387.0, 46416.0, 46444.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", Column(46381.0, 46388.0));
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "GAL", "USD", "VOLUME", "GAL");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), Row("GAL", 1.0, "GAL", 0.0, 0.0));
            var index = (string)Seam.Call("_CreateIndex", "ETHANE", "Ethane - synthetic volume index", schedule, conventions, specifications, holidays, "GAL");
            var payments = (string)Seam.Call("_CreateHolidayCalendar", 46388.0);
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("GAL", "month", "monthly", 1.0, "asian", "cleared", "financial", "Prototype Clearing", "+2bd", payments));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var rows = new object[,] { { 1.0, 46346.0, "Z26", 4400.0, 0.25 }, { 2.0, 46346.0, "Z26", -2200.0, 0.26 } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal("asian", spill[2, 4]);
            Assert.Equal(46392.0, spill[2, 13]);
            Assert.Equal(46392.0, spill[3, 13]);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46358.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46357.0, 46356.0), Column(0.24, 0.28), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(24, slots.GetLength(0));
            Assert.Equal(46357.0, slots[2, 2]);
            Assert.Equal(46387.0, slots[23, 2]);
            Assert.Equal(46392.0, slots[2, 3]);
            Assert.Equal(true, slots[2, 4]);
            Assert.Equal(false, slots[3, 4]);
            Assert.Equal(0.0, slots[2, 6]);
            Assert.Equal(100.0, (double)slots[3, 6], 6);
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "ETHANE", Column(0.28, 0.30, 0.32)));
            var results = (string)Seam.Call("_EvaluateTrades", prepared, market, ExcelMissing.Value);
            var values = (object[,])Seam.Call("_ReportValues", results);
            Assert.Equal(84.0, (double)values[2, 0], 6);
            Assert.Equal(0.0, values[2, 1]);
            var risk = (object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year");
            Assert.Equal(2100.0, (double)risk[3, 1], 6);
            Assert.Equal("ETHANE nominal_delta [GAL]", risk[1, 1]);
            var ticked = (string)Seam.Call("_EvaluateTrades", prepared, (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "ETHANE", Column(0.29, 0.30, 0.32))), ExcelMissing.Value);
            Assert.Equal(105.0, (double)((object[,])Seam.Call("_ReportValues", ticked))[2, 0], 6);
            Assert.Equal(84.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            var physical = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house"), Row("GAL", "month", "monthly", 1.0, "asian", "cleared", "physical", "Prototype Clearing"));
            Assert.Equal("#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the asian method of trade 1 at row 1; an asian future is cash settled on the average of its month's pricing days", Seam.Call("_CreateTrades", index, headers, rows, physical));
        }

        // Calendar day quantities, trade-periods-and-bal.md slice A: on the NG index of the batch
        // fact, a calday template; C over X26-Z26 at 100 lots a calendar day and D of Z26 at 110 a
        // day read back with the days each month covers, 30 and 31, the months' quantities, 3,000,
        // 3,100 and 3,410 lots, and the quote quantities ten thousand times those, the entered
        // quantities beside them, two columns more than a month batch's spill had; a basis that is
        // neither word refused by name.
        [Fact]
        public void a_calday_batch_holds_the_entered_quantity_times_the_days_its_month_covers()
        {
            var schedule = Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27"), Column(46323.0, 46351.0, 46385.0), ExcelMissing.Value);
            var holidays = Seam.Call("_CreateHolidayCalendar", Column(46352.0, 46381.0));
            var ng = Index(schedule, holidays, "Henry Hub NYMEX");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "calday", "monthly", 1.0, "lastday", "cleared", "physical", "CME Clearing"));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var rows = new object[,] { { 3.0, 46289.0, "X26-Z26", 100.0, 3.0 }, { 4.0, 46289.0, "Z26", 110.0, 3.0 } };
            var spill = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateTrades", ng, headers, rows, template));
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(22, spill.GetLength(1));
            Assert.Equal("covered_days", spill[0, 15]);
            Assert.Equal("int64", spill[1, 15]);
            Assert.Equal("component_quantity", spill[0, 16]);
            Assert.Equal("calday", spill[2, 10]);
            Assert.Equal(100.0, spill[2, 8]);
            Assert.Equal(110.0, spill[4, 8]);
            Assert.Equal(46327.0, spill[2, 13]);
            Assert.Equal(46356.0, spill[2, 14]);
            Assert.Equal(30.0, spill[2, 15]);
            Assert.Equal(31.0, spill[3, 15]);
            Assert.Equal(31.0, spill[4, 15]);
            Assert.Equal(3000.0, spill[2, 16]);
            Assert.Equal(3100.0, spill[3, 16]);
            Assert.Equal(3410.0, spill[4, 16]);
            Assert.Equal(30000000.0, spill[2, 17]);
            Assert.Equal(34100000.0, spill[4, 17]);
            Assert.Equal("#ERROR _CreateTradeTemplate: ValueError: quantity_per is 'day', expected month, calday or period", Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "day", "monthly", 1.0, "lastday", "cleared", "physical", "CME Clearing")));
        }

        // Explicit dates, trade-periods-and-bal.md slice C: on the ethane index of the asian fact, a
        // ticket booked by start_date and end_date, P the balance of Z26 from 15 December through the
        // helpers on BALZ26 and Q the whole of December through them on Z26, under the asian template;
        // the spill shows the code the resolution bound and the days each covers, 17 and 31; on
        // 2 December, the 1st fixed at 0.24 and the rest live at 0.28, the batch marks 122, P's 60 and
        // Q's 62, with 4,100 of delta over 22 slots; a part of a month under lastday, both forms
        // together and a date alone are refused in the library's words.
        [Fact]
        public void a_batch_booked_by_dates_covers_its_days_and_values_beside_the_coded_one()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27", "G27"), Column(46356.0, 46387.0, 46416.0, 46444.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", Column(46381.0, 46388.0));
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "GAL", "USD", "VOLUME", "GAL");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), Row("GAL", 1.0, "GAL", 0.0, 0.0));
            var index = (string)Seam.Call("_CreateIndex", "ETHANE", "Ethane - synthetic volume index", schedule, conventions, specifications, holidays, "GAL");
            var payments = (string)Seam.Call("_CreateHolidayCalendar", 46388.0);
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("GAL", "month", "monthly", 1.0, "asian", "cleared", "financial", "Prototype Clearing", "+2bd", payments));
            var midDecember = (string)Seam.Call("_CreateValuationDate", 46371.0, 0.5);  // the helpers take the handle since #173
            var start = (double)Seam.Call("util_StartDate", "BALZ26", midDecember);
            var end = (double)Seam.Call("util_EndDate", "BALZ26", midDecember);
            var first = (double)Seam.Call("util_StartDate", "Z26", midDecember);
            var last = (double)Seam.Call("util_EndDate", "Z26", midDecember);
            var headers = Row("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price");
            var rows = new object[,] { { 16.0, 46346.0, start, end, 2000.0, 0.25 }, { 17.0, 46346.0, first, last, 2200.0, 0.25 } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(24, spill.GetLength(1));
            Assert.Equal("Z26", spill[2, 3]);
            Assert.Equal("start_date", spill[0, 15]);
            Assert.Equal(46371.0, spill[2, 15]);
            Assert.Equal(46387.0, spill[2, 16]);
            Assert.Equal(17.0, spill[2, 17]);
            Assert.Equal(2000.0, spill[2, 18]);
            Assert.Equal(46357.0, spill[3, 15]);
            Assert.Equal(31.0, spill[3, 17]);
            Assert.Equal(46392.0, spill[2, 13]);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46358.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", Column(46357.0, 46356.0), Column(0.24, 0.28), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            Assert.Equal(24, ((object[,])Seam.Call("util_ReadHandle", prepared)).GetLength(0));
            var results = (string)Seam.Call("_EvaluateTrades", prepared, (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "ETHANE", Column(0.28, 0.30, 0.32))), ExcelMissing.Value);
            Assert.Equal(122.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            Assert.Equal(4100.0, (double)((object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year"))[3, 1], 6);
            var lastday = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("GAL", "month", "monthly", 1.0, "lastday", "cleared", "financial", "Prototype Clearing", "+2bd", payments));
            Assert.Equal("#ERROR _CreateTrades: ValueError: Z26 of trade 16 at row 1 is covered from 2026-12-15 to 2026-12-31, part of its month, expected the whole month under lastday; the expiry-based methods take the contract's month entire, and a part of it prices under asian", Seam.Call("_CreateTrades", index, headers, Row(16.0, 46346.0, start, end, 2000.0, 0.25), lastday));
            Assert.Equal("#ERROR _CreateTrades: ValueError: start_date row 1 is 2026-12-15 without end_date row 1, expected both dates, the period's first and last day, or neither and a contract_code", Seam.Call("_CreateTrades", index, Row("trade_date", "contract_code", "start_date", "quantity", "fixed_price"), Row(46346.0, "Z26", start, 2000.0, 0.25), template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: start_date row 1 is 2026-12-15 without end_date row 1, expected both dates, the period's first and last day, or neither and a contract_code", Seam.Call("_CreateTrades", index, Row("trade_date", "start_date", "quantity", "fixed_price"), Row(46346.0, start, 2000.0, 0.25), template));
        }

        // Two payment days on one contract, multiple-payment-groups.md: the synthetic index PAYS of
        // X26, Z26 and F27, 46356, 46360 and 46395, closed on New Year's Day 2026 alone, 46023, one
        // specification UNIT of one MMBTU; a last3day template over seven fields, the lag left to the
        // ticket; A, 60 of Z26 at 70 at +1bd, paying Monday 7 December, 46363, and B, -30 at 72 at
        // +3bd, paying Wednesday the 9th, 46365: two groups of Z26, the lags and the days read back off
        // the batch. On 3 December, 46359, the 2nd fixed at 71, the mark is 150 and the delta 20 over
        // six slots, two a day, one quote serving both groups, and a tick to 75 marks 170; on the 7th,
        // every settle in, A is cash, 180, and B mark, -30, the preparation showing A's slots settled
        // and B's not, each with its payment day, and the results the contract's delta of nothing.
        [Fact]
        public void two_payment_days_on_one_contract_are_two_groups_each_paid_on_its_own_day()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27"), Column(46356.0, 46360.0, 46395.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46023.0);
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "MMBTU", "USD", "ENERGY", "MMBTU");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), Row("UNIT", 1.0, "MMBTU", 0.0, 0.0));
            var index = (string)Seam.Call("_CreateIndex", "PAYS", "Synthetic gas index for the payment-groups example", schedule, conventions, specifications, holidays, "UNIT");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("UNIT", "month", "monthly", 1.0, "last3day", "cleared", "financial", "Prototype Clearing", holidays));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "payment_day");
            var rows = new object[,] { { 1.0, 46356.0, "Z26", 60.0, 70.0, "+1bd" }, { 2.0, 46356.0, "Z26", -30.0, 72.0, "+3bd" } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal("+1bd", spill[2, 12]);
            Assert.Equal("+3bd", spill[3, 12]);
            Assert.Equal(46363.0, spill[2, 13]);
            Assert.Equal(46365.0, spill[3, 13]);
            var third = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46359.0, 0.5), index);
            var early = (string)Seam.Call("_CreateMarketHistory", third, (string)Seam.Call("_CreateFuturesFixings", Column(46358.0, 46357.0), Column(71.0, 74.0), index));
            var live = (string)Seam.Call("_PrepareTrades", trades, early);
            Assert.Equal(8, ((object[,])Seam.Call("util_ReadHandle", live)).GetLength(0));
            var market = (string)Seam.Call("_CreateMarket", early, (string)Seam.Call("_CreatePriceVector", "PAYS", Column(74.0, 80.0)));
            var results = (string)Seam.Call("_EvaluateTrades", live, market, ExcelMissing.Value);
            Assert.Equal(150.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            Assert.Equal(20.0, (double)((object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year"))[3, 1], 6);
            var mixed = (object[,])Seam.Call("util_ReadHandle", results);  // observation-prices-readback.md: the 2nd fixed at 71, the 3rd and the 4th live at 74, each slot's own, last
            Assert.Equal(31, mixed.GetLength(1));  // since cva-reserve.md one more among the reserves
            Assert.Equal("observation_coefficient", mixed[0, 27]);
            Assert.Equal("observation_price", mixed[0, 28]);
            Assert.Equal("price_unit", mixed[0, 29]);
            Assert.Equal("floating_contribution", mixed[0, 30]);
            Assert.Equal(20.0, (double)mixed[2, 27], 9);
            Assert.Equal(71.0, (double)mixed[2, 28], 9);
            Assert.Equal("USD/MMBTU", mixed[2, 29]);
            Assert.Equal(1420.0, (double)mixed[2, 30], 9);
            Assert.Equal(0.0, (double)mixed[2, 7], 9);  // the live contribution stays zero on a fixed slot
            Assert.Equal(74.0, (double)mixed[3, 28], 9);
            Assert.Equal(1480.0, (double)mixed[3, 30], 9);
            Assert.Equal(1480.0, (double)mixed[3, 7], 9);
            Assert.Equal(-10.0, (double)mixed[5, 27], 9);
            Assert.Equal(-710.0, (double)mixed[5, 30], 9);
            var ticked = (string)Seam.Call("_EvaluateTrades", live, (string)Seam.Call("_CreateMarket", early, (string)Seam.Call("_CreatePriceVector", "PAYS", Column(75.0, 80.0))), ExcelMissing.Value);
            Assert.Equal(170.0, (double)((object[,])Seam.Call("_ReportValues", ticked))[2, 0], 6);
            var seventh = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46363.0, 0.5), index);
            var history = (string)Seam.Call("_CreateMarketHistory", seventh, (string)Seam.Call("_CreateFuturesFixings", Column(46360.0, 46359.0, 46358.0, 46357.0), Column(73.0, 75.0, 71.0, 74.0), index));
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(8, slots.GetLength(0));
            Assert.Equal(8, slots.GetLength(1));
            Assert.Equal("payment_date", slots[0, 3]);
            Assert.Equal("live_lots", slots[0, 7]);
            Assert.Equal(46358.0, slots[2, 2]);
            Assert.Equal(46358.0, slots[5, 2]);
            Assert.Equal(46363.0, slots[2, 3]);
            Assert.Equal(46365.0, slots[5, 3]);
            Assert.Equal(true, slots[2, 4]);
            Assert.Equal(true, slots[2, 5]);
            Assert.Equal(false, slots[5, 5]);
            Assert.Equal(0.0, slots[7, 6]);
            var paid = (string)Seam.Call("_EvaluateTrades", prepared, (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "PAYS", Column(80.0))), ExcelMissing.Value);
            var values = (object[,])Seam.Call("_ReportValues", paid);
            Assert.Equal(-30.0, (double)values[2, 0], 6);
            Assert.Equal(180.0, (double)values[2, 1], 6);
            Assert.Equal(0.0, (double)((object[,])Seam.Call("_ReportRisk", paid, "nominal_delta", "year"))[3, 1], 6);
            var contributions = (object[,])Seam.Call("util_ReadHandle", paid);
            Assert.Equal(31, contributions.GetLength(1));  // since #197 two columns more, since slice 3 two more, since observation-prices-readback.md four more, last, since cva-reserve.md one more among the reserves
            Assert.Equal("contract_nominal_delta", contributions[0, 10]);
            Assert.Equal("contract_delta", contributions[0, 11]);
            Assert.Equal(46365.0, contributions[5, 3]);
            Assert.Equal(0.0, contributions[5, 10]);
            Assert.Equal(20.0, (double)contributions[2, 27], 9);  // paid: every slot's settle and contribution still shown, history and no mark
            Assert.Equal(75.0, (double)contributions[3, 28], 9);
            Assert.Equal(1500.0, (double)contributions[3, 30], 9);
            Assert.Equal(73.0, (double)contributions[7, 28], 9);
            Assert.Equal(-730.0, (double)contributions[7, 30], 9);
            Assert.Equal(0.0, (double)contributions[7, 7], 9);  // the live contribution, zero once fixed
        }

        // Mixed fields in one batch, mixed-trade-fields.md: the index MIXED, USD per GAL, X26, Z26, F27
        // and G27, 46356, 46387, 46416 and 46444, the market closed on 25 December, 46381, GAL of one
        // gallon and BBL of one barrel; a template of six fields, the route, the settlement, the trade
        // date, the price of 10, +1bd and a payment calendar closed on New Year's Day, 46388; four rows
        // of Z26, each its own unit, basis, method and clearing house, read back row by row. Every
        // settle 11 and the projection 12: on 30 December, 46386, the 29th and before fixed, 194 of mark
        // and 66 of delta, a tick to 13 marking 260 on the same preparation; on the 31st, 46387, B fixed
        // and paid, -62 of cash, 275 of mark and 85 of delta, the preparation's 23 slots in two groups;
        // a template holding the method beside the ticket's column refused, and a unit the index does
        // not define refused by its row.
        [Fact]
        public void a_mixed_batch_values_each_row_by_its_own_unit_basis_and_method()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27", "G27"), Column(46356.0, 46387.0, 46416.0, 46444.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46381.0);
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "GAL", "USD", "VOLUME", "GAL");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "GAL", 1.0, "GAL", 0.0, 0.0 }, { "BBL", 1.0, "BBL", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "MIXED", "Synthetic volume index for the mixed-fields example", schedule, conventions, specifications, holidays, "GAL");
            var payments = (string)Seam.Call("_CreateHolidayCalendar", 46388.0);
            var fields = Row("route", "settlement_method", "trade_date", "fixed_price", "payment_day", "payment_holiday_calendar", "settlement_frequency", "nearby");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("cleared", "financial", 46356.0, 10.0, "+1bd", payments, "monthly", 1.0));
            var headers = Row("trade_id", "contract_code", "quantity", "quantity_unit", "quantity_per", "schedule_method", "clearing_house");
            var rows = new object[,] { { 1.0, "Z26", 1.0, "BBL", "month", "lastday", "Clearer A" }, { 2.0, "Z26", -2.0, "GAL", "calday", "penultimate", "Clearer B" }, { 3.0, "Z26", 3.0, "BBL", "month", "last3day", "Clearer A" }, { 4.0, "Z26", 22.0, "GAL", "month", "asian", "Clearer B" } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(6, spill.GetLength(0));
            Assert.Equal("lastday", spill[2, 4]);
            Assert.Equal("penultimate", spill[3, 4]);
            Assert.Equal("last3day", spill[4, 4]);
            Assert.Equal("asian", spill[5, 4]);
            Assert.Equal("Clearer B", spill[3, 7]);
            Assert.Equal("BBL", spill[2, 9]);
            Assert.Equal("GAL", spill[3, 9]);
            Assert.Equal("calday", spill[3, 10]);
            Assert.Equal(46391.0, spill[2, 13]);
            Assert.Equal(46387.0, spill[3, 13]);
            Assert.Equal(-62.0, spill[3, 18]);
            Assert.Equal(42.0, spill[2, 19]);
            Assert.Equal(126.0, spill[4, 19]);
            Assert.Equal(22.0, spill[5, 19]);
            var thirtieth = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46386.0, 0.5), index);
            var early = (string)Seam.Call("_CreateMarketHistory", thirtieth, (string)Seam.Call("_CreateFuturesFixings", Column(46385.0, 46384.0, 46380.0, 46379.0, 46378.0, 46377.0, 46374.0, 46373.0, 46372.0, 46371.0, 46370.0, 46367.0, 46366.0, 46365.0, 46364.0, 46363.0, 46360.0, 46359.0, 46358.0, 46357.0), Column(11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0), index));
            var live = (string)Seam.Call("_PrepareTrades", trades, early);
            var market = (string)Seam.Call("_CreateMarket", early, (string)Seam.Call("_CreatePriceVector", "MIXED", Column(12.0, 13.0, 14.0)));
            var results = (string)Seam.Call("_EvaluateTrades", live, market, ExcelMissing.Value);
            Assert.Equal(194.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            Assert.Equal(66.0, (double)((object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year"))[3, 1], 6);
            var ticked = (string)Seam.Call("_EvaluateTrades", live, (string)Seam.Call("_CreateMarket", early, (string)Seam.Call("_CreatePriceVector", "MIXED", Column(13.0, 13.0, 14.0))), ExcelMissing.Value);
            Assert.Equal(260.0, (double)((object[,])Seam.Call("_ReportValues", ticked))[2, 0], 6);
            var last = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46387.0, 0.5), index);
            var history = (string)Seam.Call("_CreateMarketHistory", last, (string)Seam.Call("_CreateFuturesFixings", Column(46386.0, 46385.0, 46384.0, 46380.0, 46379.0, 46378.0, 46377.0, 46374.0, 46373.0, 46372.0, 46371.0, 46370.0, 46367.0, 46366.0, 46365.0, 46364.0, 46363.0, 46360.0, 46359.0, 46358.0, 46357.0), Column(11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0), index));
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(25, slots.GetLength(0));
            Assert.Equal(46387.0, slots[2, 3]);
            Assert.Equal(46391.0, slots[3, 3]);
            Assert.Equal(true, slots[2, 5]);
            Assert.Equal(false, slots[3, 5]);
            Assert.Equal(85.0, (double)slots[24, 6], 6);
            var paid = (string)Seam.Call("_EvaluateTrades", prepared, (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "MIXED", Column(12.0, 13.0, 14.0))), ExcelMissing.Value);
            var values = (object[,])Seam.Call("_ReportValues", paid);
            Assert.Equal(275.0, (double)values[2, 0], 6);
            Assert.Equal(-62.0, (double)values[2, 1], 6);
            var risk = (object[,])Seam.Call("_ReportRisk", paid, "nominal_delta", "year");
            Assert.Equal(85.0, (double)risk[3, 1], 6);
            Assert.Equal("MIXED nominal_delta [GAL]", risk[1, 1]);
            var withMethod = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("route", "settlement_method", "trade_date", "fixed_price", "payment_day", "payment_holiday_calendar", "schedule_method"), Row("cleared", "financial", 46356.0, 10.0, "+1bd", payments, "lastday"));
            Assert.Equal("#ERROR _CreateTrades: ValueError: schedule_method is supplied by the template and by the ticket, expected by one of them", Seam.Call("_CreateTrades", index, headers, rows, withMethod));
            Assert.Equal("#ERROR _CreateTrades: ValueError: quantity_unit row 2 is 'ICE', expected one of the index's specifications: 'GAL', 'BBL'", Seam.Call("_CreateTrades", index, headers, new object[,] { { 1.0, "Z26", 1.0, "BBL", "month", "lastday", "Clearer A" }, { 5.0, "Z26", 1.0, "ICE", "month", "lastday", "Clearer A" } }, template));
            // A batch on an index made without a reporting lot is refused when it is made, never when its risk is read.
            var lotless = (string)Seam.Call("_CreateIndex", "MIXED", "Synthetic volume index for the mixed-fields example", schedule, conventions, specifications, holidays, ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateTrades: ValueError: index 'MIXED' has no reporting_lot, expected one of its specifications named when the index was made; a batch's delta is reported in lots of it", Seam.Call("_CreateTrades", lotless, headers, rows, template));
        }

        // A holiday calendar: a column of dates makes one, a single cell makes one of one day, and
        // A date shifted on a calendar of the host's making: Monday 12 October 2026 closed, so Friday
        // the 9th steps to Tuesday the 13th and the closed Monday back to the Friday; a zero count
        // leaves the Saturday as it is, a week of calendar days reads no holiday, and a valuation
        // date where the calendar should be is refused in the seam's words.
        [Fact]
        public void a_date_is_shifted_on_a_holiday_calendar_the_host_made()
        {
            var calendar = (string)Seam.Call("_CreateHolidayCalendar", 46307.0);
            Assert.Equal(46308.0, Seam.Call("util_ShiftDate", 46304.0, "+1BD", calendar));
            Assert.Equal(46304.0, Seam.Call("util_ShiftDate", 46307.0, "-1bd", calendar));
            Assert.Equal(46305.0, Seam.Call("util_ShiftDate", 46305.0, "+0bd", calendar));
            Assert.Equal(46311.0, Seam.Call("util_ShiftDate", 46304.0, "+7cd", calendar));
            Assert.Equal(46326.0, Seam.Call("util_ShiftDate", 46304.0, "+0em", calendar));
            var valuation = (string)Seam.Call("_CreateValuationDate", 46304.0, 0.5);
            Assert.Equal("#ERROR util_ShiftDate: holiday_calendar is valuation date handle '" + valuation + "', expected holiday calendar handle", Seam.Call("util_ShiftDate", 46304.0, "+1bd", valuation));
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

        // An IFERC schedule: two columns make one, two single cells make one of one contract
        // month, and util_ReadHandle spills it back, the two headers, the two types, then a
        // row per contract month, the code as text and the publication day as a serial; since
        // iferc-publication-payment-anchor.md the schedule holds no last trading date.
        [Fact]
        public void an_iferc_schedule_is_created_from_two_columns_and_read_back_through_its_handle()
        {
            var handle = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46296.0, 46328.0, 46357.0));
            Assert.StartsWith(Pid + ":iferc_schedule:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(2, spill.GetLength(1));
            Assert.Equal("contract_code", spill[0, 0]);
            Assert.Equal("publication_date", spill[0, 1]);
            Assert.Equal("str", spill[1, 0]);
            Assert.Equal("datetime64[D]", spill[1, 1]);
            Assert.Equal("V26", spill[2, 0]);
            Assert.Equal(46296.0, spill[2, 1]);
            Assert.Equal("Z26", spill[4, 0]);
            Assert.Equal(46357.0, spill[4, 1]);
            var one = (string)Seam.Call("_CreateIfercSchedule", "V26", 46296.0);
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

        // The index: a name, a description, a futures schedule of three contracts, the conventions, the
        // specifications and a holiday calendar make one, and util_ReadHandle spills it back as one
        // row, the name, the description, the kind, three contracts, two specifications and TRUE; an IFERC schedule
        // without a holiday calendar makes one whose row says IFERC and FALSE. The library's rules
        // answer through the same objects: the futures schedule without its holiday calendar, the
        // Gas Daily schedule with one, a holiday calendar where the schedule should be, and a handle
        // of another kind where the conventions should be.
        [Fact]
        public void an_index_is_created_from_two_texts_and_four_handles_and_read_back_through_its_handle()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("m26", "n26", "q26"), Column(46161.0, 46195.0, 46224.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46167.0);
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "MMBTU", "USD", "ENERGY", "MMBTU");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0 }, { "ICE NG", 2500.0, "MMBTU", 0.75, 0.5 } });
            var handle = (string)Seam.Call("_CreateIndex", "Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", schedule, conventions, specifications, holidays, ExcelMissing.Value);
            Assert.StartsWith(Pid + ":index:Henry Hub NYMEX:", handle);
            // The reporting lot, named: read back with its size, unit and two conversions after the six; a name the specifications lack refused naming them.
            var lotted = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateIndex", "Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", schedule, conventions, specifications, holidays, "NYMEX NG"));
            Assert.Equal(11, lotted.GetLength(1));
            Assert.Equal("reporting_lot", lotted[0, 6]);
            Assert.Equal("NYMEX NG", lotted[2, 6]);
            Assert.Equal(10000.0, lotted[2, 7]);
            Assert.Equal("MMBTU", lotted[2, 8]);
            Assert.Equal(10000.0, lotted[2, 9]);
            Assert.Equal(10000.0, lotted[2, 10]);
            Assert.Equal("#ERROR _CreateIndex: ValueError: reporting_lot is 'LOT', expected one of the specifications: 'NYMEX NG', 'ICE NG'", Seam.Call("_CreateIndex", "Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", schedule, conventions, specifications, holidays, "LOT"));
            // The lot units are units of the conventions' quantity type: the same MMBTU lots under volume conventions are refused, naming the row and the units that would have done.
            var volume = (string)Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "VOLUME", "BBL");
            Assert.Equal("#ERROR _CreateIndex: ValueError: specifications row 1 lot_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3", Seam.Call("_CreateIndex", "WTI NYMEX", "West Texas Intermediate crude oil - NYMEX", schedule, volume, specifications, holidays, ExcelMissing.Value));
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(3, spill.GetLength(0));
            Assert.Equal(7, spill.GetLength(1));
            Assert.Equal("reporting_lot", spill[0, 6]);
            Assert.Equal("unset", spill[2, 6]);
            Assert.Equal("display_name", spill[0, 1]);
            Assert.Equal("kind", spill[0, 2]);
            Assert.Equal("str", spill[1, 1]);
            Assert.Equal("Henry Hub natural gas - NYMEX", spill[2, 1]);
            Assert.Equal("int64", spill[1, 3]);
            Assert.Equal("Henry Hub NYMEX", spill[2, 0]);
            Assert.Equal("futures", spill[2, 2]);
            Assert.Equal(3.0, spill[2, 3]);
            Assert.Equal(2.0, spill[2, 4]);
            Assert.Equal(true, spill[2, 5]);
            var iferc = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46296.0, 46328.0, 46357.0));
            var monthly = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateIndex", "Henry Hub IFERC", "Henry Hub natural gas - Inside FERC monthly index", iferc, conventions, specifications, ExcelMissing.Value, ExcelMissing.Value));
            Assert.Equal("Henry Hub natural gas - Inside FERC monthly index", monthly[2, 1]);
            Assert.Equal("IFERC", monthly[2, 2]);
            Assert.Equal(false, monthly[2, 5]);
            Assert.Equal("#ERROR _CreateIndex: ValueError: holiday_calendar is missing, expected holiday calendar handle with a futures schedule", Seam.Call("_CreateIndex", "Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", schedule, conventions, specifications, ExcelMissing.Value, ExcelMissing.Value));
            var gasDaily = (string)Seam.Call("_CreateGasDailySchedule", Column("U26", "V26", "X26"), Column(46266.0, 46296.0, 46327.0), Column(46295.0, 46326.0, 46356.0));
            Assert.Equal("#ERROR _CreateIndex: ValueError: holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule", Seam.Call("_CreateIndex", "Henry Hub Gas Daily", "Henry Hub natural gas - Platts Gas Daily", gasDaily, conventions, specifications, holidays, ExcelMissing.Value));
            Assert.Equal("#ERROR _CreateIndex: ValueError: schedule is a holiday calendar, expected a futures, IFERC or Gas Daily schedule", Seam.Call("_CreateIndex", "Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", holidays, conventions, specifications, ExcelMissing.Value, ExcelMissing.Value));
            Assert.Equal("#ERROR _CreateIndex: index_conventions is holiday calendar handle '" + holidays + "', expected index conventions handle", Seam.Call("_CreateIndex", "Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", schedule, holidays, specifications, holidays, ExcelMissing.Value));
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
            Assert.Equal("nearby_1", spill[0, 1]);  // the prompt contract's settle, nearby-selection.md
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
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: settle has 1 row, expected 2, one per date", Seam.Call("_CreateFuturesFixings", Column(46146.0, 46143.0), Column(106.42), index));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-06, expected a date before row 1's 2026-05-05", Seam.Call("_CreateFuturesFixings", Column(46147.0, 46148.0), Column(102.27, 95.08), index));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-01, expected 2026-05-04, the business day before row 1's 2026-05-05", Seam.Call("_CreateFuturesFixings", Column(46147.0, 46143.0), Column(102.27, 101.94), index));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-05-02, a Saturday, expected a business day", Seam.Call("_CreateFuturesFixings", Column(46144.0, 46143.0), Column(100.0, 101.94), index));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-01-19, a holiday, expected a business day", Seam.Call("_CreateFuturesFixings", 46041.0, 100.0, index));
            var gasDaily = Index(Seam.Call("_CreateGasDailySchedule", Column("U26"), Column(46266.0), Column(46295.0)), ExcelMissing.Value);
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: index is a Gas Daily index, expected a futures index", Seam.Call("_CreateFuturesFixings", 46143.0, 101.94, gasDaily));
            Assert.Equal("#ERROR _CreateFuturesFixings: index is futures fixings handle '" + handle + "', expected index handle", Seam.Call("_CreateFuturesFixings", 46143.0, 101.94, handle));
            // nearby-selection.md: a settle range two columns wide keeps a column for each nearby contract, the
            // prompt's first, read back under nearby_1 and nearby_2; a row of settles beside one date is that day's
            // nearbys, and beside two dates it is one row short.
            var wide = (string)Seam.Call("_CreateFuturesFixings", Column(46146.0, 46143.0), new object[,] { { 106.42, 107.5 }, { 101.94, 102.5 } }, index);
            var wideSpill = (object[,])Seam.Call("util_ReadHandle", wide);
            Assert.Equal(4, wideSpill.GetLength(0));
            Assert.Equal(3, wideSpill.GetLength(1));
            Assert.Equal("nearby_1", wideSpill[0, 1]);
            Assert.Equal("nearby_2", wideSpill[0, 2]);
            Assert.Equal(106.42, wideSpill[2, 1]);
            Assert.Equal(107.5, wideSpill[2, 2]);
            Assert.Equal(102.5, wideSpill[3, 2]);
            Assert.Equal(3, ((object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateFuturesFixings", 46143.0, Row(101.94, 102.5), index))).GetLength(1));
            Assert.Equal("#ERROR _CreateFuturesFixings: ValueError: settle has 1 row, expected 2, one per date", Seam.Call("_CreateFuturesFixings", Column(46146.0, 46143.0), Row(106.42, 101.94), index));
        }

        // The fixings of more than one nearby, nearby-selection.md: the ROLL index, K26 expiring 15 May 2026
        // and bounding the calendar, M26 on Monday 15 June, N26 on 15 July, Q26 on 14 August and U26 on 15
        // September, valued 17 June; a settle on each of the 22 business days from 18 May to 16 June, the
        // prompt's and the second nearby's, 80 and 82 on the expiry day and 81 and 83 the day after. The
        // history reads back the calendar's four columns, the prompt's fixing_price, and for the second
        // nearby the contract its settle is of on each day, N26 on the expiry day and Q26 after it, and the
        // settle; a Saturday closed, a day to come unfixed, and a dash where the schedule lists no second
        // nearby. A history of the prompt's column alone reads back its five columns as it always did.
        [Fact]
        public void a_history_holds_a_settle_for_each_nearby_and_reads_back_the_contract_it_is_of()
        {
            var schedule = Seam.Call("_CreateFuturesSchedule", Column("K26", "M26", "N26", "Q26", "U26"), Column(46157.0, 46188.0, 46218.0, 46248.0, 46280.0), ExcelMissing.Value);
            var index = Index(schedule, (string)Seam.Call("_CreateHolidayCalendar", 46388.0), "ROLL");
            var days = new List<double>();
            for (var serial = 46189.0; serial >= 46160.0; serial--)
            {
                if (serial % 7 > 1)  // a serial divisible by 7 is a Saturday, the next a Sunday
                {
                    days.Add(serial);
                }
            }
            Assert.Equal(22, days.Count);
            var dates = new object[days.Count, 1];
            var settles = new object[days.Count, 2];
            var prompt = new object[days.Count, 1];
            for (var i = 0; i < days.Count; i++)
            {
                dates[i, 0] = days[i];
                settles[i, 0] = days[i] == 46189.0 ? 81.0 : days[i] == 46188.0 ? 80.0 : 70.0;
                settles[i, 1] = days[i] == 46189.0 ? 83.0 : days[i] == 46188.0 ? 82.0 : 72.0;
                prompt[i, 0] = settles[i, 0];
            }
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46190.0, 0.5), index);
            var fixings = (string)Seam.Call("_CreateFuturesFixings", dates, settles, index);
            var spill = (object[,])Seam.Call("util_ReadHandle", fixings);
            Assert.Equal(24, spill.GetLength(0));
            Assert.Equal("nearby_2", spill[0, 2]);
            Assert.Equal(46189.0, spill[2, 0]);
            Assert.Equal(83.0, spill[2, 2]);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, fixings);
            Assert.StartsWith(Pid + ":market_history:ROLL:", history);
            var read = (object[,])Seam.Call("util_ReadHandle", history);
            Assert.Equal(7, read.GetLength(1));
            Assert.Equal("fixing_price", read[0, 4]);
            Assert.Equal("nearby_2_contract", read[0, 5]);
            Assert.Equal("nearby_2_fixing_price", read[0, 6]);
            Assert.Equal("str", read[1, 5]);
            Assert.Equal("float64", read[1, 6]);
            Assert.Equal(46158.0, read[2, 0]);  // the calendar begins the day after K26 expires
            Assert.Equal(46188.0, read[32, 0]);  // Monday 15 June, M26's expiry day
            Assert.Equal("M26", read[32, 1]);
            Assert.Equal(80.0, read[32, 4]);
            Assert.Equal("N26", read[32, 5]);
            Assert.Equal(82.0, read[32, 6]);
            Assert.Equal("N26", read[33, 1]);  // the day after, N26 prompt and Q26 the second nearby
            Assert.Equal(81.0, read[33, 4]);
            Assert.Equal("Q26", read[33, 5]);
            Assert.Equal(83.0, read[33, 6]);
            Assert.Equal("unfixed", read[34, 4]);  // the valuation day
            Assert.Equal("Q26", read[34, 5]);
            Assert.Equal("unfixed", read[34, 6]);
            Assert.Equal("closed", read[30, 4]);  // Saturday 13 June
            Assert.Equal("closed", read[30, 6]);
            var last = read.GetLength(0) - 1;
            Assert.Equal(46280.0, read[last, 0]);  // U26's expiry day, the schedule's last
            Assert.Equal("U26", read[last, 1]);
            Assert.Equal("-", read[last, 5]);
            var alone = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateMarketHistory", calendar, (string)Seam.Call("_CreateFuturesFixings", dates, prompt, index)));
            Assert.Equal(5, alone.GetLength(1));
            Assert.Equal(80.0, alone[32, 4]);
            Assert.Equal(81.0, alone[33, 4]);
        }

        // The nearby on a trade, nearby-selection.md's second slice. Two rows over the two days across
        // M26's expiry, one lot of 10,000 against 80 each, the first row's nearby 1 and the second's 2
        // in a ticket column: one batch, one payment group, one history two settles wide and one
        // market. The readback shows each row's nearby last; the prepared slots are four, M26 and
        // N26 read on the 15th and N26 and Q26 on the 16th; the first row averages 80.5 and the
        // second 82.5, 5,000 and 25,000 of mark. A nearby the schedule lists no contract for, a number
        // that is no position, text, and the field left out are refused when the batch is made, a
        // third nearby the history holds no settle of when it is prepared. A quote template's nearby is
        // priced as a row's is, since the ticket's third slice: the window quotes 80.5 at the first
        // nearby and 82.5 at the second, and a later nearby under lastday is refused by name.
        [Fact]
        public void a_row_reads_the_nearby_it_names_and_a_second_nearby_averages_the_next_contract()
        {
            var schedule = Seam.Call("_CreateFuturesSchedule", Column("K26", "M26", "N26", "Q26", "U26"), Column(46157.0, 46188.0, 46218.0, 46248.0, 46280.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46388.0);
            var index = Index(schedule, holidays, "ROLL");
            var days = new List<double>();
            for (var serial = 46189.0; serial >= 46160.0; serial--)
            {
                if (serial % 7 > 1)  // a serial divisible by 7 is a Saturday, the next a Sunday
                {
                    days.Add(serial);
                }
            }
            var dates = new object[days.Count, 1];
            var settles = new object[days.Count, 2];
            for (var i = 0; i < days.Count; i++)
            {
                dates[i, 0] = days[i];
                settles[i, 0] = days[i] == 46189.0 ? 81.0 : days[i] == 46188.0 ? 80.0 : 70.0;
                settles[i, 1] = days[i] == 46189.0 ? 83.0 : days[i] == 46188.0 ? 82.0 : 72.0;
            }
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46190.0, 0.5), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, (string)Seam.Call("_CreateFuturesFixings", dates, settles, index));
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "ROLL", Column(81.5, 83.5)));
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "period", "onetime", "asian", "cleared", "financial", "CME Clearing", 46191.0, holidays));
            var headers = Row("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price", "nearby");
            var trades = (string)Seam.Call("_CreateTrades", index, headers, new object[,] { { 1.0, 46174.0, 46188.0, 46189.0, 1.0, 80.0, 1.0 }, { 2.0, 46174.0, 46188.0, 46189.0, 1.0, 80.0, 2.0 } }, template);
            Assert.StartsWith(Pid + ":trades:ROLL:", trades);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(4, spill.GetLength(0));
            Assert.Equal(spill.GetLength(1) - 1, Heading(spill, "nearby"));  // last, after settlement_frequency
            Assert.Equal("int64", spill[1, Heading(spill, "nearby")]);
            Assert.Equal(1.0, spill[2, Heading(spill, "nearby")]);
            Assert.Equal(2.0, spill[3, Heading(spill, "nearby")]);
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(6, slots.GetLength(0));  // two heading rows and four slots, a day and a contract each
            Assert.Equal("M26", slots[2, 0]);
            Assert.Equal("N26", slots[3, 0]);
            Assert.Equal(46188.0, slots[3, 2]);
            Assert.Equal("N26", slots[4, 0]);
            Assert.Equal("Q26", slots[5, 0]);
            Assert.Equal(46189.0, slots[5, 2]);
            var values = (object[,])Seam.Call("_ReportValues", (string)Seam.Call("_EvaluateTrades", prepared, market, ExcelMissing.Value));
            Assert.Equal(30000.0, (double)values[2, 0], 6);
            Assert.Equal(0.0, values[2, 1]);
            var second = (string)Seam.Call("_CreateTrades", index, headers, Row(2.0, 46174.0, 46188.0, 46189.0, 1.0, 80.0, 2.0), template);
            var alone = (object[,])Seam.Call("_ReportValues", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", second, history), market, ExcelMissing.Value));
            Assert.Equal(25000.0, (double)alone[2, 0], 6);  // 10,000 at the 82.5 average against 80
            Assert.Equal("#ERROR _CreateTrades: ValueError: trade 1 at row 1 observes 2026-06-16 at nearby 4, expected at most 3 that day, 'N26' being prompt and 'U26' the schedule's last contract; the schedule lists no contract for a later nearby", Seam.Call("_CreateTrades", index, headers, Row(1.0, 46174.0, 46188.0, 46189.0, 1.0, 80.0, 4.0), template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: nearby row 1 is 0, expected a whole number of 1 or more, of at most 15 digits: 1 the prompt contract, 2 the next the schedule lists", Seam.Call("_CreateTrades", index, headers, Row(1.0, 46174.0, 46188.0, 46189.0, 1.0, 80.0, 0.0), template));
            Assert.Equal("#ERROR _CreateTrades: trade_rows cell (1, 7) is text '2', expected number", Seam.Call("_CreateTrades", index, headers, Row(1.0, 46174.0, 46188.0, 46189.0, 1.0, 80.0, "2"), template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: nearby is missing, expected a value in the template or a column in the ticket", Seam.Call("_CreateTrades", index, Row("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price"), Row(1.0, 46174.0, 46188.0, 46189.0, 1.0, 80.0), template));
            var third = (string)Seam.Call("_CreateTrades", index, headers, Row(3.0, 46174.0, 46188.0, 46189.0, 1.0, 80.0, 3.0), template);
            Assert.StartsWith(Pid + ":trades:ROLL:", third);
            Assert.Equal("#ERROR _PrepareTrades: ValueError: requested fixing of 'Q26' on 2026-06-15 is the 3rd nearby's, 'M26' being prompt that day, beyond the 2 settles a day the history holds; expected fixings with a settle column for it", Seam.Call("_PrepareTrades", third, history));
            var quoteFields = Row("route", "settlement_method", "schedule_method", "quantity_per", "settlement_frequency", "payment_day", "payment_holiday_calendar", "nearby");
            var later = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", quoteFields, Row("cleared", "financial", "asian", "period", "onetime", 46191.0, holidays, 2.0));
            Assert.StartsWith(Pid + ":quote_template:", later);
            Assert.Equal(82.5, (double)Seam.Call("_QuoteByDates", market, 46188.0, 46189.0, later, "flat", ExcelMissing.Value), 12);
            var expiry = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", quoteFields, Row("cleared", "financial", "lastday", "month", "monthly", "+2bd", holidays, 2.0));
            Assert.Equal("#ERROR _Quote: ValueError: nearby of the quote is 2, expected 1 under schedule_method = lastday; the expiry-based methods take their own contract's days, and a later nearby is priced under asian", Seam.Call("_Quote", market, "N26", expiry, "flat", ExcelMissing.Value));
            var prompt = (string)Seam.Call("_CreateQuoteTemplate", "fixed_float", quoteFields, Row("cleared", "financial", "asian", "period", "onetime", 46191.0, holidays, 1.0));
            Assert.Equal(80.5, (double)Seam.Call("_QuoteByDates", market, 46188.0, 46189.0, prompt, "flat", ExcelMissing.Value), 12);
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
            var iferc = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46296.0, 46328.0, 46357.0));
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
            var iferc = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46296.0, 46328.0, 46357.0));
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
            var december = (string)Seam.Call("_CreateIfercFixings", Column("Z26", "X26", "V26"), Column(2.20, 2.10, 1.85), ifercIndex);
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
            var iferc = (string)Seam.Call("_CreateIfercSchedule", Column("V26", "X26", "Z26"), Column(46296.0, 46328.0, 46357.0));
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
            var published = (string)Seam.Call("_CreateMarketHistory", december, (string)Seam.Call("_CreateIfercFixings", Column("Z26", "X26", "V26"), Column(2.20, 2.10, 1.85), ifercIndex));
            Assert.Equal("#ERROR _CreateMarket: ValueError: market_history has no unfixed period, expected at least one to quote", Seam.Call("_CreateMarket", published, oneQuote));
        }

        // IFERC fixings: a column of contract codes, newest first, a column of indices and the
        // index of those months make one, two single cells make the fixings of one month, and
        // util_ReadHandle spills it back, the two headers, the text type over the number type,
        // then a row per month newest first as the creator took them, over a schedule that runs
        // the other way, the code as text and the index as a number; the spill's two columns
        // handed back to the creator make fixings that spill the same. With the index live, the
        // library's rules answer: a price column one row short, a code given twice, a code the
        // index does not hold, the months oldest first, and a futures index where the IFERC
        // index should be; a handle of another kind where the index should be fails in the seam's.
        [Fact]
        public void iferc_fixings_are_created_from_two_columns_and_an_index_and_read_back_through_their_handle()
        {
            var schedule = (string)Seam.Call("_CreateIfercSchedule", Column("F26", "G26", "H26", "J26"), Column(46027.0, 46055.0, 46083.0, 46113.0));
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
            Assert.Equal("#ERROR _CreateIfercFixings: ValueError: contract_code row 2 is 'G26', published 2026-02-02, expected a month published before row 1's 'F26', published 2026-01-05", Seam.Call("_CreateIfercFixings", Column("F26", "G26", "H26", "J26"), Column(1.85, 2.10, 1.95, 1.60), index));
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
            var iferc = Index(Seam.Call("_CreateIfercSchedule", "F26", 46027.0), ExcelMissing.Value, "Waha IFERC");
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
            var handle = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), anchors);
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
            var handle = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), Curve());
            Assert.StartsWith(Pid + ":discount_curve:SOFR:", handle);
            var spill = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(3, spill.GetLength(1));
            Assert.Equal("name", spill[0, 2]);
            Assert.Equal("SOFR", spill[3, 2]);
            Assert.Equal("date", spill[0, 0]);
            Assert.Equal("float64", spill[1, 1]);
            Assert.Equal(46277.0, spill[3, 0]);
            Assert.Equal(0.9999, spill[3, 1]);
            var swapped = new object[,] { { 1.0, 46276.0 }, { 0.9999, 46277.0 }, { 0.9998, 46278.0 } };
            var reversed = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("discount_factor", "date"), swapped);
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
        public void ping_says_which_catalyst_is_running()
        {
            Assert.Contains("catalyst", (string)Seam.Call("Ping"));
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

        // Calendar-driven asian references, calendar-driven-asian-references.md: the WTI-like index
        // of Z26, F27, G27 and H27 expiring 20 November, 21 December, 20 January and 22 February,
        // 46346, 46377, 46407 and 46440, closed on 25 December and New Year's Day, 46381 and 46388,
        // dollars a barrel settled in dollars, a barrel and a thousand-barrel LOT the specifications,
        // the LOT reported; the asian template paying +2bd on the same calendar; W, 1,200 barrels of
        // 18 to 28 December, 46374 to 46384, at 70. Six observations, the 18th and the 21st F27's and
        // the four from the 22nd G27's, booked as Z26 and paying 30 December, 46386: all live on the
        // 18th at 72 and 75 the mark is 4,800 and the delta 1.2 lots, 0.4 on F27 and 0.8 on G27; on
        // the 22nd, F27's days fixed at 71 and 73 and G27 quoted alone at 76, 5,600; on the 30th,
        // every day fixed and paid, 5,200 of cash. The settles run from 23 November, newest first.
        [Fact]
        public void a_december_asian_prices_off_the_calendars_contract_for_each_day()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("Z26", "F27", "G27", "H27"), Column(46346.0, 46377.0, 46407.0, 46440.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", Column(46381.0, 46388.0));
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "VOLUME", "BBL");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "BBL", 1.0, "BBL", 0.0, 0.0 }, { "LOT", 1000.0, "BBL", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "WTI", "West Texas Intermediate crude oil - NYMEX", schedule, conventions, specifications, holidays, "LOT");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("BBL", "month", "monthly", 1.0, "asian", "cleared", "financial", "Prototype Clearing", "+2bd", holidays));
            var headers = Row("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price");
            var trades = (string)Seam.Call("_CreateTrades", index, headers, new object[,] { { 23.0, 46346.0, 46374.0, 46384.0, 1200.0, 70.0 } }, template);
            double[] days = { 46385.0, 46384.0, 46380.0, 46379.0, 46378.0, 46377.0, 46374.0, 46373.0, 46372.0, 46371.0, 46370.0, 46367.0, 46366.0, 46365.0, 46364.0, 46363.0, 46360.0, 46359.0, 46358.0, 46357.0, 46356.0, 46353.0, 46352.0, 46351.0, 46350.0, 46349.0 };
            double[] settles = { 78.0, 77.0, 75.0, 76.0, 74.0, 73.0, 71.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0 };
            object[,] From(double[] values, int first)
            {
                var column = new object[values.Length - first, 1];
                for (var i = first; i < values.Length; i++) column[i - first, 0] = values[i];
                return column;
            }
            string History(double asOf, int first)
            {
                var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", asOf, 0.5), index);
                return (string)Seam.Call("_CreateMarketHistory", calendar, (string)Seam.Call("_CreateFuturesFixings", From(days, first), From(settles, first), index));
            }
            string Valued(string history, string prepared, params object[] quotes)
            {
                return (string)Seam.Call("_EvaluateTrades", prepared, (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "WTI", Column(quotes))), ExcelMissing.Value);
            }
            var eighteenth = History(46374.0, 7);
            var live = (string)Seam.Call("_PrepareTrades", trades, eighteenth);
            var slots = (object[,])Seam.Call("util_ReadHandle", live);
            Assert.Equal(8, slots.GetLength(0));
            Assert.Equal("pricing_contract", slots[0, 0]);
            Assert.Equal("booked_period", slots[0, 1]);
            Assert.Equal("F27", slots[2, 0]);
            Assert.Equal("Z26", slots[2, 1]);
            Assert.Equal("F27", slots[3, 0]);
            Assert.Equal("G27", slots[4, 0]);
            Assert.Equal("G27", slots[7, 0]);
            Assert.Equal("Z26", slots[7, 1]);
            Assert.Equal(46374.0, slots[2, 2]);
            Assert.Equal(46386.0, slots[2, 3]);
            Assert.Equal(200.0, (double)slots[2, 6], 6);
            Assert.Equal(0.2, (double)slots[2, 7], 6);
            var results = Valued(eighteenth, live, 72.0, 75.0);
            Assert.Equal(4800.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            var risk = (object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year");
            Assert.Equal(1.2, (double)risk[3, 1], 6);
            Assert.Equal("WTI nominal_delta [LOT]", risk[1, 1]);
            var contributions = (object[,])Seam.Call("util_ReadHandle", results);
            Assert.Equal("booked_period", contributions[0, 1]);
            Assert.Equal(0.4, (double)contributions[2, 10], 6);
            Assert.Equal(0.8, (double)contributions[4, 10], 6);
            Assert.Equal(0.4, (double)contributions[2, 11], 6);  // the discounted twin, cleared
            var rolled = History(46378.0, 5);
            var after = Valued(rolled, (string)Seam.Call("_PrepareTrades", trades, rolled), 76.0);
            Assert.Equal(5600.0, (double)((object[,])Seam.Call("_ReportValues", after))[2, 0], 6);
            Assert.Equal(0.8, (double)((object[,])Seam.Call("_ReportRisk", after, "nominal_delta", "year"))[3, 1], 6);
            var thirtieth = History(46386.0, 0);
            var paid = (object[,])Seam.Call("_ReportValues", Valued(thirtieth, (string)Seam.Call("_PrepareTrades", trades, thirtieth), 75.0));
            Assert.Equal(0.0, (double)paid[2, 0], 6);
            Assert.Equal(5200.0, (double)paid[2, 1], 6);
        }

        // Delta by day, month and year, daily-risk-vector.md: the month-aligned index of X26, Z26 and
        // F27 expiring 30 November, 31 December and 29 January, 46356, 46387 and 46416, closed on
        // 25 December and New Year's Day, dollars a barrel, a barrel and a thousand-barrel LOT, the LOT
        // reported; a template leaving the method to the rows, cleared and financial at +1bd; A, 22 LOT
        // of a December asian, and P, 3 LOT of a Z26 penultimate, both at 70, every settle and the
        // quote 75. On 1 December, 46357, every day live: the day view 22 rows, a lot each and 4 on
        // the 30th, 46386, the month view one row from 1 December of 25 and the year view one row from
        // 1 January 2026, 46023, of 25, the selector left out the day view; 125,000 of mark. On the
        // 31st, 46387, the 30th's row at zero and the 31st's at 1, the month at 1; 110,000 of mark and
        // 15,000 of cash. A bucket that is none of the three refused by name.
        [Fact]
        public void a_batch_reports_its_delta_by_day_month_and_year_from_the_same_results()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27"), Column(46356.0, 46387.0, 46416.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", Column(46381.0, 46388.0));
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "VOLUME", "BBL");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "BBL", 1.0, "BBL", 0.0, 0.0 }, { "LOT", 1000.0, "BBL", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "MONTHLY", "Month-aligned WTI-like index", schedule, conventions, specifications, holidays, "LOT");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("LOT", "month", "monthly", 1.0, "cleared", "financial", "Prototype Clearing", "+1bd", holidays));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "schedule_method");
            var trades = (string)Seam.Call("_CreateTrades", index, headers, new object[,] { { 1.0, 46346.0, "Z26", 22.0, 70.0, "asian" }, { 16.0, 46346.0, "Z26", 3.0, 70.0, "penultimate" } }, template);
            double[] days = { 46386.0, 46385.0, 46384.0, 46380.0, 46379.0, 46378.0, 46377.0, 46374.0, 46373.0, 46372.0, 46371.0, 46370.0, 46367.0, 46366.0, 46365.0, 46364.0, 46363.0, 46360.0, 46359.0, 46358.0, 46357.0, 46356.0 };
            object[,] From(int first)
            {
                var column = new object[days.Length - first, 1];
                for (var i = first; i < days.Length; i++) column[i - first, 0] = days[i];
                return column;
            }
            object[,] Settles(int first)
            {
                var column = new object[days.Length - first, 1];
                for (var i = first; i < days.Length; i++) column[i - first, 0] = 75.0;
                return column;
            }
            string Results(double asOf, int first)
            {
                var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", asOf, 0.5), index);
                var history = (string)Seam.Call("_CreateMarketHistory", calendar, (string)Seam.Call("_CreateFuturesFixings", From(first), Settles(first), index));
                var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "MONTHLY", Column(75.0)));
                return (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", trades, history), market, ExcelMissing.Value);
            }
            var first = Results(46357.0, 21);
            Assert.Equal(125000.0, (double)((object[,])Seam.Call("_ReportValues", first))[2, 0], 6);
            Assert.Equal(25.0, (double)((object[,])Seam.Call("_ReportRisk", first, "nominal_delta", "year"))[3, 1], 6);
            var byDay = (object[,])Seam.Call("_ReportRisk", first, "nominal_delta", "day");
            Assert.Equal(26, byDay.GetLength(0));
            Assert.Equal(2, byDay.GetLength(1));
            Assert.Equal("as_of", byDay[0, 0]);
            Assert.Equal(46357.0, byDay[0, 1]);
            Assert.Equal("period", byDay[1, 0]);
            Assert.Equal("MONTHLY nominal_delta [LOT]", byDay[1, 1]);
            Assert.Equal("str | datetime64[D]", byDay[2, 0]);
            Assert.Equal("float64", byDay[2, 1]);
            Assert.Equal("Total", byDay[3, 0]);
            Assert.Equal(25.0, (double)byDay[3, 1], 6);
            Assert.Equal(46357.0, byDay[4, 0]);
            Assert.Equal(1.0, (double)byDay[4, 1], 6);
            Assert.Equal(46386.0, byDay[24, 0]);
            Assert.Equal(4.0, (double)byDay[24, 1], 6);
            Assert.Equal(46387.0, byDay[25, 0]);
            Assert.Equal(1.0, (double)byDay[25, 1], 6);
            var delta = (object[,])Seam.Call("_ReportRisk", first, "delta", "day");
            Assert.Equal("MONTHLY delta [LOT]", delta[1, 1]);
            Assert.Equal(1.0, (double)delta[4, 1], 6);  // the discounted lots the nominal, cleared
            var everything = (object[,])Seam.Call("_ReportRisk", first, "all", "month");
            Assert.Equal(5, everything.GetLength(0));
            Assert.Equal(5, everything.GetLength(1));  // since #197
            Assert.Equal("MONTHLY cleared cross_gamma [LOT per basis point]", everything[1, 4]);
            Assert.Equal("cleared USD dv01 [USD per basis point]", everything[1, 3]);
            Assert.Equal(46357.0, everything[4, 0]);
            Assert.Equal(25.0, (double)everything[4, 1], 6);
            Assert.Equal(25.0, (double)everything[4, 2], 6);
            Assert.Equal(0.0, (double)everything[4, 3], 6);
            var byYear = (object[,])Seam.Call("_ReportRisk", first, "nominal_delta", "year");
            Assert.Equal(46023.0, byYear[4, 0]);
            Assert.Equal(25.0, (double)byYear[4, 1], 6);
            Assert.Equal("#ERROR _ReportRisk: ValueError: bucket is 'quarter', expected day, month or year", Seam.Call("_ReportRisk", first, "nominal_delta", "quarter"));
            Assert.Equal("#ERROR _ReportRisk: ValueError: risk is 'gamma', expected nominal_delta, delta, dv01, cross_gamma or all", Seam.Call("_ReportRisk", first, "gamma", "day"));
            Assert.Equal("#ERROR _ReportRisk: bucket is missing, expected text", Seam.Call("_ReportRisk", first, "delta", ExcelMissing.Value));
            var last = Results(46387.0, 0);
            var values = (object[,])Seam.Call("_ReportValues", last);
            Assert.Equal(110000.0, (double)values[2, 0], 6);
            Assert.Equal(15000.0, (double)values[2, 1], 6);
            var lastDays = (object[,])Seam.Call("_ReportRisk", last, "nominal_delta", "day");
            Assert.Equal(0.0, (double)lastDays[24, 1], 6);
            Assert.Equal(1.0, (double)lastDays[25, 1], 6);
            Assert.Equal(1.0, (double)((object[,])Seam.Call("_ReportRisk", last, "nominal_delta", "month"))[4, 1], 6);
        }

        // IFERC basis futures, iferc-basis-futures.md: the Waha-like index, X26, Z26 and F27
        // published 46328, 46357 and 46391, dollars an MMBtu, a 2,500 MMBtu LOT and a bare MMBTU, the
        // LOT reported, no pricing calendar; the payment calendar closing New Year's Day, 46388; the
        // template cleared, financial, lastday, LOT a month at +2bd from publication since
        // iferc-publication-payment-anchor.md; WAH001, 1 LOT of Z26 at -0.50 booked 46356, paying
        // 46359, read back in the batch. On 46357, the publication day, live at -0.30: 500 of mark, a lot, the slot Z26 on
        // 46357 paying 46359 with 2,500 of live coefficient, a tick to -0.25 625 on the same
        // preparation with the first results standing; on 46358 with the index at -0.20, 750 of
        // mark, fixed and unpaid, no lot; on 46359, 750 of cash. The delta by day one row, 46357, a
        // lot and then zero. A physical template refused by name.
        [Fact]
        public void an_iferc_basis_future_marks_fixes_and_pays_from_its_published_index()
        {
            var schedule = (string)Seam.Call("_CreateIfercSchedule", Column("X26", "Z26", "F27"), Column(46328.0, 46357.0, 46391.0));
            var pays = (string)Seam.Call("_CreateHolidayCalendar", Column(46388.0));
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "MMBTU", "USD", "ENERGY", "MMBTU");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "LOT", 2500.0, "MMBTU", 0.0, 0.0 }, { "MMBTU", 1.0, "MMBTU", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "WAHA", "Waha basis - ICE", schedule, conventions, specifications, ExcelMissing.Value, "LOT");
            Assert.StartsWith(Pid + ":index:WAHA:", index);
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("LOT", "month", "monthly", 1.0, "lastday", "cleared", "financial", "ICE Clear Europe", "+2bd", pays));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var row = new object[,] { { 1001.0, 46356.0, "Z26", 1.0, -0.5 } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, row, template);
            var batch = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal("payment_date", batch[0, 13]);
            Assert.Equal(46359.0, batch[2, 13]);
            Assert.Equal("lastday", batch[2, 4]);
            string History(double asOf, object[,] codes, object[,] indices)
            {
                var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", asOf, 0.5), index);
                return (string)Seam.Call("_CreateMarketHistory", calendar, (string)Seam.Call("_CreateIfercFixings", codes, indices, index));
            }
            string Valued(string history, string prepared, params object[] quotes)
            {
                return (string)Seam.Call("_EvaluateTrades", prepared, (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "WAHA", Column(quotes))), ExcelMissing.Value);
            }
            var live = History(46357.0, Column("X26"), Column(-0.4));
            var prepared = (string)Seam.Call("_PrepareTrades", trades, live);
            var slots = (object[,])Seam.Call("util_ReadHandle", prepared);
            Assert.Equal(3, slots.GetLength(0));
            Assert.Equal("Z26", slots[2, 0]);
            Assert.Equal("Z26", slots[2, 1]);
            Assert.Equal(46357.0, slots[2, 2]);
            Assert.Equal(46359.0, slots[2, 3]);
            Assert.False((bool)slots[2, 4]);
            Assert.Equal(2500.0, (double)slots[2, 6], 6);
            Assert.Equal(1.0, (double)slots[2, 7], 6);
            var first = Valued(live, prepared, -0.3, -0.1);
            var values = (object[,])Seam.Call("_ReportValues", first);
            Assert.Equal(500.0, (double)values[2, 0], 6);
            Assert.Equal(0.0, (double)values[2, 1], 6);
            var risk = (object[,])Seam.Call("_ReportRisk", first, "nominal_delta", "year");
            Assert.Equal(1.0, (double)risk[3, 1], 6);
            Assert.Equal("WAHA nominal_delta [LOT]", risk[1, 1]);
            var byDay = (object[,])Seam.Call("_ReportRisk", first, "nominal_delta", "day");
            Assert.Equal(5, byDay.GetLength(0));
            Assert.Equal(46357.0, byDay[4, 0]);
            Assert.Equal(1.0, (double)byDay[4, 1], 6);
            var ticked = Valued(live, prepared, -0.25, -0.1);
            Assert.Equal(625.0, (double)((object[,])Seam.Call("_ReportValues", ticked))[2, 0], 6);
            Assert.Equal(500.0, (double)((object[,])Seam.Call("_ReportValues", first))[2, 0], 6);
            var printed = History(46358.0, Column("Z26", "X26"), Column(-0.2, -0.4));
            var fixedPrepared = (string)Seam.Call("_PrepareTrades", trades, printed);
            var fixedSlots = (object[,])Seam.Call("util_ReadHandle", fixedPrepared);
            Assert.True((bool)fixedSlots[2, 4]);
            Assert.False((bool)fixedSlots[2, 5]);
            var unpaid = Valued(printed, fixedPrepared, -0.1);
            var unpaidValues = (object[,])Seam.Call("_ReportValues", unpaid);
            Assert.Equal(750.0, (double)unpaidValues[2, 0], 6);
            Assert.Equal(0.0, (double)unpaidValues[2, 1], 6);
            Assert.Equal(0.0, (double)((object[,])Seam.Call("_ReportRisk", unpaid, "nominal_delta", "year"))[3, 1], 6);
            Assert.Equal(0.0, (double)((object[,])Seam.Call("_ReportRisk", unpaid, "nominal_delta", "day"))[4, 1], 6);
            var paidHistory = History(46359.0, Column("Z26", "X26"), Column(-0.2, -0.4));
            var paid = (object[,])Seam.Call("_ReportValues", Valued(paidHistory, (string)Seam.Call("_PrepareTrades", trades, paidHistory), -0.1));
            Assert.Equal(0.0, (double)paid[2, 0], 6);
            Assert.Equal(750.0, (double)paid[2, 1], 6);
            var physical = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house"), Row("LOT", "month", "monthly", 1.0, "lastday", "cleared", "physical", "ICE Clear Europe"));
            Assert.Equal("#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' on an IFERC index; an IFERC basis future is cash settled on its month's published index", Seam.Call("_CreateTrades", index, headers, row, physical));
        }

        // Reserve totals, reserve-totals.md: the worked example on the ethane schedule, X26, Z26, F27
        // and G27 expiring 46356, 46387, 46416 and 46444, closed 46381 and 46388, dollars a gallon,
        // LOT a thousand barrels at 10 and 4 a lot, BBL a barrel at 0.01 and 0.004, GAL free; 101 to
        // 104 booked 46346, 2 LOT, -2 LOT, 1,000 BBL and 0 LOT of Z26 at 0.25, financial at +2bd on a
        // calendar closed 46388, brokered by ION since #188. On 46358 at 0.28: 1,260 of mark, a lot, and 50 of brokerage, 20 of
        // clearing and none of marketing in USD, the report's one row and the results readback's
        // first, the batch's readback without a reserve column; a tick to 0.31 marks 2,520 and
        // reserves the same. A rate of 1e308 a lot: two lots refused by row, one lot each of two rows
        // refused for the batch, nothing published.
        [Fact]
        public void a_batch_books_its_reserves_once_and_its_results_report_them_unchanged()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27", "G27"), Column(46356.0, 46387.0, 46416.0, 46444.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", Column(46381.0, 46388.0));
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "GAL", "USD", "VOLUME", "GAL");
            var headings = Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", headings, new object[,] { { "LOT", 1000.0, "BBL", 10.0, 4.0 }, { "BBL", 1.0, "BBL", 0.01, 0.004 }, { "GAL", 1.0, "GAL", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "RESERVES", "Ethane with the reserve ticket rates", schedule, conventions, specifications, holidays, "LOT");
            var pays = (string)Seam.Call("_CreateHolidayCalendar", Column(46388.0));
            // Since #188, reserve-fee-applicability.md, the template names ION as broker: brokerage charges the rows
            // naming a broker and clearing the cleared route, so the 50 below stands and the readback gains a column.
            var fields = Row("quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "broker", "payment_day", "payment_holiday_calendar");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("month", "monthly", 1.0, "lastday", "cleared", "financial", "Prototype Clearing", "ION", "+2bd", pays));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "quantity_unit", "fixed_price");
            var rows = new object[,] { { 101.0, 46346.0, "Z26", 2.0, "LOT", 0.25 }, { 102.0, 46346.0, "Z26", -2.0, "LOT", 0.25 }, { 103.0, 46346.0, "Z26", 1000.0, "BBL", 0.25 }, { 104.0, 46346.0, "Z26", 0.0, "LOT", 0.25 } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            Assert.StartsWith(Pid + ":trades:RESERVES:", trades);
            var batch = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(25, batch.GetLength(1));
            Assert.Equal("broker", batch[0, 8]);
            Assert.Equal("ION", batch[2, 8]);
            Assert.Equal("offset", batch[0, 22]);
            // Since #181, compound-date-offsets.md: a payment rule of several instructions reads as the date
            // utility's offset does and is kept as written beside the day it made: Z26's 31 December 2026 to its
            // month's end, the same day, and the business day after, past New Year's Day closed, Monday 4 January.
            var chained = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("month", "monthly", 1.0, "lastday", "cleared", "financial", "Prototype Clearing", "ION", "+0em+1bd", pays));
            var ruled = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateTrades", index, headers, rows, chained));
            Assert.Equal("payment_day", ruled[0, 13]);
            Assert.Equal("payment_date", ruled[0, 14]);
            Assert.Equal("+0em+1bd", ruled[2, 13]);
            Assert.Equal(46391.0, ruled[2, 14]);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46358.0, 0.5), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, (string)Seam.Call("_CreateFuturesFixings", Column(46357.0, 46356.0), Column(0.24, 0.28), index));
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            string Valued(params object[] quotes)
            {
                return (string)Seam.Call("_EvaluateTrades", prepared, (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "RESERVES", Column(quotes))), ExcelMissing.Value);
            }
            var results = Valued(0.28, 0.30, 0.32);
            Assert.Equal(1260.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            Assert.Equal(1.0, (double)((object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year"))[3, 1], 6);
            var reserves = (object[,])Seam.Call("_ReportReserves", results);
            Assert.Equal(3, reserves.GetLength(0));
            Assert.Equal(5, reserves.GetLength(1));  // since cva-reserve.md the signed CVA before the currency
            Assert.Equal("brokerage_reserve", reserves[0, 0]);
            Assert.Equal("cva_reserve", reserves[0, 3]);  // signed, since cva-reserve.md
            Assert.Equal("currency", reserves[0, 4]);
            Assert.Equal("float64", reserves[1, 0]);
            Assert.Equal("str", reserves[1, 4]);
            Assert.Equal(50.0, (double)reserves[2, 0], 9);
            Assert.Equal(20.0, (double)reserves[2, 1], 9);
            Assert.Equal(0.0, (double)reserves[2, 2], 9);
            Assert.Equal("USD", reserves[2, 4]);
            Assert.Equal(0.0, (double)reserves[2, 3], 9);
            var table = (object[,])Seam.Call("util_ReadHandle", results);
            Assert.Equal(3, table.GetLength(0));
            Assert.Equal(31, table.GetLength(1));  // since #197 the two cross-gamma columns, since slice 3 the key and the curve, since observation-prices-readback.md the four price columns, last, since cva-reserve.md the CVA reserve among the reserves
            Assert.Equal("brokerage_reserve", table[0, 18]);
            Assert.Equal("currency", table[0, 22]);
            Assert.Equal(50.0, (double)table[2, 18], 9);
            Assert.Equal(20.0, (double)table[2, 19], 9);
            Assert.Equal("USD", table[2, 22]);
            var ticked = Valued(0.31, 0.30, 0.32);
            Assert.Equal(2520.0, (double)((object[,])Seam.Call("_ReportValues", ticked))[2, 0], 6);
            var again = (object[,])Seam.Call("_ReportReserves", ticked);
            Assert.Equal(50.0, (double)again[2, 0], 9);
            Assert.Equal(20.0, (double)again[2, 1], 9);
            var dear = (string)Seam.Call("_CreateContractSpecifications", headings, new object[,] { { "LOT", 1000.0, "BBL", 1e308, 0.0 } });
            var huge = (string)Seam.Call("_CreateIndex", "HUGE", "A rate a cell holds that two lots outrun", schedule, conventions, dear, holidays, "LOT");
            Assert.Equal("#ERROR _CreateTrades: ValueError: brokerage reserve of trade 101 at row 1 is inf, expected a finite amount of USD; 2.0 of 'LOT' at 1e+308 a lot", Seam.Call("_CreateTrades", huge, headers, new object[,] { { 101.0, 46346.0, "Z26", 2.0, "LOT", 0.25 } }, template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: the batch has inf of brokerage reserve in all, expected a finite amount of USD; the components' reserves, each finite, sum past the largest number", Seam.Call("_CreateTrades", huge, headers, new object[,] { { 101.0, 46346.0, "Z26", 1.0, "LOT", 0.25 }, { 102.0, 46346.0, "Z26", 1.0, "LOT", 0.25 } }, template));
            // Since #175, booking-fields-and-marketing-reserve.md: a marketing column books 15, 20, 25 and 5
            // once per row, 65, the strip Z26-F27 showing its one amount on both components, over 60 and
            // 24; a template's 7 books 28 on the four plain rows, the mark and the lot as without; a
            // bilateral template names its counterparty, kept per row, its batch made and prepared and
            // refused at evaluation as before; the conditions and the rule refuse the rest.
            var marketedHeaders = Row("trade_id", "trade_date", "contract_code", "quantity", "quantity_unit", "fixed_price", "marketing_reserve");
            var marketedRows = new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, 15.0 }, { 1002.0, 46346.0, "Z26", -2.0, "LOT", 0.25, 20.0 }, { 1003.0, 46346.0, "Z26-F27", 1.0, "LOT", 0.25, 25.0 }, { 1004.0, 46346.0, "Z26", 0.0, "LOT", 0.25, 5.0 } };
            var marketed = (string)Seam.Call("_CreateTrades", index, marketedHeaders, marketedRows, template);
            var marketedTable = (object[,])Seam.Call("util_ReadHandle", marketed);
            Assert.Equal(26, marketedTable.GetLength(1));  // a cleared batch names no curve
            Assert.Equal("marketing_reserve", marketedTable[0, 15]);
            Assert.Equal("entered_contract_code", marketedTable[0, 16]);
            Assert.Equal(15.0, (double)marketedTable[2, 15], 9);
            Assert.Equal(25.0, (double)marketedTable[4, 15], 9);
            Assert.Equal(25.0, (double)marketedTable[5, 15], 9);
            Assert.Equal("F27", marketedTable[5, 3]);
            Assert.Equal(5.0, (double)marketedTable[6, 15], 9);
            string Market() => (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "RESERVES", Column(0.28, 0.30, 0.32)));
            var marketedReserves = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", marketed, history), Market(), ExcelMissing.Value));
            Assert.Equal(60.0, (double)marketedReserves[2, 0], 9);
            Assert.Equal(24.0, (double)marketedReserves[2, 1], 9);
            Assert.Equal(65.0, (double)marketedReserves[2, 2], 9);
            Assert.Equal("USD", marketedReserves[2, 4]);
            Assert.Equal(0.0, (double)marketedReserves[2, 3], 9);
            Assert.Equal("#ERROR _CreateTrades: ValueError: marketing_reserve row 2 is -5.0, expected a finite amount of zero or more", Seam.Call("_CreateTrades", index, marketedHeaders, new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, 15.0 }, { 1002.0, 46346.0, "Z26", -2.0, "LOT", 0.25, -5.0 } }, template));
            var seven = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "broker", "payment_day", "payment_holiday_calendar", "marketing_reserve"), Row("month", "monthly", 1.0, "lastday", "cleared", "financial", "Prototype Clearing", "ION", "+2bd", pays, 7.0));
            var templated = (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", (string)Seam.Call("_CreateTrades", index, headers, rows, seven), history), Market(), ExcelMissing.Value);
            var templatedReserves = (object[,])Seam.Call("_ReportReserves", templated);
            Assert.Equal(50.0, (double)templatedReserves[2, 0], 9);
            Assert.Equal(28.0, (double)templatedReserves[2, 2], 9);
            Assert.Equal(1260.0, (double)((object[,])Seam.Call("_ReportValues", templated))[2, 0], 6);
            Assert.Equal(1.0, (double)((object[,])Seam.Call("_ReportRisk", templated, "nominal_delta", "year"))[3, 1], 6);
            // Since #188, reserve-fee-applicability.md: the same rows under a cleared template naming no broker book no
            // brokerage and the same 20 of clearing; a broker column mixing ION and None, none and NONE charges the
            // ION row alone, 20, every text read back as typed; a broker from both the template and the ticket is refused.
            var direct = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar"), Row("month", "monthly", 1.0, "lastday", "cleared", "financial", "Prototype Clearing", "+2bd", pays));
            var directReserves = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", (string)Seam.Call("_CreateTrades", index, headers, rows, direct), history), Market(), ExcelMissing.Value));
            Assert.Equal(0.0, (double)directReserves[2, 0], 9);
            Assert.Equal(20.0, (double)directReserves[2, 1], 9);
            var brokeredHeaders = Row("trade_id", "trade_date", "contract_code", "quantity", "quantity_unit", "fixed_price", "broker");
            var brokeredRows = new object[,] { { 101.0, 46346.0, "Z26", 2.0, "LOT", 0.25, "ION" }, { 102.0, 46346.0, "Z26", -2.0, "LOT", 0.25, "None" }, { 103.0, 46346.0, "Z26", 1000.0, "BBL", 0.25, "none" }, { 104.0, 46346.0, "Z26", 0.0, "LOT", 0.25, "NONE" } };
            var mixed = (string)Seam.Call("_CreateTrades", index, brokeredHeaders, brokeredRows, direct);
            var mixedReserves = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", mixed, history), Market(), ExcelMissing.Value));
            Assert.Equal(20.0, (double)mixedReserves[2, 0], 9);
            Assert.Equal(20.0, (double)mixedReserves[2, 1], 9);
            var mixedTable = (object[,])Seam.Call("util_ReadHandle", mixed);
            Assert.Equal("broker", mixedTable[0, 8]);
            Assert.Equal("None", mixedTable[3, 8]);
            Assert.Equal("NONE", mixedTable[5, 8]);
            Assert.Equal("#ERROR _CreateTrades: ValueError: broker is supplied by the template and by the ticket, expected by one of them", Seam.Call("_CreateTrades", index, brokeredHeaders, brokeredRows, template));
            Assert.Equal("#ERROR _CreateTradeTemplate: ValueError: marketing_reserve is -5.0, expected a finite amount of zero or more", Seam.Call("_CreateTradeTemplate", "fixed_float", Row("marketing_reserve"), -5.0));
            Assert.Equal("#ERROR _CreateTrades: ValueError: marketing_reserve is supplied by the template and by the ticket, expected by one of them", Seam.Call("_CreateTrades", index, marketedHeaders, marketedRows, seven));
            // cva-reserve.md: a signed CVA column, 25 on 2 LOT of Z26, -40 on -2 LOT of the strip Z26-F27 and 0 on
            // 0 LOT, books -15 once per row over 60 and 24, the strip's two components each showing its one amount,
            // the fourth column of the report before the currency; both reserve columns side by side, 65 and -10; a
            // template's -40 books -160 on the four plain rows, the mark as without; the field from both and a total
            // past the largest number in either direction refused; a pair books the amount once, in its own fact.
            var cvaHeaders = Row("trade_id", "trade_date", "contract_code", "quantity", "quantity_unit", "fixed_price", "cva_reserve");
            var cvaRows = new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, 25.0 }, { 1002.0, 46346.0, "Z26-F27", -2.0, "LOT", 0.25, -40.0 }, { 1003.0, 46346.0, "Z26", 0.0, "LOT", 0.25, 0.0 } };
            var cva = (string)Seam.Call("_CreateTrades", index, cvaHeaders, cvaRows, template);
            var cvaTable = (object[,])Seam.Call("util_ReadHandle", cva);
            Assert.Equal(26, cvaTable.GetLength(1));
            Assert.Equal("cva_reserve", cvaTable[0, 15]);
            Assert.Equal("entered_contract_code", cvaTable[0, 16]);
            Assert.Equal(25.0, (double)cvaTable[2, 15], 9);
            Assert.Equal(-40.0, (double)cvaTable[3, 15], 9);
            Assert.Equal(-40.0, (double)cvaTable[4, 15], 9);
            Assert.Equal("F27", cvaTable[4, 3]);
            var cvaReserves = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", cva, history), Market(), ExcelMissing.Value));
            Assert.Equal(60.0, (double)cvaReserves[2, 0], 9);
            Assert.Equal(24.0, (double)cvaReserves[2, 1], 9);
            Assert.Equal(0.0, (double)cvaReserves[2, 2], 9);
            Assert.Equal(-15.0, (double)cvaReserves[2, 3], 9);
            Assert.Equal("USD", cvaReserves[2, 4]);
            var bothHeaders = Row("trade_id", "trade_date", "contract_code", "quantity", "quantity_unit", "fixed_price", "marketing_reserve", "cva_reserve");
            var bothRows = new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, 15.0, 25.0 }, { 1002.0, 46346.0, "Z26", -2.0, "LOT", 0.25, 20.0, -40.0 }, { 1003.0, 46346.0, "Z26-F27", 1.0, "LOT", 0.25, 25.0, 0.0 }, { 1004.0, 46346.0, "Z26", 0.0, "LOT", 0.25, 5.0, 5.0 } };
            var both = (string)Seam.Call("_CreateTrades", index, bothHeaders, bothRows, template);
            var bothTable = (object[,])Seam.Call("util_ReadHandle", both);
            Assert.Equal("marketing_reserve", bothTable[0, 15]);
            Assert.Equal("cva_reserve", bothTable[0, 16]);
            var bothReserves = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", both, history), Market(), ExcelMissing.Value));
            Assert.Equal(65.0, (double)bothReserves[2, 2], 9);
            Assert.Equal(-10.0, (double)bothReserves[2, 3], 9);
            var forty = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house", "broker", "payment_day", "payment_holiday_calendar", "cva_reserve"), Row("month", "monthly", 1.0, "lastday", "cleared", "financial", "Prototype Clearing", "ION", "+2bd", pays, -40.0));
            var fortyResults = (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", (string)Seam.Call("_CreateTrades", index, headers, rows, forty), history), Market(), ExcelMissing.Value);
            var fortyReserves = (object[,])Seam.Call("_ReportReserves", fortyResults);
            Assert.Equal(50.0, (double)fortyReserves[2, 0], 9);
            Assert.Equal(0.0, (double)fortyReserves[2, 2], 9);
            Assert.Equal(-160.0, (double)fortyReserves[2, 3], 9);
            Assert.Equal(1260.0, (double)((object[,])Seam.Call("_ReportValues", fortyResults))[2, 0], 6);
            Assert.Equal(-40.0, (double)((object[,])Seam.Call("util_ReadHandle", forty))[2, Heading((object[,])Seam.Call("util_ReadHandle", forty), "cva_reserve")], 9);
            Assert.Equal("#ERROR _CreateTrades: ValueError: cva_reserve is supplied by the template and by the ticket, expected by one of them", Seam.Call("_CreateTrades", index, cvaHeaders, cvaRows, forty));
            Assert.Equal("#ERROR _CreateTrades: ValueError: the batch has inf of cva reserve in all, expected a finite amount of USD; the rows' amounts, each finite, sum past the largest number", Seam.Call("_CreateTrades", index, cvaHeaders, new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, 9e307 }, { 1002.0, 46346.0, "Z26", -2.0, "LOT", 0.25, 9e307 } }, template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: the batch has -inf of cva reserve in all, expected a finite amount of USD; the rows' amounts, each finite, sum past the largest number", Seam.Call("_CreateTrades", index, cvaHeaders, new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, -9e307 }, { 1002.0, 46346.0, "Z26", -2.0, "LOT", 0.25, -9e307 } }, template));
            // cva-reserve.md's review: a dollar beside ten thousand trillion and its negative is a dollar in any
            // order, the exact total; amounts cancelling past the largest number net to nothing and are not refused.
            foreach (var amounts in new[] { new[] { 1e16, 1.0, -1e16 }, new[] { 1e16, -1e16, 1.0 }, new[] { 1.0, 1e16, -1e16 } })
            {
                var ordered = new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, amounts[0] }, { 1002.0, 46346.0, "Z26-F27", -2.0, "LOT", 0.25, amounts[1] }, { 1003.0, 46346.0, "Z26", 0.0, "LOT", 0.25, amounts[2] } };
                var orderedReserves = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", (string)Seam.Call("_CreateTrades", index, cvaHeaders, ordered, template), history), Market(), ExcelMissing.Value));
                Assert.Equal(1.0, (double)orderedReserves[2, 3], 12);
            }
            var cancelling = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", (string)Seam.Call("_CreateTrades", index, cvaHeaders, new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, 9e307 }, { 1002.0, 46346.0, "Z26", -2.0, "LOT", 0.25, 9e307 }, { 1003.0, 46346.0, "Z26", 2.0, "LOT", 0.25, -9e307 }, { 1004.0, 46346.0, "Z26", -2.0, "LOT", 0.25, -9e307 } }, template), history), Market(), ExcelMissing.Value));
            Assert.Equal(0.0, (double)cancelling[2, 3], 12);
            // and a tiny amount keeps every bit beside zero rows, 3e-308 to the last bit.
            var tiny = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", (string)Seam.Call("_CreateTrades", index, cvaHeaders, new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, 3e-308 }, { 1002.0, 46346.0, "Z26", -2.0, "LOT", 0.25, 0.0 }, { 1003.0, 46346.0, "Z26", 0.0, "LOT", 0.25, 0.0 } }, template), history), Market(), ExcelMissing.Value));
            Assert.Equal(3e-308, (double)tiny[2, 3]);
            // and past the largest number on the way, 9e307 twice and -9e307 twice beside 3e-308, with five rows and nine.
            foreach (var zeros in new[] { 0, 4 })
            {
                var past = new object[5 + zeros, 7];
                var amounts = new[] { 9e307, 9e307, -9e307, -9e307, 3e-308, 0.0, 0.0, 0.0, 0.0 };
                for (var r = 0; r < 5 + zeros; r++) { past[r, 0] = 1001.0 + r; past[r, 1] = 46346.0; past[r, 2] = "Z26"; past[r, 3] = 2.0; past[r, 4] = "LOT"; past[r, 5] = 0.25; past[r, 6] = amounts[r]; }
                var pastReserves = (object[,])Seam.Call("_ReportReserves", (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", (string)Seam.Call("_CreateTrades", index, cvaHeaders, past, template), history), Market(), ExcelMissing.Value));
                Assert.Equal(3e-308, (double)pastReserves[2, 3]);
            }
            var bilateral = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "counterparty", "discount_curve_key", "payment_day", "payment_holiday_calendar"), Row("month", "monthly", 1.0, "lastday", "bilateral", "financial", "ACME Trading", "SOFR", "+2bd", pays));
            var faced = (string)Seam.Call("_CreateTrades", index, headers, rows, bilateral);
            var facedTable = (object[,])Seam.Call("util_ReadHandle", faced);
            Assert.Equal(25, facedTable.GetLength(1));
            Assert.Equal("counterparty", facedTable[0, 7]);
            Assert.Equal("ACME Trading", facedTable[2, 7]);
            Assert.Equal("discount_curve_key", facedTable[0, 8]);  // after the counterparty, since named-curves-slice-3.md
            Assert.Equal("SOFR", facedTable[2, 8]);
            Assert.Equal("#ERROR _EvaluateTrades: ValueError: discount_curve_set is missing, expected a collection of discount curves with a bilateral batch, whose payments it discounts", Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", faced, history), Market(), ExcelMissing.Value));
            // Since #197, single-curve-cross-gamma.md: the faced batch valued on a curve of 0.99 on its payment day, two business days past its 31 December expiry with New Year's Day closed,
            // 5 January 2027, 34 days out: a lot of Z26 net, 0.99 discounted, and -0.0001 times 33 over 365 times 0.99
            // of cross-gamma on the contract's 2026 under the curve's label; all four five wide; the readback's
            // last two columns the contract's cross-gamma on every row and its unit.
            var facedCurve = (string)Seam.Call("_CreateDiscountCurve", "SOFR", Row("date", "discount_factor"), new object[,] { { 46358.0, 1.0 }, { 46392.0, 0.99 } });
            var facedCurves = (string)Seam.Call("_CollectDiscountCurves", facedCurve);  // the collection of one the evaluation takes since named-curves-slice-3.md
            Assert.Equal("#ERROR _EvaluateTrades: discount_curve_set is discount curve handle '" + facedCurve + "', expected discount curve set handle", Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", faced, history), Market(), facedCurve));
            var facedResults = (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", faced, history), Market(), facedCurves);
            var facedCross = (object[,])Seam.Call("_ReportRisk", facedResults, "cross_gamma", "year");
            Assert.Equal(5, facedCross.GetLength(0));
            Assert.Equal("RESERVES SOFR cross_gamma [LOT per basis point]", facedCross[1, 1]);
            Assert.Equal(-0.0001 * 34 / 365 * 0.99, (double)facedCross[3, 1], 12);
            Assert.Equal(46023.0, facedCross[4, 0]);
            Assert.Equal(-0.0001 * 34 / 365 * 0.99, (double)facedCross[4, 1], 12);
            var facedAll = (object[,])Seam.Call("_ReportRisk", facedResults, "all", "month");
            Assert.Equal(5, facedAll.GetLength(1));
            Assert.Equal("RESERVES SOFR cross_gamma [LOT per basis point]", facedAll[1, 4]);
            Assert.Equal(0.99, (double)facedAll[3, 2], 12);
            var facedReadback = (object[,])Seam.Call("util_ReadHandle", facedResults);
            Assert.Equal(31, facedReadback.GetLength(1));
            Assert.Equal("contract_cross_gamma", facedReadback[0, 23]);
            Assert.Equal(-0.0001 * 34 / 365 * 0.99, (double)facedReadback[2, 23], 12);
            Assert.Equal("lots of LOT (1000 BBL) per basis point", facedReadback[2, 24]);
            Assert.Equal("discount_curve_key", facedReadback[0, 25]);  // the key and the curve, last, since named-curves-slice-3.md
            Assert.Equal("SOFR", facedReadback[2, 25]);
            Assert.Equal("discount_curve", facedReadback[0, 26]);
            Assert.Equal("SOFR", facedReadback[2, 26]);
            Assert.Equal("observation_coefficient", facedReadback[0, 27]);  // observation-prices-readback.md: the four price columns, last
            Assert.Equal("floating_contribution", facedReadback[0, 30]);
            // Since named-curves-slice-3.md: two rows naming their curves on the ticket, two lots of Z26 on SOFR and one
            // short on FFOIS, 0.99 and 0.98 on the payment day, 34 days out: 2,520 and -1,260 of amount, 1,260 of mark,
            // one lot net and 1.98 less 0.98 discounted, each curve's DV01 and cross-gamma in its own column in key
            // order, the readback naming the key and the curve on each row, the collection's curve cell both names,
            // and a collection missing a key refused with the key, the row and the names it holds.
            var keyedHeaders = Row("trade_id", "trade_date", "contract_code", "quantity", "quantity_unit", "fixed_price", "discount_curve_key");
            var keyedRows = new object[,] { { 101.0, 46346.0, "Z26", 2.0, "LOT", 0.25, "SOFR" }, { 102.0, 46346.0, "Z26", -1.0, "LOT", 0.25, "FFOIS" } };
            var unkeyed = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "counterparty", "payment_day", "payment_holiday_calendar"), Row("month", "monthly", 1.0, "lastday", "bilateral", "financial", "ACME Trading", "+2bd", pays));
            var keyed = (string)Seam.Call("_CreateTrades", index, keyedHeaders, keyedRows, unkeyed);
            var keyedTable = (object[,])Seam.Call("util_ReadHandle", keyed);
            Assert.Equal("discount_curve_key", keyedTable[0, 8]);
            Assert.Equal("SOFR", keyedTable[2, 8]);
            Assert.Equal("FFOIS", keyedTable[3, 8]);
            var ffoisCurve = (string)Seam.Call("_CreateDiscountCurve", "FFOIS", Row("date", "discount_factor"), new object[,] { { 46358.0, 1.0 }, { 46392.0, 0.98 } });
            var bothCurves = (string)Seam.Call("_CollectDiscountCurves", Column(facedCurve, ffoisCurve));
            var keyedPrepared = (string)Seam.Call("_PrepareTrades", keyed, history);
            Assert.Equal("#ERROR _EvaluateTrades: ValueError: discount_curve_key 'FFOIS' of trade 102 at row 2 names no curve of the collection, which holds SOFR; expected a curve of that name", Seam.Call("_EvaluateTrades", keyedPrepared, Market(), facedCurves));
            var keyedResults = (string)Seam.Call("_EvaluateTrades", keyedPrepared, Market(), bothCurves);
            Assert.Equal(1260.0, (double)((object[,])Seam.Call("_ReportValues", keyedResults))[2, 0], 9);
            var perDay = 0.0001 * 34 / 365;
            var keyedDv01 = (object[,])Seam.Call("_ReportRisk", keyedResults, "dv01", "day");
            Assert.Equal(3, keyedDv01.GetLength(1));
            Assert.Equal("SOFR USD dv01 [USD per basis point]", keyedDv01[1, 1]);
            Assert.Equal("FFOIS USD dv01 [USD per basis point]", keyedDv01[1, 2]);
            Assert.Equal(-perDay * 2520.0 * 0.99, (double)keyedDv01[3, 1], 12);
            Assert.Equal(perDay * 1260.0 * 0.98, (double)keyedDv01[3, 2], 12);
            var keyedAll = (object[,])Seam.Call("_ReportRisk", keyedResults, "all", "month");
            Assert.Equal(7, keyedAll.GetLength(1));
            Assert.Equal("RESERVES SOFR cross_gamma [LOT per basis point]", keyedAll[1, 5]);
            Assert.Equal("RESERVES FFOIS cross_gamma [LOT per basis point]", keyedAll[1, 6]);
            Assert.Equal(1.0, (double)keyedAll[3, 1], 12);
            Assert.Equal(2.0 * 0.99 - 0.98, (double)keyedAll[3, 2], 12);
            Assert.Equal(-perDay * 2.0 * 0.99, (double)keyedAll[3, 5], 12);
            Assert.Equal(perDay * 0.98, (double)keyedAll[3, 6], 12);
            var keyedReadback = (object[,])Seam.Call("util_ReadHandle", keyedResults);
            Assert.Equal(4, keyedReadback.GetLength(0));
            Assert.Equal("SOFR", keyedReadback[2, 25]);
            Assert.Equal("FFOIS", keyedReadback[3, 25]);
            Assert.Equal("SOFR", keyedReadback[2, 26]);
            Assert.Equal("FFOIS", keyedReadback[3, 26]);
            var keyedCollection = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_AggregateResults", keyedResults));
            Assert.Equal("SOFR, FFOIS", keyedCollection[2, 4]);
            var facedHeaders = Row("trade_id", "trade_date", "contract_code", "quantity", "quantity_unit", "fixed_price", "counterparty");
            var facedRows = new object[,] { { 1001.0, 46346.0, "Z26", 2.0, "LOT", 0.25, "ACME Trading" }, { 1002.0, 46346.0, "Z26", -2.0, "LOT", 0.25, "Beta Energy" } };
            var unfaced = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "discount_curve_key", "payment_day", "payment_holiday_calendar"), Row("month", "monthly", 1.0, "lastday", "bilateral", "financial", "SOFR", "+2bd", pays));
            var byRow = (object[,])Seam.Call("util_ReadHandle", (string)Seam.Call("_CreateTrades", index, facedHeaders, facedRows, unfaced));
            Assert.Equal("ACME Trading", byRow[2, 7]);
            Assert.Equal("Beta Energy", byRow[3, 7]);
            Assert.Equal("#ERROR _CreateTrades: ValueError: counterparty is 'ACME Trading', expected none unless route = bilateral", Seam.Call("_CreateTrades", index, facedHeaders, facedRows, template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: counterparty is missing, expected it when route = bilateral", Seam.Call("_CreateTrades", index, headers, rows, unfaced));
        }

        // Contract codes and dates on one ticket, contract-codes-and-dates.md: the synthetic index
        // BBL_ASIAN, USD per BBL, U26, V26, X26 and Z26 expiring 46294, 46325, 46356 and 46387, so
        // that V26 prices every October pricing day, a calendar closed on 1 January 2030 alone,
        // 47484, a BBL of one barrel and a LOT of 1,000, the reporting lot; an asian template paying
        // +1bd on the same calendar, the basis left to the ticket; three rows struck on 15 September,
        // 46280, at 70: V26 with empty dates, 100 BBL a month, the whole of October; V26 beside 12 to
        // 31 October, 46307 to 46326, the dates winning; no code and 12 to 20 October, 46315, at 10
        // BBL a calendar day, 90 BBL. Read back with the entered code apart from the resolved
        // contract, `(not supplied)` where the row entered none, the days and the months'
        // quantities, and the payment days, 2 November, 46328, and the 21st, 46316; on 1 October,
        // 46296, every observation live at 72, 29 slots in two groups, 580 of mark and 0.29 lots, by
        // month as a whole, and each row alone its own share, 200, 200 and 180; a start without its
        // end and a row with no period refused by their rows, a number where a code should be by
        // the seam, and a template whose period cell is blank reading back `(not supplied)`.
        [Fact]
        public void a_ticket_books_each_row_by_its_dates_or_its_code_and_values_as_the_page_says()
        {
            var schedule = (string)Seam.Call("_CreateFuturesSchedule", Column("U26", "V26", "X26", "Z26"), Column(46294.0, 46325.0, 46356.0, 46387.0), ExcelMissing.Value);
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 47484.0);
            var conventions = (string)Seam.Call("_CreateIndexConventions", "USD", "BBL", "USD", "VOLUME", "BBL");
            var specifications = (string)Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "BBL", 1.0, "BBL", 0.0, 0.0 }, { "LOT", 1000.0, "BBL", 0.0, 0.0 } });
            var index = (string)Seam.Call("_CreateIndex", "BBL_ASIAN", "Synthetic barrel index for the codes-and-dates example", schedule, conventions, specifications, holidays, "LOT");
            var fields = Row("quantity_unit", "schedule_method", "route", "settlement_method", "clearing_house", "payment_day", "payment_holiday_calendar", "settlement_frequency", "nearby");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("BBL", "asian", "cleared", "financial", "Prototype Clearing", "+1bd", holidays, "monthly", 1.0));
            var headers = Row("trade_id", "trade_date", "contract_code", "start_date", "end_date", "quantity", "quantity_per", "fixed_price");
            var rows = new object[,] { { 1.0, 46280.0, "V26", "", "", 100.0, "month", 70.0 }, { 2.0, 46280.0, "V26", 46307.0, 46326.0, 100.0, "month", 70.0 }, { 3.0, 46280.0, "", 46307.0, 46315.0, 10.0, "calday", 70.0 } };
            var trades = (string)Seam.Call("_CreateTrades", index, headers, rows, template);
            var spill = (object[,])Seam.Call("util_ReadHandle", trades);
            Assert.Equal(5, spill.GetLength(0));
            Assert.Equal(24, spill.GetLength(1));
            Assert.Equal("payment_date", spill[0, 13]);
            Assert.Equal("entered_contract_code", spill[0, 14]);
            Assert.Equal("start_date", spill[0, 15]);
            for (var r = 2; r < 5; r++) Assert.Equal("V26", spill[r, 3]);
            Assert.Equal("V26", spill[2, 14]);
            Assert.Equal("V26", spill[3, 14]);
            Assert.Equal("(not supplied)", spill[4, 14]);
            Assert.Equal(46296.0, spill[2, 15]);
            Assert.Equal(46307.0, spill[3, 15]);
            Assert.Equal(46307.0, spill[4, 15]);
            Assert.Equal(46326.0, spill[2, 16]);
            Assert.Equal(46326.0, spill[3, 16]);
            Assert.Equal(46315.0, spill[4, 16]);
            Assert.Equal(31.0, spill[2, 17]);
            Assert.Equal(20.0, spill[3, 17]);
            Assert.Equal(9.0, spill[4, 17]);
            Assert.Equal(100.0, spill[2, 18]);
            Assert.Equal(100.0, spill[3, 18]);
            Assert.Equal(90.0, spill[4, 18]);
            Assert.Equal(46328.0, spill[2, 13]);
            Assert.Equal(46328.0, spill[3, 13]);
            Assert.Equal(46316.0, spill[4, 13]);
            var calendar = (string)Seam.Call("_CreateCalendar", (string)Seam.Call("_CreateValuationDate", 46296.0, 0.5), index);
            var history = (string)Seam.Call("_CreateMarketHistory", calendar, (string)Seam.Call("_CreateFuturesFixings", 46295.0, 70.0, index));
            var prepared = (string)Seam.Call("_PrepareTrades", trades, history);
            Assert.Equal(31, ((object[,])Seam.Call("util_ReadHandle", prepared)).GetLength(0));
            var market = (string)Seam.Call("_CreateMarket", history, (string)Seam.Call("_CreatePriceVector", "BBL_ASIAN", Column(72.0, 72.0, 72.0)));
            var results = (string)Seam.Call("_EvaluateTrades", prepared, market, ExcelMissing.Value);
            Assert.Equal(580.0, (double)((object[,])Seam.Call("_ReportValues", results))[2, 0], 6);
            Assert.Equal(0.29, (double)((object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "year"))[3, 1], 6);
            var byMonth = (object[,])Seam.Call("_ReportRisk", results, "nominal_delta", "month");
            Assert.Equal(5, byMonth.GetLength(0));
            Assert.Equal(46296.0, byMonth[4, 0]);
            Assert.Equal(0.29, (double)byMonth[4, 1], 6);
            var alone = new[] { 200.0, 200.0, 180.0 };
            for (var r = 0; r < 3; r++)
            {
                var line = new object[1, 8];
                for (var c = 0; c < 8; c++) line[0, c] = rows[r, c];
                var one = (string)Seam.Call("_CreateTrades", index, headers, line, template);
                var valued = (string)Seam.Call("_EvaluateTrades", (string)Seam.Call("_PrepareTrades", one, history), market, ExcelMissing.Value);
                Assert.Equal(alone[r], (double)((object[,])Seam.Call("_ReportValues", valued))[2, 0], 6);
            }
            Assert.Equal("#ERROR _CreateTrades: ValueError: start_date row 1 is 2026-10-12 without end_date row 1, expected both dates, the period's first and last day, or neither and a contract_code", Seam.Call("_CreateTrades", index, headers, Row(5.0, 46280.0, "V26", 46307.0, "", 100.0, "month", 70.0), template));
            Assert.Equal("#ERROR _CreateTrades: ValueError: row 1 has no period, expected a contract_code or start_date with end_date on each row; contract_code, start_date and end_date are not supplied", Seam.Call("_CreateTrades", index, headers, Row(6.0, 46280.0, ExcelEmpty.Value, "", "", 100.0, "month", 70.0), template));
            Assert.Equal("#ERROR _CreateTrades: trade_rows cell (1, 3) is number 26.0, expected text", Seam.Call("_CreateTrades", index, headers, Row(7.0, 46280.0, 26.0, "", "", 100.0, "month", 70.0), template));
            var blank = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", Row("contract_code", "quantity_unit"), Row(ExcelEmpty.Value, "BBL"));
            var shown = (object[,])Seam.Call("util_ReadHandle", blank);
            Assert.Equal("contract_code", shown[0, 1]);
            Assert.Equal("str", shown[1, 1]);
            Assert.Equal("(not supplied)", shown[2, 1]);
        }

        // The balance of a period from a valuation-date handle, date-helper-inputs.md: the ticket's table,
        // October 2026 from 20 September, 46285, the whole month, 46296 to 46326, from the 12th, 46307,
        // that day, on the 31st, 46326, one day, and from 1 November, 46327, refused by both readers;
        // January 2026 from the December before, 46011, the whole month; a strip from 12 November,
        // 46338; a calendar year from the October before; December from the 15th, 46371, and the leap
        // day, 46812, one day; an ordinary label its whole period with either handle; the fraction of
        // the day read for nothing; a handle of another kind refused by the seam whatever the label.
        [Fact]
        public void the_balance_of_a_period_starts_on_the_later_of_the_valuation_day_and_its_first_day()
        {
            var september = (string)Seam.Call("_CreateValuationDate", 46285.0, 0.0);
            var october12 = (string)Seam.Call("_CreateValuationDate", 46307.0, 0.5);
            var october31 = (string)Seam.Call("_CreateValuationDate", 46326.0, 1.0);
            var november = (string)Seam.Call("_CreateValuationDate", 46327.0, 0.0);
            var december = (string)Seam.Call("_CreateValuationDate", 46371.0, 0.5);
            Assert.Equal(46296.0, Seam.Call("util_StartDate", "balv26", september));
            Assert.Equal(46326.0, Seam.Call("util_EndDate", "balv26", september));
            Assert.Equal(46307.0, Seam.Call("util_StartDate", "BALV26", october12));
            Assert.Equal(46326.0, Seam.Call("util_EndDate", "BALV26", october12));
            Assert.Equal(46326.0, Seam.Call("util_StartDate", "BalV26", october31));
            Assert.Equal(46326.0, Seam.Call("util_EndDate", "BalV26", october31));
            Assert.Equal(46023.0, Seam.Call("util_StartDate", "balf26", (string)Seam.Call("_CreateValuationDate", 46011.0, 0.0)));
            Assert.Equal(46388.0, Seam.Call("util_StartDate", "balcal27", october12));
            Assert.Equal(46752.0, Seam.Call("util_EndDate", "balcal27", october12));
            Assert.Equal(46338.0, Seam.Call("util_StartDate", "balx26-z26", (string)Seam.Call("_CreateValuationDate", 46338.0, 0.0)));
            Assert.Equal(46371.0, Seam.Call("util_StartDate", "BALZ26", december));
            Assert.Equal(46387.0, Seam.Call("util_EndDate", "BALZ26", december));
            Assert.Equal(46812.0, Seam.Call("util_StartDate", "BALG28", (string)Seam.Call("_CreateValuationDate", 46812.0, 0.0)));
            Assert.Equal(46357.0, Seam.Call("util_StartDate", "Z26", december));
            Assert.Equal(46357.0, Seam.Call("util_StartDate", "Z26", september));
            Assert.Equal(46387.0, Seam.Call("util_EndDate", "Z26", october12));
            Assert.Equal("#ERROR util_StartDate: ValueError: valuation_date is 2026-11-01, after 'balv26' ended on 2026-10-31, expected a valuation day on or before the period's last day", Seam.Call("util_StartDate", "balv26", november));
            Assert.Equal("#ERROR util_EndDate: ValueError: valuation_date is 2026-11-01, after 'balv26' ended on 2026-10-31, expected a valuation day on or before the period's last day", Seam.Call("util_EndDate", "balv26", november));
            var holidays = (string)Seam.Call("_CreateHolidayCalendar", 46381.0);
            Assert.Equal("#ERROR util_StartDate: valuation_date is holiday calendar handle '" + holidays + "', expected valuation date handle", Seam.Call("util_StartDate", "Z26", holidays));
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

        // Since #190, reject-nonfinite-trade-arithmetic.md: a row of 1e308 lots of 10,000 MMBTU is a
        // quote quantity past the largest number; the creator refuses it by the trade and the
        // operation and publishes nothing, the store's live count standing, and a row of ten lots
        // then creates through the ordinary path and releases.
        [Fact]
        public void a_batch_past_the_largest_number_publishes_nothing_and_a_corrected_one_creates()
        {
            var schedule = Seam.Call("_CreateFuturesSchedule", Column("X26", "Z26", "F27"), Column(46323.0, 46351.0, 46385.0), ExcelMissing.Value);
            var holidays = Seam.Call("_CreateHolidayCalendar", Column(46352.0, 46381.0));
            var conventions = Seam.Call("_CreateIndexConventions", "USD", "MMBTU", "USD", "ENERGY", "MMBTU");
            var specifications = Seam.Call("_CreateContractSpecifications", Row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"), new object[,] { { "NYMEX NG", 10000.0, "MMBTU", 0.0, 0.0 } });
            var ng = (string)Seam.Call("_CreateIndex", "Henry Hub NYMEX", "Henry Hub NYMEX index", schedule, conventions, specifications, holidays, "NYMEX NG");
            var fields = Row("quantity_unit", "quantity_per", "settlement_frequency", "nearby", "schedule_method", "route", "settlement_method", "clearing_house");
            var template = (string)Seam.Call("_CreateTradeTemplate", "fixed_float", fields, Row("NYMEX NG", "month", "monthly", 1.0, "lastday", "cleared", "physical", "CME Clearing"));
            var headers = Row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price");
            var publisher = Bridge.PreparePublisher("_CreateTrades");
            var (live, _) = Bridge.LiveHandles();
            var refused = Bridge.Publish(publisher, ng, headers, Row(1001.0, 46289.0, "Z26", 1e308, 3.1), template);
            Assert.False(refused.Owned);
            Assert.Equal("#ERROR _CreateTrades: ValueError: trade 1001 at row 1 has inf of quote quantity, expected a finite number of MMBTU; its count times its specification's size in the quote unit outruns the largest number", refused.Value);
            Assert.Equal(live, Bridge.LiveHandles().Live);
            var made = Bridge.Publish(publisher, ng, headers, Row(1001.0, 46289.0, "Z26", 10.0, 3.1), template);
            Assert.True(made.Owned);
            Assert.StartsWith(Pid + ":trades:Henry Hub NYMEX:", (string)made.Value);
            Assert.Equal(live + 1, Bridge.LiveHandles().Live);
            Assert.Equal(Release.Released, Bridge.Release((string)made.Value));
            Assert.Equal(live, Bridge.LiveHandles().Live);
        }
    }
}
