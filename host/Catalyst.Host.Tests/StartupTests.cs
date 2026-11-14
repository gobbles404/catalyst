using System;
using System.IO;
using System.Linq;
using System.Reflection;
using ExcelDna.Integration;
using Xunit;

namespace Catalyst.Host.Tests
{
    /// <summary>The pieces of AutoOpen that do not need Excel: the config file and the delegates.</summary>
    [Collection("python")]
    public class StartupTests
    {
        private readonly PythonFixture python;

        public StartupTests(PythonFixture python)
        {
            this.python = python;
        }

        [Fact]
        public void the_config_file_is_key_equals_value_with_comments_and_blank_lines()
        {
            var path = Path.GetTempFileName();
            File.WriteAllLines(path, new[]
            {
                "# where python lives",
                "pythondll = C:\\python\\python313.dll",
                "",
                "pythonpath=C:\\repo\\src;C:\\repo\\.venv\\Lib\\site-packages",
            });
            var config = Config.Load(path);
            Assert.Equal("C:\\python\\python313.dll", config["pythondll"]);
            Assert.Equal("C:\\repo\\src;C:\\repo\\.venv\\Lib\\site-packages", config["pythonpath"]);
            Assert.Equal(2, config.Count);
            Assert.False(config.TryGetValue("probes", out _));  // an end user's config: no probe is loaded
        }

        // A test or a measurement build names the probes' package on a line of its own.
        [Fact]
        public void a_config_that_names_the_probes_holds_their_package()
        {
            var path = Path.GetTempFileName();
            File.WriteAllLines(path, new[]
            {
                "pythondll=C:\\python\\python313.dll",
                "pythonpath=C:\\repo\\src;C:\\repo\\test_support;C:\\repo\\.venv\\Lib\\site-packages",
                "probes=catalyst_probes",
            });
            var config = Config.Load(path);
            Assert.True(config.TryGetValue("probes", out var probes));
            Assert.Equal("catalyst_probes", probes);
        }

        // Two configs that stop the add-in before Python starts, which tools\release_check.ps1 reads
        // by these same rules and calls faults. A line that is neither blank nor a comment and has
        // no = stops the load itself.
        [Fact]
        public void a_line_with_no_equals_sign_stops_the_config_from_loading()
        {
            var path = Path.GetTempFileName();
            File.WriteAllLines(path, new[]
            {
                "pythondll=C:\\python\\python313.dll",
                "where the library is",
                "pythonpath=C:\\repo\\src",
            });
            Assert.ThrowsAny<Exception>(() => Config.Load(path));
        }

        // And a key is held as written: one in capitals is not the key the host asks for.
        [Fact]
        public void a_key_in_capitals_is_not_the_key_the_host_asks_for()
        {
            var path = Path.GetTempFileName();
            File.WriteAllLines(path, new[]
            {
                "pythondll=C:\\python\\python313.dll",
                "PYTHONPATH=C:\\repo\\src",
            });
            var config = Config.Load(path);
            Assert.True(config.ContainsKey("PYTHONPATH"));
            Assert.False(config.ContainsKey("pythonpath"));
        }

        // The bridge imported and nothing more, where an end user's build stops: Excel is told of
        // every function a person types, of no probe, and of nothing hidden. The probes' folder was
        // on the path all the while; being importable registers nothing.
        [Fact]
        public void before_the_probes_are_loaded_excel_is_told_of_no_probe_and_nothing_hidden()
        {
            var told = python.EndUserFunctions;
            Assert.DoesNotContain(told, f => f.Hidden);
            Assert.DoesNotContain(told, f => f.Name == "Add" || f.Name == "Zero" || f.Name == "Fail");
            Assert.Contains(("Ping", false), told);
            Assert.Contains(("_CreateValuationDate", false), told);
            Assert.Contains(("_EvaluateTrades", false), told);
            Assert.Contains(("util_ReadHandle", false), told);
        }

        // With the probes loaded Excel is told of each, hidden, after every function it was told of
        // before, none of which moved or changed: what the probes' package added is hidden to a name.
        [Fact]
        public void with_the_probes_loaded_excel_is_told_of_each_hidden_and_of_the_rest_as_before()
        {
            var told = PythonFixture.Told();
            Assert.Equal(python.EndUserFunctions, told.Take(python.EndUserFunctions.Count));
            var added = told.Skip(python.EndUserFunctions.Count).ToList();
            Assert.All(added, f => Assert.True(f.Hidden));
            Assert.Contains(("Zero", true), added);
            Assert.Contains(("Add", true), added);
            Assert.Contains(("Fail", true), added);
        }

        [Fact]
        public void a_registered_delegate_forwards_its_arguments_to_the_prepared_path()
        {
            var add = Registration.MakeDelegate(Bridge.Prepare("Add"), 2);
            Assert.Equal(3.0, add.DynamicInvoke(1.0, 2.0));
        }

        // Excel-DNA reads the delegate's own signature, one object parameter per argument.
        [Fact]
        public void the_delegate_has_one_parameter_per_declared_argument()
        {
            Assert.Equal(2, Registration.MakeDelegate(Bridge.Prepare("Add"), 2).GetType().GetMethod("Invoke").GetParameters().Length);
            Assert.Empty(Registration.MakeDelegate(Bridge.Prepare("Ping"), 0).GetType().GetMethod("Invoke").GetParameters());
        }

        // The floor is test support, a library of its own: the host's assembly holds no HostAdd,
        // marked or not, for Excel or any caller to reach.
        [Fact]
        public void the_host_assembly_holds_no_floor()
        {
            var every = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly;
            var methods = typeof(Bridge).Assembly.GetTypes().SelectMany(type => type.GetMethods(every));
            Assert.DoesNotContain(methods, method => method.Name == "HostAdd");
            Assert.Null(typeof(Bridge).Assembly.GetType("Catalyst.Host.Floor"));
        }

        // The help beside each parameter reaches the argument's registration attribute, with an
        // optional argument's label in brackets and its default in the words of the sheet; the
        // function's description and hidden flag travel beside them.
        [Fact]
        public void the_help_beside_each_argument_reaches_its_registration_attribute()
        {
            var (delegates, attributes, argumentAttributes) = Registration.Describe();
            Assert.Equal(attributes.Count, delegates.Count);
            var times = attributes.FindIndex(a => ((ExcelFunctionAttribute)a).Name == "Times");
            var factor = (ExcelArgumentAttribute)argumentAttributes[times][1];
            Assert.Equal("[factor]", factor.Name);
            Assert.Equal("One multiplier. 1 when omitted.", factor.Description);
            var curve = attributes.FindIndex(a => ((ExcelFunctionAttribute)a).Name == "_CreateDiscountCurve");
            Assert.False(((ExcelFunctionAttribute)attributes[curve]).IsHidden);
            var name = (ExcelArgumentAttribute)argumentAttributes[curve][0];
            Assert.Equal("name", name.Name);
            Assert.StartsWith("The curve's name, text such as SOFR", name.Description);
            var table = (ExcelArgumentAttribute)argumentAttributes[curve][2];
            Assert.Equal("table", table.Name);
            Assert.StartsWith("The rows under the headers", table.Description);
        }
    }
}
