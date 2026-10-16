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
            {
                object error;
                var item = Marshal.ToPython(value, "Fn", 1, out error);
                Assert.Null(error);
                try
                {
                    using (var text = Bridge.Module.InvokeMethod("describe", item))
                    {
                        return text.As<string>();
                    }
                }
                finally
                {
                    Marshal.Release(item);
                }
            }
        }

        private static string Attribute(object[,] grid, string name)
        {
            using (Py.GIL())
            {
                object error;
                using (var cells = Marshal.ToPython(grid, "Fn", 1, out error))
                {
                    Assert.Null(error);
                    using (var attribute = cells.GetAttr(name))
                    {
                        return attribute.HasAttr("tolist") ? attribute.InvokeMethod("tolist").ToString() : attribute.ToString();
                    }
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
            {
                object error;
                Assert.Null(Marshal.ToPython(ExcelError.ExcelErrorNA, "Fn", 1, out error));
                Assert.Equal(ExcelError.ExcelErrorNA, error);
            }
        }

        [Fact]
        public void an_error_anywhere_in_a_grid_wins_even_after_text()
        {
            var grid = new object[,] { { "x" }, { ExcelError.ExcelErrorDiv0 } };
            using (Py.GIL())
            {
                object error;
                Assert.Null(Marshal.ToPython(grid, "Fn", 1, out error));
                Assert.Equal(ExcelError.ExcelErrorDiv0, error);
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
            Assert.Equal("31", Attribute(grid, "seen"));  // every kind occurred: one bit each
        }

        [Fact]
        public void text_cells_keep_their_order_and_an_empty_one_survives_the_join()
        {
            var grid = new object[,] { { "x", 1.0 }, { "", "y" } };
            Assert.Equal("[[1, 0], [1, 1]]", Attribute(grid, "kinds"));
            Assert.Equal("('x', '', 'y')", Attribute(grid, "texts"));
            Assert.Equal("3", Attribute(grid, "seen"));  // numbers and text
        }

        [Fact]
        public void a_range_of_only_numbers_carries_no_text()
        {
            Assert.Equal("()", Attribute(new object[,] { { 1.0 }, { 2.0 } }, "texts"));
            Assert.Equal("1", Attribute(new object[,] { { 1.0 }, { 2.0 } }, "seen"));  // numbers only
        }

        [Fact]
        public void an_omitted_argument_is_the_missing_held_since_start_and_releasing_it_keeps_it()
        {
            using (Py.GIL())
            {
                object error;
                var first = Marshal.ToPython(ExcelMissing.Value, "Fn", 1, out error);
                Assert.Same(Bridge.Missing, first);
                Marshal.Release(first);
                Assert.Equal("missing", Described(ExcelMissing.Value));
            }
        }

        // The seam promises a number, text, a boolean, an array, or a mixed rectangle as a tuple;
        // the host says so if it gets anything else.
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

        // The mixed road reads the tuple by position and checks the seam's promise on each part.
        [Fact]
        public void a_mixed_result_whose_kinds_are_not_bytes_fails_loudly()
        {
            using (Py.GIL())
            using (var kinds = new PyFloat(1.0))
            using (var numbers = new PyFloat(2.0))
            using (var text = new PyString(""))
            using (var tuple = new PyTuple(new PyObject[] { kinds, numbers, text }))
            {
                var shown = Assert.IsType<string>(Marshal.FromPython(tuple, "Fn"));
                Assert.Equal("#ERROR host: Fn returned a mixed array whose kinds give no buffer", shown);
            }
        }
    }
}
