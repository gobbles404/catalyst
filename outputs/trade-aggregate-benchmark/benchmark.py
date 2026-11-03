"""Synthetic amount-kernel timing; no production API, Excel, discounting or rates risk.

Run: uv run python outputs/trade-aggregate-benchmark/benchmark.py
Numerical inputs are prepared before tick timing. Timing is diagnostic, never a test gate.
"""

from __future__ import annotations

import json
import os
import platform
import statistics
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["BLIS_NUM_THREADS"] = "1"

import numpy as np

from catalyst.instrumentation.work_counts import WorkCounter

SIZES = (100, 1_000, 10_000, 100_000)
MARKETS = 24
TERMS_PER_TRADE = 3
BATCHES = 7
TARGET_NS = 20_000_000


def measure(run: Callable[[], object]) -> dict[str, object]:
    """Median of calibrated repeated-call batches, not latency percentiles."""
    for _ in range(30):
        run()
    iterations = 1
    while True:
        start = perf_counter_ns()
        for _ in range(iterations):
            run()
        elapsed = perf_counter_ns() - start
        if elapsed >= TARGET_NS:
            break
        iterations *= 2
    samples = []
    for _ in range(BATCHES):
        start = perf_counter_ns()
        for _ in range(iterations):
            run()
        samples.append((perf_counter_ns() - start) / iterations / 1_000)
    return {
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
        "iterations_per_batch": iterations,
        "batch_means_us": samples,
    }


def scenario(n: int) -> dict[str, object]:
    rng = np.random.default_rng(20261003 + n)
    columns = (rng.integers(0, MARKETS, (n, 1)) + np.arange(TERMS_PER_TRADE)) % MARKETS
    signed_quantity = rng.integers(-100, 101, n).astype(np.float64)
    relative_weights = rng.uniform(0.1, 1.0, (n, TERMS_PER_TRADE))
    relative_weights /= relative_weights.sum(axis=1, keepdims=True)
    weights = signed_quantity[:, None] * relative_weights
    fixed_set = -signed_quantity * rng.uniform(65.0, 85.0, n)
    prices = np.linspace(70.0, 85.0, MARKETS)
    dense = np.zeros((n, MARKETS), dtype=np.float64)
    dense[np.arange(n)[:, None], columns] = weights

    def aggregate_inputs(counter: WorkCounter):
        counter.hit("exposure_terms_read", weights.size)
        counter.hit("fixed_set_amounts_read", n)
        counter.hit("aggregate_coefficients_allocated", MARKETS)
        exposure = np.bincount(columns.ravel(), weights=weights.ravel(), minlength=MARKETS)
        return exposure, float(np.sum(fixed_set))

    prepare_counter = WorkCounter()
    exposure, summed_fixed_set = aggregate_inputs(prepare_counter)

    def dense_tick(counter: WorkCounter) -> float:
        counter.hit("coefficient_products", dense.size)
        counter.hit("component_amounts_formed", n)
        counter.hit("result_float_elements_allocated", 2 * n)
        return float(np.sum(dense @ prices + fixed_set))

    def sparse_tick(counter: WorkCounter) -> float:
        counter.hit("coefficient_products", weights.size)
        counter.hit("component_amounts_formed", n)
        counter.hit("result_float_elements_allocated", 2 * weights.size + 2 * n)
        return float(np.sum(np.sum(weights * prices[columns], axis=1) + fixed_set))

    def aggregate_tick(counter: WorkCounter) -> float:
        counter.hit("coefficient_products", MARKETS)
        counter.hit("component_amounts_formed", 0)
        counter.hit("result_float_elements_allocated", 0)
        return float(exposure @ prices + summed_fixed_set)

    # Check three price vectors before and after timings. Tolerances
    # accommodate changed floating-point summation order, not altered economics.
    def validate() -> None:
        original = prices.copy()
        for step in (-2.0, 0.0, 3.0):
            prices[:] = original + step * np.linspace(0.2, 1.0, MARKETS)
            dense_value = dense_tick(WorkCounter())
            sparse_value = sparse_tick(WorkCounter())
            aggregate_value = aggregate_tick(WorkCounter())
            np.testing.assert_allclose(aggregate_value, dense_value, rtol=1e-10, atol=1e-7)
            np.testing.assert_allclose(aggregate_value, sparse_value, rtol=1e-10, atol=1e-7)
        prices[:] = original

    validate()
    methods = {
        "dense_trade_values_then_sum": dense_tick,
        "sparse_trade_values_then_sum": sparse_tick,
        "prepared_aggregate": aggregate_tick,
    }
    timings = {}
    counts = {}
    for name, method in methods.items():
        counter = WorkCounter()
        method(counter)
        counts[name] = counter.freeze().as_dict()
        # Reuse a counter across repetitions for every route, so ordinary work
        # reporting overhead is present without constructing a counter each tick.
        timed_counter = WorkCounter()
        timings[name] = measure(lambda f=method, c=timed_counter: f(c))
    prep_counter = WorkCounter()
    prep_timing = measure(lambda: aggregate_inputs(prep_counter))
    validate()
    return {
        "trades": n,
        "live_inputs": MARKETS,
        "terms_per_trade": TERMS_PER_TRADE,
        "timings": timings,
        "aggregation_preparation": prep_timing,
        "work_counts_per_tick": counts,
        "aggregation_work_counts": prepare_counter.freeze().as_dict(),
        "dense_coefficients_bytes": dense.nbytes,
        "sparse_weights_and_positions_bytes": weights.nbytes + columns.nbytes,
        "aggregate_coefficients_bytes": exposure.nbytes,
        "checked_price_scenarios": 3,
    }


def main() -> None:
    config = np.show_config(mode="dicts")
    rows = []
    for n in SIZES:
        row = scenario(n)
        rows.append(row)
        print(json.dumps(row), flush=True)
    result = {
        "utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "numpy_configuration": config,
        "thread_environment": {
            key: os.environ[key]
            for key in (
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OMP_NUM_THREADS",
                "BLIS_NUM_THREADS",
            )
        },
        "scope": (
            "Warm NumPy amount kernel only, fixed 24 live inputs, 3 terms/trade; counters included"
        ),
        "excludes": [
            "trade creation",
            "full schedule/history preparation",
            "market binding",
            "NPV",
            "cash lifecycle",
            "delta/DV01 computation",
            "Excel/host",
            "reader publication",
        ],
        "rows": rows,
    }
    destination = Path(__file__).with_name("results.json")
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {destination}", flush=True)


if __name__ == "__main__":
    main()
