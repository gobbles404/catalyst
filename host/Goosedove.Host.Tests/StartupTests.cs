using System.IO;
using ExcelDna.Integration;
using Xunit;

namespace Goosedove.Host.Tests
{
    /// <summary>The pieces of AutoOpen that do not need Excel: the config file and the delegates.</summary>
    [Collection("python")]
    public class StartupTests
    {
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
            var curve = attributes.FindIndex(a => ((ExcelFunctionAttribute)a).Name == "CreateDiscountCurve");
            Assert.False(((ExcelFunctionAttribute)attributes[curve]).IsHidden);
            var table = (ExcelArgumentAttribute)argumentAttributes[curve][1];
            Assert.Equal("table", table.Name);
            Assert.StartsWith("The body under the headers", table.Description);
        }
    }
}
