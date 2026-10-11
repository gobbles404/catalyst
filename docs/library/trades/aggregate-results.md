# The collector of saved risk

Built in #179 as the ticket [aggregate-risk-kernel.md](../../engineering-tickets/trade-valuation-pipeline/aggregate-risk-kernel.md), the second of the [risk reporting and aggregation series](../../engineering-tickets/trade-valuation-pipeline/aggregate-evaluated-results.md), privately: `aggregate_results(sources, counter)` and `aggregate_view(aggregate, risk, bucket)` in `src/goosedove/trades/aggregation.py`, no worksheet function yet. The next ticket adds `_AggregateResults(result_handles)` on the sheet and lets [_ReportRisk](report-risk.md) take the collector's handle beside a result's; this page then gains the worksheet contract.

One or many evaluated batches combined into one immutable record of risk, nothing priced, discounted or converted again. A result's risk is already saved on it when it is made, [evaluate-trades.md](evaluate-trades.md): the nominal lots and the discounted lots by pricing reference and by observation day, calendar month and calendar year with their totals, and for a bilateral batch the DV01 by payment day, month and year with its total, every vector frozen. The collector reads those and nothing else. It groups the occurrences by the index object they are on, every occurrence of a group over the same history object and the same price-vector object as the group's first, and the bilateral occurrences by the curve object they were valued on and the result's currency; within a group it sums the saved vectors onto the union of the saved axes and the saved totals into one; across groups it sums nothing, the lots of one index never added to another's and the DV01 of one curve and currency never to another's. Each result has already applied its route's valuation treatment, so a cleared batch's 10 lots and a bilateral batch's 9.5 discounted lots on one index combine to 20 of nominal delta and 19.5 of delta, the collector discounting nothing again. Every occurrence counts: `[A, B, A]` holds A twice and sums it twice. The groups follow first appearance among the occurrences, and the report axes, the union of the groups' observation axes, the union of their payment axes and the union of both at each of the three buckets, are made with the collection with every group's places on them, so that a report copies saved vectors through saved places and discovers, sorts and sums nothing.

## The record

| Field | What it holds |
|---|---|
| `as_of` | the valuation day every source shares |
| `sources` | the occurrences in the order given, every one, by reference; a held collection keeps its sources readable after newer valuations are made, and a list appended to after collecting changes nothing |
| `index_groups` | one `IndexGroup` per distinct index object, in first-appearance order: the index, its reporting lot, the history and the price vector its occurrences share, the occurrences' positions, the union of their pricing references with both lot vectors summed onto it, the two totals, and the unions of their observation days, months and years with both lot vectors summed onto each |
| `rate_groups` | one `RateGroup` per distinct curve object and currency among the bilateral occurrences, in first-appearance order: the curve, its number by first appearance among the collection's curves, `curve_1` the first whatever the currency, the currency, the occurrences' positions, the DV01s summed, and the unions of their payment days, months and years with the DV01 summed onto each |
| `currencies` | the sources' currencies in first-appearance order, the DV01 columns of nothing a collection valued on no curve reports |
| `by_day`, `by_month`, `by_year` | `ReportAxes`: the union of the index groups' axes with each group's places, the union of the rate groups' payment axes with each group's places, no day when no curve values, and the union of both with every group's places |

Every array the collection makes is frozen; nothing of a source's preparation, market or curve is copied, and nothing is written after the record is made. Positions count the occurrences from zero in the arrays and from one in a refusal, as a sheet counts.

## The rules

| Question | Rule |
|---|---|
| Nothing given | refused: a collection holds at least one result |
| Valuation day | every occurrence's `as_of` is the first's |
| Index group | the exact index object; names and descriptions are labels, and a distinct index object whose name a group already has is refused, two indexes of one name being a mistake to show and not a group to make |
| Snapshot within an index | the exact history object and the exact price-vector object of the group's first occurrence; another `Market` wrapper over those two objects combines, a history or a vector equal in every value but another object does not |
| Rate group | the exact curve object and the result's currency; one curve valuing two currencies is two groups under one number, two curves equal in every value two groups |
| A cleared occurrence | in its index group and in no rate group; a collection with no rate group reports a DV01 of nothing per currency, over no day |
| Repeats | every occurrence counts, a repeated result twice, two results of equal trades separately; trade IDs are no key |
| Order | the groups and the curve numbers follow first appearance; the arithmetic is the same in any order |
| Finiteness | every new vector and total is finite, else the first that is not is refused by its measure, group and coordinate, the vectors before the total since a coordinate can outrun what the total, cancelling elsewhere, does not |

## What it reads and what it does

Per index group, from each occurrence: `encoded.references` with `lot_delta` and `discounted_lot_delta`; `encoded.days`, `months` and `years` with the preparation's `daily_lots`, `monthly_lots` and `yearly_lots` and the result's discounted three; `lot_delta_total` and `discounted_lot_delta_total`. Per rate group: the encoding's `PaymentAxes` with the result's `dv01_by_day`, `dv01_by_month` and `dv01_by_year`, and `dv01`. For each axis the occurrences' saved axes are stacked once, their union taken once and their places on it found once, then one `bincount` per kind of vector over every entry of every occurrence; a single occurrence takes the same path, its union a sorted copy of its own axis. The totals are the saved scalars summed. Then the report axes: three unions and their places per bucket. No quote, fixing or factor is read, no trade resolved, no unit converted, nothing evaluated and no day bucketed again: the saved month and year vectors are summed onto their own unions.

`aggregate_view(aggregate, risk, bucket)` returns the same `RiskView` a result's `risk_view` does, so [_ReportRisk](report-risk.md)'s rectangle needs no new layout: the nominal lots or the discounted lots on the union of the observation axes, one column per index group under `HNG nominal_delta [LOT]` or `HNG delta [LOT]`; the DV01 on the union of the payment axes, one column per rate group under `curve_1 USD dv01 [USD per basis point]`, or one column of nothing per currency under `cleared USD dv01 [USD per basis point]` over no day when no curve values; and all three on the union of both, each index group's two columns then each rate group's, every vector copied through its saved places and zero where the group has no entry. A copy per column and nothing else.

Work: the occurrences collected, the index groups, the rate groups, the entries aligned over every reduction, the reductions and the report coordinates saved, each reported to the counter; `sources_collected`, `index_groups`, `rate_groups`, `entries_aligned`, `aggregate_reductions`, `report_coordinates`.

## Refusals

In the order given, each occurrence's day first, then its index's compatibility; a sum past the largest number after the groups are made.

| Rule | Refused as |
|---|---|
| Nothing given | `results are none, expected at least one evaluated batch` |
| Another valuation day | `results 2 is valued on 2027-01-05, expected 2027-01-04, the valuation day of results 1` |
| A distinct index of a name already seen | `results 2 is on another index named 'HNG' than results 1, expected one index for one name` |
| Another history object | `results 2 is on index 'HNG' over another history than results 1, expected one history for one index` |
| Another price-vector object | `results 2 is on index 'HNG' quoted off another price vector than results 1, expected one price vector for one index` |
| A sum past the largest number, by contract, day, month, year or in all | `the nominal delta of index 'HNG' for contract F27 is inf, expected a finite number of lots; the results' lots sum past the largest number`; `the DV01 of curve_1 USD on 2028-01-04 is -inf, expected a finite amount of USD per basis point; the results' DV01s sum past the largest number` |

Nothing of the collection is made when a refusal stands; a collection already held is unchanged by a later call that fails.

## The worked example

The ticket's four sources on 4 January 2027, one-barrel indexes HNG and WTI, the bilateral ones on one USD curve of 0.95 a year out and 0.90 two years out: A, HNG cleared +10 lots; B, HNG bilateral +10 paying a year out and -10 two years out; C, WTI cleared +2, observing 5 January at 55 against 50; D, WTI bilateral +4 paying on 4 January 2028, 365 days from the valuation day. `[A, B]` is one HNG group of 10 nominal and 10.5 discounted lots and one rate group, `curve_1 USD`, of -0.0095 and 0.018 on the two payment days, 0.0085 in all. `[A, B, C, D]`, all three by day:

| period | HNG nominal_delta [LOT] | HNG delta [LOT] | WTI nominal_delta [LOT] | WTI delta [LOT] | curve_1 USD dv01 [USD per basis point] |
|---|---:|---:|---:|---:|---:|
| Total | 10 | 10.5 | 6 | 5.8 | 0.0066 |
| 4 Jan 2027 | 10 | 10.5 | 0 | 0 | 0 |
| 5 Jan 2027 | 0 | 0 | 6 | 5.8 | 0 |
| 4 Jan 2028 | 0 | 0 | 0 | 0 | -0.0114 |
| 3 Jan 2029 | 0 | 0 | 0 | 0 | 0.018 |

The first payment is HNG's -0.0095 and WTI's -0.0019 together. By month the two observation days are one January 2027 and the payments two more; `[A, B, A]` is 20 and 20.5 with the DV01 B's alone; `[C, D, A, B]` puts WTI's columns first and changes no number; HNG quoted 81 and A and B valued again moves the DV01s to -0.01235 and 0.0198, 0.00745 in all, and the lots not at all; the curve at 0.96 and 0.92 with B and D valued again makes HNG's delta 10.4, WTI's 5.84 and the DV01s -0.01152 and 0.0184, 0.00688 in all.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_aggregate_risk.py` | the figures above, every selection and bucket; one source collecting as itself for every selection, the aggregate record and not the source; repeats and order; the quote and the curve moved; the refusals in the order given and another `Market` wrapper combining; two curves equal in every value two groups, one curve in dollars and in cents two groups under one number; a collection with no curve and its DV01 of nothing; a fully paid source keeping its payment axis and its rate group; the membership owned and nothing written; sums past the largest number refused by the contract and in all |
| `tests/performance/test_aggregate_budgets.py` | the counts by source, group, entry, reduction and coordinate; the same functions and numpy calls at one source and at twenty-four, none of the kernel's, the market's or the curve's; the peak within five arrays of eight bytes a stacked entry over the bytes retained, the retained bytes exactly the new arrays'; a view one copy per column; a cleared source beside a bilateral one |

## Not here

No worksheet function, handle kind or input-range binding, the next ticket's; no aggregate mark, cash or reserves, the sources keeping theirs; no equivalence of lots across indexes, no FX, no nested collection, no curve-tenor DV01, no incremental or cached collection, a changed result collected afresh from every input; no identity registry, a name no key.
