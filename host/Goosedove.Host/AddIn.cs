using ExcelDna.Integration;

namespace Goosedove.Host
{
    public static class Functions
    {
        [ExcelFunction(Description = "Confirms the Goosedove add-in is loaded.")]
        public static string Ping()
        {
            return "pong from C#";
        }
    }
}
