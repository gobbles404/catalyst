using System;
using System.Collections.Generic;
using ExcelDna.Integration;
using Xunit;

namespace Goosedove.Host.Tests
{
    /// <summary>
    /// The handle lifetime without Excel: the publisher's combined result, release of one entry,
    /// and the publication class driven by a fake observer, so that first delivery, ownership,
    /// disposal and its failures are pinned here and Excel's own subscription engine is left to the
    /// live lifetime script.
    /// </summary>
    [Collection("python")]
    public class LifetimeTests
    {
        private sealed class Observer : IExcelObserver
        {
            public readonly List<object> Values = new List<object>();
            public Exception Throws;

            public void OnNext(object value)
            {
                Values.Add(value);
                if (Throws != null) throw Throws;
            }

            public void OnError(Exception exception) => throw new InvalidOperationException("OnError is never used");

            public void OnCompleted() => throw new InvalidOperationException("a publication never completes");
        }

        private static Func<Outcome> Once(Outcome outcome, List<string> log)
        {
            return () => { log.Add("create"); return outcome; };
        }

        private static Func<string, Release> Releasing(List<string> log, Release outcome = Release.Released)
        {
            return text => { log.Add("release " + text); return outcome; };
        }

        // The seam's combined result: a creator's success is the handle and yes; its failure, the
        // failure's text and no; an Excel error among the arguments is the error and no, before Python.
        [Fact]
        public void the_publisher_says_whether_a_call_published()
        {
            var prepared = Bridge.PreparePublisher("_CreateValuationDate");
            var made = Bridge.Publish(prepared, 46276.0, 0.5);
            Assert.True(made.Owned);
            Assert.StartsWith("valuation_date:", (string)made.Value);
            var failed = Bridge.Publish(prepared, 46276.0, 1.5);
            Assert.False(failed.Owned);
            Assert.Equal("#ERROR _CreateValuationDate: ValueError: day_fraction_elapsed is number 1.5, expected a number from 0 to 1", failed.Value);
            var error = Bridge.Publish(prepared, ExcelError.ExcelErrorNA, 0.5);
            Assert.False(error.Owned);
            Assert.Equal(ExcelError.ExcelErrorNA, error.Value);
            Assert.Equal(Release.Released, Bridge.Release((string)made.Value));
        }

        // Release takes the one entry: the text then names nothing, a second release finds nothing,
        // and the live count moves down by one and no more.
        [Fact]
        public void release_takes_one_entry_and_a_second_release_finds_nothing()
        {
            var handle = (string)Seam.Call("_CreateValuationDate", 46276.0, 0.5);
            var (live, _) = Bridge.LiveHandles();
            Assert.Equal(Release.Released, Bridge.Release(handle));
            Assert.Equal(live - 1, Bridge.LiveHandles().Live);
            Assert.Equal("#ERROR util_ReadHandle: handle is text '" + handle + "' naming no live object, expected a handle", Seam.Call("util_ReadHandle", handle));
            Assert.Equal(Release.Missing, Bridge.Release(handle));
            Assert.Equal(Release.Missing, Bridge.Release("valuation_date:9999999"));
            Assert.Equal(live - 1, Bridge.LiveHandles().Live);
        }

        // Once the add-in is closing, a release is skipped and counted, the entry stays, and Python is
        // not called: the path a disconnect takes when Excel is quitting.
        [Fact]
        public void a_release_while_closing_is_skipped_and_reaches_no_python()
        {
            var handle = (string)Seam.Call("_CreateValuationDate", 46276.0, 0.5);
            var (live, _) = Bridge.LiveHandles();
            var skipped = System.Threading.Interlocked.Read(ref Lifetime.SkippedAtClose);
            Lifetime.Closing = true;
            try
            {
                Assert.Equal(Release.Skipped, Bridge.Release(handle));
                var publication = new Publication(() => new Outcome(handle, true), Bridge.Release);
                publication.Subscribe(new Observer());
                publication.Dispose();
                Assert.Equal(skipped + 1, System.Threading.Interlocked.Read(ref Lifetime.SkippedAtClose));
            }
            finally
            {
                Lifetime.Closing = false;
            }
            Assert.Equal(live, Bridge.LiveHandles().Live);
            Assert.Equal(Release.Released, Bridge.Release(handle));
        }

        // First delivery happens inside Subscribe, before it returns, and the creator runs once
        // however many subscribers arrive.
        [Fact]
        public void subscribe_creates_once_and_delivers_before_returning()
        {
            var log = new List<string>();
            var publication = new Publication(Once(new Outcome("curve:7", true), log), Releasing(log));
            var first = new Observer();
            var returned = publication.Subscribe(first);
            Assert.Same(publication, returned);
            Assert.Equal(new object[] { "curve:7" }, first.Values);
            Assert.Equal("curve:7", publication.Owned);
            var second = new Observer();
            publication.Subscribe(second);
            Assert.Equal(new object[] { "curve:7" }, second.Values);
            Assert.Equal(new[] { "create" }, log);
        }

        // Disposal releases the one publication it owns, once, however many times Excel calls it.
        [Fact]
        public void dispose_releases_once_however_often_it_is_called()
        {
            var log = new List<string>();
            var publication = new Publication(Once(new Outcome("curve:7", true), log), Releasing(log));
            publication.Subscribe(new Observer());
            publication.Dispose();
            publication.Dispose();
            Assert.Equal(new[] { "create", "release curve:7" }, log);
            Assert.Null(publication.Owned);
        }

        // A failure owns no publication, so its disposal releases nothing; and a publication never
        // subscribed owns nothing either.
        [Fact]
        public void a_failure_and_an_unsubscribed_publication_own_nothing()
        {
            var log = new List<string>();
            var failed = new Publication(Once(new Outcome("#ERROR MakeCurve: ValueError: as asked", false), log), Releasing(log));
            var observer = new Observer();
            failed.Subscribe(observer);
            failed.Dispose();
            Assert.Equal(new object[] { "#ERROR MakeCurve: ValueError: as asked" }, observer.Values);
            Assert.Equal(new[] { "create" }, log);
            var never = new Publication(Once(new Outcome("curve:8", true), log), Releasing(log));
            never.Dispose();
            Assert.Equal(new[] { "create" }, log);
        }

        // A value Excel cannot take leaves no orphan entry: the publication is released and the
        // failure goes on to the caller.
        [Fact]
        public void a_failed_delivery_releases_the_publication_and_rethrows()
        {
            var log = new List<string>();
            var publication = new Publication(Once(new Outcome("curve:9", true), log), Releasing(log));
            var observer = new Observer { Throws = new InvalidOperationException("Excel refused it") };
            var thrown = Assert.Throws<InvalidOperationException>(() => publication.Subscribe(observer));
            Assert.Equal("Excel refused it", thrown.Message);
            Assert.Equal(new[] { "create", "release curve:9" }, log);
            Assert.Null(publication.Owned);
        }

        // A release that fails is reported and counted, never swallowed and never thrown at Excel.
        [Fact]
        public void a_failing_release_is_counted_and_reported()
        {
            var errors = System.Threading.Interlocked.Read(ref Lifetime.DisposalErrors);
            var publication = new Publication(
                () => new Outcome("curve:10", true),
                text => throw new InvalidOperationException("the interpreter is gone"));
            publication.Subscribe(new Observer());
            publication.Dispose();
            Assert.Equal(errors + 1, System.Threading.Interlocked.Read(ref Lifetime.DisposalErrors));
            Assert.Contains("the interpreter is gone", Lifetime.LastDisposalError);
            Assert.Null(publication.Owned);
        }

        // A release the seam does not find is a miss, counted apart from a release.
        [Fact]
        public void a_release_that_finds_nothing_is_a_miss()
        {
            var releases = System.Threading.Interlocked.Read(ref Lifetime.Releases);
            var misses = System.Threading.Interlocked.Read(ref Lifetime.ReleaseMisses);
            var publication = new Publication(() => new Outcome("curve:11", true), Releasing(new List<string>(), Release.Missing));
            publication.Subscribe(new Observer());
            publication.Dispose();
            Assert.Equal(releases, System.Threading.Interlocked.Read(ref Lifetime.Releases));
            Assert.Equal(misses + 1, System.Threading.Interlocked.Read(ref Lifetime.ReleaseMisses));
        }

        // The specs' flag chooses the delegate: a creator's has the observed path behind it and the
        // same parameters, a consumer's the plain path.
        [Fact]
        public void the_observed_delegate_has_one_parameter_per_argument()
        {
            var observed = Registration.MakeObservedDelegate(Bridge.PreparePublisher("_CreateValuationDate"), 2);
            Assert.Equal(2, observed.GetType().GetMethod("Invoke").GetParameters().Length);
        }

        // The status function's report names every count; the live count is the store's.
        [Fact]
        public void the_report_names_every_count()
        {
            var report = Status.GoosedoveHandles();
            Assert.StartsWith("live ", report);
            foreach (var word in new[] { "; price bytes ", "; published ", "; reused ", "; released ", "; release misses ", "; disposal errors ", "; skipped at close " })
            {
                Assert.Contains(word, report);
            }
        }
    }
}
