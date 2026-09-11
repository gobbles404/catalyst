"""Profile every probe once and save an HTML report of where its time went."""

from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from pyinstrument import Profiler

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells

# Each function's prepared path, fetched once as the host does at registration.
ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}

REPORTS = Path(__file__).resolve().parents[2] / "profiles"


def profile_call[T](operation: Callable[[], T], report: Path, seconds: float = 0.5) -> T:
    """Run one operation over and over under the profiler for `seconds`, then write the report.

    The profiler samples once a millisecond. One call of a microsecond is never seen, so the
    report shows how repeated calls split their time, not how long one took.
    """
    profiler = Profiler()
    deadline = perf_counter() + seconds
    profiler.start()
    try:
        while True:
            result = operation()
            if perf_counter() >= deadline:
                break
    finally:
        profiler.stop()
    report.write_text(profiler.output_html(), encoding="utf-8")
    return result


def workloads() -> dict[str, Callable[[], object]]:
    """One representative call per probe, at a size a sheet might send."""
    n = 10_000
    column = Cells.from_rows([[float(i)] for i in range(n)])
    row = Cells.from_rows([[float(i) for i in range(n)]])
    weights = Cells.from_rows([[1.0] for _ in range(n)])
    grid = Cells.from_rows([[float(r * 100 + c) for c in range(100)] for r in range(100)])
    return {
        "Zero": lambda: ENTRY["Zero"](),
        "Add": lambda: ENTRY["Add"](1.0, 2.0),
        "Times": lambda: ENTRY["Times"](5.0, MISSING),
        "EchoText": lambda: ENTRY["EchoText"]("WTI"),
        "EchoBoolean": lambda: ENTRY["EchoBoolean"](True),
        "SumArray": lambda: ENTRY["SumArray"](grid),
        "Dot": lambda: ENTRY["Dot"](column, weights),
        "EchoColumn": lambda: ENTRY["EchoColumn"](column),
        "EchoRow": lambda: ENTRY["EchoRow"](row),
        "RowSums": lambda: ENTRY["RowSums"](grid),
        "Grid": lambda: ENTRY["Grid"](5000, 2),
        "Fail": lambda: ENTRY["Fail"](),
    }


if __name__ == "__main__":
    REPORTS.mkdir(exist_ok=True)
    for name, operation in workloads().items():
        operation()  # the first call pays for imports and caches; profile the second
        report = REPORTS / f"{name}.html"
        profile_call(operation, report)
        print(f"{name:<12} {report}")
