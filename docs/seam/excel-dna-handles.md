# Excel-DNA and handles: the evidence

What Excel-DNA 1.9 supplies for holding an object behind text in a cell, read from its
source at the `v1.9.0-Release` tag, commit `fb3c19e2def68c6c64d6fece13daa9efd36a2748`, on
2026-09-12. It selects nothing: the spec is [handles.md](handles.md). Native call reuse below is
evidence about Excel-DNA, not proof that it meets every ownership rule the spec asks for.

## What Excel-DNA 1.9 supplies

The host already references `ExcelDna.AddIn` 1.9.0. Extended registration is part
of that version; a separate registration package is not needed for this feature.
`[ExcelHandle]` can mark returns, parameters, or .NET types. Return processing
publishes a text handle to a retained .NET object; parameter processing resolves
the handle back to an object. See the [release notes][release] and
[extended-registration guide][guide].

The tagged implementation supplies:

| Capability | Evidence and limit |
|---|---|
| Object storage and lookup | `ObjectHandler` holds a concurrent dictionary and exposes `TryGetObject` and `Remove`. This is an existing store we can evaluate before creating another. |
| Handle naming | `HandleInfo` generates `tag:counter`, using an incrementing counter. Treat the text as opaque; it is not a content digest or a persistent identifier. |
| Reuse of live calls | Function name and argument values identify an active call. Arrays are hashed and compared by their elements. Matching active calls can reuse the existing object and handle. |
| Delayed construction | Automatic return-handle registration wraps the constructor so its body is evaluated when a new tracked object is needed. Reuse is not just discarding a newly built duplicate. |
| Normal cleanup | The handle is published through Excel's RTD subscription mechanism. When its last creator subscription disconnects, the object is removed and `IDisposable.Dispose()` is called if implemented. |

These details come from [ObjectHandler][store], [HandleInfo][handle],
[object-handle registration][registration], [LazyLambda][lazy], and
[call tracking and equality][observer]. RTD supplies Excel's subscription tracking
here; using it does not require the pricing library to become a live-feed system.

There are two public `GetHandle` paths in the tagged source. The overload taking
function name, arguments, and object uses tracked observation. The overload taking
only a tag and object adds a manual entry without that automatic subscription
lifetime. They must not be treated as equivalent. The lazy construction wrapper
used by automatic registration is internal; eagerly creating an object before a
manual call does not itself provide construction reuse.

## Retention, identity, and memory limits

The spec once required distinct objects and handles for separate creator formulas even
with equal inputs; since the handles page's #114 it accepts native function-and-argument
sharing between creator cells, while separate trade rows within a batch stay separate
objects, which the native return transformation's per-row spill does not give. That
changes what must be tested, not the source facts below.

Native lookup does not add a subscription or ownership count. Pasted text is
outside our supported worksheet workflow. Ordinary consumers refer to creator
cells or names, and rely on those creators' ownership; the lookup itself does not
retain the producer's subscription. Clearing the final creator can remove the
entry and dispose its stored object. A downstream .NET reference does not prevent
that disposal, so retained Python dependencies need their own owned references.
Verify this integration rather than equating Excel dependencies with Python
reference counts.

Native reuse is based on the active call's inputs, not on the contents of the
returned record. For example, different capitalization of a header can produce a
different native key even though the agreed header contract treats both names
identically.
After disposal, equal inputs can receive a new handle. The counter also has no
session identifier, so a saved handle string is not guaranteed to be rejected in
a later session merely because it came from an earlier one. Domain content
identity and stale-handle behavior remain separate design questions.

Reuse does not make input processing free. Excel-DNA retains arguments for the
active key and hashes/compares array contents. A retained curve may therefore
coexist with managed input arrays used for tracking. Measure allocations,
construction, transport, and hashing before claiming a memory or work budget.
The first concurrent calls also need scrutiny before promising exactly one
construction: the observable factory runs before the registration lock's second
lookup in the tagged source. This is a source-derived concern, not an observed
failure in our host.

Workbook-close and Excel-quit cleanup remain unverified. Microsoft documents an
RTD path in which `ServerTerminate` occurs without individual topic disconnects.
The tagged observer-server termination method does not walk the subscriptions
and dispose each object. Do not infer deterministic cleanup for that path from
ordinary formula-deletion behavior. See [Microsoft's RTD explanation][rtd],
[observer termination][observer], and [base server termination][server].

## Fit to the existing C# / Python seam

The following are integration gaps, not implementation decisions:

| Current behavior | Question to resolve |
|---|---|
| [Registration](../../host/Goosedove.Host/AddIn.cs) builds all-`object` delegates and calls `ExcelIntegration.RegisterDelegates`. | Supply declared object argument/result metadata and apply native handle processing during prepared registration. The current low-level call does not activate it. |
| [The bridge](../../src/goosedove/excel/bridge.py) declares `Handle[Kind]` since #53 and keeps the objects in one Python store, keyed by the handle's text, with the host carrying only that text. | A C# store would have to take over owned Python references from the store that already holds them; the Python store needs the host's lifecycle notifications and nothing else. |
| The host disposes the returned `PyObject` wrapper after scalar/array conversion. | An owner retained by Excel-DNA must acquire its own Python reference or explicitly receive ownership. It cannot retain the wrapper that the existing path disposes. |
| Incoming arguments are temporary Python references released after each call. | Resolve and unwrap a retained owner to a temporary reference to the actual Python object, instead of passing a CLR proxy or disposing the owner's retained reference. |
| Errors currently travel as visible `#ERROR ...` strings. | Failed construction must remain an error and publish no object. Blindly marking an all-`object` result as a handle could retain an error string. |
| Native missing-handle conversion returns an invalid-handle sentinel, and its typed casts only distinguish .NET types. | Preserve useful unknown/expired/wrong-kind errors at our seam, including distinction between Python object kinds. |
| `AutoClose()` currently leaves Python cleanup to process exit. | Establish lifetime and shutdown ordering before relying on callbacks that release Python references. |

A candidate is a small managed owner of one Python object, retained by the native
store. The Python record would own its NumPy arrays. Python.NET's public
`PyObject.NewReference()` acquires a reference without copying that data;
`Dispose()` releases the reference and must be used under the Python interpreter
lock while the runtime is alive. See [the pinned Python.NET implementation][pyobject]
and [embedding guidance][pythonnet]. A second Python dictionary mapping handle
strings to objects has not been shown necessary.

The current [buffer input path](../../src/goosedove/excel/bridge.py) already
copies the host's reusable buffers into Python-owned NumPy arrays. Existing
[ownership tests](../../tests/unit/test_bridge.py) verify that overwriting the
host buffers does not change those arrays, and the
[work budget](../../tests/performance/test_seam_budgets.py) pins two copies.
Retention alone does not require another defensive copy. The arrays are writable,
however: retaining a reference is not the same as establishing immutable contents.
Final construction must establish ownership and eliminate writable aliases once.
Views can retain larger backing arrays, so retained size is an ownership question,
not simply the sum of every visible array's element bytes.

If another retained Python record depends on that object, it needs its own strong
Python reference. Releasing the creator owner's reference then need not destroy
the underlying object. Holding the same disposable C# wrapper is not equivalent
to owning an independent Python reference.

For dynamic registration, the public [ExcelRegistration API][api] provides
`ProcessFunctions()` and `RegisterFunctions()` as separate steps. The latter alone
does not apply the handle transformations. Any future adaptation must preserve
our existing strict missing/blank/type behavior; enabling the extended pipeline
is not evidence of equivalent seam behavior.

## Removal and recalculation

Microsoft describes recalculation through worksheet dependencies and explicit
calculation requests. A failed lookup of text in our private object store does
not automatically mark its creator for recalculation. The host can schedule
Excel work, including through `ExcelAsyncUtil.QueueAsMacro`, but this is not an
automatic missing-object recovery protocol. See [Excel recalculation][calculation]
and [Excel-DNA scheduled work][scheduled-work].

There is a sharper distinction in the tagged native source. Manually calling
`ObjectHandler.Remove` removes/disposes the object without invalidating the
active observable call state. An unchanged creator call can follow the existing
state shortcut and return its cached handle without invoking the factory. A full
recalculation therefore is not a guaranteed repair while that state survives.
Normal RTD disconnection removes the call state and key as well as unsubscribing;
that permits a later call to construct again. See [object removal][store] and
[the lookup/disconnection paths][observer]. This is source-derived, not a live
recovery test in Goosedove.

## Lessons considered from an earlier handle system

Two engineer retrospectives from an earlier handle system were read during planning; their
timing and soak figures are that project's, not Goosedove measurements, and are not kept
here, and the mechanisms they recommend are not instructions.

Their useful distinction is between object references, equivalent economic
content, calculation reuse, and lifetime. Content-idempotent publication can
reuse an already-live equivalent object, but recognizing it after construction
does not avoid the preparation that already happened. Native argument-based reuse
can happen earlier; normalization can make different raw inputs economically
equivalent. That is a separate equality/reuse decision, not automatic proof of an
incorrect result.

Carry forward the ordinary Excel editing scenarios, visible failures, immutable
owned data, and measurement of the whole call. Avoid importing per-publication
store scans, duplicated size derivations, or a collector whose diagnostics create
owners. If fingerprints become necessary, use finalized typed content and retain
required identity/size facts; do not repeatedly traverse objects during lookup.
Simpler publication still needs safe release of temporary Python references on
failure. No reservation system or replacement fingerprint framework is selected.

The live-object eviction warning does not rule out releasing objects proven
unused, nor optional result-cache eviction when inputs remain available. Our
agreed Excel workflow excludes independently managed pasted handle strings.
It also follows this repository's existing no-reload and explicit-dependency
rules; another project's singleton/reload machinery is not a requirement here.

## The live tests of 26 September 2026

Two rounds of tests in hidden Excel processes, on Excel 16.0.20326.20158 with Excel-DNA 1.9.0,
Python.NET 3.1.0 and Python 3.13, Excel's live-data throttle left at 2,000 ms: the first
against `ffbbd43`, the second against main at `68f95d9`, with the index's name and the new
handle text. Both drove the real creators and the real bridge beneath an experimental adapter
built on `ExcelAsyncUtil.Observe`: a publication object whose `Subscribe` runs the prepared
call once, hands the value to Excel before returning and never completes on its own, and whose
`Dispose` asks the seam to release the one text it owns. The adapter, its second lookup of the
store and its test-only release are evidence of the approach, not the production change;
nothing in the repository changed for them.

| What was tested | What held |
|---|---|
| a thousand changed updates of a 150-price vector and its market, in bursts | at every settled checkpoint, 250 to 1,000, three store entries, one live quote array of 1,200 bytes and one history and calendar; all 2,003 publications released when the last workbook closed, none twice, with Python still running; a new workbook in the same process then worked and the count went on |
| a thousand updates of a two-price vector, unchanged recalculation, equal creators sharing then diverging, a retained old market, invalid inputs and recovery, nested and conditional creators, manual calculation without a move | 93 checks held; 2,019 publications released at the last close, none twice |
| the first result handed over inside `Subscribe`, against 50 ms after the first return, twenty inputs a second apart | inside: a handle on every first return and the market current on all 80 observations; after: `#N/A` on every first return and on 76 of 80 observations, catching up now and then and fully once the feed stopped |
| a creator cut to another cell in manual calculation mode | about 0.4 s after the cut Excel called `DisconnectData` for the moved creator's topic and others on the sheet, then `ServerTerminate`; the old texts named nothing while the cells still showed them; F9, Ctrl+Alt+F9 and Ctrl+Alt+Shift+F9 each rebuilt the chain, and later prices propagated through two such recoveries; the same happened with Excel-DNA's own handles and no Python |
| the same cut in automatic calculation mode, and manual mode without a move | the publications stayed valid |
| two sheets, and two workbooks, one creator cut in one of them | the other kept its publications and the shared history alive; a full calculation restored the cut one's |
| quitting Excel with three live publications | every disposal arrived and the process exited normally, once; not a guarantee that a disconnect arrives for every topic at quit |

The correction to the first round: it read the cells too soon. Excel's callbacks arrive after
the edit returns, so an immediate successful lookup said nothing about the subscription's
survival, and the long editing sequence the first explanation named was never needed; a single
cut in manual mode reproduces the disconnects. Three entries and 1,200 bytes are the fixture's
baseline after it removed eight setup publications no formula owned, not a target for a real
workbook; the transient peak of 293 entries in the first round is neither a bound nor an
acceptable steady state, since it settled.

The research's scripts and logs stayed in the owner's Codex workspace, `work/lifecycle-validation`
and the temporary folders its findings name. What the repository keeps is the build's own:
`tools/excel_lifetime.ps1`, whose groups replay the scenarios above through the production
registration, and `tools/performance/handle_retention.ps1`, the thousand-update run.

## Verification status

The [acceptance scenarios](handles.md#acceptance-scenarios) are built in #114 and verified
through the production registration by `tools/excel_lifetime.ps1`, whose `core` group runs in
`check.ps1` and whose other groups ran before the merge, and by
`tools/performance/handle_retention.ps1`; the pull request records the counts and the Excel
build. Upstream Excel-DNA [reuse tests][reuse-tests] and [disposal tests][dispose-tests]
establish intended native behavior but were inspected rather than run here.

[release]: https://excel-dna.net/docs/release-notes-1-9/#object-handle-support-with-excelhandle
[guide]: https://excel-dna.net/docs/guides-basic/extended-registration/#object-handles
[store]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/ExcelDna.Integration/ObjectHandles/ObjectHandler.cs
[handle]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/ExcelDna.Integration/ObjectHandles/HandleInfo.cs
[registration]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/ExcelDna.Integration/ObjectHandles/ObjectHandleRegistration.cs
[lazy]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/ExcelDna.Integration/ObjectHandles/LazyLambda.cs
[observer]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/ExcelDna.Integration/ExcelRtdObserver.cs
[server]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/ExcelDna.Integration/ExcelRtdServer.cs
[rtd]: https://learn.microsoft.com/en-us/previous-versions/office/troubleshoot/office-developer/create-realtimedata-server-in-excel
[api]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/ExcelDna.Integration/Registration/ExcelRegistration.cs
[pyobject]: https://github.com/pythonnet/pythonnet/blob/3d76836e80284aae8abcac92e1676d7d83178ec1/src/runtime/PythonTypes/PyObject.cs
[pythonnet]: https://pythonnet.github.io/pythonnet/dotnet.html
[reuse-tests]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/Tests/ExcelDna.RuntimeTests/Registration.cs#L314-L359
[dispose-tests]: https://github.com/Excel-DNA/ExcelDna/blob/fb3c19e2def68c6c64d6fece13daa9efd36a2748/Source/Tests/ExcelDna.RuntimeTests/ObjectHandleOutOfProcess.cs#L34-L76
[calculation]: https://learn.microsoft.com/en-us/office/client-developer/excel/excel-recalculation
[scheduled-work]: https://excel-dna.net/docs/guides-advanced/performing-asynchronous-work/
