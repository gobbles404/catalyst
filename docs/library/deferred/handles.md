# Handles and object retention: deferred research

Set aside for a later discussion. These notes are preserved for reference and are
outside the active [library planning review](../README.md). Constructor handle
outputs remain specified; no handle mechanism or lifetime policy has been chosen.

Reviewed 2026-09-12 against Excel-DNA's `v1.9.0-Release` tag, commit
`fb3c19e2def68c6c64d6fece13daa9efd36a2748`, and this repository's current host.
This records available machinery and design questions. It does not select a
handle architecture, authorize implementation, or report new smoke-test results.

A handle is text in Excel that identifies an object retained in memory. The
library's functions should receive the corresponding typed Python object after
resolution at the seam. Handles are infrastructure shared across the library;
they are not a Globals-specific hierarchy.

## Reuse proposal set aside from the ValuationDate draft

Desired reuse proposal: identical inputs share one retained object and handle;
changing either field produces a distinct object while previously published
records stay unchanged. The lifetime over which reuse is promised remains open.
This is not a guarantee of permanent handle identity or current Excel-DNA
behavior. Python tests would inspect the published records.

Retaining one object does not prove the builder ran only once. Future handle work
needs to count construction, lookup, storage, hashing, and conversion where
performed, and establish the applicable budgets. Handle spelling, storage
ownership, retention, reclamation, and restart behavior remain undecided.

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

**A live creator formula and a copied handle string are different.** Native lookup
does not add a subscription or ownership count. Source inspection therefore
indicates that pasted handle text, ordinary consumers, and downstream .NET
references do not retain the producer's subscription. Clearing the final creator
can remove the entry and dispose its stored object. Verify the worksheet behavior
before promising a policy to users.

Native reuse is based on the active call's inputs, not on the contents of the
returned record. For example, different capitalization of a header can produce a
different native key even though our library interprets both headers identically.
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
| [Registration](../../../host/Goosedove.Host/AddIn.cs) builds all-`object` delegates and calls `ExcelIntegration.RegisterDelegates`. | Supply declared object argument/result metadata and apply native handle processing during prepared registration. The current low-level call does not activate it. |
| [Bridge metadata](../../../src/goosedove/excel/bridge.py) exports names, descriptions, parameter names, and hidden status. Its declared inputs/results do not include retained domain objects. | Add object type information at the seam without exposing bridge types inside the numerical library. |
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

If another retained Python record depends on that object, it needs its own strong
Python reference. Releasing the creator owner's reference then need not destroy
the underlying object. Holding the same disposable C# wrapper is not equivalent
to owning an independent Python reference.

For dynamic registration, the public [ExcelRegistration API][api] provides
`ProcessFunctions()` and `RegisterFunctions()` as separate steps. The latter alone
does not apply the handle transformations. Any future adaptation must preserve
our existing strict missing/blank/type behavior; enabling the extended pipeline
is not evidence of equivalent seam behavior.

## Candidate smoke coverage for later agreement

These are review questions for a small diagnostic experiment, not new product
functions or committed acceptance guarantees:

- Create and resolve a retained Python object; verify the original record and
  NumPy arrays survive between calls without a data copy.
- Recalculate unchanged inputs and place identical creator formulas in two cells;
  count construction and live owners. Change a scalar and an array element.
- Clear one creator and then the final creator; observe release counts. Exercise
  copied-as-value handles and invalid/wrong-kind handles.
- Fail construction and confirm that no retained entry is published and the
  established error remains visible in Excel.
- Retain a Python dependency from another object, remove its creator formula, and
  establish the difference between dependency lifetime and handle lifetime.
- Close a sheet/workbook and exit Excel; test formula reconstruction and saved
  handle text in a fresh runtime. Observe cleanup rather than assuming it.

Use deterministic counts for work and ownership assertions. Upstream Excel-DNA
[reuse tests][reuse-tests] and [disposal tests][dispose-tests] establish intended
native behavior, but were inspected rather than run here. Existing repository
checks exercise the current seam; they do not cover this proposed integration.

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
