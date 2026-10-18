"""Warm timings of the Python side of the seam, one probe at a time, on inputs built first.

Run with `uv run python tools/performance/measure_python.py`. The clock includes each function's
prepared path, entry(name), held once as the host holds it, on Cells already built: type
validation, the probe, and result conversion. cells_from_buffers from the host's buffers is its
own scenario, so what owning a range costs is timed apart. The clock
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

# Each function's prepared path, fetched once as the host does at registration.
ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}

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


def mixed_out(rows: int, cols: int = 1) -> Callable[[object], None]:
    """What the mixed road hands the host: the kinds, the numbers and the texts joined."""

    def check(result: object) -> None:
        if not isinstance(result, tuple) or cast(Any, result[0]).shape != (rows, cols):
            raise AssertionError(f"got {result!r}, expected a {rows}x{cols} mixed array")

    return check


def column(n: int) -> Cells:
    return Cells.from_rows([[float(i)] for i in range(n)])


def total(n: int) -> float:
    return float(n * (n - 1) // 2)


def mixed(n: int, chars: int = 2) -> Cells:
    """A column holding all three kinds a mixed range may, in turn, with text of a given length."""
    text = "n" * chars
    kinds: list[object] = [text, 1.0, True]
    return Cells.from_rows([[kinds[i % 3]] for i in range(n)])


def texts(n: int, chars: int = 2) -> Cells:
    """A column of text alone, so the scan for an empty text is read on its own."""
    return Cells.from_rows([["n" * chars] for _ in range(n)])


HEADERS = Cells.from_rows([["date", "product", "quantity", "cleared"]])


def trades(rows: int) -> Cells:
    """A table's body: a date, a text, a number and a flag per row, one column of each type."""
    return Cells.from_rows([[46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(rows)])


_buffers: list[object] = []  # keeps the ctypes buffers alive for the life of the run


def host_buffers(n: int) -> tuple[int, int]:
    kinds = (ctypes.c_uint8 * n)(*([0] * n))
    numbers = (ctypes.c_double * n)(*[float(i) for i in range(n)])
    _buffers.extend((kinds, numbers))
    return ctypes.addressof(kinds), ctypes.addressof(numbers)


CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def curve_body(rows: int) -> Cells:
    """A curve's table: one calendar day and its factor per row, from 11 September 2026."""
    return Cells.from_rows([[46276.0 + i, 1.0 - i * 1e-5] for i in range(rows)])


def scenarios() -> list[Scenario]:
    """Every timed case, with its inputs built here, before any clock starts."""
    # A valuation date and a ten-year curve, created once here: the reader's handles. The
    # creators themselves have no row, because each call would retain an object for the life of
    # the run.
    valuation = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    curve = ENTRY["_CreateDiscountCurve"]("SOFR", CURVE_HEADERS, curve_body(3_631))
    cases = [
        Scenario("Zero", "scalar", 0, 1, lambda run=ENTRY["Zero"]: run(), equals(0.0)),
        Scenario("Add", "scalar", 2, 1, lambda run=ENTRY["Add"]: run(1.0, 2.0), equals(3.0)),
        Scenario(
            "Times", "missing", 1, 1, lambda run=ENTRY["Times"]: run(5.0, MISSING), equals(5.0)
        ),
        # A handle in: the resolver, then the object's table out. The valuation date's spill is
        # six cells, so the row is the handle's cost; the ten-year curve's is 10,899 cells out,
        # its days, its factors and its name on every row.
        Scenario(
            "util_ReadHandle",
            "a handle in",
            1,
            6,
            lambda run=ENTRY["util_ReadHandle"], h=valuation: run(h),
            mixed_out(3, 2),
        ),
        Scenario(
            "util_ReadHandle",
            "a ten-year curve out",
            1,
            10_899,
            lambda run=ENTRY["util_ReadHandle"], h=curve: run(h),
            mixed_out(3_633, 3),
        ),
    ]
    for n in (10, *SIZES):  # ten cells is a trade's own row, smaller than the working size
        cells = column(n)
        mixed_cells = mixed(n)
        cases.append(
            Scenario(
                "CountArray",
                "cells in",
                n,
                1,
                lambda run=ENTRY["CountArray"], c=cells: run(c),
                equals(float(n)),
            )
        )
        cases.append(
            Scenario(
                "CountMixed",
                "cells in",
                n,
                1,
                lambda run=ENTRY["CountMixed"], c=mixed_cells: run(c),
                equals(float(n)),
            )
        )
    # Text count and text length, one at a time, because only the text costs anything per cell.
    for label, cells in (
        ("mixed: no text", column(10_000)),
        ("mixed: all text, 2 characters", texts(10_000, 2)),
        ("mixed: all text, 100 characters", texts(10_000, 100)),
    ):
        cases.append(
            Scenario(
                "CountMixed",
                label,
                10_000,
                1,
                lambda run=ENTRY["CountMixed"], c=cells: run(c),
                equals(10_000.0),
            )
        )
    for n in SIZES:
        cells = column(n)
        weights = Cells.from_rows([[1.0] for _ in range(n)])
        cases.append(
            Scenario(
                "SumArray",
                "cells in",
                n,
                1,
                lambda run=ENTRY["SumArray"], c=cells: run(c),
                equals(total(n)),
            )
        )
        # A table in: as many rows of four columns as make n cells, bound and refined in the
        # bridge, so what lies between this row and CountMixed's is the binding and the refining.
        rows = max(1, n // 4)
        body = trades(rows)
        cases.append(
            Scenario(
                "SumQuantity",
                "cells in",
                4 * rows,
                1,
                lambda run=ENTRY["SumQuantity"], b=body: run(HEADERS, b),
                equals(total(rows)),
            )
        )
        cases.append(
            Scenario(
                "Dot",
                "two ranges in",
                2 * n,
                1,
                lambda run=ENTRY["Dot"], c=cells, w=weights: run(c, w),
                equals(total(n)),
            )
        )
        cases.append(
            Scenario(
                "EchoColumn",
                "round trip",
                n,
                n,
                lambda run=ENTRY["EchoColumn"], c=cells: run(c),
                array(n, 1, total(n)),
            )
        )
        # The mixed road out, over the numbers alone and over the mixed column: what lies between
        # the first and EchoColumn is the road, and between the two is the text.
        echoed = mixed(n)
        cases.append(
            Scenario(
                "EchoMixed",
                "round trip, numbers",
                n,
                n,
                lambda run=ENTRY["EchoMixed"], c=cells: run(c),
                mixed_out(n),
            )
        )
        cases.append(
            Scenario(
                "EchoMixed",
                "round trip, mixed",
                n,
                n,
                lambda run=ENTRY["EchoMixed"], c=echoed: run(c),
                mixed_out(n),
            )
        )
        cases.append(
            Scenario(
                "Grid",
                "cells out",
                2,
                n,
                lambda run=ENTRY["Grid"], n=n: run(n, 1),
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
                    lambda run=ENTRY["RowSums"], g=grid: run(g),
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
                lambda own=bridge.cells_from_buffers, k=kinds, m=numbers, n=n: own(
                    k, m, n, 1, "", 1
                ),
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
                lambda run=ENTRY["EchoRow"]: run(shape),
                equals("#ERROR EchoRow: values is 10000x1 array, expected row of numbers"),
            ),
            Scenario(
                "SumArray",
                "rejected: text first",
                n,
                0,
                lambda run=ENTRY["SumArray"]: run(first),
                equals("#ERROR SumArray: values cell (1, 1) is text 'x', expected number"),
            ),
            Scenario(
                "SumArray",
                "rejected: text last",
                n,
                0,
                lambda run=ENTRY["SumArray"]: run(last),
                equals("#ERROR SumArray: values cell (10000, 1) is text 'x', expected number"),
            ),
            Scenario(
                "SumArray",
                "rejected: blank deep",
                n,
                0,
                lambda run=ENTRY["SumArray"]: run(deep),
                equals("#ERROR SumArray: values cell (5001, 1) is blank, expected number"),
            ),
        )
    )
    # A mixed range can fail two ways, and naming an empty text costs more than naming a blank,
    # because its place among the texts has to be turned into its place among the cells.
    mixed_kinds = "number, nonempty text or boolean"
    empty_deep: list[list[object]] = [[f"n{i}"] for i in range(n)]
    empty_deep[5_000][0] = ""
    blank_mixed, empty_mixed = Cells.from_rows(blank_deep), Cells.from_rows(empty_deep)
    cases.extend(
        (
            Scenario(
                "CountMixed",
                "rejected: blank deep",
                n,
                0,
                lambda run=ENTRY["CountMixed"]: run(blank_mixed),
                equals(
                    f"#ERROR CountMixed: values cell (5001, 1) is blank, expected {mixed_kinds}"
                ),
            ),
            Scenario(
                "CountMixed",
                "rejected: empty text deep",
                n,
                0,
                lambda run=ENTRY["CountMixed"]: run(empty_mixed),
                equals(
                    f"#ERROR CountMixed: values cell (5001, 1) is empty text, "
                    f"expected {mixed_kinds}"
                ),
            ),
        )
    )
    # A table rejected on a cell deep in one column: the column's look, then the naming.
    text_in_quantity: list[list[object]] = [
        [46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(n // 4)
    ]
    text_in_quantity[n // 8][2] = "x"
    bad_table = Cells.from_rows(text_in_quantity)
    cases.append(
        Scenario(
            "SumQuantity",
            "rejected: text deep in a column",
            n,
            0,
            lambda run=ENTRY["SumQuantity"]: run(HEADERS, bad_table),
            equals(
                f"#ERROR SumQuantity: trades cell ({n // 8 + 1}, 3) is text 'x', expected number"
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
            "Each function's prepared path, entry(name), held once, on Cells built before the "
            "clock: validation, the probe, result conversion. cells_from_buffers is timed apart. "
            "Excludes the host, Excel, and building inputs. Each row is one batch; per_call_us is "
            "that batch's mean."
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
