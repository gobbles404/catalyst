using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace Goosedove.Host
{
    /// <summary>
    /// What the host did during one call, by name. An observer supplies one; a worksheet call
    /// never does, so the worksheet path builds nothing and pays only a null check at each
    /// boundary. The names, each a thing the host did:
    ///   trips              calls into Python: the seam's call, and cells_block once per range
    ///   name_lookups       Python attributes fetched by their text name
    ///   objects_built      Python objects the host made: the name, the argument list, each
    ///                      scalar, and the five values that carry a range
    ///   cells_scanned      cells visited by the range loop, the Excel error that stopped it included
    ///   text_cells         text cells collected in that loop
    ///   buffers_allocated  managed arrays made for a range in or a block out
    ///   buffer_bytes       their payload bytes
    ///   result_copies      copies made of a block on its way to Excel
    ///   result_cells       cells in that block
    /// </summary>
    internal sealed class WorkCounter
    {
        private readonly Dictionary<string, long> counts = new Dictionary<string, long>();

        public void Hit(string name, long count = 1)
        {
            if (count == 0)
            {
                return;
            }
            counts.TryGetValue(name, out var previous);
            counts[name] = previous + count;
        }

        /// <summary>A snapshot; an absent name is work that did not happen.</summary>
        public IReadOnlyDictionary<string, long> Freeze()
        {
            return new ReadOnlyDictionary<string, long>(new Dictionary<string, long>(counts));
        }
    }
}
