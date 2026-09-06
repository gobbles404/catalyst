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

    import numpy as np

    from goosedove.excel import bridge

    repo_root = Path(__file__).resolve().parents[2]
    rows, cols = 100, 100
    block = np.arange(rows * cols, dtype=np.float64).reshape(rows, cols)
    nested = block.tolist()

    # Where the time goes, per shape: one HTML tree each.
    profile_call(
        lambda: bridge.call("SumRange", [nested]), repo_root / "profiles" / "sum_nested.html"
    )
    profile_call(
        lambda: bridge.call("SumRange", [block]), repo_root / "profiles" / "sum_array.html"
    )

    # How much it costs: repeated, no profiler attached.
    n = 200
    t_nested = timeit(lambda: bridge.call("SumRange", [nested]), number=n) / n * 1e6
    t_array = timeit(lambda: bridge.call("SumRange", [block]), number=n) / n * 1e6
    print(f"nested list  {t_nested:8.1f} us per call")
    print(f"numpy array  {t_array:8.1f} us per call  ({t_nested / t_array:.0f}x faster)")
