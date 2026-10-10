# Trade valuation pipeline: design and engineering handoff

**Status:** Working design for review, 3 October 2026. No production implementation in this packet.\
**Purpose:** Make the responsibilities and connections understandable before choosing their implementation.\
**Reading order:** This overview, instrument definitions, CreateTrades and its retained state, then the worked example and individual responsibility documents.

## How to use this handoff

This packet is the authoritative design for the next trade implementation. Read it alongside
the linked instrument-reader and template function specifications. Its agreed boundaries and
economic meanings govern the work; its explicitly open questions still need decisions in
their implementation slices. Internal types and array layouts remain engineering choices.
Surface any proposed change to an agreed boundary or economic meaning for design discussion.

**Naming update, 10 October:** PR #174, reviewed at `29fe38f`, renamed the broad
instrument from `future` to `fixed_float`, keeping the existing cleared/bilateral routes.
The [bilateral representation inventory](bilateral-discounting-and-dv01.md#trade-representation-field-inventory)
records the agreed fields, new counterparty and nonnegative marketing reserve, and the
agreed direct curve input at evaluation. Futures index/schedule names remain.
The [rename-only ticket](rename-instrument-fixed-float.md) is complete on the reviewed
prototype, and [counterparty and marketing reserve](booking-fields-and-marketing-reserve.md) is built in
#NN, awaiting review; then the private bilateral kernel and its evaluation/reporting integration. Older
design passages below retain their historical wording; this update and the bilateral
plan define the current delivery arc.

| Material | How engineering should use it |
|---|---|
| This packet and its linked function specifications | Current pipeline, field policy, responsibilities and acceptance targets |
| [Trade surface UAT notes](surface-uat-notes.md) | Implemented features and release-testing checklist, suggested order for pending engineering work, and the detailed owner decisions behind each item |
| [Human readable index names](readable-index-names.md) | Required `display_name` at index creation, retained as descriptive text and exposed through index readback |
| [Brokerage and clearing reserve totals](reserve-totals.md) | Implemented static cost totals read through `_ReportReserves`; marketing the optional manual amount since #NN |
| [Shift a date by a text offset](date-offset-utility.md) | Implemented in PR #171: explicit date plus signed `bd`, `cd` or `em`, optional holiday calendar, returning one date without valuation context |
| [Contract codes and dates on one ticket](contract-codes-and-dates.md) | Implemented in PR #172: choose dates or code per row; complete dates take precedence, with blank and empty-text absence scoped to the three period fields |
| [BAL dates from a valuation-date handle](date-helper-inputs.md) | Implemented and reviewed in PR #173: explicit handle supplies BAL `as_of`; future periods start at their first day, expired periods fail, and users freeze booking dates by pasting values |
| [Numeric trade IDs](numeric-trade-ids.md) | Accept whole-number source-system IDs directly from Excel, retain numeric attribution and spill numbers, preserving duplicate occurrences |
| [IFERC basis futures](iferc-basis-futures.md) | Monthly basis futures through the existing pipeline: publication-date fixing, last-trading-date payment lag, aggregate values and lot risk |
| [Delta by day, month and year](daily-risk-vector.md) | Saved lot-delta vectors aggregated by observation time across payment groups; `_ReportDelta` selects the reporting bucket, with unchanged valuation ownership |
| [Calendar driven Asian pricing references](calendar-driven-asian-references.md) | Generic daily reference resolution from the index schedule/calendar, separating averaging month and payment ownership from the futures supplying prices |
| [Lot-delta reporting](lot-delta-reporting.md) | Engineering ticket for delta in an explicitly designated index-specific lot, preserving monetary valuation coefficients |
| [Rename future to fixed_float](rename-instrument-fixed-float.md) | Implemented and reviewed in PR #174: catalog/caller cutover only, with unchanged fields, numerical results and work budgets |
| [Counterparty and marketing reserve](booking-fields-and-marketing-reserve.md) | Implemented in PR #NN, awaiting review: bilateral counterparty attribution and optional static marketing cost on either route, summed once per original trade row and read through the existing reserve report |
| [Bilateral discounting and DV01](bilateral-discounting-and-dv01.md) | Agreed: optional curve at evaluation, as-of anchor, payment-date DFs, analytic signed DV01; both risk readers spill nominal_delta and delta with unchanged signatures. Measure added work; no new public rate preparation step |
| [Golden harness plan](../ethane-golden-validation-harness.md) | Active plan for independent financial expectations and separately reviewed production snapshots |
| [Contract survey](../../futures-trade-field-review.md) | Product facts and examples for checking coverage, not a second trade schema |
| [Dense matrix specimen](../../linear-trade-matrices.md) and PR119 | Evidence for arithmetic and measured work; their helper names, component outputs and layouts do not prescribe production APIs or tick work |
| [Archived pipeline](../../archive/trade-pipeline/linear-trade-pipeline.md) and [archived preparation proposal](../../archive/trade-pipeline/trade-evaluation-preparation-reuse.md) | Design history only; their superseded APIs and delivery plans are not additional backlogs |

## Intended outcome

Start from a library-owned instrument definition. CreateTrades resolves the accepted terms
and statically encodes their contributions and market inputs. Binding connects those inputs
to a supplied market state; evaluation produces named valuation and risk measures.
The target has **two route-specific value fields plus explicitly distinguished risk measures**, all completed
before the results handle is published. The agreed pairs are `bilateral_mark`/`bilateral_cash`
and `cleared_mark`/`cleared_cash`. [Result fields by route](result-fields-by-route.md) defines
their meanings and the proposed cumulative scope and date-driven settlement convention;
the 10 October bilateral steer specifies analytic signed DV01 and both nominal and
valuation-weighted lot delta. Risk readers spill `nominal_delta` and `delta` together:
equal for cleared, with `delta` discounted for bilateral. No basis-selection argument is
added. See the bilateral plan for the public header cutover. One result has separate valuation and risk sections
with shared context; [evaluation](04-evaluation.md) coordinates small private operations that
reuse current inputs and amounts. Margining is outside this initial model. The first undiscounted amount specimen
is an intermediate step, not that full result.
Readers consume the resulting snapshot without repricing it. **The supplied collection is
the unit being valued:** one aggregate result for its compatible amounts and market risks.
For an individual trade, evaluate a collection containing that trade. One and many use the
same path; every occurrence contributes, including duplicates. Retained source trade facts
do not imply that each evaluation also computes individual trade values.

The instrument catalog is a prerequisite. Resolution and encoding are private children of
the public CreateTrades operation; subsequent responsibilities have their own boundaries.
They do not require a worksheet function, public handle or class for every responsibility.
Engineering should be able to show each input and output independently while keeping
the normal Excel workflow short. Cash records have their own approved meanings and schemas;
they are not forced to carry the executed fields of a commodity trade.

```mermaid
flowchart LR
    I[Library-owned definitions] --> A[Shared template fields + ticket fields]
    A --> B
    subgraph CT[CreateTrades - public wrapper]
        B[Resolve trade terms] --> C[Encode static contributions and market inputs]
        C --> T[TradeBatch: resolved + encoded]
        B --> T
    end
    T --> D[PrepareTrades - explicit prepared handle]
    H[History including as-of and defined live layout] --> D
    D --> E[EvaluateTrades - compatibility then evaluation]
    P[Compatible market with current prices] --> E
    Q[Applicable current rate inputs - interface to specify] --> E
    E --> R[5. Immutable valuation and risk result]
    R --> V[6a. Valuation reader - mark and cash]
    R --> K[6b. Risk reader - delta and DV01]
```

The valuation reader and risk reader are the first two result-reader responsibilities.
They close the initial **trade-to-results pipeline**: both consume the same completed
snapshot, with no further market access or valuation. A leg-decomposition reader or richer
reporting views can follow later; they are not additional prerequisites for this first path.

This is an end-to-end design, not an end-to-end implementation claim. Static index/product
definitions and market creation supply upstream inputs. Detailed schemas, Excel declarations,
the rate-input interface and risk conventions still need specification within the existing
boundaries. The next implementation should trace a small worked collection through this
complete path, rather than introduce more pipeline stages.

| Stage artifact | Question it settles |
|---|---|
| [0. Instrument definitions](00-instrument-definitions.md) | Which instruments, fields, values and combinations may users construct? |
| [CreateTrades and retained state](create-trade.md) | How do the two private children create one immutable trade batch, and what does its handle retain? |
| [1. Resolution and representation](01-trade-representation.md) | What deal was agreed, under which definitions? First child of CreateTrades. |
| [2. Static encoding](02-static-encoding.md) | Which numerical contributions and market inputs follow from the resolved terms? Second child of CreateTrades. |
| [3. Market binding](03-market-binding.md) | Which market inputs come from history, and which from the live market? |
| [4. Evaluation](04-evaluation.md) | Which numerical operation produces the requested measure and risk? |
| [5. Results](05-results.md) | What do the returned numbers mean, and which inputs produced them? |
| [6. Readers](06-readers.md) | How does Excel inspect those results without new valuation work? |
| [Worked example](worked-example.md) | Can we trace the same trades and independently known answers through all six? |
| [NG creation/preparation example](ng-creation-preparation-example.md) | How do five signed occurrences compress to two exposures, with independently checked values and a separate toy payment lifecycle? |
| [Excel trade-input binding proposal](excel-trade-input-binding.md) | What seam extensions, reference lifetimes and terminal market behavior does the proposed surface need? |
| [Prepared matrix walkthrough](prepared-matrix.md) | How do many trade contributions become one batch exposure vector before evaluation? |
| [Aggregation performance](aggregation-performance.md) | What does a synthetic 100/1,000/10,000/100,000-trade timing show, and what does it exclude? |
| [Batch boundaries and discounting](batch-boundaries-and-discounting.md) | How do a shared template, index scope, payment groups and current rate inputs fit before final compression? |
| [Fixing and payment state](fixing-and-payment-state.md) | What does an ICE Henry Hub calendar strip establish, and how does a known price differ from paid cash? |
| [Proposed result fields by route](result-fields-by-route.md) | How do encoded payment dates move bilateral amounts into modeled cash, and which values/risks does each route return? |

These documents specify input/output meaning, dependencies, a toy payload and acceptance
conditions. The plural CreateTrades/PrepareTrades/EvaluateTrades boundaries are agreed design
names; detailed schemas/signatures remain drafts and do not commit to a storage format.

The agreed supporting readers for the instrument-definition stage are
[_ListInstruments](../../library/instruments/list-instruments.md) and
[_ShowInstrument](../../library/instruments/show-instrument.md). They inspect library-owned
schemas without market inputs. List spills instrument and description; Show takes an
instrument identifier as text and spills one column per instrument field. The first column
contains `field`, `description`, `required`, `required_when`, `type`, `options` and `rule` as
row labels, giving seven rows and N + 1 columns for N fields. Field names span the first row
to match trade-row entry; metadata includes conditional requirements and the source of
contextual choices. Both return tables
from the same definitions used by construction; implementation remains pending. Specifications
for template creation and the CreateTrades wrapper now accompany them; final worksheet
declarations and later functions follow their own reviews. A library-owned schema does not
require building a separate product-catalog system:
the existing static definition objects can supply the initial reference facts.

The next constructor sketch is [_CreateTradeTemplate](../../library/trades/trade-template.md),
using a small CL/LOT defaults row. Its partial mixed values and static object references need
a targeted seam specification before implementation; its shape is not yet a supported call.

The [instrument field sketch](instrument-field-sketch.md) records the current schema pass:
the trade selects a library-defined `schedule_method` and a `quantity_per` of month or day;
templates can default both. Exact/CFD and physical-delivery handling are outside v1. Pricing
observations and payment dates remain separate. The sketch proposes method definitions,
calendar-day quantity semantics and library homes without implementing them. Existing
contract specifications retain their lot/quantity/fee responsibility. The proposed future
family can accommodate supported bilateral lookalikes without discarding their actual terms.

The next refinement admits monthly strips through the existing period grammar: CAL27 and
Z27-X28 resolve to monthly components, each with its schedule method, quantity allocation
and payment date. Explicit date-window inputs remain deferred. Specification data comes
from Index, with the selected row named by the template/ticket. The proposed future field
is fixed_price. Trade creation is not yet implemented.

The [cleared payment review](fixing-and-payment-state.md#cleared-payment-convention-selected-rule-and-resolved-date)
records the accepted starting point: payment_time_lag, a string such as "+1bd", and
payment_holiday_calendar, supplied in the trade row or template. The supported product
definition establishes the actual traded contract's last-trading-day anchor and strict-after
counting. PHH uses "+1bd" and ETE "+2bd". CreateTrades parses the lag once and stores a
resolved payment_date per monthly component. Reuse the existing HolidayCalendar handle
and NumPy business-day arithmetic. Pricing calendars and final fixing dates are separate.
Broader bilateral payment conventions remain deferred; their limited coverage is accepted
for this first step. This design agreement does not imply implementation. Exact-date inputs
and zero-day adjustment semantics also remain deferred.

The larger grouping is: **instrument definitions -> CreateTrades (resolve, then encode) ->
market binding and preparation -> evaluation -> results -> readers and reporting views**.
The agreed first approach retains preparation in an explicit `_PrepareTrades` handle.
Market input descriptors identify the data to bind; they contain no current prices or
history-dependent flags at creation.

## How to reason backward, then build forward

First work backward from the requested outputs:

1. Name the measure and risk axes: projected unpaid payment amount, entry-price P&L or NPV;
   USD per price unit, delta in lots, or a specifically defined rates risk.
2. Identify the evaluation inputs needed to produce those outputs. NPV requires payment
   dates and valuation treatment; DV01 uses the agreed analytic parallel-zero-rate sensitivity,
   beyond the commodity price matrix alone.
3. Identify the bound observations, market coordinates and known amounts those inputs require.
4. Identify the static quantities, schedules, conversions and component ownership that binding needs.
5. Identify the executed fields and shared definitions needed to create those static facts.
6. Establish the approved instrument schema and allowed combinations that constrain those fields.

Then trace the worked example forward and implement a small complete path. Do not build all
possible trade representations before evaluating one example, or force every future product
to conform to PR119's present record names.

The arithmetic should become straightforward when these contracts are correct. Economic
meaning, dependency validity and ownership still need explicit decisions; they do not follow
automatically from matrix multiplication.

## Intent we should preserve

- A trade is a consummated deal. Market values do not rewrite its executed terms.
- Users select library-owned instrument definitions; they do not author new payoff schemas.
- Template and ticket fields must match the selected definition's identifiers exactly.
  Unknown fields, aliases, case/whitespace variants and arbitrary extra metadata fail;
  column order may vary. ShowInstrument exposes the accepted field names.
- A template provides shared fields under its selected instrument definition. Template and
  ticket fields must be disjoint; even equal duplicates fail. Specifications and conventions
  provide static reference facts through the Index.
- CreateTrades wraps two private jobs: resolution establishes meaning; encoding derives
  static numerical contributions and market input descriptors from those resolved facts.
- Keep `fixed_leg`, `floating_leg_set` and `floating_leg_live` distinct for fixed/float products.
- Bind from explicit inputs. The index identifies the reference; it does not choose an ambient market.
- Ordinary commodity-price updates should perform no contract parsing, calendar generation,
  static encoding or historical-fixing folding once a valid preparation is retained.
- Preserve trade occurrences, observation identities, market axes, units and payment ownership.
- Keep evaluation and risk in one coherent input context. Readers never produce a new valuation.
- Optimize the demonstrated workload. Full-batch vectorized evaluation is an acceptable starting point.

“Volatile price vector” here means frequently changing values. It is not a requirement to
register every worksheet function as an Excel-volatile function.

## Agreed worksheet boundaries; creation arguments remain open

```python
_CreateTrades(...)                 -> trades_handle
_PrepareTrades(trades, history)    -> prepared_trades_handle
_EvaluateTrades(prepared, market)  -> results_handle
```

Plural names express the agreed cardinality contract: one handle represents one or many
trade occurrences, and a single occurrence uses the same batch path. Cardinality refers
to trades inside a handle; accepting or combining several handles is a separate future
interface question. For the initial compatible undiscounted amount measure, preparation
sums exposure by identified live market input and retains aggregate fixed/set amounts.
Evaluation prices that aggregate vector. This supersedes the earlier assumption that every
batch evaluation must also return one result per trade. Original occurrences and payment
facts remain in the retained source batch; duplicate occurrences contribute twice.

The current trade-input sketch preserves the optional template last:

```text
_CreateTrades(index, fields, trade_rows, [template])
```

Adding the instrument catalog exposes a missing distinction: an index does not choose an
instrument type. The same reference can underlie a future or swap, while cash has no commodity
index. The constructor therefore needs explicit instrument context, directly or through a
selected approved template. The instrument selection without a template and the authoritative
source of index remain to settle. The final argument list remains open; see
[instrument definitions](00-instrument-definitions.md) for the selection flow.

fields is the agreed column-header argument. No labels argument is included; aliasing is
a separate future use case. trade_id remains optional attribution in the trade fields,
independent of the retained identity of every occurrence. Every call represents one or
many trade rows. Resolution and encoding
are private children of CreateTrades, whose handle retains both outputs. Result readers consume
an evaluated result handle. Valuation and risk are the first two reader responsibilities;
their public names and table layouts remain to be designed.

`_PrepareTrades` applies complete supplied history to the static encoding, retaining
the batch's `floating_leg_set` and summed live exposure vector. Its fixed-leg total can be
retained from static creation. History carries as-of context. The initial
signature assumes that its live layout/projection is determined by history and retained
static definitions; any independently variable mapping needs an explicit dependency.
`_EvaluateTrades` checks market compatibility, obtains the aligned live prices and evaluates.
It does not silently prepare again if the market's history or layout is incompatible.
Summing is done during preparation, not rebuilt by every price tick. The initial single
aggregate assumes compatible amount meaning and currency. Future NPV support must apply
payment-specific treatment before summing; the single undiscounted total is insufficient
for discounting several payment dates. Preserve those source facts without pricing unused
per-trade outputs now.

| Change | Initial work policy |
|---|---|
| Trade or used static definitions | Create, prepare, evaluate |
| Fixing arrival/correction or as-of change | Prepare the whole batch from history, evaluate |
| Live prices only, compatible history/layout | Evaluate the retained preparation |
| Reader selection | Read existing results |

This selects the explicit preparation handle over the earlier private-store candidate for
the first implementation. Preparation inside CreateTrades is also outside the agreed static
creation boundary. Excel handle ownership and release still need integration proof, but
a separate history cache, incremental fixing patches and per-row preparation reuse are not
prerequisites. Do not feed live prices into the preparation formula.

## What PR119 contributes

[PR119](https://github.com/gobbles404/goosedove/pull/119), last checked at `60ae5d2`, is an
experiment we can retain, change or replace. It does not define the pipeline's domain model.

| Existing piece | Evidence/useful role | Missing surrounding contract |
|---|---|---|
| `Terms` | Static coefficients and fixed amounts | Actual trade encoder, observation identities, units and attribution |
| `Binding` | Fixed flags, prints and live mark positions | Adapter from meaningful observations and real history/layout |
| `Compressed` | Folded set contributions and live exposures | Ownership, validity and retention across Excel updates |
| `compressed_amounts` | Small full-batch tick calculation | Evaluation measure, valuation treatment, risk/output contract |
| Numerical examples and work budgets | Starting evidence for arithmetic and cost | Independent financial acceptance and end-to-end Excel behavior |

The market/history split predates the new kernel and remains useful evidence. Neither it nor
the kernel automatically provides the prepared-handle lifecycle. Preserve independent expected answers
and useful tests even if their present production implementation is replaced. A failing
comparison should be understood, not removed merely because architecture changes.

## Suggested delivery and review gates

### Handoff readiness: one concrete function-contract pass

The packet is ready for engineering review and scoping. Before authorizing an end-to-end
implementation against it, complete one focused pass through the first supported example.
The architecture and responsibility boundaries are established; several public calls and
payloads are still illustrative. This pass should fill those contracts rather than reopen
the pipeline or require every future instrument to be designed.

| Boundary | Already established | What the concrete pass must finish |
|---|---|---|
| Instrument inspection | Library-owned definitions; list and field-detail spills | Approved first future field set, exact supported product/treatment and constructible combinations |
| Template | Instrument first; optional partial shared fields; template/ticket overlap fails even for equal values; blank is not omission | Review and implement the [typed partial-input proposal](excel-trade-input-binding.md) |
| CreateTrades | Private resolution plus encoding; one immutable batch for one or many occurrences; fields names the column headers; optional template last | Instrument/index source for template/no-template paths, ticket column names/types/units, and first batch compatibility rules |
| PrepareTrades | Explicit history/as-of input; complete rebuild on history changes; retained set amounts and live exposure; [worked payload](ng-creation-preparation-example.md) | Review the concrete mapping and the proposed terminal market path before claiming the fully fixed lifecycle |
| EvaluateTrades | Small orchestration; shared inputs; completed mark/cash/delta/DV01 result | First product's numerical definitions and units; explicit compatibility checks; identify the separate rates-input/DV01 decisions needed before bilateral support |
| First two result readers | Pure valuation and risk views of the same completed snapshot | Exact names/arguments and expected spill headers, units, coordinates and shapes, including singleton/empty-risk cases |

For each callable boundary, capture the worksheet call, one toy input table, the logical
output/array shapes, validation ownership, and which input changes require work. State
examples of rejected inputs and the offending field/row. Exact error prose can follow the
existing seam conventions. Private helpers need clear typed array contracts, not frozen
class hierarchies or a worksheet function for each substep.

The constructor design includes the no-template path. Establish its direct instrument
selection before claiming the complete creation contract. The proposed schema uses
`quantity` plus `quantity_unit` and `contract_code`; validate their meanings for the first
product without introducing silent field aliases.

The [NG creation/preparation example](ng-creation-preparation-example.md) now specifies the
small collection: opposite signs, two contracts and a duplicate occurrence, with static and
prepared arrays and independent hand answers. Its real NG portion covers open-contract
economic marks. A separately labeled toy product checks fixing and payment transitions;
it does not invent financial settlement for physical NG. The fixture also identifies the
preceding schedule contract needed to build the real market calendar.

Then use the existing [average fixture](worked-example.md) as a design check for partial
fixings and different payment dates. Show hand answers and expected reader cells before
building snapshots. The existing fixture proves amounts and illustrative PV/delta; its
bare discount factors do not define DV01, and it is not yet a complete Excel function trace.

Separate the first delivery from the broader design check. A narrow cleared NG path can
start before bilateral rates are implemented. Specify the actual listed product and the
lifecycle covered: an open-position specimen must not imply support for physical delivery
or treat expiry automatically as a financial payoff. In an explicitly undiscounted specimen
with no finalized components, zero cash and zero DV01 are supported answers, not substitutes
for unimplemented lifecycle or bilateral rate risk. Fully fixed/payment-date behavior needs
its own supported path before that scope is claimed.

Pin event acceptance alongside numerical answers: a price tick performs no creation or
fixing fold; a fixing correction/as-of change prepares afresh; a reader performs no pricing;
duplicates count and aggregate equals summed compatible singleton results. Include wrong
market identity/order, required missing fixings, date cutoff and handle release in the slice
where each behavior is introduced. Exact work counts can be proposed by engineering from
the selected representation; zero unwanted work at these boundaries is part of the contract.

Three current-code gaps must be visible in the relevant implementation slices:

- [Template transport](../../library/trades/trade-template.md) does not yet support the
  proposed schema-selected partial record with typed references. The
  [Excel binding proposal](excel-trade-input-binding.md) specifies the proposed extension,
  error ownership and dependency/lifetime acceptance cases.
- The current PriceVector's display name and positional values cannot verify a silently
  permuted input, and Market rejects an entirely fixed calendar. The Excel binding proposal
  makes the current positional alignment limit explicit and recommends an optional-vector
  terminal market extension. That recommendation still needs approval and implementation;
  it is not an agreed change to the market API.
- Current Market carries no rate context. The 10 October bilateral plan now specifies
  a separate curve argument at evaluation, the as-of anchor, payment-date DFs, analytic
  signed DV01 and both lot-risk columns. That agreed extension remains unimplemented;
  it is not a prerequisite for the narrow undiscounted cleared specimen.

Engineering can choose internal module/class names, compact versus dense storage, and
temporary allocation strategy while preserving the agreed contracts and measured work.
Have engineering map existing main/PR119 components to reuse, adapt or replace at the start
of its slice; neither wholesale reuse nor wholesale replacement is preselected.
Review a small runnable path and its independent expected answers before broadening scope.

### Delivery slices

1. **Contract review:** start with the approved instrument schema, then walk the shared example
   through the six per-record stages, including the two payment dates. Decide the first result
   measure and mark-risk units. Record remaining choices.
2. **Small executable specimen:** manually supply the resolved inputs; prove amounts, risk,
   batch total equals the sum of separate singleton evaluations, fixings and missing-input
   behavior. PR119 may supply the arithmetic. This is still a prototype.
3. **First complete product path:** NG trade rows through construction, encoding, binding,
   evaluation, results and one reader. Name the entry-price P&L measure explicitly if that is
   the chosen starting output. Prove actual worksheet dependencies before claiming tick reuse.
4. **Averaging path:** add a narrowly specified product using independently reviewed ethane
   examples; prove fixing transitions and corrections through real schedules and adapters.
5. **Payment valuation and rate risk:** introduce NPV per payment and a defined DV01 measure
   after the amount path is understood. The illustrative PV column in this packet is not a
   promise that rates support ships in the first product release.

Use one thin vertical example early, then broaden each stage as new cases demand. A feature
branch can hold this exploration and its runnable specimen; branch topology does not decide
architecture. Before creating one, choose whether its base is main or an inspected PR119
revision, use an isolated checkout, and keep incremental reviews focused. This packet creates
no branch and changes no production code.

The [golden harness plan](../ethane-golden-validation-harness.md) supplies the separate
financial-reference and snapshot workflow. Snapshots of a standalone specimen do not become
production goldens. Required comparisons include first evaluation, unchanged repeat, commodity
tick, fixing update, date roll, trade amendment, rate-input change when supported, and reader-only calls.

## Decisions to make before their implementation slice

| Decision | Needed by |
|---|---|
| Approved first prototype fields, static reference facts and supported product combinations; disjoint template/ticket field policy is established | Instrument-definition slice |
| How instrument context enters the constructor, including cash without an index | Public input API |
| First product's exact mark/cash semantics, risk units and required booking fields; mark/cash naming and rejection of duplicate field sources are established | Trade/encoding slice |
| Observation identity, publication cutoff, missing-fixing policy and forward projection | Binding slice |
| Where static unit definitions and market-axis identities live | Encoding/binding slice |
| Ownership/release of the selected explicit prepared handle across updates/workbooks | Excel integration slice |
| Fully fixed market route; current kernel supports zero marks but current Market requires an unfixed period | Fully fixed Excel integration |
| Modeled payment cutoff/cumulative scope, common risk conventions, reader declarations/layouts, completeness and reader ownership | Result/reader slice |
| Initial one-curve discounting treatment, as-of anchor, analytic signed DV01 and nominal_delta/delta readers are agreed in the bilateral plan; cross-result aggregation remains deferred | Implement in rates slice |

Dense versus sparse arrays, shared exposure-pattern evaluation, selective repricing, incremental
fixing edits, row-level cache reuse and broad product inheritance are not prerequisites for those contracts. Measure before
choosing them. Report unsupported measures explicitly; a zero result is not a placeholder.

## Relationship to earlier artifacts

The earlier [pipeline parent](../../archive/trade-pipeline/linear-trade-pipeline.md) and
[preparation-reuse ticket](../../archive/trade-pipeline/trade-evaluation-preparation-reuse.md)
are archived. In particular, the private history store, mandatory per-trade tick results and
earlier delivery sequence do not carry forward. The explicit PrepareTrades handle and
aggregate evaluation described here supersede them. Preserve useful financial examples
when replacing a specimen implementation, and validate the new path against independently
reviewed expectations.
