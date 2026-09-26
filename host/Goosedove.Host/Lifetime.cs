using System;
using System.Threading;
using ExcelDna.Integration;

namespace Goosedove.Host
{
    /// <summary>
    /// A creator's publication owned by Excel's live-data subscription. Excel-DNA asks for one
    /// through the factory in <see cref="Lifetime.Observe"/> when no live call with the same
    /// function and argument values exists, and hands the live one's value back otherwise, so a
    /// reuse runs nothing here. Subscribe runs the creator's prepared path once and hands its
    /// value to Excel before returning, so a new publication never shows #N/A while Excel waits
    /// for its next update; the subscription never completes on its own. Dispose, which Excel-DNA
    /// calls when the last subscriber disconnects, releases the one publication this owns, once,
    /// however many times it is called, and reports a failure rather than swallowing it.
    /// docs/seam/handles.md is the page.
    /// </summary>
    internal sealed class Publication : IExcelObservable, IDisposable
    {
        private readonly Func<Outcome> create;
        private readonly Func<string, Release> release;
        private object value;
        private string owned;
        private bool delivered;
        private int disposed;

        public Publication(Func<Outcome> create, Func<string, Release> release)
        {
            this.create = create;
            this.release = release;
        }

        /// <summary>The handle this owns, or null: for the tests and the status function.</summary>
        public string Owned => owned;

        public IDisposable Subscribe(IExcelObserver observer)
        {
            if (!delivered)
            {
                var outcome = create();
                value = outcome.Value;
                if (outcome.Owned)
                {
                    owned = (string)outcome.Value;
                    Interlocked.Increment(ref Lifetime.Publications);
                }
                delivered = true;
            }
            try
            {
                observer.OnNext(value);
            }
            catch
            {
                // A value Excel could not take leaves no orphan entry behind.
                Dispose();
                throw;
            }
            return this;
        }

        public void Dispose()
        {
            if (Interlocked.Exchange(ref disposed, 1) != 0)
            {
                return;
            }
            var text = Interlocked.Exchange(ref owned, null);
            if (text == null)
            {
                return;
            }
            try
            {
                switch (release(text))
                {
                    case Release.Released:
                        Interlocked.Increment(ref Lifetime.Releases);
                        break;
                    case Release.Missing:
                        Interlocked.Increment(ref Lifetime.ReleaseMisses);
                        break;
                    default:
                        Interlocked.Increment(ref Lifetime.SkippedAtClose);
                        break;
                }
            }
            catch (Exception error)
            {
                Interlocked.Increment(ref Lifetime.DisposalErrors);
                Lifetime.LastDisposalError = error.ToString();
            }
        }
    }

    /// <summary>
    /// What became of a release: the seam let the entry go; it found no entry, a text already gone;
    /// or the call was skipped, the add-in closing or Python gone, so no finalized interpreter is
    /// ever called.
    /// </summary>
    internal enum Release
    {
        Released,
        Missing,
        Skipped,
    }

    /// <summary>What a creator's prepared path came back with: the cell's value, and whether it published.</summary>
    internal readonly struct Outcome
    {
        public readonly object Value;
        public readonly bool Owned;

        public Outcome(object value, bool owned)
        {
            Value = value;
            Owned = owned;
        }
    }

    /// <summary>
    /// The observed path every creator takes, and the counts of what it did: calls observed,
    /// factories run (a call observed and no factory run is a reuse), publications owned,
    /// releases made, releases that found nothing, and disposal failures. GoosedoveHandles
    /// reports them beside the store's live count.
    /// </summary>
    internal static class Lifetime
    {
        public static long Observed;
        public static long Factories;
        public static long Publications;
        public static long Releases;
        public static long ReleaseMisses;
        public static long DisposalErrors;
        public static long SkippedAtClose;
        public static volatile string LastDisposalError;
        public static volatile bool Closing;

        /// <summary>
        /// A creator's call: an Excel error among the arguments is the result before any
        /// subscription, as the plain path has it, and owns nothing; otherwise Excel-DNA finds
        /// the live call with this function and these argument values, or asks for a new one.
        /// </summary>
        public static object Observe(Prepared prepared, object[] args)
        {
            foreach (var arg in args)
            {
                if (arg is ExcelError)
                {
                    return arg;
                }
            }
            Interlocked.Increment(ref Observed);
            return ExcelAsyncUtil.Observe(prepared.Name, args, () =>
            {
                Interlocked.Increment(ref Factories);
                return new Publication(() => Bridge.Publish(prepared, args), Bridge.Release);
            });
        }

        public static string Report(long live, long priceBytes)
        {
            var text = "live " + live + "; price bytes " + priceBytes
                + "; published " + Interlocked.Read(ref Publications)
                + "; reused " + (Interlocked.Read(ref Observed) - Interlocked.Read(ref Factories))
                + "; released " + Interlocked.Read(ref Releases)
                + "; release misses " + Interlocked.Read(ref ReleaseMisses)
                + "; disposal errors " + Interlocked.Read(ref DisposalErrors)
                + "; skipped at close " + Interlocked.Read(ref SkippedAtClose);
            var error = LastDisposalError;
            return error == null ? text : text + "; last disposal error: " + error;
        }
    }
}
