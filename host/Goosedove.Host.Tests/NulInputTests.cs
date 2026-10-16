using ExcelDna.Integration;
using Xunit;

namespace Goosedove.Host.Tests
{
    /// <summary>
    /// Since #189, reject-nul-input-text.md: a text holding NUL (U+0000) is refused by the host
    /// where its pass reaches it, before anything crosses into Python. The host packs a range's
    /// texts into one string separated by NUL, so a NUL inside a cell would split into two cells
    /// on the other side and move text into another field; the ticket's example put a broker's
    /// text into schedule_method. The refusal names the function, the argument's one-based
    /// position and, inside a range, the cell's one-based row and column; it never carries the
    /// character itself. Scalar text, a one-cell array and larger ranges obey the same rule, the
    /// ordinary call and the creator's publication alike, and the first Excel error or NUL the
    /// traversal meets, arguments left to right and cells row-major, is the one reported.
    /// </summary>
    [Collection("python")]
    public class NulInputTests
    {
        private static object[,] Row(params object[] cells)
        {
            var row = new object[1, cells.Length];
            for (var i = 0; i < cells.Length; i++)
            {
                row[0, i] = cells[i];
            }
            return row;
        }

        private static object[,] Column(params object[] cells)
        {
            var column = new object[cells.Length, 1];
            for (var i = 0; i < cells.Length; i++)
            {
                column[i, 0] = cells[i];
            }
            return column;
        }

        private static string Refusal(string function, int position) =>
            "#ERROR host: " + function + " argument " + position + " is text holding NUL (U+0000), expected text without it";

        private static string Refusal(string function, int position, int row, int column) =>
            "#ERROR host: " + function + " argument " + position + " cell (" + row + ", " + column + ") is text holding NUL (U+0000), expected text without it";

        // The ticket's example through the creator's own path: the broker's text holding NUL and
        // "penultimate" would have become the schedule method. The refusal names argument 3 and
        // cell (1, 1), the publisher owns nothing and the store's live count stands; the corrected
        // broker makes a template whose schedule_method is lastday.
        [Fact]
        public void the_shifting_fields_example_cannot_publish_and_the_corrected_template_keeps_its_method()
        {
            var publisher = Bridge.PreparePublisher("_CreateTradeTemplate");
            var fields = Row("broker", "schedule_method");
            var (live, _) = Bridge.LiveHandles();
            var refused = Bridge.Publish(publisher, "fixed_float", fields, Row("desk\u0000penultimate", "lastday"));
            Assert.Equal(Refusal("_CreateTradeTemplate", 3, 1, 1), refused.Value);
            Assert.False(refused.Owned);
            Assert.Equal(live, Bridge.LiveHandles().Live);
            var made = Bridge.Publish(publisher, "fixed_float", fields, Row("desk", "lastday"));
            Assert.True(made.Owned);
            var handle = Assert.IsType<string>(made.Value);
            Assert.DoesNotContain("#ERROR", handle);
            var table = (object[,])Seam.Call("util_ReadHandle", handle);
            Assert.Equal("broker", table[0, 1]);
            Assert.Equal("desk", table[2, 1]);
            Assert.Equal("schedule_method", table[0, 2]);
            Assert.Equal("lastday", table[2, 2]);
            Assert.Equal(live + 1, Bridge.LiveHandles().Live);
            Assert.Equal(Release.Released, Bridge.Release(handle));
            Assert.Equal(live, Bridge.LiveHandles().Live);
        }

        // The character at the start, in the middle, at the end, twice over and alone: each is a
        // refusal, as scalar text, as a one-cell array, in a row, in a column and in a rectangle,
        // the first affected argument and cell named each time.
        [Theory]
        [InlineData("\u0000abc")]
        [InlineData("a\u0000bc")]
        [InlineData("abc\u0000")]
        [InlineData("a\u0000\u0000b")]
        [InlineData("\u0000")]
        [InlineData("\u0000\u0000")]
        public void a_nul_anywhere_in_a_text_is_refused_by_argument_and_cell(string text)
        {
            Assert.Equal(Refusal("_ShowInstrument", 1), Seam.Call("_ShowInstrument", text));
            Assert.Equal(Refusal("EchoMixed", 1, 1, 1), Seam.Call("EchoMixed", new object[,] { { text } }));
            Assert.Equal(Refusal("EchoMixed", 1, 1, 2), Seam.Call("EchoMixed", Row("a", text, "b")));
            Assert.Equal(Refusal("EchoMixed", 1, 3, 1), Seam.Call("EchoMixed", Column(1.0, true, text)));
            var rectangle = new object[,] { { "a", 1.0, true }, { 2.0, "b", text } };
            Assert.Equal(Refusal("EchoMixed", 1, 2, 3), Seam.Call("EchoMixed", rectangle));
            Assert.Equal(Refusal("SumQuantity", 2, 1, 2), Seam.Call("SumQuantity", Row("date", "product", "quantity", "cleared"), Row(46276.0, text, 1.0, true)));
        }

        // Two texts holding NUL in one range: the earlier in sheet order, row-major, is the one
        // named, and the scan goes no further.
        [Fact]
        public void the_first_nul_in_sheet_order_is_the_one_named()
        {
            var rectangle = new object[,] { { "a", "b" }, { "c\u0000", "d\u0000" } };
            Assert.Equal(Refusal("EchoMixed", 1, 2, 1), Seam.Call("EchoMixed", rectangle));
            var later = new object[,] { { "a", "b\u0000" }, { "c\u0000", "d" } };
            Assert.Equal(Refusal("EchoMixed", 1, 1, 2), Seam.Call("EchoMixed", later));
        }

        // An ordinary call and a creator's publication refuse alike, after earlier arguments have
        // already crossed: the instrument's name and the row of fields are built and released
        // when the third argument is refused, and the next call is whole.
        [Fact]
        public void an_ordinary_call_and_a_publication_refuse_alike_after_earlier_arguments_crossed()
        {
            Assert.Equal(Refusal("EchoFieldRow", 3, 1, 1), Seam.Call("EchoFieldRow", "fixed_float", Row("broker"), Row("a\u0000")));
            var (live, _) = Bridge.LiveHandles();
            var outcome = Bridge.Publish(Bridge.PreparePublisher("_CreateTradeTemplate"), "fixed_float", Row("broker"), Row("a\u0000"));
            Assert.Equal(Refusal("_CreateTradeTemplate", 3, 1, 1), outcome.Value);
            Assert.False(outcome.Owned);
            Assert.Equal(live, Bridge.LiveHandles().Live);
            var echoed = (object[,])Seam.Call("EchoFieldRow", "fixed_float", Row("broker"), Row("desk"));
            Assert.Equal("desk", echoed[1, 0]);
        }

        // The narrow priority rule: the traversal is the one the host already makes, arguments
        // left to right and cells row-major, and it stops at the first Excel error or NUL it
        // meets. An earlier error comes back unchanged; an earlier NUL is reported without the
        // scan looking ahead for errors; a later argument is never reached.
        [Fact]
        public void the_first_excel_error_or_nul_in_traversal_order_wins()
        {
            Assert.Equal(ExcelError.ExcelErrorNA, Seam.Call("EchoMixed", Column("x", ExcelError.ExcelErrorNA, "a\u0000")));
            Assert.Equal(Refusal("EchoMixed", 1, 1, 1), Seam.Call("EchoMixed", Column("a\u0000", ExcelError.ExcelErrorNA)));
            var headers = Row("date", "product", "quantity", "cleared");
            var body = Row(46276.0, "p", 1.0, true);
            Assert.Equal(Refusal("SumQuantity", 1, 1, 2), Seam.Call("SumQuantity", Row("date", "product\u0000", "quantity", "cleared"), Row(46276.0, ExcelError.ExcelErrorDiv0, 1.0, true)));
            Assert.Equal(ExcelError.ExcelErrorDiv0, Seam.Call("SumQuantity", Row("date", ExcelError.ExcelErrorDiv0, "quantity", "cleared"), Row(46276.0, "p\u0000", 1.0, true)));
            Assert.Equal(Refusal("SumQuantity", 1, 1, 2), Seam.Call("SumQuantity", Row("date", "product\u0000", "quantity", "cleared"), body));
            Assert.Equal(1.0, Seam.Call("SumQuantity", headers, body));
        }

        // The host's refusal comes before the seam's shape and type rules: a column where a row is
        // wanted, holding a NUL, is refused for the NUL.
        [Fact]
        public void a_wrong_shape_holding_a_nul_is_refused_by_the_host_before_the_seam()
        {
            Assert.Equal("#ERROR EchoRow: values is 2x1 array, expected row of numbers", Seam.Call("EchoRow", Column(1.0, 2.0)));
            Assert.Equal(Refusal("EchoRow", 1, 2, 1), Seam.Call("EchoRow", Column(1.0, "a\u0000")));
        }

        // After a refusal the kept buffers serve the next calls as before: a smaller mixed range
        // echoes cell for cell, a range of numbers sums, a template publishes; ordinary Unicode, a
        // nonbreaking space, a tab, a line break and the two characters backslash and zero are
        // ordinary text and survive unchanged.
        [Fact]
        public void after_a_refusal_the_buffers_serve_valid_calls_and_texts_stay_in_their_fields()
        {
            var wide = new object[,] { { "a", "b", "c" }, { "d", "e", "f" }, { "g", "h", "i\u0000" } };
            Assert.Equal(Refusal("EchoMixed", 1, 3, 3), Seam.Call("EchoMixed", wide));
            var texts = new object[] { "naïve", "日本", "a b", "tab\tx", "line\nbreak", "\\0", "#ERROR not a refusal" };
            var echoed = (object[,])Seam.Call("EchoMixed", Column(texts));
            for (var i = 0; i < texts.Length; i++)
            {
                Assert.Equal(texts[i], echoed[i, 0]);
            }
            Assert.Equal(3.0, Seam.Call("SumArray", Column(1.0, 2.0)));
            var (live, _) = Bridge.LiveHandles();
            var made = Bridge.Publish(Bridge.PreparePublisher("_CreateTradeTemplate"), "fixed_float", Row("broker", "schedule_method"), Row("\\0", "lastday"));
            Assert.True(made.Owned);
            var table = (object[,])Seam.Call("util_ReadHandle", (string)made.Value);
            Assert.Equal("\\0", table[2, 1]);
            Assert.Equal("lastday", table[2, 2]);
            Assert.Equal(Release.Released, Bridge.Release((string)made.Value));
            Assert.Equal(live, Bridge.LiveHandles().Live);
        }

        // Nothing else about text changes: an empty text and a blank fail where the seam's rules
        // say, a missing argument takes its default, and the text of a refusal is ordinary text.
        [Fact]
        public void blank_empty_missing_and_error_shaped_texts_keep_their_rules()
        {
            Assert.Equal("#ERROR EchoMixed: values cell (1, 1) is empty text, expected number, nonempty text or boolean", Seam.Call("EchoMixed", new object[,] { { "" } }));
            Assert.Equal("#ERROR EchoMixed: values cell (1, 1) is blank, expected number, nonempty text or boolean", Seam.Call("EchoMixed", new object[,] { { ExcelEmpty.Value } }));
            Assert.Equal(5.0, Seam.Call("Times", 5.0, ExcelMissing.Value));
            Assert.Equal("#ERROR _ShowInstrument: instrument is empty text, expected text", Seam.Call("_ShowInstrument", ""));
            var shown = (object[,])Seam.Call("EchoMixed", new object[,] { { "#ERROR host: looks like one" } });
            Assert.Equal("#ERROR host: looks like one", shown[0, 0]);
        }
    }
}
