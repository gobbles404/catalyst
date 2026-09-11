using ExcelDna.Integration;
using Python.Runtime;
using Xunit;

namespace Goosedove.Host.Tests
{
    /// <summary>What Python receives for each thing Excel can hand over.</summary>
    [Collection("python")]
    public class MarshalTests
    {
        // The seam's own words for what arrived: "number 1.5", "blank", "2x2 array".
        private static string Described(object value)
        {
            using (Py.GIL())
            using (var args = new PyList())
            {
                Assert.Null(Marshal.Append(args, value));
                using (var item = args[0])
                using (var text = Bridge.Module.InvokeMethod("describe", item))
                {
                    return text.As<string>();
                }
            }
        }

        private static string Attribute(object[,] grid, string name)
        {
            using (Py.GIL())
            using (var args = new PyList())
            {
                Assert.Null(Marshal.Append(args, grid));
                using (var cells = args[0])
                using (var attribute = cells.GetAttr(name))
                {
                    return attribute.HasAttr("tolist") ? attribute.InvokeMethod("tolist").ToString() : attribute.ToString();
                }
            }
        }

        [Fact] public void a_number_is_a_number() => Assert.Equal("number 1.5", Described(1.5));
        [Fact] public void text_is_text() => Assert.Equal("text 'n/a'", Described("n/a"));
        [Fact] public void a_boolean_is_a_boolean() => Assert.Equal("boolean TRUE", Described(true));
        [Fact] public void a_blank_cell_is_blank() => Assert.Equal("blank", Described(ExcelEmpty.Value));
        [Fact] public void an_omitted_argument_is_missing() => Assert.Equal("missing", Described(ExcelMissing.Value));
        [Fact] public void a_grid_is_an_array() => Assert.Equal("2x2 array", Described(new object[,] { { 1.0, 2.0 }, { 3.0, 4.0 } }));

        [Fact]
        public void an_error_argument_comes_back_and_python_is_not_called()
        {
            using (Py.GIL())
            using (var args = new PyList())
            {
                Assert.Equal(ExcelError.ExcelErrorNA, Marshal.Append(args, ExcelError.ExcelErrorNA));
                Assert.Equal(0, args.Length());
            }
        }

        [Fact]
        public void an_error_anywhere_in_a_grid_wins_even_after_text()
        {
            var grid = new object[,] { { "x" }, { ExcelError.ExcelErrorDiv0 } };
            using (Py.GIL())
            using (var args = new PyList())
            {
                Assert.Equal(ExcelError.ExcelErrorDiv0, Marshal.Append(args, grid));
                Assert.Equal(0, args.Length());
            }
        }

        [Fact]
        public void every_kind_of_cell_is_coded_in_sheet_order()
        {
            var grid = new object[,]
            {
                { 1.5, "n/a" },
                { ExcelEmpty.Value, true },
                { ExcelMissing.Value, null },
            };
            Assert.Equal("[[0, 1], [3, 2], [4, 3]]", Attribute(grid, "kinds"));
            Assert.Equal("[[1.5, nan], [nan, 1.0], [nan, nan]]", Attribute(grid, "numbers"));
            Assert.Equal("('n/a',)", Attribute(grid, "texts"));
        }

        [Fact]
        public void text_cells_keep_their_order_and_an_empty_one_survives_the_join()
        {
            var grid = new object[,] { { "x", 1.0 }, { "", "y" } };
            Assert.Equal("[[1, 0], [1, 1]]", Attribute(grid, "kinds"));
            Assert.Equal("('x', '', 'y')", Attribute(grid, "texts"));
        }

        [Fact]
        public void a_range_of_only_numbers_carries_no_text()
        {
            Assert.Equal("()", Attribute(new object[,] { { 1.0 }, { 2.0 } }, "texts"));
        }

        // The seam promises a number, text, a boolean, or an array; the host says so if it gets anything else.
        [Fact]
        public void a_result_the_host_cannot_show_fails_loudly()
        {
            using (Py.GIL())
            using (var missing = Bridge.Module.GetAttr("MISSING"))
            {
                var shown = Assert.IsType<string>(Marshal.FromPython(missing, "Fn"));
                Assert.Equal("#ERROR host: Fn returned a Missing, which the host cannot show", shown);
            }
        }
    }
}
