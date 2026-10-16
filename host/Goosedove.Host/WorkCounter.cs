using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace Goosedove.Host
{
    /// <summary>
    /// What the host did during one call, by name. An observer supplies one; a worksheet call
    /// never does, so the worksheet path builds nothing and pays only a null check at each
    /// boundary. The names, each a thing the host did:
    ///   trips              calls into Python: the function's prepared path, and cells_from_buffers
    ///                      once per range
    ///   name_lookups       Python attributes fetched by their text name; a prepared call makes none
    ///   objects_built      Python objects the host made: each scalar; a range's rows, cols and
    ///                      kinds seen, its text when it has any, and the two buffer addresses
    ///                      when the buffers grow
    ///   cells_scanned      cells visited by the range loop, the Excel error that stopped it included
    ///   text_cells         text cells collected in that loop
    ///   texts_checked      texts looked at for NUL (U+0000), each once as it is reached, a scalar
    ///                      argument or a range's cell, the refused one included, since #189
    ///   buffers_allocated  managed arrays made: for a range in only when the kept buffers grow,
    ///                      and for an array out, of doubles or of mixed cells
    ///   buffer_bytes       their payload bytes
    ///   result_copies      copies made of an array of doubles on its way to Excel
    ///   result_cells       cells in the array out
    ///   result_texts       text cells of a mixed array out, one string each
    ///   result_boxes       number cells of a mixed array out, one box each
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
