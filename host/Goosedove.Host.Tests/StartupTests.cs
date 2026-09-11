using System.IO;
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
    }
}
