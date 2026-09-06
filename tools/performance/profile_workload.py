"""Profile one operation and save an HTML report."""

from collections.abc import Callable
from pathlib import Path
from time import sleep

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
    repo_root = Path(__file__).resolve().parents[2]

    # Demonstrate report generation with a short pause.
    profile_call(
        lambda: sleep(0.1),
        repo_root / "profiles" / "smoke.html",
    )
