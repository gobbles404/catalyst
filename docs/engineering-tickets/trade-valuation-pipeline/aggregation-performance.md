# Aggregate evaluation: first timing evidence and limits

[Pipeline overview](README.md) · [Prepared exposure](prepared-matrix.md) · [Results](05-results.md)

**Status:** Synthetic diagnostic measurement, 3 October 2026. Not a production benchmark
of PR119, an Excel measurement, a financial golden, or a full mark/cash/delta/DV01 implementation.
Timings guide design; deterministic work counts remain the regression gate.

## Scope and reproducibility

Compare two numerical routes to the same aggregate undiscounted amount:

```text
Expanded reference: sum(W @ prices + fixed_and_set_by_component)
Prepared aggregate: summed_exposure @ prices + summed_fixed_and_set
```

Every scenario has 24 live inputs, three stored coefficient terms per trade, signed quantities
(including possible zeros), and a precomputed fixed/set amount per trade. Market-input count
stays constant as trade count grows. Inputs are reproducibly generated, not real schedules.
Both routes are vectorized NumPy, not Python pricing loops. Creation, calendars, fixing lookup,
binding, discounting, cash accounting, risk calculation, host/Excel and readers are excluded.

A compact coefficient/column gather reference also forms per-trade values then sums them.
It was slower than the dense route in this test; that is not a claim about all sparse kernels.
The headline comparison uses the faster of the two measured per-trade baselines. Neither
reference claims to be the fastest possible implementation for retaining per-trade values.

Environment: Windows 11, Python 3.13.13, NumPy 2.5.2/OpenBLAS. The standalone process sets
BLAS/OpenMP thread environment variables to one before importing NumPy. All routes include
three WorkCounter calls, with a counter reused across timed repetitions. Counter cost is
not exactly identical: the aggregate route adds zero for two counters. Results are medians
of seven calibrated batch means after warm-up, not single-call latency percentiles.

Reproduce with `uv run python outputs/trade-aggregate-benchmark/benchmark.py`.
[Script](../../../outputs/trade-aggregate-benchmark/benchmark.py) and
[raw results](../../../outputs/trade-aggregate-benchmark/results.json) include configuration,
timing batches, counts and array sizes. These tables record the run at
2026-10-03 15:31:51 UTC; rerunning replaces the raw JSON.

## Warm tick results

Times are microseconds; 1,000 microseconds = 1 millisecond.

| Trades | Dense per-trade calculation then sum | Prepared aggregate | Approximate kernel speedup |
|---|---:|---:|---:|
| 100 | 4.57 us | 1.63 us | 2.8x |
| 1,000 | 8.10 us | 1.62 us | 5.0x |
| 10,000 | 36.67 us | 1.62 us | 22.6x |
| 100,000 | 1,367.91 us | 1.62 us | 842x |

The aggregate remains nearly flat because it still multiplies 24 coefficients. The dense
route reads progressively larger matrices; memory behavior contributes to the large increase
at 100,000 rows. Ratios are specific to this workload/hardware/comparison, not a claim of
842x faster Excel. At 100 trades the saving is about three microseconds; at 100,000 it is
about 1.37 milliseconds per amount-kernel call in this experiment.

| Trades | Extra aggregation pass, outside tick timing | Dense coefficient storage | Aggregate coefficient storage |
|---|---:|---:|---:|
| 100 | 3.35 us | 19,200 bytes | 192 bytes |
| 1,000 | 6.00 us | 192,000 bytes | 192 bytes |
| 10,000 | 33.89 us | 1,920,000 bytes | 192 bytes |
| 100,000 | 318.83 us | 19,200,000 bytes | 192 bytes |

The aggregation pass reads already constructed compact terms and fixed/set amounts. This
is not full preparation or first calculation from tickets. It runs on relevant trade/history
changes, not price ticks. At 100 trades its cost plus the first aggregate tick is about
4.98 us, slightly more than the 4.57 us dense tick; subsequent ticks reuse the preparation.

Storage figures exclude source facts, history, metadata, Python objects and other library
state. The benchmark holds all representations for comparison; its process memory is not a
production peak-memory measurement.

## Counts and correctness

For N trades, M live inputs and K stored coefficients per trade:

| Route | Coefficient products per tick | Per-trade amounts formed per tick |
|---|---:|---:|
| Dense expanded matrix | N x M | N |
| Compact gather reference | N x K | N |
| Prepared aggregate | M | 0 |

Here M = 24 and K = 3. At 100,000 trades, those product counts are 2,400,000, 300,000 and 24.
Work reduction is not elapsed speedup: call overhead, allocation, counters and memory behavior
also contribute. Raw allocation counts describe bulk float-array elements, excluding
scalars, Python objects and BLAS workspace; the aggregate route still allocates scalar objects.

Before and after timing, all routes agree on three price vectors along one perturbation
direction, using rtol 1e-10 and atol 1e-7 for changed floating-point summation order. These
are not exhaustive axis-shock tests. Hand examples separately establish financial expectations;
this experiment checks numerical equivalence and cost, not real schedule correctness.

## Extending to the requested four measures

The target is two aggregate route-specific value fields plus shared delta and DV01, all
complete before publication; see [proposed fields](result-fields-by-route.md). This benchmark
measures only the amount arithmetic. For rates/cash, retain groups compatible in
payment dates, currencies, discount/settlement treatment and relevant cash status. With G
groups and M live inputs, a straightforward grouped amount path reads G x M coefficients
instead of N x M. G may be much smaller than N, but every payment could differ. Rate-risk
axes and the chosen bump method add work. Commodity ticks, rate ticks and fixing updates
therefore require separate production measurements.

No evaluated object per trade is required. Immutable arrays and group metadata can support
the outputs. Source facts needed for future fixing changes are distinct from per-trade values.

Next measurements: actual encoded NG and averaging schedules; compatible payment groups;
the full four-measure result once its conventions are defined; Excel first call, repeat,
commodity tick, rate tick, fixing correction and date roll. Compare work and temporary
memory as well as diagnostic timings. These are follow-up implementation checks, not
capabilities supplied by this standalone specimen.
