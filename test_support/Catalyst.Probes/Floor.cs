using ExcelDna.Integration;

namespace Catalyst.Probes
{
    /// <summary>
    /// The floor under every probe: a worksheet function with the host's argument shape and no
    /// Python, so what Excel and Excel-DNA charge for a call is measured beside what the seam adds.
    /// It is a probe, hidden from the function wizard like the Python ones, and like them test
    /// support. This library is no part of the host and no release holds it: Excel knows HostAdd
    /// only where a harness staged the add-in in a folder of its own with this library beside it
    /// and named in that folder's copy of the add-in's .dna file, tools\host_build.ps1.
    /// </summary>
    public static class Floor
    {
        [ExcelFunction(IsHidden = true, Description = "Probe: a number in and out with no Python; the Excel-DNA floor.")]
        public static object HostAdd(object a, object b)
        {
            return (double)a + (double)b;
        }
    }
}
