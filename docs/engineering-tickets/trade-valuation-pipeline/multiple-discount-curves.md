# Named discount curves within one trade batch

**Status:** Agreed feature direction, updated after engineering feedback on 18 October 2026. The collector is `_CollectDiscountCurves`; every bilateral trade keeps an explicit curve key, including the one-curve case. [Cashflow PR200](https://github.com/gobbles404/goosedove/pull/200), including its mapping-array fix, is merged; its cashflow collection follow-up is folded into slice 2, [named-curves-slice-2.md](named-curves-slice-2.md), as decided on 18 October. This arc precedes [template-based quoting](template-based-quoting.md).

**Starting point:** Main after the single-curve cross-gamma, contract interpolation, curve-bump and cashflow work. Record the actual base and any subsequent cashflow dependency when implementation starts. Use a feature branch and a short sequence of independently reviewable PRs.

[Pipeline](README.md) · [UAT notes](surface-uat-notes.md#24-multiple-discount-curves-within-one-trade-batch) · [Curve](../../library/globals/discount-curve.md) · [Evaluation](../../library/trades/evaluate-trades.md) · [Risk](../../library/trades/report-risk.md) · [Collection](../../library/trades/aggregate-results.md)

## Outcome and scope

A bilateral `fixed_float` batch can contain trades discounted on different named curves, such as SOFR and FFOIS. A template or ticket row names the curve to use; evaluation receives the current curves. Updating a curve changes results without recreating the trades or applying the same fixings again.

The commodity index and route remain uniform within a batch. Keep the existing currency, settlement, payment-date and quantity rules. A cleared batch remains undiscounted. This arc changes which supplied discount curve each bilateral payment uses; it does not introduce different discounting formulas, construct SOFR/FFOIS curves from market instruments, or establish that those names match any external source.

The initial implementation targets `fixed_float`. Preserve cashflow's existing single-curve behavior. Coordinate any internal adaptations when shared payment, result or collector interfaces change, and migrate its curve-creation calls when the name argument is added. Multiple-curve cashflow booking and evaluation remain a separate, explicit extension.

## Fit with the cashflow implementation

PR200 makes the shared boundary concrete: `globals/payments.py` owns `time_fractions`, `curve_starts_on`, `factors_on` and `discounted`. Both valuation paths use that arithmetic. Extend the trade evaluator's binding and grouping around it; do not create a second implementation of discounting or DV01 for the several-curve case. Payment ownership, paid status and the required coverage remain each evaluator's responsibility.

The cashflow public path stays:

```text
_CreateCashflows(fields, cashflow_rows, template)
_EvaluateCashflows(cashflows, valuation_date, discount_curve)
```

Its curve becomes named through the shared creator change, but its evaluation still takes one ordinary curve directly. It needs neither a `discount_curve_key` field nor a singleton set in this arc. This is the cashflow contract, not a compatibility alternative on `_EvaluateTrades`. When common reporting labels are updated, show its supplied curve's name consistently without adding commodity risk or changing its mark/cash/DV01 meanings.

PR200 supplies `Cashflows`, `CashflowResults`, shared value/risk readers and readback; it deliberately does not put cashflow results into `_AggregateResults`. On 18 October, after slice 1, the owner folded that integration into slice 2 below, since the slice reworks the collector's rate groups, the labels and the readbacks in the one place the integration would touch: slice 2 lands cashflow-only and mixed trade-and-cashflow collections together with the curve-owned contributions, the cashflows keeping their single-curve evaluation and contributing their saved DV01 to the matching curve-and-currency group, and proves that adding a cashflow moves the right DV01 while the commodity delta and the cross-gamma stand.

## Agreed direction

The direction agreed in discussion is:

- Put the name on the discount curve when it is created. The collection holds those curves without assigning or replacing their names.
- Require a static selection key in every bilateral trade's terms, supplied through the template or ticket, even when evaluation receives only one curve. Keep live curve handles and factors out of those terms.
- Supply the collection directly to evaluation, in the existing rates-input position. Do not attach it to the commodity market or introduce a rates preparation function.
- Preserve curve ownership through compression, evaluation, saved risk and collection. Several curves mean several DV01 and cross-gamma vectors.

The public behavior is:

| Choice | Rule |
|---|---|
| One-curve trade evaluation after the change | Supply a singleton curve set to `_EvaluateTrades`, with the booked key matching its curve. Cut over kept callers; no direct-curve alternative and no implicit selection when a key is absent. |
| Name matching | Nonempty text, exact and case-sensitive; no trimming, alias or fallback to the first curve. Reject whitespace-only names and surrounding whitespace. |
| Extra curves in a set | Allowed. Validate valuation-date and payment coverage for the curves the batch selects; unused curves do not impose coverage requirements. |
| Two distinct curve snapshots sharing a name across evaluated results | Keep separate groups by exact object identity, as today; qualify both headings with the local curve number, `SOFR (curve_1)` and `SOFR (curve_2)`. A shared name never proves shared market state. |

Engineering should raise a concrete implementation conflict before changing these rules. The one-time caller migration is part of the arc, rather than a reason to introduce a permanent singleton exception.

## Worksheet functions and booking field

```text
_CreateDiscountCurve(name, header_row, table) -> discount_curve handle
_CollectDiscountCurves(curve_handles)        -> discount_curve_set handle

_EvaluateTrades(prepared, market, [discount_curve_set]) -> trade_results handle
```

`_CreateDiscountCurve` gains the required first argument. Its date/factor table, interpolation and validity checks remain unchanged. Curve creation still makes an ordinary curve, with its name retained and visible in readback and handle text, such as `pid:discount_curve:SOFR:N`, through the existing named-handle machinery. `util_BumpDiscountCurve(curve, bump_bps)` keeps its signature and preserves the source curve's name on the new object.

`_CollectDiscountCurves` gathers existing named curves; it does not construct their factors or combine them numerically. It replaces the earlier draft's `_CreateDiscountCurveSet` name, with no alias. The collection still uses ordinary creator publication, immutable references, reuse and release. Keep its handle compact, `pid:discount_curve_set:N`; do not concatenate member names into `SOFR+FFOIS` or use that text as an identity. Membership belongs in readback.

The set accepts a nonempty cell, row or column of curve handles through the existing handle-vector seam. It keeps references in supplied order and resolves no trade. Duplicate names fail, including the same handle supplied twice. Name uniqueness is local to this set; no process-wide registry is introduced. Readback shows membership and names, with curve coverage useful for inspection; it does not duplicate every daily factor table.

A base SOFR curve and its bumped SOFR curve belong in different sets. To make a scenario, construct another set containing the bumped SOFR curve and the same unchanged FFOIS curve. Do not rename the trade or mutate the original set.

Add this field to the `fixed_float` definition:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `discount_curve_key` | text | Bilateral route; refused on cleared route | Exact name of the supplied curve to use for this row's payments |

The field follows existing template/ticket rules: supplied in either place, never both. Rows may select different keys. Trade creation requires and validates the static field on the completed booking and encodes its ownership, but cannot verify a key against curves that have not yet been supplied. Templates may remain partial. Evaluation performs that binding once per distinct key. An absent booked field fails trade creation; a key absent from the supplied set names the key and the first affected ticket row at evaluation, with no results handle published. There is no exception based on the number of curves: a SOFR trade must not silently use a singleton FFOIS set, and adding an unused curve must not change a valid trade's selection.

The evaluator's third argument stays optional only because cleared evaluation needs no rates input. Bilateral evaluation requires a set even when it contains one curve, or the batch is fully paid. Cleared evaluation rejects a supplied set as it rejects a supplied curve today. Preserve the existing blank-versus-omitted argument rules.

Many evaluation formulas can reference the same collection cell. Migrate their input references; do not manufacture a separate collector cell per evaluation where the named curves and scenario are shared. Cashflow evaluation retains its direct ordinary-curve argument as specified above.

Example shape, with ordinary dates/factors in the two curve tables:

```text
B2 = _CreateDiscountCurve("SOFR", sofr_headers, sofr_rows)
B3 = _CreateDiscountCurve("FFOIS", ffois_headers, ffois_rows)
B4 = _CollectDiscountCurves(B2:B3)
B5 = _EvaluateTrades(prepared, market, B4)
```

The template supplies the other common bilateral terms. Ticket rows can then differ as follows:

| contract_code | quantity | fixed_price | discount_curve_key |
|---|---:|---:|---|
| G27 | 10 | 4.00 | SOFR |
| G27 | -5 | 4.00 | FFOIS |

There is no new argument to `_CreateTrades` or `_PrepareTrades`.

## Updating rates without changing a booked batch

The objects remain immutable. A changed curve formula produces a new named curve, its set produces a new set, and evaluation produces new results over the existing prepared batch. There is no function that edits a curve inside an existing trade or result handle.

| Change on the sheet | What is rebuilt | What stays reusable |
|---|---|---|
| SOFR's factors change, its name stays `SOFR` | That curve, the set containing it, evaluation and dependent result collections | Created trades, preparation, commodity market and the unchanged FFOIS curve |
| A scenario substitutes a bumped SOFR handle into a new set | Scenario set, scenario evaluation and its collections | Original set/results, created trades, preparation and commodity market |
| A ticket/template changes a row's `discount_curve_key` from `SOFR` to `FFOIS` | Created trades and their static grouping, preparation, evaluation and collections | The supplied curves and commodity inputs |
| A supplied curve is renamed without updating the booked key | The changed curve/set, followed by a visible missing-key evaluation failure | The booked terms; they are never silently redirected |

For the worksheet example above, changing `sofr_rows` updates B2, B4 and B5. B3 and `prepared` stand. The new result selects the new SOFR object by the same static key. A held old result keeps its original curve and values. Changing a single curve may reevaluate the whole batch initially; unchanged contributions must retain their numerical answers, but selective computation is not promised.

## Ownership through the pipeline

| Stage | Responsibility |
|---|---|
| Create and encode | Retain each row's key, carry it to components, and keep distinct payment groups when keys differ. Build static mappings and risk axes here. |
| Prepare | Apply history and as_of as today. Retain the key-to-payment mapping, unpaid payments and nominal exposure. Read no curve or discount factor. |
| Evaluate | Resolve selected keys to actual curves; gather factors for unpaid payments; calculate value, discounted delta, DV01 and cross-gamma with curve ownership intact. |
| Save results | Retain the exact curves used, payment factors and curve-specific risk vectors/totals alongside the combined commodity delta. Keep the source set by reference if useful; unused members create no risk groups. |
| Collect and report | Combine compatible saved vectors and display them. Read no quotes, fixings or factors, and recalculate no sensitivities. |

The current financial compression groups components by booked contract and payment date. Extend that identity with the static curve key before summing coefficients, fixed legs or set amounts. Existing slot identity remains payment group plus observation date. Two otherwise identical components on different keys must not net out before discounting.

Payment-factor lookup can deduplicate by selected curve and payment date even where different contracts have separate payment groups on that date. Keep this distinction: economic groups retain their existing ownership; a factor lookup is merely shared data gathering.

On evaluation, check each selected curve's start against as_of, then its coverage of the unpaid dates that use it. Preserve the existing paid cutoff: payment dates on or before as_of contribute modeled cash, no mark, and no rate risk. Do not request a historical factor for them. A selected curve still must satisfy the existing start-date requirement if its payments are all paid.

All producing steps keep the existing finiteness checks. A missing curve, wrong start, uncovered unpaid date or nonfinite calculation fails before publication, identifying the relevant key and date/group where applicable. No extrapolation, default curve or partial result.

## Saved risks and reporting

Keep the existing analytic conventions. For unpaid payment group `g`, with amount `A_g`, selected curve `c`, payment factor `D_c(t_g)` and `tau_g = (payment_date - as_of) / 365`:

```text
NPV_g          = A_g * D_c(t_g)
DV01_g         = -tau_g * NPV_g / 10000

discounted_live_lots_s = nominal_live_lots_s * D_c(t_g)
cross_gamma_s         = -tau_g * discounted_live_lots_s / 10000
```

Slot `s` belongs to group `g`. A curve's DV01 and cross-gamma mean a parallel one-basis-point rise in that curve's continuously compounded zero rates, holding commodity prices, fixings and every other curve fixed. Continue to calculate analytically; bumping is an independent validation method.

| Measure | Saved/reporting grouping | Time axis |
|---|---|---|
| `nominal_delta` | One combined lot vector per index | Observation day; pricing contract month/year |
| `delta` | One combined discounted lot vector per index, after applying each payment's factor | Same commodity axes |
| `dv01` | One vector and total per exact curve object and settlement currency | Payment day/month/year |
| `cross_gamma` | One vector and total per index and exact curve object | Same commodity axes as delta |

Retain the existing contract-axis risk where it is already stored. Do not substitute a payment-date axis for cross-gamma. Fixed-but-unpaid payments retain DV01 while their commodity delta and cross-gamma are zero.

`_ReportRisk(results, risk, bucket)` keeps its signature, selectors and required `day`, `month` or `year` argument. It works on one result or a collection. Delta remains one column per index; rate and cross-gamma columns expand per used curve. Keep the saved Total first and existing period-start/zero-bucket behavior. The reader selects saved vectors and performs only the alignment/formatting it already owns.

Use curve names in headings and readback labels throughout, including single trade results, cashflow results and collected results; the `cleared` label remains unchanged. For example, one result may show `SOFR USD dv01` and `FFOIS USD dv01`, and `HNG SOFR cross_gamma` and `HNG FFOIS cross_gamma`, with the current units/context rows retained. If a collection contains distinct snapshots both named SOFR, qualify **both** consistently as `SOFR (curve_1)` and `SOFR (curve_2)` in rate, cross-gamma and corresponding readback labels. Do not leave the first snapshot looking like the unqualified default. Local numbering and group order follow first appearance; the numbers and names are display labels, not identity keys.

`_AggregateResults` must accept several rate/cross contributions from each source result. It combines only matching exact curve objects and currencies for DV01, and matching exact index/curve pairs for cross-gamma. Existing index/history/price-vector compatibility checks and duplicate-occurrence counting remain. A mixed batch collected alone must report the same economics as its separate single-key batches collected together.

An overall saved DV01 or cross-gamma scalar, where needed to preserve current result/readback totals, means all used curves shifted by one basis point together. It is not the sensitivity to either individual curve. Preserve that meaning explicitly and retain the separate vectors/totals; add no new combined-risk selector. `_ReportValues` still shows the batch's aggregate mark and cash, and reserves are unchanged.

Readback must expose the static key on booked rows, the key on compressed payment groups and the actual named curve used on evaluated groups. Existing per-group amount, factor, NPV and DV01 remain inspectable. A collection's membership readback may no longer imply one curve per source; show its used curve names/identifiers without repeating its entire saved scalar for each curve. Agree the precise layout in the surface PR before editing positional workbook reads.

## Hand-worked acceptance

Use a synthetic HNG-style fixture with a reporting lot of 10,000 quantity units, prices in USD per quantity unit, and no fees. This is a mathematical fixture, not an exchange specification. Both trades observe the same live contract on 1 February 2027 and pay on 4 January 2028, exactly 365 days after as_of 4 January 2027. The market quote is 4.10; both fixed prices are 4.00. Use a schedule/calendar that makes those observations valid.

| Row | Lots | Curve | Payment DF | Amount | Mark | Nominal delta | Delta | DV01, USD/bp | Cross-gamma, LOT/bp |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| A | 10 | SOFR | 0.95 | 10,000 | 9,500 | 10 | 9.5 | -0.95 | -0.00095 |
| B | -5 | FFOIS | 0.90 | -5,000 | -4,500 | -5 | -4.5 | 0.45 | 0.00045 |
| Combined | 5 | Two curves | — | 5,000 | 5,000 | 5 | 5 | Separate columns | Separate columns |

Cash is zero before payment. The aggregate mark of 5,000 is coincidental to these inputs, not a rule that the net amount is undiscounted. Commodity risk stands in February 2027; DV01 stands in January 2028. In a month report, the preceding valuation month remains visible as prescribed today.

These are excerpts from the risk values, with context/type/unit rows and intervening zero buckets omitted for brevity:

| bucket | SOFR USD dv01 | FFOIS USD dv01 |
|---|---:|---:|
| Total | -0.95 | 0.45 |
| January 2028 | -0.95 | 0.45 |

| bucket | HNG SOFR cross_gamma | HNG FFOIS cross_gamma |
|---|---:|---:|
| Total | -0.00095 | 0.00045 |
| February 2027 | -0.00095 | 0.00045 |

Also price B at -10 LOT with everything else unchanged. Nominal delta then nets to zero, but mark is 500 and discounted delta is 0.5 LOT. The two DV01s are -0.95 and +0.90; the two cross-gammas are -0.00095 and +0.00090. This is the essential test that compression has not lost curve ownership.

For the first, nonzero-nominal example, replace only SOFR's payment factor with 0.96. Mark becomes 5,100 and delta 5.1; SOFR DV01 becomes -0.96 and its cross-gamma -0.00096. Every FFOIS contribution stays unchanged. The original result still holds the original 0.95 curve and its numbers.

## Validation and measured work

Pin the hand answers before testing equivalence. The acceptance suite must also cover:

1. One key through a singleton set reproduces the existing single-curve answers. A missing booked key fails creation; a singleton with the wrong name fails evaluation. Adding an unused curve changes neither selection nor economics. One mixed batch equals separate key-specific batches collected together, including each dated risk vector, duplicated rows and reversed row order.
2. Same contract/date/key can compress; different keys remain distinct. Cover multiple payment dates and Asian observations so neither payment ownership nor pricing-contract attribution is accidentally lost.
3. A fully fixed unpaid payment has DV01 but no commodity delta/cross-gamma. On payment it becomes cash and both rate measures are zero. Preserve zero risk buckets and fully paid batches.
4. Change a quote, then one curve, then history/as_of. Assert the correct dependencies rebuild, preparation survives quote/curve updates, and held results retain their original objects and values. Reordering a set changes no economic answer.
5. Bump just one selected curve up and down using `util_BumpDiscountCurve`; centered differences of mark and discounted delta agree with that curve's analytic DV01/cross-gamma within justified tolerances. Other curves' contributions do not change.
6. Missing/duplicate names, inappropriate keys on cleared rows, wrong curve start and insufficient selected-curve coverage fail clearly. Extra unused curves are accepted without rate groups. Distinct same-name snapshots in different result sources stay separate and visibly distinguishable; equal-valued copies do not become identical objects.
7. Aggregation across HNG and another index shares a rate group only for the same curve/currency; cross-gamma stays separated by index. Readers calculate no valuation or sensitivities, and nonfinite sums fail before publication.
8. Freeze the final arrays retained on every record, including selection/group mappings after any dtype conversion. Held trades, preparations, curves, sets and results cannot change through downstream calls. Preserve PR200's single-curve cashflow values and readers; slice 3 also preserves the cashflow collection behavior from its separately landed prerequisite.

Measure key resolutions, used curves, distinct curve/payment-date factor reads, live slots processed and saved risk reductions. State retained-memory and temporary-memory changes. Preparing or evaluating must not run a whole independent trade pipeline per curve. Work should follow the actual groups, slots and requested reporting vectors, rather than blindly multiplying the whole batch size by the number of curves.

Full evaluation on each changed quote or curve is acceptable initially. No selective repricing, new cache or incremental update algorithm is required. Record actual work counts for one, two and several curves and compare singleton costs with the current path. Use profiling for investigation rather than a timing-based merge gate.

## Delivery and migration

Plan the stacked PRs in the order below, revised on 18 October after slice 1 landed its review: the saved contributions, the reporting and the collection first, with today's single-curve evaluator producing one contribution and every economic number unchanged, then the keyed booking and the mixed-curve evaluation with the complete worksheet migration. The complete stack is the integration and UAT target: each PR stays useful for review, but no temporary adapter is written and no extra PR forced to make an intermediate state independently shippable; a temporary gap is named in the slice ticket that opens it and closed before the stack lands on main. Engineering writes each short slice ticket as the first commit of that PR, including its hand answers, acceptance and migration scope, and presents it for owner review before adding implementation. The parent ticket establishes the direction; the slice ticket makes the work reviewable. If a boundary below proves artificial in the code, the slice ticket proposes combining the slices rather than building around it.

Use `feat/named-curves` for the first branch, then a separate branch for each subsequent PR based on the preceding head and targeting that preceding branch. This is one feature arc, not several PRs sharing one moving branch. Each PR remains independently reviewable and leaves the repository coherent. Land bottom-up by squash-merging; after each merge, rebase the next branch onto `main`, retarget its PR to `main`, and restack its dependants, checking each next diff before it lands.

| Slice | Reviewable outcome |
|---|---|
| 1. Named curves and collection, built in #201 | Required curve name and named individual handle, ordinary curve readback, bump preserving the name, `_CollectDiscountCurves` with compact handle/readback and membership validation. Migrate all curve-creation callers, including cashflow callers; its evaluator still takes the ordinary curve. Trade evaluation still uses its existing input until the coordinated cutover. |
| 2. Curve-owned contributions, named labels and the collection of trades and cashflows, built in #202, [named-curves-slice-2.md](named-curves-slice-2.md) | Saved DV01 and cross-gamma vectors retain their curve's ownership as contributions on every result, today's single-curve evaluator producing one of each and a cleared batch none; reporting labels carry curve names, `SOFR USD dv01`, with both same-name snapshots qualified in a collection; `_AggregateResults` collects trade and cashflow results in one range, combining contributions on the same exact curve object and currency, cashflow-only and mixed collections included, the cashflows keeping their single-curve evaluation. Every economic number unchanged. |
| 3. Keyed booking, mixed-curve evaluation and the worksheet cutover, [named-curves-slice-3.md](named-curves-slice-3.md) | The `discount_curve_key` field, required on bilateral rows and refused on cleared ones; the static selection carried through encoding and preparation; grouped factor gathering and per-curve analytic risks; `_EvaluateTrades` taking the collection, a singleton included; the hand-priced acceptance and the work budgets; and the complete migration, the kept workbook's evaluations and templates, host, smoke, lifetime, readback layouts, pages and UAT. Remove `_EvaluateTrades`' superseded direct-curve call form; no compatibility shim. |

Before slice 2, reconcile with PR200: reuse the shared payment helpers, preserve the existing single-curve cashflow surface and regress its known answers. Cashflow multiple-curve booking/evaluation is outside these slices until separately agreed.

The cutover includes curve-creation formulas, every bilateral booking/fixture's explicit key supplied by its template or ticket, the evaluation inputs, handle and report labels, positional readback consumers, and the kept workbook, smoke, host, lifetime, unit tests and owning documentation. Use engineering's inventory to plan the edits and refresh it on the actual implementation base. Do not keep legacy inputs to avoid those edits. Recalculate the changed workbook blocks and run each PR's full gate; a moved label or input must not silently alter the pinned economics.

At implementation, update the maintained function owners and affected references under the repository's documentation policy. This ticket is the design record, not another maintained API reference. Run the full repository gate on each implementation PR; any new numerical reference must have independently reviewed expected answers.

No mixed routes, multiple commodity indexes inside one batch, market quote sets, automatic curve construction, FX, key-rate DV01, rates correlation model, netting agreements, new reserves or global curve registry in this arc.

The owner-selected fast follow is [template-based quoting](template-based-quoting.md). Its distinct quote template selects pricing fields and the static key from the shared `fixed_float` definition; `_Quote` consumes that template and the same curve-set input after this arc's worksheet cutover. It adds no quoting work to the named-curve PRs themselves.
