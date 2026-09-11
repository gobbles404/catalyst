"""Warm timings of the Python side of the seam, one probe at a time, on inputs built first.

Run with `uv run python tools/performance/measure_python.py`. The clock includes bridge.call
on Cells already built: type validation, the probe, and result conversion. cells_from_buffers from
the host's buffers is its own scenario, so what owning a range costs is timed apart. The clock
excludes the host, Excel, and building the inputs. Each row of python-timing.csv is one batch:
a calibrated number of calls whose mean is the figure, never a percentile of single calls.
Results are checked before and after the clock, never inside it. A second, untimed pass
records the peak of the Python heap per call in python-allocation.csv. Timings choose
experiments; nothing gates on them.
"""

import csv
import ctypes
import hashlib
import json
import platform
import subprocess
import sys
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "profiles"
SIZES = (1, 100, 1_000, 10_000, 100_000)  # 100 is the working size; 100,000 the control
BATCH_MS = 50.0
BATCHES = 5

COLUMNS: tuple[str, ...] = (
    "layer",
    "probe",
    "scenario",
    "calls",
    "cells_in",
    "cells_out",
    "batch",
    "iterations",
    "elapsed_ms",
    "per_call_us",
)


@dataclass(frozen=True)
class Scenario:
    probe: str
    scenario: str
    cells_in: int
    cells_out: int
    run: Callable[[], object]
    check: Callable[[object], None]


def equals(expected: object) -> Callable[[object], None]:
    def check(result: object) -> None:
        if result != expected:
            raise AssertionError(f"got {result!r}, expected {expected!r}")

    return check


def array(rows: int, cols: int, total: float) -> Callable[[object], None]:
    def check(result: object) -> None:
        if not isinstance(result, np.ndarray):
            raise AssertionError(f"got {result!r}, expected an array")
        array = cast(NDArray[Any], result)
        if array.shape != (rows, cols) or float(array.sum()) != total:
            raise AssertionError(
                f"got shape {array.shape} sum {array.sum()}, expected {rows}x{cols} sum {total}"
            )

    return check


def column(n: int) -> Cells:
    return Cells.from_rows([[float(i)] for i in range(n)])


def total(n: int) -> float:
    return float(n * (n - 1) // 2)


_buffers: list[object] = []  # keeps the ctypes buffers alive for the life of the run


def host_buffers(n: int) -> tuple[int, int]:
    kinds = (ctypes.c_uint8 * n)(*([0] * n))
    numbers = (ctypes.c_double * n)(*[float(i) for i in range(n)])
    _buffers.extend((kinds, numbers))
    return ctypes.addressof(kinds), ctypes.addressof(numbers)


def scenarios() -> list[Scenario]:
    """Every timed case, with its inputs built here, before any clock starts."""
    cases = [
        Scenario("Zero", "scalar", 0, 1, lambda: bridge.call("Zero", []), equals(0.0)),
        Scenario("Add", "scalar", 2, 1, lambda: bridge.call("Add", [1.0, 2.0]), equals(3.0)),
        Scenario(
            "Times", "missing", 1, 1, lambda: bridge.call("Times", [5.0, MISSING]), equals(5.0)
        ),
    ]
    for n in SIZES:
        cells = column(n)
        weights = Cells.from_rows([[1.0] for _ in range(n)])
        cases.append(
            Scenario(
                "SumArray",
                "cells in",
                n,
                1,
                lambda c=cells: bridge.call("SumArray", [c]),
                equals(total(n)),
            )
        )
        cases.append(
            Scenario(
                "Dot",
                "two ranges in",
                2 * n,
                1,
                lambda c=cells, w=weights: bridge.call("Dot", [c, w]),
                equals(total(n)),
            )
        )
        cases.append(
            Scenario(
                "EchoColumn",
                "round trip",
                n,
                n,
                lambda c=cells: bridge.call("EchoColumn", [c]),
                array(n, 1, total(n)),
            )
        )
        cases.append(
            Scenario(
                "Grid",
                "cells out",
                2,
                n,
                lambda n=n: bridge.call("Grid", [n, 1]),
                array(n, 1, n * (n + 1) / 2),
            )
        )
        if n >= 10:
            count = n // 10
            grid = Cells.from_rows([[float(r * 10 + c) for c in range(10)] for r in range(count)])
            cases.append(
                Scenario(
                    "RowSums",
                    "one answer per row",
                    n,
                    count,
                    lambda g=grid: bridge.call("RowSums", [g]),
                    array(count, 1, total(n)),
                )
            )
        kinds, numbers = host_buffers(n)
        cases.append(
            Scenario(
                "cells_from_buffers",
                "owning a range",
                n,
                0,
                lambda k=kinds, m=numbers, n=n: bridge.cells_from_buffers(k, m, n, 1, ""),
                lambda result: None,
            )
        )
    n = 10_000
    good: list[list[object]] = [[float(i)] for i in range(n)]
    text_first = [list(row) for row in good]
    text_first[0][0] = "x"
    text_last = [list(row) for row in good]
    text_last[-1][0] = "x"
    blank_deep = [list(row) for row in good]
    blank_deep[5_000][0] = None
    shape, first, last, deep = (
        column(n),
        Cells.from_rows(text_first),
        Cells.from_rows(text_last),
        Cells.from_rows(blank_deep),
    )
    cases.extend(
        (
            Scenario(
                "EchoRow",
                "rejected: shape",
                n,
                0,
                lambda: bridge.call("EchoRow", [shape]),
                equals("#ERROR EchoRow: values is 10000x1 array, expected row of numbers"),
            ),
            Scenario(
                "SumArray",
                "rejected: text first",
                n,
                0,
                lambda: bridge.call("SumArray", [first]),
                equals("#ERROR SumArray: values cell (1, 1) is text 'x', expected number"),
            ),
            Scenario(
                "SumArray",
                "rejected: text last",
                n,
                0,
                lambda: bridge.call("SumArray", [last]),
                equals("#ERROR SumArray: values cell (10000, 1) is text 'x', expected number"),
            ),
            Scenario(
                "SumArray",
                "rejected: blank deep",
                n,
                0,
                lambda: bridge.call("SumArray", [deep]),
                equals("#ERROR SumArray: values cell (5001, 1) is blank, expected number"),
            ),
        )
    )
    return cases


def timed(case: Scenario) -> list[dict[str, object]]:
    """Warm, calibrate to a batch of about BATCH_MS, then BATCHES batches checked off the clock."""
    case.check(case.run())
    iterations = 1
    while True:
        started = perf_counter_ns()
        for _ in range(iterations):
            case.run()
        elapsed_ms = (perf_counter_ns() - started) / 1e6
        if elapsed_ms >= BATCH_MS or iterations >= 1_000_000:
            break
        iterations *= 2
    rows: list[dict[str, object]] = []
    for batch in range(1, BATCHES + 1):
        result: object = None
        started = perf_counter_ns()
        for _ in range(iterations):
            result = case.run()
        elapsed_ms = (perf_counter_ns() - started) / 1e6
        case.check(result)
        rows.append(
            {
                "layer": "python",
                "probe": case.probe,
                "scenario": case.scenario,
                "calls": 1,
                "cells_in": case.cells_in,
                "cells_out": case.cells_out,
                "batch": batch,
                "iterations": iterations,
                "elapsed_ms": f"{elapsed_ms:.3f}",
                "per_call_us": f"{elapsed_ms * 1000 / iterations:.3f}",
            }
        )
    return rows


def peak_bytes(case: Scenario) -> int:
    """The peak of the Python heap during one warm call; numpy's data buffers included."""
    case.run()
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        case.run()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment() -> dict[str, object]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "revision": revision,
        "bridge_sha256": sha256(ROOT / "src" / "goosedove" / "excel" / "bridge.py"),
        "probes_sha256": sha256(ROOT / "src" / "goosedove" / "excel" / "probes.py"),
        "python": sys.version,
        "numpy": np.__version__,
        "machine": platform.machine(),
        "processor": platform.processor(),
        "batch_target_ms": BATCH_MS,
        "batches": BATCHES,
        "timed_scope": (
            "bridge.call on Cells built before the clock: validation, the probe, result "
            "conversion. cells_from_buffers is timed apart. Excludes the host, Excel, and building "
            "inputs. Each row is one batch; per_call_us is that batch's mean."
        ),
        "allocation_scope": (
            "tracemalloc peak of the Python heap during one warm call, numpy data included, "
            "the host's pinned buffers excluded."
        ),
    }


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    cases = scenarios()
    with (REPORTS / "python-timing.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=list(COLUMNS))
        writer.writeheader()
        for case in cases:
            rows = timed(case)
            writer.writerows(rows)
            means = sorted(float(cast(str, row["per_call_us"])) for row in rows)
            median = means[len(means) // 2]
            shape = f"{case.cells_in:>7} in {case.cells_out:>7} out"
            spread = f"({means[0]:.3f}..{means[-1]:.3f})"
            print(
                f"{case.probe:<18} {case.scenario:<22} {shape}  median {median:>10.3f} us  {spread}"
            )
    with (REPORTS / "python-allocation.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(("probe", "scenario", "cells_in", "cells_out", "peak_bytes"))
        for case in cases:
            writer.writerow(
                (case.probe, case.scenario, case.cells_in, case.cells_out, peak_bytes(case))
            )
    (REPORTS / "python-environment.json").write_text(
        json.dumps(environment(), indent=2), encoding="utf-8"
    )
    print(f"Results: {REPORTS / 'python-timing.csv'}, {REPORTS / 'python-allocation.csv'}")


if __name__ == "__main__":
    main()
