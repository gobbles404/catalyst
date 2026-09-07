# Architecture review — goosedove

*Reviewed at commit `fb5f274`, September 2026. A commodities derivatives pricing and risk library for
Excel, written in Python 3.13 and hosted in-process by an Excel-DNA add-in through pythonnet.*

## Summary

The smoke test works, and it works for the right reasons. Someone thought about the seam before building
it: numeric ranges cross as one pinned buffer rather than cell by cell, results come back as spilled
blocks, worksheet functions are declared in Python and registered from Python, and there is already a
vocabulary for counting work. That is a better starting point than most pricing libraries have after a
year.

Four things came out of reading it closely and measuring it.

**The traversal thesis is right, and I can put numbers on it.** Measured on this stack (Appendix A):
pricing 50,000 trades as objects rather than columns costs **9x**; aggregating them by book and delivery
month costs **83x**; counting business days one date at a time costs **100x**. The kernel gap is real and
modest. The traversal gap is the one that decides whether a book revalues in 30 ms or 3 s.

**But two obvious fixes for traversal are wrong, and both were nearly in this document.** First: "give
every kernel a leading scenario axis so one call covers all the bumps" buys **1.16x** on a realistic delta
ladder and costs 60x the memory; knowing *which risk factors touch which trades* buys **35x** for nothing
(A.7). Second: "make the block as big as possible" saturates. Moving a million cells costs 5,257 ms at one
cell per call, 6.5 ms at a thousand, and **1.29 ms at ten thousand — after which more block buys nothing
at all** (A.10) while the return path amplifies 8 bytes of payload into roughly 80 bytes of transient
allocation. Fewer calls is not less work. The right unit is *one derivation per group*, chunked at around
10^4 cells — not "one call for everything".

**The most serious problem in the code today is not performance.** `AddIn.cs:90` maps every Excel error
value to `None`, the same value a blank cell gets, so `=Price(A1)` where `A1` is `#N/A` prices as though
`A1` were empty. Outbound, errors leave as text that `IFERROR` cannot see (`bridge.py:62`), and a blank
cell round-trips back out as `#N/A` (`AddIn.cs:181` then `:151`). Two of those are one-line fixes and
should be made this week.

**The discipline has no witness.** `counter.hit(KERNEL)` is a claim, not an observation: a kernel that
loops per item and reports `KERNEL: 1` passes every budget test in the repo and every budget test this
review could propose. There is a fix, it is about twenty-five lines of standard library, and I verified it
works on this exact code (Section 4). It is the single highest-value thing to build before the first
kernel.

**What to settle before the first pricing function lands.** Not much, and less than I expected when I
started. The worksheet function *name*, because a workbook is a caller you cannot refactor (D1). That
market data never arrives as a raw range (D2). The time axes, including the one everybody forgets (D3).
That declared trade economics are the source of truth and the incidence matrix is derived from them (D4).
Everything else on the list is either a one-line fix now or genuinely cheap to defer, and Section 8 says
so explicitly, because the most useful thing an architecture review of an empty repository can do is
refuse to fill it.

### How this review was produced, and what that is worth

Fourteen independent reviewers each took one dimension and read the whole repository. Each dimension's
blocking and major findings then went to a separate adversarial reviewer whose only job was to refute
them, from three angles: is the evidence real, is the concern premature, is there a better
recommendation. Three critics — a quant developer who has shipped Excel add-ins, a performance engineer
crossed with a sceptic, and a model validator — then attacked the combined result. Ninety findings were
graded blocking or major; **thirty-four did not survive refutation and are not in this document.**
Several that did survive appear here in the refuter's corrected form rather than the original.

Separately, I benchmarked the repository's own code rather than assuming the thesis. Those numbers are
Appendix A. Three of them changed conclusions I had already written down, including two of my own
headline recommendations — the scenario axis and "one call per block" — so the appendix is not
decoration.

Every claim in this document is either a line reference you can check or a measurement you can rerun.

---

## What is here today

About 250 lines of Python, 280 lines of C#, and 13 passing tests.

- **`host/Goosedove.Host/AddIn.cs`** — an Excel-DNA add-in on `net48` hosting CPython through pythonnet
  3.1. It starts Python, reads `goosedove.cfg` for the interpreter and path, imports
  `goosedove.excel.bridge`, asks it what functions exist, and compiles an Excel-DNA delegate per function
  with `Expression.Compile`. Numeric ranges cross as one pinned `double[]`; anything else crosses cell by
  cell as nested `PyList`s. numpy results return through the buffer protocol and spill.
- **`src/goosedove/excel/bridge.py`** — the whole Python side of the seam: a decorator registry, a spec
  function, a dispatcher, and three demonstration worksheet functions.
- **`src/goosedove/instrumentation/work_counts.py`** — `WorkCounter` and a frozen `WorkCounts` snapshot,
  with four counter names.
- **`tests/`** — 13 tests, one of them a property test, three of them work budgets over a stand-in pricer.
- CI runs format, lint, `pyright` strict and pytest on `windows-2022`, and separately builds the host.

There is no domain code: no curves, no calendars, no instruments, no models, no risk. That is the point,
and it is why this is the right moment.

---

## 1. The traversal thesis, measured — and where it actually points

The intuition is correct. Appendix A puts numbers on it against this repository's own code:

| | per-item | bulk | ratio |
|---|---|---|---|
| price 50,000 trades | 22.8 ms (objects) | 2.4 ms (columns) | 9x |
| aggregate by book x delivery month | 11.3 ms (dict walk) | 0.14 ms (`np.bincount`) | **83x** |
| 200,000 curve lookups | 6.13 ms (`dict[str, float]`) | 0.19 ms (fancy index) | 32x |
| 200,000 interpolations | 109.9 ms (loop) | 9.42 ms (`np.interp`) | 12x |
| 50,000 business-day counts | 104 ms (per date) | 1.04 ms (`np.busday_count`) | **100x** |
| implied vol, 5,000 options | 158 ms (`brentq` per option) | 12.9 ms (vectorised bisection) | 12x |
| `SumRange` over 10,000 cells | 599 us (nested list) | 11.9 us (ndarray) | 52x |

The kernel gap is 9x. The traversal gap is 83x to 100x. That is the thesis, on your stack.

### Where the naive reading of it goes wrong

**The saving from bigger blocks saturates, and past the saturation point it costs memory.** A.10 measures
the total cost of moving a million cells at each chunk size:

| chunk | calls | total |
|---|---|---|
| 1 | 1,000,000 | 5,257 ms |
| 100 | 10,000 | 51.8 ms |
| 1,000 | 1,000 | 6.5 ms |
| **10,000** | **100** | **1.29 ms** |
| 1,000,000 | 1 | 1.30 ms |

Going from a chunk of 10^4 to a chunk of 10^6 saves nothing measurable, while the return path
(`AddIn.cs:134-155`) allocates a `byte[]`, then a `double[]`, then an `object[,]`, then boxes every
non-NaN cell — roughly 80 bytes of transient per 8 bytes of payload, inside Excel's own process. So the
design rule is **chunk, not "one call"**, and the budget assertion is `crossings == ceil(cells / CHUNK)`,
not `crossings == 1`. Pick `CHUNK` from a committed measurement rather than a guess; on this box the
crossing cost falls below 1% of the kernel somewhere between 10^3 and 10^4.

**The million-cell headline is not a workbook anyone maintains.** A large blotter is 10^3 to 10^4 pricing
*cells*, with 10^6 elements living *inside* those calls. At that scale per-call dispatch (0.287 us of
Python, A.1) is tens of milliseconds and does not matter. What matters is **re-derivation**: rebuilding
the same forward curve once per row, five thousand times. The requirement is *one derivation per group*,
and framing it as call-count reduction points the design at collapsing calls that were never the problem.

**And the result shape is a layout decision the library does not own.** A commodities blotter is rows the
trader owns: they insert a trade mid-list, sort by counterparty, put a comment column beside the PV. A
spilled block cannot interleave with those columns, does not follow an inserted row, and returns
`#SPILL!` when anything is in the way — including the trader's own note. So the first real user puts a
formula on every row, which is exactly the per-cell shape the architecture was built to avoid.

**The reachable design is therefore neither one call per block nor one call per cell: it is per-cell calls
that share one group derivation.** The row's arguments name the group (a snapshot identity, a portfolio
identity) and the row within it (a trade id the trader already has) — never a re-marshalled slice of the
blotter. The first call of a calculation cycle derives the whole group; the other 4,999 are lookups. The
budget that expresses this is **5,000 crossings and one KERNEL**, and it is a shape that neither the dense
scenario-axis design nor the pure-block design can state. Keep block returns for things that genuinely
want their own region — a delta ladder, a curve — and say so, rather than making spill normative.

**One more caution about output size.** Every ratio in this review is Python-side. Excel charges per cell
*written* — calc-engine dispatch per formula, an `XLOPER12` per returned cell, the spill write. A risk UDF
returning a 5,000x60 detail block pays 300,000 cell-writes to display a number nobody reads. Measure it
once (`tools/excel_dev.ps1` already registers the `.xll` into a live Excel; fill a sheet with N
`ScaleBlock` formulas and time `Application.CalculateFull` against N), then state the vocabulary rule that
follows: pricing and risk functions return aggregates at the granularity asked for, and trade-level detail
is an opt-in second function.

---

## 2. The decisions that are actually expensive to reverse

Ten of them. Each names the alternative I rejected, because a recommendation without a rejected
alternative is a preference. This list is much shorter than the one I first drafted; Section 8 says what
came off it and why.

### D1 — The worksheet function name is the one genuinely irreversible bit

`_FUNCTIONS[fn.__name__]` (`bridge.py:44`) welds Excel's function namespace to Python identifiers. Excel
has a single global function namespace shared with every other add-in the user has installed, and `Add`
and `SumRange` are already in it (`bridge.py:76`, `:86`).

This matters more than it looks because of CLAUDE.md:18 — "no compatibility shims; cut over and let stale
callers fail". That rule is right for a library whose callers are modules. **A workbook is a caller you
cannot refactor**, sitting on a trader's desk, possibly emailed to a counterparty. Renaming a function
after release breaks sheets you will never see.

**Recommendation.** Decide the naming convention now — a prefix (`GD.Price`) plus an explicit `Category`,
and a rule that the Excel name is declared, not inferred from the Python identifier, so renaming a Python
function is not a workbook-visible event. Write the carve-out into CLAUDE.md: the "let stale callers fail"
rule stops at the worksheet surface. Also add a comment at `AddIn.cs:224` recording that `IsVolatile` is
never set, deliberately (D10).

**Rejected: widening `function_specs()` into a versioned record now.** I drafted this and it did not
survive. The argument for it was that the `.xll` and the Python package are independently deployed
artifacts — but that deployment does not exist: CI builds both halves from one commit, uploads nothing,
and tags nothing. Until there is a release process, the 3-tuple is an internal protocol between two files
in one repository, changeable in one commit. Do the name; leave the spec format alone.

**Also rejected: the handle/token model as the primary evaluation mechanism.** It is the classic way to
get batching and laziness into Excel, `pyproject.toml` already says "a lazy pricing library", and I
recommended it in an earlier draft. Three things killed it. Excel only recalculates a dependent when a
precedent's *value* changes, so a stable handle string leaves downstream cells silently stale. Making the
handle content-dependent means hashing the payload on every construction — 126 ms for 76 MiB (A.4) — which
is the traversal problem in a costume. And handles *coarsen* invalidation: per-cell range arguments give
Excel precise dirty propagation, so funnelling 200 curve cells through one `Snapshot(...)` means nudging
one mark dirties everything downstream, converting a partial recalc into a full one. Handles win when a
whole curve refreshes at once and lose when single points are tweaked, and nobody can know which pattern
this library serves before it has users. The honest deliverable today is one sentence, not a scheme:
*no domain function takes a raw range where it will later take a handle.*

### D2 — Market data never arrives as a raw range

Related to D1 but separable, and this one I would commit to.

Two facts about a real desk make it necessary. Inputs **tick**: Bloomberg or Refinitiv RTD cells refresh
many times a minute and hardest into settlement, so any identity derived from the contents of a range
containing a ticking cell changes on every tick and the cache hit rate is zero exactly when the desk is
busiest. And market data has a **source**: `numeric_block` (`bridge.py:26`) is currently the entire
market-data ingress, fed by whatever an analyst pasted, so no identity scheme can ever say "this is ICE
settle for 2026-09-05, revision 2" rather than "these bytes".

**Recommendation.** One written rule, costing zero lines today: pricing functions consume a *snapshot*,
never a live range. A snapshot is built by a single builder function whose arguments include an explicit
refresh trigger the user or a timer controls, and it carries a small provenance record — source id,
instrument set, as-of, knowledge time, revision, ingest time, actor — that crosses the seam once as
scalars, not per cell, so it costs nothing against a 7.6 MiB payload. Manual data is legitimate and
common; it enters through the same door stamped `source='manual'` with the workbook and user recorded,
rather than being indistinguishable from a vendor feed.

Two consequences worth committing to at the same time, because both are one field now and a repo-wide
change later. Base snapshots are **immutable** — arrays `setflags(write=False)` at construction, which is
normalisation, not verification, so it stays inside the house rules. And an *effective* snapshot is a base
snapshot plus an ordered adjustment set, each adjustment carrying target, old value, new value, reason,
actor and effective window. Official marks get adjusted — IPV overlays, manual marks on illiquid points,
model reserves — and with no representation for them the only available mechanism is typing over the input
range, which destroys the base data and makes any digest certify the overridden values as the vendor's.
Build no UI and no approval workflow. Reserve the field and write the rule.

### D3 — Time is three axes, and the third one is the one people forget

**Observation day** and **delivery period** are different axes and must not collapse into one date type.
A commodity contract prices as an average over business days in a delivery month; the observation axis and
the delivery axis have different lengths, different calendars, and different roll rules.

The third is **knowledge time**. Exchange settlements are corrected, assessment agencies reissue, a broker
mark is fixed the next morning. Reproducing the 30 June official mark means using *what was known on
30 June*, not today's corrected series — which will produce a different and entirely defensible wrong
answer. A curve keyed only by as-of physically cannot answer both questions, and the knowledge axis can
never be recovered retrospectively because the original values were overwritten.

**Recommendation.** Market-data identity is `(source, instrument set, effective as_of, knowledge_time,
revision)` from the first curve, with revision monotone per `(source, as_of)` and the original never
overwritten. Both queries must be expressible and distinguishable in an evaluation record: *as-of-latest*
(today's best view of 30 June) and *as-known* (30 June as it stood at 18:00 that day). A valuation pins
`knowledge_time` explicitly rather than defaulting to now, so a restatement is a deliberate second run
rather than an accident. Extend the same treatment to holiday tables and conventions: a historical
revaluation must pin the calendar revision that was in force, not silently use HEAD's.

**Representation, and it is not a close call.** Dates as `datetime64[D]` arrays; delivery periods as
integer `(start_day, end_day)` pairs, which makes monthly, quarterly, seasonal and cal-year the same type
with different bounds; contract months as one sortable integer (`year * 12 + month`) that indexes directly
into a curve column; calendars as `np.busdaycalendar` with business-day arithmetic through
`np.busday_count` and `np.busday_offset`; and expiry rules as **data, not code** — "three business days
before the 25th of the month preceding delivery" is a row with an anchor, an offset, a calendar id and a
direction. WTI, Brent, TTF, JKM, NBP and Henry Hub all differ, and one table row each beats one function
each.

**Rejected: pandas offsets, `workalendar`, `exchange_calendars`.** All correct, all maintained, all
scalar. Each makes "the business days in this delivery month" a Python loop over date objects, which A.9
prices at 100x. numpy's busday machinery is array-first and already installed; the missing piece is only
the holiday tables, which are data you must own anyway because desks disagree about them. Keep them as
reviewed goldens.

**Rejected: an integer day-number `NewType` as the single time type.** It erases the distinction between
the observation and delivery axes, which is the one distinction that matters here.

### D4 — Declared economics are the truth; the incidence matrix is derived

This is where A.7's 35x actually lives, and it needs one correction to be safe.

The performance insight: a commodity swap's payoff is a weighted average over pricing days and contracts.
That same sparse `(trade x contract)` weight matrix *is* the averaging definition, *is* the risk-factor
incidence, and *is* the batching key. Three things, one structure — which is why a delta ladder over
60 buckets can be 2 kernel calls rather than 61.

The correction, and it matters: **if the weight matrix is the definition, the term sheet is no longer
legible anywhere in the system.** A validator cannot read the trade's economics, a booking error in the
weights is invisible, and there is nothing to reconcile against trade capture. So: keep declared economic
terms — contract, period, averaging convention *by name*, calendar — as the recorded source of truth, make
the incidence matrix a derived artefact, and write the test that re-derives it from the terms. That
preserves the whole 35x argument while keeping the trade reviewable.

**Recommendation.** A portfolio is a set of parallel numpy columns plus a group index; a per-trade object,
if one exists, exists only at the Excel boundary to parse one row and is destroyed immediately. Add the
companion sentence to the house rules next to CLAUDE.md:17: *domain code takes columns and returns
columns*, and *fewer kernel calls is not the same as less work.* Then write the budget test before the
first risk function exists:

```python
def test_delta_ladder_is_flat_in_the_number_of_buckets() -> None:
    counter = WorkCounter()
    delta_ladder(book, snapshot, buckets=60, counter=counter)
    assert counter.freeze()[KERNEL] == 2  # not 61, and not 1-with-60x-memory
```

**Rejected: mandating a kernel signature now** (`price(terms, market, rows, shifts, shift_factor_ix,
counter)`, or a CSR `indptr`/`indices` layout). The sparsity pattern that would decide between them is a
property of instruments that do not exist. The insight is worth a sentence in CLAUDE.md; the signature is
not yet knowable.

**Rejected: a class per instrument with a `price()` method.** It reads beautifully and it makes "no
per-item loops" unenforceable, because the loop moves into the `for trade in book` that every caller
writes.

### D5 — Units need a runtime carrier; `NewType` alone will not do it

CLAUDE.md says "`NewType` for units and digests". For digests that is exactly right. For units it is not,
and it is cheaper to know now than after fifty signatures.

`NewType` is erased at runtime and does not survive arithmetic — `Barrels(a) * 2` is a `float` — and it
cannot annotate the elements of an array. Meanwhile a commodities library converts bbl to MT with a
**grade-specific density that is itself a market quote**, not a constant; MMBtu to MWh with a fixed
factor; therms to GJ. Getting one wrong is a seven-figure error that no erased type will catch.

**Recommendation.** Keep `NewType` for digests and identifiers. Carry units at runtime **on the
container**, not on the number: a `Quantity` of `(values: NDArray[float64], unit: Unit, grade, period)`,
where `Unit` is an enum, conversion is a lookup plus one broadcast multiply, and the conversion factor is
versioned market data resolved from the snapshot rather than a hard-coded table. One object per column,
not per number, so it costs nothing in the hot path — which is the only reason it is affordable. This is
also the first natural home for `match` over an enum with `assert_never`, a house rule with no instances
yet.

**Rejected: `pint`.** Right for a scientific script, wrong here: it wraps values in per-quantity objects,
which is per-item traversal in a library whose premise is avoiding it.

### D6 — The value / missing / error triple

Four defects — B1 (Excel errors silently become blanks), B3 (a 1-D array return becomes an error string),
B4 (blank in, `#N/A` out) and B5 (errors are text) — are one missing decision: **the library has no
representation for "absent" or "wrong", so `NaN` does both jobs and neither well.**

The eventual design is a values array paired with a `uint8` status array over a closed enum — `OK`,
`MISSING`, `NOT_APPLICABLE`, `NO_CONVERGENCE`, `OUT_OF_MODEL_SCOPE`, `BAD_INPUT` — with the Excel boundary
as the only place that maps status onto `#N/A`, `#VALUE!`, `#NUM!`, `#DIV/0!`. It is one byte per cell
against eight for the value, it vectorises, and it lets a vectorised solver report that 3 of 5,000 options
failed to converge — something a scalar `brentq` raising an exception cannot do without abandoning the
batch. It also recovers a single useful meaning for `NaN` internally: *a kernel produced a NaN*, which is
a bug, and which `np.errstate` should be set to make loud.

**But do not build it yet, and do not let that be a reason to leave the bugs in.** The now-items are small
and independent: return an `ExcelError` member from `Marshal.FromPython` instead of a `#ERROR ...` string,
so `SUM` propagates and `IFERROR` fires; stop mapping inbound `ExcelError` to `None`; and stop rendering
outbound `NaN` as `#N/A` when it came from a blank. The full status-array design waits for a function that
can actually fail numerically.

One note for when you do set the numerical policy: numpy's error state is **thread-local**, so a single
`np.seterr` at import will silently not apply on Excel's calculation threads if `IsThreadSafe` is ever
turned on. `filterwarnings = ["error"]` in `pyproject.toml` covers tests and says nothing about
production.

Related and separate: there is currently **no data-quality gate at ingest**. A curve range three buckets
short because a paste failed arrives as blanks; the host has already flattened blanks to `NaN`
(`AddIn.cs:181`) before Python can tell "never populated" from "computed as NaN". Settle the market-data
blank policy now, before the two demo functions are copied: **for a curve, blank means absent and must
never silently mean zero.** A snapshot should declare its expected coverage and ingest should check it in
one vectorised pass, refusing to mint a snapshot with unexplained holes.

### D7 — A valuation needs a record, and the workbook is not one

A priced number leaves exactly one trace today: the number, in a cell. Nothing in `src/` or the host
writes a log line of any kind. `Ping` (`bridge.py:66`) reports a package version and an install path.
`Bridge.StartupError` (`AddIn.cs:48`) is assigned once at load and never cleared, so `GoosedoveStatus` can
only ever report what happened at startup — not calls run, not failures, not the last error.

Explaining a number six months later needs five things at once: inputs, snapshot, library version, model
version, config. The repository can produce one. And Excel stores last-computed values in the saved file,
so a workbook reopened without the add-in shows the old numbers with nothing marking them as stale.

**Recommendation.** Decide now that a terminal valuation produces an `EvaluationRecord` — as-of, snapshot
ids and digests, model versions, library version and commit, resolved config path, scalar arguments,
result digest, `WorkCounts`, wall clock, machine, user — written out of process (an append-only file to
start), never only into the sheet. Do not build the store. Do give the record a defined home, and add a
`GD.STAMP()` function whose one-line record id the user pastes as a value beside the block, so a printed
sheet points at something durable.

The cheap seam that must exist first: **one opaque correlation token in the call protocol**, minted
host-side on the first call of each calculation cycle and passed through unchanged. Python ignores it until
something consumes it. Without it nothing you record can ever be grouped into "this recalc", and per-cell
logging is unaffordable at 10^4 lines per F9. That token rides the same protocol that is expensive to
change later, which is the only reason it belongs in this section rather than in "later".

Distinguish three identities and layer them rather than collapsing them into one integer chosen for hit
rate: **provenance identity** (durable, externally resolvable, recorded — what an auditor asks for),
**cache identity** (cheap, in-process, evictable), and a **display handle**. Provenance is the truth; the
cache key derives from it; the handle displays it.

### D8 — Model version is data, not deployment state

"No compatibility shims; cut over and let stale callers fail" (CLAUDE.md:18) is sound engineering and
unworkable model governance. A model change that moves numbers requires a parallel run of old and new over
a real book, and sign-off, before it becomes the official mark — and during that window both versions must
be computable in one process. Under the current rule the only way to price with the previous model is to
install the previous build, so the comparison a validator needs cannot be produced and every model change
is an unreviewable big bang.

**Recommendation.** Carve model implementations out of CLAUDE.md:18 explicitly. Make model identity data:
a registry entry per `(method id, version)` carrying the implementing callable, its applicability bounds,
and the golden set that validated it. A valuation pins a model version; the default is the approved
version for that instrument; pricing with a non-approved version stays possible; the evaluation record
says which was used. Enforce applicability at the boundary as one whole-array predicate and return a
distinct out-of-scope status rather than `NaN` — otherwise "outside the model" and "blank cell" render
identically (`AddIn.cs:151`). One registry and one field today; every pricer signature after fifty exist.

### D9 — No clock reads below the Excel boundary

The stand-in pricer (`test_work_budgets.py:27`) takes no as-of date, and it is the template. The first
pricing function that reaches for the system clock becomes non-reproducible, un-goldenable, and answers
differently either side of the desk's roll — which is not midnight but an exchange- and desk-specific
time, with the evening session often already trading the next date.

**Recommendation.** Two rules, free today. Valuation time and trading date are always explicit arguments,
resolved once at the boundary from cells the user can see and override, and they are two different things.
And no worksheet function may depend on state only Excel can produce: the Excel layer resolves references
into values and identities, everything below is a pure function of its arguments.

That second rule is worth more than it looks. The acceptance gate for a pricing add-in is never a golden
the team wrote — it is whether it ties out to the vendor risk system or the legacy sheet, on real
positions that cannot be committed to a repository. It is also what you reach for at 4:10pm when a trader
disputes a number: take the actual inputs, run them outside Excel, compare. The repository is in the right
state for this today (`bridge.call` is pure Python and every test drives it directly). Several tempting
designs quietly break it — a handle minted in C# from an `ExcelReference`, a cache keyed on
`XlCall.xlfCaller` — because neither can be reproduced from an exported file. Protect the property
deliberately rather than losing it by accident. Build the reconciliation harness as a `tools/` script
reading exported positions from disk; never a merge gate, never in CI, on data that never enters the repo.

Add a short conventions register while you are here — sign (from the book's side), the per-what scaling of
every risk measure (per \$1, per 1%, per 1bp, per lot), day count, discounting basis — before the first
pricer, and have golden headers cite it. Every one of those gets silently baked into the first golden if
nobody states it first.

### D10 — `IsVolatile` is never set, and that is a decision

Every other traversal cost here scales with cells. `IsVolatile` scales with **edits**: a volatile UDF
re-evaluates on every recalculation regardless of dependencies, so one volatile pricing function turns a
5,000-formula book into 5,000 revaluations per keystroke. `AddIn.cs:224` already gets this right by
omission; the risk is that widening the registration record later legitimises the flag.

**Recommendation.** A comment at `AddIn.cs:224` recording that the omission is deliberate, and a line in
CLAUDE.md: market-data refresh is an input cell or RTD, never volatility. If a registration record is ever
built, this is the one flag that should not be in it. Zero code, and it is the cheapest defence of the
traversal thesis available.

**Its neighbour, `IsThreadSafe`, is a non-decision and worth saying so once.** It buys nothing until
kernels are block-shaped and release the GIL, at which point there is roughly one call in flight and
little left to parallelise. The one honest qualification: a non-thread-safe UDF also constrains Excel's
multi-threaded recalculation of *native* formulas downstream of it, so the cost is imposed on the whole
workbook, not just on goosedove's cells. Revisit with a measurement once kernels are block-shaped; do not
declare it a non-lever permanently.

---

## 3. Fix now: small, verified, worth doing this week

Ordered by value per line changed. Every one of these is checked against the code, and three of them are
one line.

1. **Return an `ExcelError` member instead of a `#ERROR ...` string** (`AddIn.cs:80`, `bridge.py:62`). One
   line at the boundary makes `SUM` propagate and `IFERROR` fire. Keep the diagnostic text — it just needs
   somewhere else to go (D7).
2. **Stop mapping inbound `ExcelError` to `None`** (`AddIn.cs:90`). This is the wrong-number bug: an
   upstream `#N/A` currently prices as a blank.
3. **Stop rendering a blank-derived `NaN` as `#N/A`** (`AddIn.cs:151`). Note the refuters were right that
   `SumRange` counting a blank as zero and `ScaleBlock` mapping it to `NaN` are *consistent* — a reduction
   and a map need different answers, and Excel's own `SUM` agrees. The defect is downstream, in the
   rendering, not in the demo functions.
4. **Reject a non-2-D block instead of crashing** (`bridge.py:39`, `AddIn.cs:139`). `is_block` accepts any
   `ndarray`; the host reads `shape[1]` unconditionally, so returning `np.array([d1, d2, d3])` — the
   natural shape for a delta vector — produces `#ERROR host: ...`. Either accept 1-D and reshape, or say
   so in `is_block`.
5. **Restore the three downgraded pyright rules.** I measured this: setting
   `reportUnknownMemberType`, `reportUnknownVariableType` and `reportUnknownArgumentType` back to `error`
   produces **exactly two errors, both on one line** — `tests/unit/test_bridge.py:45`, where
   `np.asarray(result, ...)` inherits `Unknown` because `bridge.call` returns `object`. The comment in
   `pyproject.toml` says numpy's stubs cannot express shapes; with numpy 2.5 that is no longer the
   binding constraint. A project-wide downgrade lets `Any` spread silently through all future numerical
   code, and it is currently being paid for by one line in one test.
6. **Delete the `# type: ignore` at `tests/performance/test_work_budgets.py:57`, and set
   `reportUnnecessaryTypeIgnoreComment = "error"`.** CLAUDE.md:8 forbids adding these, the repository has
   exactly one, and pyright confirms it is unnecessary — I verified both. This is the one lint setting
   that catches something real in the tree today.
7. **Add an argument-size policy at the boundary.** `=SumRange(A:A)` is what a trader types when the
   blotter will grow, and it is a habit, not a mistake. Every parameter is `object` (`AddIn.cs:239`), so
   the whole column arrives as `object[,]`; `IsNumeric` walks 1,048,576 boxed cells and `NumericBlock`
   pins an 8 MB `double[]` for Python to copy — per call. There is no size check and no message. Reject
   above a stated cell count, naming the argument and the limit; a 50,000-row blotter is legitimate, a
   full column is not. Do this before the first pricing function ships, because once a trader has a
   working `A:A` formula, tightening it is a support incident.
8. **Make `AutoOpen` idempotent, and fix the comment at `AddIn.cs:39-42`.** That comment says "Excel is
   exiting; the process ends and takes Python with it." Excel also calls `xlAutoClose` when a user clears
   the add-in's checkbox in File > Options > Add-ins, and `xlAutoOpen` again when it is re-checked — same
   process, same already-initialised CPython. The current code would reassign `Runtime.PythonDLL`, call
   `PythonEngine.Initialize()` and `BeginAllowThreads()` a second time with no matching `Shutdown`, and
   push duplicate `sys.path` entries; and because `StartupError` is never cleared, a successful second
   load still reports the first failure. Uncheck-and-re-check is the first thing a user tries and the
   first thing support tells them to do. CLAUDE.md:18's "no reload support" is a rule about Python
   callers; the add-in lifecycle is controlled by the user.
9. **Commit `goosedove.cfg.example`.** `.gitignore:19` excludes the file `Config.Load` requires, no
   template exists, and the keys (`pythondll`, `pythonpath`) are discoverable only by reading
   `AddIn.cs:18` and `:23`. Also guard `IndexOf('=')` returning `-1` at `AddIn.cs:276`, where a stray line
   currently throws `ArgumentOutOfRangeException` and surfaces to the user as "python did not start".
10. **Assert `owndata` in `numeric_block`** (`bridge.py:26-29`) and say in the docstring that the `.copy()`
    is load-bearing. The pinned-pointer protocol is memory-safe only under strict synchrony, and nothing
    in the file says so. (Inverting the protocol — allocate in Python, `Marshal.Copy` from C# — was
    proposed and does not survive: it relocates a raw cross-language pointer rather than removing one, and
    makes a numpy array writable by the host after Python may have handed out a view.)
11. **Delete `hello()` from `goosedove/__init__.py`.** It will become somebody's copied example, and the
    root `__init__` sits on the Excel startup path.

Also worth knowing, not worth fixing: `.python-version` pins `3.13.13` exactly, and `uv python install`
could not obtain that build on Linux while writing this — 3.13.12 is the nearest available. CI is
Windows-only so nothing is broken, but the pin is tighter than the reproducibility argument requires and
it blocks a Linux development loop the day anyone wants one. The full suite passes on 3.13.12 with the
locked dependency set.

---

## 4. The independent witness: the highest-value thing to build before the first kernel

`counter.hit(KERNEL)` is a **claim**. A kernel that loops per item and reports `KERNEL: 1` passes every
budget test in `tests/performance` and every budget test this review proposes. The counts-not-time
discipline is excellent, and it is entirely self-reported: adding more names (`CROSSING`, `ELEMENTS`,
`ITER`, ...) multiplies the claims without adding a witness.

The only witness currently in the repository is `call_profile` (`test_work_budgets.py:50`), and it should
go — `cProfile` call counts merge same-named functions across modules, move with comprehension syntax and
CPython patch releases, are blind to work inside numpy, and it carries the repo's only (and unnecessary)
`# type: ignore`. Deleting it without a replacement leaves zero.

**The replacement is about twenty-five lines of standard library, and I verified it works on this exact
code.** `sys.monitoring` (3.12+) can count interpreter events raised inside the package. Run the same
evaluation at N and at 10N and assert the counts are **equal** — a scaling equality, not a magnitude.
Per-item traversal scales; array work does not. Measured against `bridge.py` as it stands today:

| | n=100 | n=1,000 | verdict |
|---|---|---|---|
| `SumRange` (nested list) | 105 | 1,005 | scales — per-item traversal |
| `SumRange` (ndarray) | 3 | 3 | **flat** |
| `ScaleBlock` (nested list) | 106 | 1,006 | scales — per-item traversal |
| `ScaleBlock` (ndarray) | 4 | 4 | **flat** |

It is deterministic, needs no dependency, is immune to the fragility that sinks `cProfile`, and it is the
only mechanism I know of that can **falsify a `WorkCounter` that lies**. Write it before the first kernel,
because every later budget is calibrated against it.

### Two constraints on any counter you add

**A process-global crossing counter is incompatible with the test runner you already use.** Both
`check.ps1:5` and `ci.yml:26` run `pytest -n auto`; xdist's default `--dist load` scatters tests across
workers, so a process-global counter accumulates whatever that worker happened to run, in whatever order.
The existing `_cache` survives only because all three budget tests call `_cache.clear()` first. Keep the
counter per-invocation and let the test own its scope — the same "the scope that constructs it freezes it"
rule `WorkCounter` already follows. If a process-lifetime counter is genuinely wanted for a live-Excel
diagnostic, keep it host-side in C# where pytest never sees it.

**`WorkCounter` is a test-time instrument and cannot become a production API.** `Marshal.FromPython`
returns one value, so counts have no channel across the seam by construction. A `GoosedoveCounters()`
worksheet function would have no dependency edge to the cells it describes, so Excel would not recalculate
it in step and its value would depend on calculation order. Write the split into CLAUDE.md in one
sentence, and the only production-observable traversal number is a host-side counter read by an explicitly
invoked macro-type diagnostic.

**And add counter names only alongside the code that increments them.** Roughly thirty were proposed
during this review. A name nothing increments makes `trace[X] == 0` indistinguishable from "this work was
never instrumented", which actively degrades the negative assertions the house rules bless. The rule is
the inverse of what an architecture review naturally wants to do: a counter lands in the PR that
increments it, never before.

---

## 5. Operations: the things that actually get an add-in uninstalled

None of this is performance and all of it is foundation, because two items constrain the kernel contract.

**The freeze-and-kill chain.** Every function registers non-thread-safe (`AddIn.cs:224`) and `Bridge.Call`
blocks on `Py.GIL()` (`AddIn.cs:59`), so a long call occupies Excel's calculation thread. Excel does not
repaint, Esc cannot interrupt a UDF already inside a call, and the trader's only exit is Task Manager —
losing unsaved work at the worst possible moment. Excel then adds the XLL to **Disabled Items**, and at
the next launch the add-in is silently absent: the book shows `#NAME?` over previously cached numbers with
nothing explaining why. That sequence, not a wrong number, is how add-ins get abandoned. It compounds:
if Python wedges, all 10^4 cells each pay the full stall.

Three things, and the first is why this section is here rather than in "later":

- **A per-call wall-clock deadline at `Bridge.Call`.** It is only implementable if kernels are bounded
  steps that can check it between iterations — so write that into the kernel contract alongside the
  fixed-iteration rule (A.6), or the deadline becomes unbuildable later.
- **A fail-fast latch at the same choke point**, so a broken recalc costs one timeout rather than ten
  thousand.
- **A kill switch** — a `GoosedoveDisable()` cell or ribbon toggle that short-circuits the seam without
  entering Python — so the trader can save and escape rather than kill Excel.

Document the Disabled Items recovery path in the README before the first user, because they will hit it.

**Staleness is invisible.** Large commodity books end up in Manual calculation precisely because an
add-in makes recalc expensive — that is the normal end state, not a pathology. In Manual mode Excel gives
no indication that a cell is stale: the sheet shows yesterday's marks and looks healthy. This is also why
"Excel's dependency graph is the invalidator" must not be stated as a *correctness* property, only as a
performance mechanism: it is wrong at both ends, invalidating nothing under Manual calc and far too often
under RTD. The stamp function from D7 is the only staleness signal a Manual-calc user will ever get,
because it is an ordinary cell and a stale sheet shows a stale stamp.

**Nothing is observable in the field.** No log line anywhere in `src/` or `host/`. Add a bounded log under
`%LOCALAPPDATA%` — aggregated per cycle at steady state, one entry per failure with the full traceback —
and widen `GoosedoveStatus` into a health line: calls and failures this cycle, last error, resident bytes,
resolved cfg path, interpreter and numpy versions. Traders will not attach a debugger; the whole support
flow has to be "paste `=GoosedoveStatus()` into a cell and send me the log file".

**Sheets leave the desk.** An XLL cannot run in Excel for the web or on Mac, so any workbook sent onward
is `#NAME?` on the recipient's machine. Publish as values; say so in the README.

**Bitness is unmanaged end to end.** Excel-DNA emits both a 32-bit and a 64-bit `.xll` side by side,
nothing asserts which Excel is running, and `tests/test_smoke.py:11` asserts the *CI runner's* Python is
64-bit — not the Python the `.xll` loads at a customer site. That is the actual reproducibility hole, and
it is bigger than the NuGet lock file.

---

## 6. The house rules, reviewed

CLAUDE.md is unusually good. It is opinionated where opinions are cheap, it names the failure modes it is
defending against, and "work is measured by counts, not time" is the best rule in it — it makes
performance reviewable rather than anecdotal. Most of what follows is about making rules *checkable*,
because a rule nobody can check decays.

**Keep as is.** Counts not time; never gate a merge on a timing; "assertions that unwanted work does not
occur are valid" (this is the rule that makes D4's budget test legal); "never change source and golden
files in the same PR".

**Sharpen.**

- *"No `isinstance` on internal calls"* versus `bridge.py`, which uses it five times. Those uses are at
  the boundary and are legal — but the boundary is currently "wherever `bridge.py` happens to end", which
  nobody can check. Name `goosedove/excel/` as the only validating layer. One sentence makes four other
  rules checkable.
- *"Numerical code takes arrays and returns arrays; no per-item loops"* — add the companion from D4:
  *domain code takes columns and returns columns*, and *fewer kernel calls is not the same as less work.*
- *"`NewType` for units and digests"* — half right; see D5.
- *"Never gate a merge on a timing"* is correct about **merge gates** and reads literally as a ban on the
  one clock the product cannot ship without (Section 5's deadline). Scope the sentence.
- **State three latency targets** even though no test will enforce them: add-in load time, single-cell
  edit latency, full-book recalculation. Counts with no wall-clock anchor are unanchored, and these are
  the three numbers a user actually judges the product on. None of them is currently recorded anywhere.

**Carve out.** CLAUDE.md:18 ("no compatibility shims") must not apply to worksheet function names (D1) or
to model versions (D8). Both are cases where the caller is not a module you control.

**Add.** A sentence on immutability (D2), a sentence on where the boundary is, and — for a project whose
whole premise is "decide now so we can be less guarded later" — a `docs/adr/` trail. This document is a
substitute for one and a poor substitute, because it is a snapshot rather than a series.

---

## 7. Tests and CI: what to build, and what not to

**The riskiest code in the repository has no automated execution at all.** `ci.yml:35` builds the host and
stops. `NumericBlock`'s pinned-pointer handoff, the buffer read in `FromPython`, and the marshalling rules
in `ToPython` are never *run* by anything except a human with Excel open — and four of the eleven items in
Section 3 live in that code. There is no dotnet toolchain in this container, so I could not run it either.

In order of value:

1. **An xunit project hosting CPython and exercising `Marshal` directly.** Same `windows-2022` runner, no
   Excel needed. It is the only way items 2, 3 and 4 of Section 3 get caught automatically, and it is the
   largest single item in this review.
2. **The `sys.monitoring` scaling witness** (Section 4). Twenty-five lines, verified working.
3. **A round-trip property test across the seam**, driven from Python against a small fake of the host's
   rules: scalars, blanks, errors, rectangular ranges mixing numbers and text.
4. **Property tests with real invariants**, once there is something to test: put-call parity, monotonicity
   in vol and strike, homogeneity in (forward, strike), additivity of aggregation across any partition,
   and — the one that matters most for caching — *a cached result equals the uncached result*.
5. **The golden rule, mechanically.** Two lines are defensible today: register the `golden` marker in
   `pyproject.toml` (required by `--strict-markers`, already on), and add a CI check failing any PR that
   touches both `src/**` and `tests/goldens/**`.

**Do not build the golden framework yet, and when you do, fix the control weakness in the rule.** A
"never source and goldens in one PR" rule plus a one-command regeneration path guarantees that the PR
accepting a changed number contains only numbers — no code, no rationale, no approver — which is the
hardest artefact in the process to review and the easiest to wave through. When goldens arrive: split by
intent (characterisation goldens, freely re-baselined; validation goldens, re-baselined only with a
recorded approval), give every golden a header naming approver, date, source of truth and the claim it
supports, and require the acceptance PR to cite the source PR that moved the numbers. A golden with no
recorded source of truth cannot tell a later reader whether it was checked against an independent
implementation, a broker quote, or merely the previous run of the same code — which proves nothing.

**And fix the measurement tooling, because none of this review's evidence currently survives in the
repository.** CLAUDE.md:39 points at `tools/performance` as where you find out where time goes. What is
there is a script that allocates a 32 MiB numpy array and prints RSS, and one that profiles a 100x100
`SumRange`. Neither exercises a crossing, a chunk boundary, a copy, or a per-item loop, and `measure.ps1`
is invoked by neither `check.ps1` nor CI. Commit one workload that *is* the thesis — cost per cell across
transport shapes and across cells-per-call from 1 to 10^6, printing ns/cell — which is the table that
decides `CHUNK` in Section 1. Roughly thirty lines; it runs on Linux; I ran it (A.10). Keep it out of CI
as a merge gate — CLAUDE.md:40 is right — but make it the first thing a contributor runs when they touch
the seam.

**Smaller gaps.** Nothing publishes an artifact, so there is no `.xll` to install. Nothing enforces the PR
rules the house style declares. NuGet transitive dependencies are unlocked (`packages.lock.json`), though
that is a smaller reproducibility hole than the customer-site Python runtime.

---

## 8. What I am deliberately not recommending

The most useful thing an architecture review of an empty repository can do is refuse to fill it. Each of
these was proposed during the review and did not survive; several were in my own first draft.

- **A versioned registration record** (`spec_version`, per-argument marshalling kinds, a JSON manifest,
  reserved enum arms). Justified by "the `.xll` and the wheel are independently deployed" — a deployment
  that does not exist. Do the function name; leave the 3-tuple alone until there is a release process.
- **A handle/identity scheme.** Six mutually incompatible ones were proposed, each argued as the decision
  that cannot be retrofitted: a content digest of the construction recipe; a monotone counter interned by
  content digest; a parsed human-readable string; a table keyed by `XlCall.xlfCaller`; a per-process
  session token; a provenance tuple. They cannot all be right, and none is choosable before there is an
  object graph to identify and an observed edit pattern to measure. Cell-keyed identity in particular is
  wrong on a trading sheet: traders insert rows, sort ranges and fill formulas down, and every one of
  those moves or duplicates the caller. One sentence is the honest deliverable (D1).
- **An `EvaluationContext` dataclass.** I recommended this and it did not survive: four of its five fields
  have no type to hold yet, so what would actually be committed today is a one-field wrapper around
  `WorkCounter` — strictly worse than the bare parameter it replaces. CLAUDE.md:18 makes the later cutover
  cheap. (A `contextvars` ambient counter is separately wrong: it makes the counter invisible at every
  call site, which defeats a rule whose point is that work is declared.)
- **Thirty new counter names**, for the reason in Section 4.
- **Five error-encoding mechanisms** (status arrays, NaN payload bits, sparse overlays, a ring buffer, a
  `GoosedoveLastError()` UDF) for a library with zero numerical routines. The now-item is one line
  (Section 3); the design waits for something that can fail numerically.
- **The full golden framework** — `%.17g` text format, per-file tolerance headers, `GOOSEDOVE_REGOLD`, an
  environment-fingerprint test asserting OpenBLAS config and FTZ/DAZ state. Two of its items are worse
  than nothing: per-golden tolerance headers invite fudging a number a reviewer already signed off, and
  pinning `OPENBLAS_NUM_THREADS` *inside the add-in* trades throughput for reproducibility in the one
  place reproducibility is not the goal.
- **A large lint and enforcement stack** — `import-linter`, TID251 banned-api tables, an AST test walking
  `src/`, and eighteen further ruff families. It would be larger than the code it polices, and most rules
  cannot fire until code exists that would violate them. Two items are worth doing now because they are
  verified to catch something real today: `reportUnnecessaryTypeIgnoreComment = "error"` and restoring the
  three downgraded pyright rules (Section 3). Layering enforcement arrives with the layers.
- **`arr.setflags(write=False)` as a blocking defect.** The invariant is right and belongs in CLAUDE.md
  (D2); it is not a defect in shipped code, and grading it blocking misallocates attention away from the
  two things at the seam that are actually wrong today.
- **Hypothesis profiles, `derandomize`, CI seed wiring, `--import-mode=importlib`.** Correct in the
  abstract; configuration churn for a thirteen-test suite with one property test.
- **Lazy imports as a startup win.** This was in my draft and it is half wrong. Deferring `scipy.optimize`
  (1,091 ms, A.5) does not remove the freeze, it relocates it — from 8am, when the trader expects Excel to
  be starting, to the first pricing cell of the day, which is a mid-recalc stall with no explanation. On a
  desk a slow load is forgivable and a mid-calculation hang is not. Warm the heavy imports on a background
  thread at `AutoOpen`, or pay them eagerly. The rule worth keeping is narrower: know what is on the
  import path, and do not let it grow by accident.
- **Algorithmic differentiation.** Not yet. Keep it possible by writing kernels as pure functions of
  arrays with no hidden state, which you want anyway; and note that pinning `NDArray[np.float64]` in every
  kernel signature forecloses complex-step and dual-number approaches for free, so a dtype-generic alias
  costs one line and keeps the door open.

---

## 9. Libraries

Runtime dependencies are `numpy` and `scipy`. That is the right answer and should stay the right answer
for a long time: everything ships inside Excel's process and is paid for at startup.

**Add now:** nothing. The two highest-value additions in this review — the `sys.monitoring` witness and the
cells-per-call workload — are standard library and about fifty-five lines between them.

**Add when a named trigger fires.** A golden-comparison helper, or thirty lines of your own, at the first
golden. `coverage`, the first time a bug reaches a workbook a test should have caught.

**Constrain what you already have.** `scipy` has no cheap subset: `scipy.optimize` costs 1,091 ms of
cumulative import and `scipy.interpolate` 498 ms (A.5). Decide which scipy APIs are legal and keep it off
the add-in's startup import path. Note especially that `scipy.optimize.brentq` is scalar — a per-item loop
arriving through a library door, which neither the house rules nor any counter currently catches. A.6
shows the array-first alternative is 12x faster *and* gives a countable iteration budget, which is exactly
the house discipline — but it must be safeguarded: naive vectorised Newton is faster still and silently
fails to converge where vega goes to zero, which is precisely the deep-OTM wing a commodities desk cares
about.

**Refuse, with reasons.**

- **Content-hashing and memoisation libraries** (`xxhash`, `blake3`, `joblib.Memory`, `diskcache`). A.4:
  hashing 76 MiB costs 126 ms, so a cache hit would cost more than the kernel it avoids. Hash once at
  ingest as *evidence* that the archived snapshot matches what was priced — that job is real and must not
  be eliminated — and never on the lookup path.
- **pandas / polars below the reporting edge.** Excellent for a report, wrong in the pricing loop. The
  structure that buys the 35x is a sparse incidence table you write yourself; a DataFrame is a dict of
  columns plus an index plus a type system and every operation goes through it.
- **numba.** Compiles the kernels — the 9x half, not the 83x half — and costs LLVM inside Excel's process,
  a first-call compilation pause, and a much harder deployment story.
- **QuantLib-Python.** Scalar, object-per-instrument, large native dependency: the opposite of D4.
- **`pint`** (D5), **`workalendar` / `exchange_calendars`** (D3).
- **JAX, PyTorch, taichi.** Enormous, and they solve a GPU and autodiff problem this library does not have.
- **`pytest-benchmark` / `pytest-codspeed`.** They gate merges on timings, which the house rules correctly
  forbid.
- **xlwings / PyXLL.** Excel-DNA plus pythonnet is the right choice and should be confirmed rather than
  revisited: free, produces a real `.xll`, supports async and RTD when you need them, and keeps Python
  in-process — which is what makes the block-marshalling path in A.2 possible at all. PyXLL is a per-seat
  licence; xlwings puts Excel and Python in separate processes, turning every crossing into IPC.

**Use properly what you have.** `pyinstrument` for where time goes, `psutil` for the memory bound the cache
will need, `hypothesis` for the property tests that barely exist (one, in the whole repository).

---

## 10. A sequenced plan

Each is one purpose. The order is chosen so nothing later has to undo something earlier.

| # | PR | Why here |
|---|---|---|
| 1 | `fix(host)`: Excel errors propagate; blank-derived NaN stops rendering as `#N/A`; non-2-D blocks rejected | Section 3 items 1–4: wrong answers, not missing features |
| 2 | `chore`: restore the three pyright rules; delete the dead `# type: ignore`; enable `reportUnnecessaryTypeIgnoreComment` | Section 3 items 5–6. Two lines of source, verified |
| 3 | `test(perf)`: the `sys.monitoring` scaling witness, replacing `call_profile` | Section 4 — every later budget is calibrated against it |
| 4 | `docs`: `docs/adr/` with D1, D2, D3, D4, D9, D10 as dated records; CLAUDE.md carve-outs and the three latency targets | Costs nothing and everything below cites it |
| 5 | `fix(host)`: argument-size policy; idempotent `AutoOpen`; `goosedove.cfg.example`; `Config.Load` guard | Section 3 items 7–9 — the support surface |
| 6 | `tools(perf)`: the cells-per-call workload; pick and record `CHUNK` | Section 1 — makes the thesis reproducible in-repo |
| 7 | `test(host)`: xunit project exercising `Marshal` against embedded CPython | The gap that let items 1–4 exist |
| 8 | `feat(host)`: correlation token in the call protocol; bounded log; `GoosedoveStatus` as a health line | D7 + Section 5, and the token rides the protocol that is expensive to change |
| 9 | `feat(market)`: snapshot with provenance and knowledge time, immutable arrays, coverage gate at ingest | D2 + D3 + D6 |
| 10 | `feat(market)`: day-number and contract-month types; `np.busdaycalendar`; expiry rules as data | D3 |
| 11 | `feat(instruments)`: declared trade terms; derived incidence matrix; the re-derivation test | D4 |
| 12 | `feat(risk)`: delta ladder with the O(1)-in-buckets budget test | D4 — the first real proof the foundation works |

Items 1–6 are days. The first pricing function should not land before item 9; the first risk function not
before item 11.

---

## Appendix A — measurements

Produced against this repository's own code and its locked dependency set (CPython 3.13, numpy 2.5.2,
scipy 1.18.1) on a 4-core Linux x86-64 container. Absolute numbers on a trader's Windows box will differ;
the *ratios* are the point, and they are large enough that machine variation changes no conclusion.
Nothing here needed the Excel host, so every figure is a **lower bound** on the real cost — the
.NET-to-Python transition is not included.

### A.1 The seam, per call

| | cost |
|---|---|
| `1.0 + 2.0` in plain Python | 0.026 us |
| `bridge.call("Add", [1.0, 2.0])` | **0.287 us** |
| — of which the `MISSING` list comprehension | 0.153 us |
| `bridge.is_block(1.0)` | 0.108 us |
| `bridge.function_specs()` (4 functions) | 26.2 us (~6.6 us/function; `inspect.signature` is not cached) |

0.287 us is *pure Python dispatch*: the `_FUNCTIONS` lookup, the `MISSING` comprehension, the `try`/
`except` frame. It excludes `Py.GIL()`, the `PyList` build, `InvokeMethod`, and every .NET marshalling
step. Note that 0.153 us of it — over half — is spent on a comprehension that can never do anything (B2).

### A.2 One call per block versus one call per cell

| range size | as nested list | as `ndarray` | ratio |
|---|---|---|---|
| 100 cells | 6.7 us | 5.0 us | 1.3x |
| 10,000 cells | 599.1 us | 11.9 us | **50x** |
| 1,000,000 cells | 64.2 ms | 1.24 ms | **52x** |

`Marshal.NumericBlock` already earns its keep — but only for ranges that are *entirely* numeric
(`AddIn.cs:159-169`). One text cell anywhere falls back to the per-cell `PyObject` path: a 52x cliff
triggered by a single header row inside a selected range, with nothing telling the user it happened.

### A.3 The block return path

| | cost |
|---|---|
| `flatten_block` on a C-contiguous float64 array (1M) | 0.36 us (no copy) |
| `flatten_block` on a transposed view (1M) | 900 us (silent 7.6 MiB copy) |
| `flatten_block` on a float32 array (1M) | 820 us (silent 7.6 MiB copy) |
| `numeric_block` copying 1M doubles from the pinned pointer | 560 us |

`np.ascontiguousarray(block, dtype=np.float64)` (`bridge.py:34`) is free on a C-contiguous float64 array
and a full copy otherwise. A kernel returning a transpose, a strided slice, or float32 pays that copy
invisibly, once per returned range, and no counter records it.

### A.4 Content hashing as a cache key

| array | `tobytes()` | `blake2b` |
|---|---|---|
| 1,000 doubles (8 KiB) | 0.2 us | 13.2 us |
| 100,000 doubles (0.8 MiB) | 37.2 us | 1.2 ms |
| 10,000,000 doubles (76 MiB) | 42.3 ms | **125.7 ms** |

`tests/performance/test_work_budgets.py:32` keys its cache on `quantities.tobytes() + prices.tobytes()`.
On a realistic curve set a *cache hit* would cost 126 ms of hashing — the traversal problem wearing a
cache's clothes. (Hashing once at ingest, as provenance evidence, is a different and legitimate job.)

### A.5 Startup cost, paid while Excel is frozen

| import | cumulative |
|---|---|
| `numpy` | 76 ms |
| `scipy` | 103 ms |
| `scipy.interpolate` | 498 ms |
| `scipy.optimize` | **1,091 ms** |
| `goosedove.excel.bridge` (today) | 84 ms |

### A.6 Root-finding: the traversal trap in the numerics

Implied vol on 5,000 options:

| method | time | max error vs the true vol |
|---|---|---|
| `scipy.optimize.brentq`, one call per option | 158 ms | 9.7e-11 |
| vectorised Newton, 8 fixed iterations | 2.3 ms | **0.79 — silently wrong at the tails** |
| vectorised bisection, 52 fixed iterations | **12.9 ms (12x)** | 2.1e-10 |

| bisection iterations | max error | time |
|---|---|---|
| 20 | 2.4e-06 | 5.1 ms |
| 30 | 2.5e-09 | 7.4 ms |
| 40 | 2.1e-10 | 9.7 ms |
| 52 | 2.1e-10 | 12.7 ms |

Array-first root-finding is worth 12x over `brentq` and its iteration count is a *countable, budgetable*
unit of work — exactly what the house rule asks for. But it must be safeguarded: naive vectorised Newton
is faster still and fails silently where vega goes to zero.

### A.7 The delta ladder: three shapes of the same computation

5,000 trades against 60 delivery-month buckets, bump-and-revalue delta. All three agree to 4e-09.

| | time | kernel calls | peak extra memory |
|---|---|---|---|
| a) Python loop, one revaluation per risk factor | 991 ms | 61 | 2.3 MiB |
| b) one kernel call with a leading scenario axis | 856 ms | 1 | 140 MiB |
| c) sparsity-aware: factor *b* touches column *b* only | **28.6 ms** | 2 | 2.3 MiB |

The obvious answer (b) buys **1.16x** for 60x the memory. Knowing which factors touch which trades (c)
buys **35x** for nothing. Fewer kernel calls is not the same as less work: (b) still performs all 61
revaluations, it just performs them in one call.

### A.8 Object-per-trade versus struct-of-arrays

50,000 trades:

| operation | objects | columns | ratio |
|---|---|---|---|
| price (Black-76) | 22.8 ms | 2.4 ms | 9x |
| aggregate by book x delivery month | 11.3 ms (dict walk) | 0.14 ms (`np.bincount`) | **83x** |
| memory | 4.24 MiB (frozen, slotted) | 2.29 MiB | 1.9x |

The kernel gap is 9x; the traversal gap is 83x. (`np.add.at` sits between the two at 0.80 ms — `ufunc.at`
is not the fast path; a flat key plus `np.bincount` is.)

### A.9 Curve lookup and calendars

200,000 lookups against a 120-bucket forward curve:

| | time | ratio |
|---|---|---|
| `dict[str, float]`, list comprehension | 6.13 ms | |
| numpy fancy index into a column | 0.19 ms | 32x |
| Python loop, piecewise-linear interpolation | 109.9 ms | |
| `np.interp` | 9.42 ms | 12x |

Business-day counting, 50,000 dates against a holiday calendar:

| | time | ratio |
|---|---|---|
| `np.busday_count` once per date | 104.0 ms | |
| `np.busday_count` vectorised | **1.04 ms** | 100x |

`np.busdaycalendar` / `np.busday_count` / `np.busday_offset` are array-first, already installed, and 100x
faster than the per-date call.

### A.10 Where the saving from bigger blocks stops

`bridge.call("SumRange", [block])` at each block size, and the total cost of moving 1,000,000 cells:

| cells/call | us/call | ns/cell | kernel ns/cell | 1M cells total |
|---|---|---|---|---|
| 1 | 5.29 | 5,286 | 4,641 | 5,257 ms |
| 10 | 5.34 | 534 | 477 | 510 ms |
| 100 | 5.25 | 52.5 | 48.5 | 51.8 ms |
| 1,000 | 6.65 | 6.65 | 6.23 | 6.5 ms |
| **10,000** | 13.60 | 1.36 | 1.26 | **1.29 ms** |
| 100,000 | 121.3 | 1.21 | 1.14 | 1.13 ms |
| 1,000,000 | 1,266 | 1.27 | 1.25 | 1.30 ms |

Two things to read here. The saving **saturates around 10^4 cells per call** — going from 10^4 to 10^6
buys nothing measurable while the return path's transient allocation grows linearly. And the `kernel
ns/cell` column shows that at small block sizes the fixed cost is mostly **numpy's own** call overhead
(4.64 us of the 5.29 us at one cell per call), not the bridge's 0.287 us. The bridge is not the expensive
part of a small call; making calls large enough to amortise numpy's fixed cost is, and that happens by
10^3–10^4.

### A.11 The scaling witness (Section 4)

Interpreter events raised inside `src/goosedove/` while doing n units of work, via `sys.monitoring`:

| | n=100 | n=1,000 | verdict |
|---|---|---|---|
| `SumRange` (nested list) | 105 | 1,005 | scales — per-item traversal |
| `SumRange` (ndarray) | 3 | 3 | flat |
| `ScaleBlock` (nested list) | 106 | 1,006 | scales — per-item traversal |
| `ScaleBlock` (ndarray) | 4 | 4 | flat |

### A.12 Type checking

With `reportUnknownMemberType`, `reportUnknownVariableType` and `reportUnknownArgumentType` restored to
`error`, and `reportUnnecessaryTypeIgnoreComment = "error"` added, pyright 1.1.411 strict reports **three
errors in the whole repository**:

- `tests/performance/test_work_budgets.py:57` — unnecessary `# type: ignore`
- `tests/unit/test_bridge.py:45` — two errors, both because `np.asarray(result, ...)` inherits `Unknown`
  from `bridge.call`'s `object` return

That is the entire cost of the project-wide downgrade currently in `pyproject.toml`: one line in one test.

---

## Appendix B — defects in what exists today

Read out of the code and, where possible, measured. Listed because a smoke test about to become a
foundation should not carry them forward silently, not because the smoke test was wrong to ship.

**B1. Excel error values are silently swallowed.** `AddIn.cs:90` maps `ExcelError` to `PyObject.None`, the
same value a blank cell gets. So `=Price(A1)` where `A1` is `#N/A` prices as though `A1` were empty. Every
native Excel function propagates errors; this add-in launders them into numbers. On a pricing sheet that
is a wrong-number bug nobody will see. **The most serious defect here.**

**B2. `MISSING` is dead code, and the module docstring is wrong about it.** `bridge.py:20` defines it,
`bridge.py:60` translates it, and `bridge.py:3` states the host uses it. The host never sends it —
`AddIn.cs:90` converts `ExcelMissing` to `None` before `call` is reached. Line 60 can never fire, and it
costs 0.153 us of the 0.287 us per-call budget (A.1). Either the host should send `MISSING` (so an omitted
argument is distinguishable from a blank cell, which matters for optional arguments with defaults) or the
name and the docstring should go.

**B3. A 1-D numpy return becomes `#ERROR host: ...`.** `is_block` (`bridge.py:39`) is true for *any*
`ndarray`; `AddIn.cs:138-139` reads `shape[0]` and `shape[1]` unconditionally, so a function returning
`np.array([d1, d2, d3])` raises `IndexError` inside the host. `ScaleBlock` only works because its input is
already 2-D. The contract "a block is a 2-D float64 C-contiguous array" is real, enforced nowhere, and
documented nowhere.

**B4. Blank in, `#N/A` out.** `AddIn.cs:181` encodes a blank input cell as `NaN`; `AddIn.cs:151` turns
every `NaN` in a result into `ExcelError.ExcelErrorNA`. A blank round-trips to `#N/A`, and a genuine `NaN`
from a model that blew up is indistinguishable from an untouched input — the two things you most need to
tell apart. It also breaks content-addressed caching, since `NaN != NaN`.

*(Note: `SumRange` counting a blank as zero and `ScaleBlock` mapping it to `NaN` are consistent — a
reduction and a map need different answers, and Excel's own `SUM` agrees. The defect is the rendering, not
the demo functions.)*

**B5. Errors are text, not errors.** `bridge.py:62` returns `"#ERROR TypeName: message"`; `AddIn.cs:55`
and `:80` return `"#ERROR host: ..."`. These are strings that merely *look* like Excel errors. `ISERROR`,
`IFERROR`, `AGGREGATE` and conditional formatting do not see them, `SUM` behaves differently than it would
over a real `#VALUE!`, and a long traceback can approach Excel's 32,767-character cell limit.

**B6. Every numeric range is traversed twice in C#.** `IsNumeric` (`AddIn.cs:161`) walks every cell to
type-test it; `NumericBlock` (`AddIn.cs:176-183`) walks every cell again to unbox it. Two million boxed
type tests for a 1,000,000-cell range before any data crosses. One fused pass that bails on the first
non-numeric cell would do.

**B7. One text cell costs 52x.** `AddIn.cs:96` sends the whole range down the per-cell `PyObject` path if
`IsNumeric` fails anywhere. Measured at 10,000 cells: 11.9 us becomes 599 us (A.2).

**B8. Two extra managed-to-Python transitions per returned value.** `AddIn.cs:127` calls `is_block` on
*every* result just to ask a type question, and `:135` calls `flatten_block` on the ones that are blocks.
The type question belongs on the C# side of the seam.

**B9. The block return path allocates roughly ten times the payload, and leaks two wrappers per block.**
For an R x C block, `AddIn.cs:140-151` allocates a `byte[]`, then a `double[]`, then an `object[,]`, then
boxes every non-NaN cell — plus Excel-DNA's own `XLOPER12` array on top. The `byte[]` intermediate is
avoidable (copy straight from the buffer pointer into the `double[]`); the boxing is not, given
Excel-DNA's return type. Separately, `shape[0]` and `shape[1]` (`AddIn.cs:138-139`) each create a
`PyObject` that is never disposed, so two wrappers per returned block go to pythonnet's finalizer, which
needs the GIL to clean up.

**B10. `flatten_block` can copy 7.6 MiB silently** — 0.36 us versus 900 us on a transposed 1M-element
view (A.3), once per returned range, uncounted.

**B11. `Config.Load` throws on any line without `=`.** `AddIn.cs:276` takes `IndexOf('=')` without checking
for `-1`, so `Substring(0, -1)` raises. Caught at `AddIn.cs:34` and surfaced as "python did not start"
with a .NET stack trace in a cell. A stray line in the config reads to the user as a broken Python install.

**B12. There is no documented install path.** `.gitignore:19` excludes `host/Goosedove.Host/goosedove.cfg`,
the file `Config.Load` requires; no `.example` exists; the keys are discoverable only by reading
`AddIn.cs:18` and `:23`; `README.md` does not mention it.

**B13. `AutoOpen` is not idempotent and the comment above `AutoClose` is wrong.** `AddIn.cs:39-42` says
"Excel is exiting; the process ends and takes Python with it." Excel also calls `xlAutoClose` when the
user clears the add-in's checkbox and `xlAutoOpen` again when it is re-checked, in the same process. A
second open would re-`Initialize()` an already-live interpreter with no matching `Shutdown`, duplicate
`sys.path` entries, and — because `StartupError` is never cleared — report the first failure even after a
successful load.

**B14. Public mutable statics across a future thread boundary.** `Bridge.Module` and `Bridge.StartupError`
(`AddIn.cs:48-49`) are written on the main thread during `AutoOpen` and read from every UDF call. Benign
while Excel serialises UDFs; a data race the day `IsThreadSafe` is set. Nullable reference types are off
(`net48`, `LangVersion 10`), so the compiler says nothing.

**B15. Registration holds the GIL while calling into Excel.** `AddIn.cs:22` opens `Py.GIL()` around
`Registration.RegisterAll()` (`:30`), which reaches `ExcelIntegration.RegisterDelegates` at `:234`.

**B16. `BeginAllowThreads`' return value is discarded** (`AddIn.cs:20`), so the saved thread state can
never be restored and `PythonEngine.Shutdown()` can never be called cleanly. Harmless while `AutoClose`
does nothing — but see B13, where that assumption is what fails.

**B17. No registration attributes at all.** `AddIn.cs:224` sets only `Name` and `Description`. No
`Category` (every function lands in "User Defined"), no per-argument `Description`, no name prefix into
Excel's single global namespace. Getting `IsVolatile` right by omission (D10) is the one thing this does
well, and nothing records that it is deliberate.

**B18. No argument-size policy.** `=SumRange(A:A)` marshals 1,048,576 cells per call, with no check and no
message.

**B19. The host is compiled but never run in CI.** `.github/workflows/ci.yml:35` runs `dotnet build` and
stops. B1, B3, B4, B7 and B9 all live in code that has no automated execution of any kind.

**B20. The repository contains a forbidden and unnecessary `# type: ignore`.** CLAUDE.md:8 says never add
one; `tests/performance/test_work_budgets.py:57` has one; pyright with
`reportUnnecessaryTypeIgnoreComment` confirms it is unnecessary (A.12).

**B21. Nothing logs.** No logging call anywhere in `src/` or `host/`. `GoosedoveStatus` (`AddIn.cs:257`)
can only ever report startup, because `Bridge.StartupError` is assigned once at `AddIn.cs:35` and never
cleared.

**B22. Minor.** `goosedove/__init__.py` still contains the `hello()` stub, which will become somebody's
copied example, and the root `__init__` sits on the Excel startup path. `function_specs()` re-runs
`inspect.signature` on every call (`bridge.py:51`) — startup-only, so it does not matter yet.
`numeric_block` (`bridge.py:26`) reads arbitrary process memory from an integer argument and is a public
name on a module the host imports; mark it as the unsafe primitive it is, and assert `owndata` on the
result. `tests/test_smoke.py:11` asserts the *CI runner's* Python is 64-bit, which is not the Python the
`.xll` loads at a customer site.

**B23. `.python-version` pins `3.13.13` exactly.** `uv python install` could not obtain that build on Linux
while writing this. CI is Windows-only so nothing is broken today, but the pin is tighter than the
reproducibility argument requires and it blocks a Linux development loop. The full suite (13 tests) passes
on 3.13.12 with the locked dependency set.

---

## Appendix C — what did not survive

Ninety findings were graded blocking or major by the dimension reviewers. Thirty-four were refuted and are
not in this document. The categories are worth recording, because they are the shapes an architecture
review of an empty repository naturally produces:

- **Prescriptions for types that do not exist yet** — kernel signatures, an `EvaluationContext` with four
  fields that have nothing to hold, CSR layouts for instruments nobody has defined.
- **Insurance against deployments that do not exist** — spec versioning justified by independently
  released artifacts, when CI builds both halves from one commit and publishes nothing.
- **Mutually incompatible schemes each argued as irreversible** — six identity designs, five error
  encodings, thirty counter names.
- **Enforcement larger than the code it polices** — an import contract, banned-api tables, an AST test and
  eighteen ruff families for 250 lines of Python.
- **Correct-in-the-abstract configuration** — hypothesis profiles, seed policy, import modes, for a
  thirteen-test suite.

Three refutations changed conclusions rather than deleting them, and those changes are the most useful
output of the exercise: the handle model (D1), the scenario axis (D4/A.7), and lazy imports (Section 8).

