# Structure review of the library planning snapshot

A review of the four draft specifications in `docs/library/` against the built seam,
the C# host, and the repository's principles, answering the brief in
[README.md](README.md#suggested-review-brief). It proposes no new functions and
implements nothing.

Every claim below about what the seam does was checked by running `bridge.py`, not
read off a document. Where a claim is a judgement rather than a measurement, it says so.
Where a choice is the owner's to make, it is written as a fork with a recommendation,
as [PRINCIPLES.md](../../PRINCIPLES.md) requires.

**What could not be checked:** `.\check.ps1` needs Windows, .NET and Excel, none of
which exist in the machine this review was written on. No source file was changed, so
format, lint, types and the Python tests are unaffected; nothing here has been seen in
Excel.

## The short version

The specifications are unusually careful, and the domain content is right. Three things
in them cannot be built as written, and one of the three is not a gap to be filled later
but a contradiction that has to be decided before anything is engineered.

| | Finding | Where it is decided |
|---|---|---|
| 1 | Three of the four specified things cannot register today; the add-in does not degrade, it fails to load at all. | Sequencing, below |
| 2 | Identifying a table's date column by its header text cannot be reconciled with the seam's charter. | **Fork 1** |
| 3 | The library-wide `max_date` bound, as written, is ambient state, and the spec forbids ambient state two paragraphs later. | **Fork 2** |

Everything else is ordinary review: corrections, simplifications, and a proposed
template so the next twenty specifications are easier to write and read than these four.

## 1. What can be built today, and what bricks the add-in

`_RESULTS` in [bridge.py](../../src/goosedove/excel/bridge.py) holds ten declared results:
`float`, `int`, `str`, `bool`, `Date`, `NumberArray`, `NumberColumn`, `NumberRow`,
`DateColumn`, `DateRow`. A handle is not among them. Declaring one is refused by
`_result`, and `register` runs at import, not at call:

```text
CreateValuationDate declares <class 'ValuationDate'> as its result, which the seam cannot send
CreateDiscountCurve declares <class 'DiscountCurve'> as its result, which the seam cannot send
```

Both messages are the real ones, produced by importing the real bridge with the two
signatures exactly as the specifications write them.

The failure is total rather than partial. `register` raises during the import that
`Registration.RegisterAll` triggers, `AutoOpen` catches it into `Bridge.StartupError`
([AddIn.cs:26](../../host/Goosedove.Host/AddIn.cs)), and **no** function registers —
not the new one, not `Ping`, not a probe. The first pull request that adds a
handle-returning constructor takes the whole add-in down until handles exist. That is
the correct behaviour under tenet 2, and it is not what a reader of the specifications
would predict, because each one describes its handle output as though the only open
question were lifetime.

So the buildable-today set is exactly two things, and neither needs a handle decision:

| Thing | Why it is buildable | Why it is a good first pull request |
|---|---|---|
| `UnitConversions` | No worksheet surface at all. Pure Python data and math. | Establishes the library package, the one-way import rule, and the work-count idiom with nothing else moving. |
| `util_InterpolateDiscountFactors` | Returns `NumberArray`, which `_RESULTS` already carries. | The only specified worksheet function the seam can carry end to end today. |

**Recommendation.** Say this in [README.md](README.md) as a sequencing note. Build those
two first. Handles are a platform decision (anti-principle A10 is precisely about
deferring one), and both Globals constructors sit behind it.

### What handles need before a constructor can exist

The [research](handles/excel-dna-research.md) covers the Excel-DNA side well. Four
smaller things are unstated and are cheap to settle now:

1. A `_RESULTS` entry that stores an object and returns its text.
2. A `_DECLARED` entry per object kind that resolves text to a live object of that kind.
3. **Where object kinds get registered.** `valuation-date.md` correctly forbids the
   library from importing the bridge to define its records. So the registration cannot
   live with either the record or the bridge. Propose a third module,
   `src/goosedove/excel/objects.py`, which imports library types and registers them.
   `excel/__init__.py` already exists as "the catalogue of every module that registers
   worksheet functions" and is the natural place to list it.
4. **A second documented exception to "never by meaning."** [inputs.md](../seam/inputs.md)
   rule 6 says the boundary checks "never by meaning", with "one documented exception"
   — the calendar. "This text names a live object of this kind" is a second. That needs
   its own numbered decision in `inputs.md`, not silence.

### A handle rule worth writing down now

A failure is text, not an Excel error: `Registered.run` returns
`#ERROR {function}: {ExceptionType}: {message}`. So when a creator fails, its cell holds
that text, and a consumer referring to that cell receives **the error text as its handle
argument**. Unless the resolver recognises the `#ERROR ` prefix, the user is told the
handle is unknown and goes looking for a store problem that does not exist.

One rule fixes it: a handle argument beginning `#ERROR ` fails as "its creator failed",
quoting the creator's message. Add it to [handles/README.md](handles/README.md).

## Fork 1 — how a date/factor table crosses the seam

**This is the one that must be decided before engineering starts.**

### Why it is a contradiction and not a gap

`discount-curve.md` calls it "an implementation gap to resolve". It is narrower than
that. Three rules that are each individually agreed cannot all hold:

- `values: NumberArray` hands over `float64`. `_numbers` does no date work, so serials
  stay raw numbers.
- The library must receive typed `datetime64[D]`, converted once, at the edge
  (tenet 1; golden rule 6). It must not parse Excel dates itself.
- *Which* column holds dates is decided by matching header text. That is meaning, and
  [inputs.md](../seam/inputs.md) rule 6 and decision 14 forbid the seam from knowing it.

The seam cannot convert, because it is not allowed to know which column. The library
must not convert, because it is not allowed to parse. No amount of deferral resolves
that; either the worksheet layout changes or the seam's charter is amended.

### The four families, with what each actually costs

| | Shape | New seam machinery | What happens to the open header questions |
|---|---|---|---|
| (a) | One table type typed by column position | A new declared type, and a family of them as more tables appear | Answered by position; header row becomes decorative |
| (b) | `dates: DateColumn, factors: NumberColumn` | **None** | **Deleted** |
| (c) | `as_of: Date, factors: NumberColumn` | **None** | **Deleted** |
| (d) | One body, library-side preparation | None | Answered, but tenet 1 is broken |

(a) starts a bespoke type per table shape, which is anti-principle A8. (d) moves Excel
parsing into pricing code, which tenet 1 exists to prevent.

(b) and (c) were both run against the real bridge. They work today, and their messages
are *better* than the table's, because the seam can say which column is wrong and why:

```text
(b) fractional serial in column A -> #ERROR CurveB: dates cell (2, 1) is number 46165.5, expected date
(b) a text date in column A       -> #ERROR CurveB: dates cell (2, 1) is text '2026-05-23', expected date
(b) date column given as a row    -> #ERROR CurveB: dates is 1x2 array, expected column of dates
(c) fractional anchor serial      -> #ERROR CurveC: as_of is number 46164.5, expected date
```

Under `NumberArray` the same mistakes can only ever produce `expected number`, because
by then a date is just a double.

### Recommendation

**Use (b) for the utility and (c) for the curve constructor.**

```python
def InterpolateDiscountFactors(dates: DateColumn, factors: NumberColumn) -> NumberArray: ...
def CreateDiscountCurve(as_of: Date, factors: NumberColumn) -> DiscountCurve: ...
```

```excel
=InterpolateDiscountFactors(A2:A35, B2:B35)
=CreateDiscountCurve(D2, E2:E3632)
```

The utility needs sparse dates as data, so it takes them. The curve is daily *by
definition*, so it should not carry a date column at all. That single change deletes:

- the date-preparation gap, entirely — the seam converts `as_of` once, as `Date`;
- the daily-coverage rule set (missing day, duplicate, reversed, nonsequential): a gap
  becomes unrepresentable rather than rejected, which is tenet 3's "first ask whether
  the work is needed at all";
- four rows from the acceptance table;
- the header row, and with it all three open header questions — case, whitespace,
  column order — which are *dissolved* rather than answered;
- `max_date` as a validated field: it becomes `as_of + (N - 1) days`, derived.

### The cost, stated honestly

This is the owner's decision under golden rule 8, and it turns on one thing.

With one body, a date and its factor are welded together by the selection: the user
cannot misalign them. With two ranges they can. `A2:A15` against `B3:B16` is
equal-length and offset by one row, and **no** validation catches it — the dates are
valid, the factors are valid, and every pairing is wrong by a day. That is a silent
wrong number, which tenet 2 calls the worst outcome.

Three things weigh against it. Under (c) the curve has no date column to misalign at
all — only a single anchor cell, and an anchor that is wrong is wrong by a visible
amount, not by one row. Under (b) the utility's inputs are almost always adjacent
columns of one table, selected together. And the header row's real job — telling the
user which column is which — is done better by the Function Arguments dialog once
argument help exists (§5), and by the Excel Table header that stays on the sheet doing
useful work for the trader instead of crossing the seam to be re-matched.

**If the owner wants the welded table anyway**, then family (a) is the honest way to get
it, and `inputs.md` needs a new decision saying that typing a column by position is
shape rather than meaning. That is a defensible amendment. What is not available is the
current specification, which asks for the welded table *and* header-based identification
*and* the existing charter.

## Fork 2 — how the `max_date` bound reaches a calculation

### The requirement contradicts itself

`discount-curve.md` asks for three things that do not compose:

1. the bound applies to "all library processes that use dates", including ones that
   never request a factor and dates "generated during processing";
2. "a process cannot opt out";
3. "the governing curve must be an explicit dependency", and "do not infer a mutable
   'last curve created' setting".

(1) and (2) describe something every function reads without being handed it. (3)
forbids exactly that. Golden rule 11 forbids it too — "no global fallback market, no
implicit clock, no singleton collection, no context variable a function reads behind the
caller's back" — and making every date-touching function re-check a bound is
anti-principle A1, the same check written many times.

The requirement is also pitched at the wrong altitude. "The library has a maximum date"
is not a property of the library. It is a property of *the inputs this calculation was
given*, which is tenet 1's own subject.

### Recommendation: invert it

Do not push a bound outward to every process. Give the calculation one object that owns
its inputs, and check once, where dates are **produced**.

- One worksheet function builds the calculation's context — call it whatever the desk
  calls it — bundling the `ValuationDate`, the curve or curves, and internally
  `UnitConversions`. It returns a handle, so Excel tracks the dependency, which is
  exactly what [handles/README.md](handles/README.md) already wants.
- Every pricing function takes that context as its first argument. The governing curve
  is then explicit by construction; there is nothing to infer and nothing to opt out of.
- The bound is enforced in **one** place: the date-generation service the context owns.
  A date that exists has already been admitted. Nothing downstream re-checks it — which
  is CLAUDE.md's "no `__post_init__` that re-checks what its caller already established".

A reviewer verifies the count by finding the one function that mints dates. One place,
greppable, testable.

This also closes two questions the specifications currently leave dangling. "Which curve
governs" becomes "the ones this context names", and with several curves the bound is
`min(max_date)` over them. "How does the curve's start relate to `ValuationDate`"
becomes an assertion made once, at context construction, instead of a rule every
function must remember.

### Two related corrections

**`as_of` names two different things.** It is `ValuationDate`'s date, and it is also the
curve's first date ("the first table date defines the curve's own `as_of`"). Tenet 5 and
golden rule 4 both say a thing gets one name. Rename the curve's field to `start_date`.
This costs a find-and-replace today and a subtle ambiguity forever if left.

**One curve will not survive the stated end state.** A commodity swap needs a discount
curve and at least one index projection curve. The moment there are two, "the curve's
`max_date`" has no referent. The context object above absorbs this without redesign;
"the library has a bound" does not. The second curve need not be specified now — only
the shape that will accept it.

## 2. Domain notes

### Interpolating on discount factors is a model choice, not data preparation

The utility interpolates linearly on the factors themselves. Taking a one-year knot gap
from the owner's own supplied sample, 2030-05-01 to 2031-05-01, 0.86799 to 0.85942:

| Method | Implied overnight forward across the gap |
|---|---|
| Linear on `df`, as specified | ramps 0.98735% → 0.99717%, +0.982 bp, monotonically |
| Linear on `log df` | flat at 0.99225% |

So DF-linear makes the implied forward ramp inside every gap and step at every knot. For
pricing linear instruments that is a real, if small, modelling decision, and it is
currently presented as mechanics.

This is not an argument to change it. The source data here is already near-daily, and
over a one-day step the difference is negligible. It *is* an argument to write one
sentence saying the choice was made and what it implies, so the first person to plot a
sawtooth forward curve knows it was chosen rather than introduced.

### The factor rules are redundant, and two of them are unreachable

The stated set is: finite; in `(0, 1]`; first exactly `1`; non-increasing. Checked
against every rejection case in the specification, this reduces with an identical
acceptance set:

| Stated | Minimal | Why |
|---|---|---|
| finite | — | Excel numbers are "always a finite double" ([inputs.md](../seam/inputs.md)) |
| `df <= 1` everywhere | — | implied by `df[0] == 1` and non-increasing |
| `df > 0` everywhere | `df[-1] > 0` | the minimum of a non-increasing array is its last element |
| `df[0] == 1` | `df[0] == 1` | independent |
| non-increasing | non-increasing | independent |

Five passes over the array become two passes and two scalar reads. Worth taking under
tenet 3, and worth stating so the implementation does not carry three checks that can
never fire.

The NaN and infinity cases are reachable only from Python, never from a cell.
`valuation-date.md` says this about its fraction; `discount-curve.md` does not say it
about its factors, and should.

### Price units are the missing object

`UnitConversions` converts quantities within a category. Commodities trade in prices:
USD/BBL, cents/gal, USD/MMBTU. The specification notices this — "changing the
denominator unit of a price uses the reciprocal factor direction" — but specifies no
type for it, so the knowledge lives in prose. Golden rule 16 asks every quantity to
carry its unit. A price carrying a numerator and a denominator unit is the next real
object, and it is what makes `UnitConversions` earn its place.

### The supplied factors are correct

All sixteen were checked against the definitions the document cites. They agree to
floating point. Round trips are exact where the stored factor is the exactly
representable reciprocal — `GAL→L→GAL` returns `1.0`, `M3→L` returns `1000.0` — and off
by one unit in the last place where it is not: `1 GAL → L` gives `3.7854117839999994`
against an exact `3.785411784`, and `1 MWH → GJ` gives `3.5999999999999996` against
`3.6`. The specification's "agreed tolerance" is right; it should say the tolerance is
about one ulp, or those become assertions nobody can argue with.

### `day_fraction_elapsed` is generality bought in advance, and it has a latent tie

The specification is explicit: the fraction "is retained now so those later
specifications can use it". That is the thing the non-goals and golden rule 34 both
name — generality without a second consumer.

It also carries a hazard worth settling while it is cheap. `(2026-09-11, 1.0)` and
`(2026-09-12, 0.0)` are the same instant, which the specification states plainly, and
different records, which it also states. So the first function that orders two valuation
dates, or measures elapsed time between them, meets a pair that sorts strictly but is
zero apart. Either drop the fraction until something consumes it, or define the ordering
key now — one fractional instant — while keeping both fields for display. Shipping it
undefined is the one option that costs later.

## 3. The Excel surface

### Argument help has no plumbing at all

Both specifications require per-argument help. `function_specs()` returns
`(name, description, [parameter names], hidden)`, and the host builds
`new ExcelArgumentAttribute { Name = p }` — with no `Description`
([AddIn.cs:429](../../host/Goosedove.Host/AddIn.cs)). There is nowhere for the wording
to go.

The change is small and touches both sides at once, which tenet 4 makes easy: widen the
tuple, set the description, and let the host and bridge move together. Two things to
know while doing it:

- One draft string is already too long. `values` in `discount-curve.md` is **292
  characters**; Excel's argument help is about 255. Measured, not estimated.
- IntelliSense and `[ExcelHandle]` processing both live in the
  `ExcelRegistration.ProcessFunctions()` pipeline. This host calls
  `ExcelIntegration.RegisterDelegates` directly and bypasses it. The research document
  says this about handles; it is equally true of the in-cell help the screenshot shows.

### The `util_` prefix is solving a problem Excel already solves

Excel groups functions in the wizard by Category, and the host currently sets none.
A `util_` prefix also puts two conventions in one name, which tenet 5 is about. Add
`category` alongside the description when widening `function_specs()`, and let the name
be `InterpolateDiscountFactors`.

### The seam's error messages are good, and the library should copy their grammar

Run against the real bridge, the mistakes a user actually makes produce:

```text
selected the table including headers -> values cell (1, 1) is text 'date', expected number
one blank cell in the body           -> values cell (2, 2) is blank, expected number
a date stored as text                -> values cell (1, 1) is text '2026-05-22', expected number
forgot the second argument           -> values is missing, expected array of numbers
headers and body swapped             -> header_row is 3x2 array, expected row of text
```

Each names the argument, the cell as `INDEX` counts it, what arrived and what was
expected. The specifications ask for library messages naming rows and offending pairs
but do not say they should use this numbering. They should — one numbering scheme, or
the user reconciles two.

Worth noting what the seam does *not* catch: three headers against a two-column body
passes the seam untouched, exactly as decision 14 says it should. That check is the
library's, and the specification correctly assigns it.

Finally, `Registered.run` renders a library rejection as
`#ERROR CreateDiscountCurve: ValueError: ...`. The exception type is deliberate under
tenet 2, so the library should choose types that read well in a cell rather than
defaulting to `ValueError`.

## 4. Testing and measured work

### The work counter cannot reach the library, and two rules disagree about whether it should

`tests/performance/test_work_budgets.py` establishes the idiom — `price_group(quantities,
prices, counter)` takes the counter positionally and returns `(result, WorkCounts)`. But
a worksheet function's signature *is* the seam contract. It cannot take a `WorkCounter`,
because `_parameter` refuses any annotation not in `_DECLARED`, and it cannot return a
tuple, because `_result` refuses any return not in `_RESULTS`.

So there is no stated mechanism by which a registered function creates a counter, threads
it inward, and disposes of the counts. Underneath sits a real conflict:

> CLAUDE.md: "Code that prices, caches, hashes, or converts data takes a `WorkCounter`
> and reports what it did."
>
> Golden rule 9: "It does not thread collectors through pricing code."

Both cannot hold for a function reached through the seam. The first library pull request
is the first thing to hit this, and it is much cheaper to decide now than inside a
review. Under the precedence table the simpler thing wins on a tie, which points at
counting at the boundary the caller controls — the registered function — rather than
inside the math.

### Smaller notes

- **The worked examples are goldens.** "Never change source and golden files in the same
  pull request" means the eight-row interpolation table lands as a golden file *before*
  the implementation, or the implementation lands with the comparison failing. Say which.
  The table itself is correct: reproduced through `np.interp` it agrees to 1.1e-16.
- **Name the invariants, not just the examples** (golden rule 20). For interpolation:
  every interpolated value lies between its bracketing knots; knots are preserved
  exactly; output is non-increasing given non-increasing input; already-daily input is
  returned unchanged; the row count is `days(last - first) + 1`. These survive a
  regenerated golden; the eight-row table does not.
- **The specifications name no counters.** The template below fixes this.

### The round trip is not a performance problem — do not argue it as one

A ten-year daily curve is 3,631 rows, 7,262 cells. The utility call plus the curve call
costs roughly 7,334 cells scanned, 66 KB in, 58 KB out, one result copy and six seam
trips (two ranges are three trips, per the measured `Dot` row in
`baseline/host-work.csv`). The seam already carries a measured 10,000-cell control.

The objection to spilling a daily table and reading it back is that a user must host
3,631 rows on a sheet, which is ergonomics. It is not cost, and arguing it as cost will
lose.

## 5. How to structure the specifications themselves

This is the part the brief actually asked for.

### Split every contract table by who checks it

The single change that most improves these documents: every specification's contract
table should have two halves, **checked by the seam** and **checked by the library**.
Today they are intermingled — `discount-curve.md`'s acceptance table puts "blank cell in
the numeric body: reject through the existing seam rules" three rows from the
daily-coverage rule — and a reviewer cannot tell at a glance whether a check happens
once, twice or never. That is the repository's central rule, and it is currently the one
thing the documents make hardest to audit.

### A template

| Section | Holds | Notes |
|---|---|---|
| Purpose | What it is for, in two sentences | |
| Worksheet contract | The typed signature and the formula a user types | |
| Checked by the seam | One row per argument: declared type, what that rejects | Cites `inputs.md`, never restates it |
| Checked by the library | One row per rule of meaning, with its exact message | Only rules the seam cannot express |
| Representation | What Python receives and what is retained | |
| Errors | The exception type and the message grammar | Uses the seam's `(row, col)` numbering |
| Work counted | Counter names and expected counts | Currently missing everywhere |
| Excel help | Function, then one row per argument, within 255 characters | |
| Acceptance | Examples, properties and goldens, labelled as such | Drop anything a seam test already covers |
| Open | Decisions deliberately deferred, and what would settle each | Already done well |

### Cite the seam; never restate it

`docs/seam/README.md` says "nothing about the seam is written anywhere else". The serial
bounds `61`/`2958465`, the whole-serial rule, the 1904 policy and the blank-versus-missing
distinction are now restated across four library documents. When the seam moves, four
documents drift silently. Link instead.

### A package layout, since none is proposed

```text
src/goosedove/
    units/          UnitConversions: the shipped definitions and the conversion math
    market/         ValuationDate, DiscountCurve, the calculation context of Fork 2
    dates/          the one place that mints dates and enforces the bound
    excel/
        bridge.py   the seam. Imports nothing from the library except in:
        objects.py  handle kinds: imports library types, registers them (§1)
        functions/  the registered worksheet functions, one module per group
```

The rule that makes it work is the one already in the documents: nothing under
`units/`, `market/` or `dates/` imports `goosedove.excel`. `objects.py` is the only
place where the two sides meet, and it depends on both so that neither depends on the
other.

### On volume

The four specifications are about 60 KB, roughly three times `bridge.py` itself, for
functions that do not exist yet. The content is good and the care is real — this review
was only possible because the documents are so explicit. But prose is a maintenance
surface too (anti-principle A11), and the template above plus "cite, don't restate"
should hold the next twenty specifications to a size that stays true.

## Two things this review is not

It does not propose an instrument taxonomy, and it does not resolve handle lifetime.
Both are correctly open.

It also does not treat every deferred decision as a fault. The documents are a planning
snapshot that says so on its first line, and most of what they defer they defer
knowingly. The three findings at the top are different in kind: they are not decisions
left open, they are decisions that cannot be left open, because work scheduled to start
now depends on each of them.
