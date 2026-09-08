"""Profile one operation and save an HTML report."""

from collections.abc import Callable
from pathlib import Path

from pyinstrument import Profiler


def profile_call[T](operation: Callable[[], T], report: Path) -> T:
    report.parent.mkdir(parents=True, exist_ok=True)

    profiler = Profiler()
    profiler.start()
    try:
        result = operation()
    finally:
        profiler.stop()

    report.write_text(profiler.output_html(), encoding="utf-8")
    print(f"Profile saved to {report.resolve()}")
    return result


if __name__ == "__main__":
    from timeit import timeit

    from goosedove.excel import bridge

    repo_root = Path(__file__).resolve().parents[2]

    # Where the time goes in one scalar call through the seam: one HTML tree.
    profile_call(lambda: bridge.call("Add", [1.0, 2.0]), repo_root / "profiles" / "add.html")

    # How much it costs: repeated, no profiler attached.
    n = 200
    t_call = timeit(lambda: bridge.call("Add", [1.0, 2.0]), number=n) / n * 1e6
    print(f"scalar call  {t_call:8.1f} us per call")
