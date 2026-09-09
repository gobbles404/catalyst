"""Profile every placeholder function once and save an HTML report of where its time went."""

from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from pyinstrument import Profiler

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

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
    """One representative call per placeholder, at a size a sheet might send."""
    n = 10_000
    column = Cells.from_rows([[float(i)] for i in range(n)])
    row = Cells.from_rows([[float(i) for i in range(n)]])
    grid = Cells.from_rows([[float(r * 100 + c) for c in range(100)] for r in range(100)])
    dates = Cells.from_rows([[float(61 + i)] for i in range(n)])
    date_row = Cells.from_rows([[float(61 + i) for i in range(n)]])
    names = Cells.from_rows([[f"name{i}"] for i in range(n)])
    name_row = Cells.from_rows([[f"name{i}" for i in range(n)]])
    return {
        "Add": lambda: bridge.call("Add", [1.0, 2.0]),
        "DateText": lambda: bridge.call("DateText", [46164.0]),
        "SumArray": lambda: bridge.call("SumArray", [grid]),
        "SumColumn": lambda: bridge.call("SumColumn", [column]),
        "SumRow": lambda: bridge.call("SumRow", [row]),
        "FirstDate": lambda: bridge.call("FirstDate", [dates]),
        "LastDate": lambda: bridge.call("LastDate", [date_row]),
        "JoinColumn": lambda: bridge.call("JoinColumn", [names]),
        "JoinRow": lambda: bridge.call("JoinRow", [name_row]),
    }


if __name__ == "__main__":
    REPORTS.mkdir(exist_ok=True)
    for name, operation in workloads().items():
        operation()  # the first call pays for imports and caches; profile the second
        report = REPORTS / f"{name}.html"
        profile_call(operation, report)
        print(f"{name:<12} {report}")
