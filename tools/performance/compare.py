"""Every row of two measurement sessions side by side: did a change move anything, anywhere.

Run with `uv run python tools/performance/compare.py profiles/before profiles/after`, or let
`tools/performance/before_after.ps1` make both directories and run this. It writes
`profiles/compare.md`: one table of every timed row across the layers, with the before and
after medians, the batch spread of each, and the change; a row is marked as moved only when the
after median lies outside the before spread, so batch noise is not read as a change. Below it,
every host counter that changed, and the allocation figures side by side. Nothing gates on it.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

Key = tuple[str, str, str, int, int]  # layer, probe, scenario, cells in, cells out
CountKey = tuple[str, str, int, int, str]  # probe, scenario, cells in, cells out, counter

TIMINGS: tuple[tuple[str, Path], ...] = (
    ("python", Path("python-timing.csv")),
    ("host", Path("host-measure") / "batches.csv"),
    ("excel", Path("excel-timing.csv")),
    ("excel, 10,000 rows", Path("excel-timing-rows10000.csv")),
)
ENVIRONMENTS: tuple[Path, ...] = (
    Path("python-environment.json"),
    Path("host-measure") / "environment.json",
    Path("excel-timing-environment.json"),
)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def timings(directory: Path) -> dict[Key, list[float]]:
    """Batch means per row, for every layer whose CSV is in the directory."""
    means: dict[Key, list[float]] = defaultdict(list)
    for layer, name in TIMINGS:
        path = directory / name
        if not path.exists():
            continue
        for row in rows(path):
            if not row["per_call_us"]:  # a row with no formula has no per-call figure
                continue
            key = (
                layer,
                row["probe"],
                row["scenario"],
                int(row["cells_in"]),
                int(row["cells_out"]),
            )
            means[key].append(float(row["per_call_us"]))
    return means


def counts(directory: Path) -> dict[CountKey, int]:
    path = directory / "host-measure" / "work.csv"
    if not path.exists():
        return {}
    return {
        (
            row["probe"],
            row["scenario"],
            int(row["cells_in"]),
            int(row["cells_out"]),
            row["counter"],
        ): int(row["count"])
        for row in rows(path)
    }


def allocation(directory: Path) -> dict[tuple[str, str, str, int, int], float]:
    """Python's peak bytes per call and the host's median managed bytes per call, by row."""
    figures: dict[tuple[str, str, str, int, int], float] = {}
    peaks = directory / "python-allocation.csv"
    if peaks.exists():
        for row in rows(peaks):
            key = (
                "python peak",
                row["probe"],
                row["scenario"],
                int(row["cells_in"]),
                int(row["cells_out"]),
            )
            figures[key] = float(row["peak_bytes"])
    batches = directory / "host-measure" / "batches.csv"
    if batches.exists():
        managed: dict[tuple[str, str, str, int, int], list[float]] = defaultdict(list)
        for row in rows(batches):
            key = (
                "host managed",
                row["probe"],
                row["scenario"],
                int(row["cells_in"]),
                int(row["cells_out"]),
            )
            managed[key].append(float(row["managed_bytes_per_call"]))
        for key, values in managed.items():
            figures[key] = sorted(values)[len(values) // 2]
    return figures


def revisions(directory: Path) -> str:
    """The revisions the environment files name, one word when they agree."""
    found: list[str] = []
    for name in ENVIRONMENTS:
        path = directory / name
        if path.exists():
            found.append(
                str(json.loads(path.read_text(encoding="utf-8-sig")).get("revision", "?"))[:7]
            )
    return ", ".join(sorted(set(found))) or "?"


def stats(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    return ordered[len(ordered) // 2], ordered[0], ordered[-1]


def cell(values: list[float]) -> str:
    median, low, high = stats(values)
    return f"{median:,.2f} ({low:,.2f}..{high:,.2f})"


def change(before: float, after: float) -> str:
    if before == 0:
        return "" if after == 0 else "new"
    return f"{(after - before) / before:+.0%}"


def moved(before: list[float], after: list[float]) -> str:
    """Only a move that leaves the two batch spreads apart counts as one."""
    _, before_low, before_high = stats(before)
    _, after_low, after_high = stats(after)
    if after_high < before_low:
        return "down"
    if after_low > before_high:
        return "up"
    return ""


def timing_table(
    before: dict[Key, list[float]], after: dict[Key, list[float]]
) -> tuple[list[str], str]:
    lines = [
        "| layer | probe | scenario | cells in | cells out | before | after | change | moved |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    ups = downs = big = 0
    for key in sorted(set(before) | set(after), key=lambda k: (k[0], k[1], k[2], k[3], k[4])):
        layer, probe, scenario, cells_in, cells_out = key
        b, a = before.get(key), after.get(key)
        if b and a:
            direction = moved(b, a)
            ups += direction == "up"
            downs += direction == "down"
            big += bool(direction) and abs(stats(a)[0] - stats(b)[0]) > 0.05 * stats(b)[0]
            columns = [cell(b), cell(a), change(stats(b)[0], stats(a)[0]), direction]
        else:
            columns = [cell(b) if b else "", cell(a) if a else "", "", "one side only"]
        lines.append(
            f"| {layer} | {probe} | {scenario} | {cells_in:,} | {cells_out:,} | "
            + " | ".join(columns)
            + " |"
        )
    both = len(set(before) & set(after))
    summary = (
        f"{both} rows on both sides; {downs} moved down and {ups} moved up beyond the batch "
        f"spreads, {big} of them by more than 5%."
    )
    return lines, summary


def count_table(before: dict[CountKey, int], after: dict[CountKey, int]) -> list[str]:
    differing = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    if not differing:
        return ["No counter moved."]
    lines = [
        "| probe | scenario | cells in | cells out | counter | before | after |",
        "|---|---|---:|---:|---|---:|---:|",
    ]
    for probe, scenario, cells_in, cells_out, counter in differing:
        key = (probe, scenario, cells_in, cells_out, counter)
        lines.append(
            f"| {probe} | {scenario} | {cells_in:,} | {cells_out:,} | {counter} | "
            f"{before.get(key, 0):,} | {after.get(key, 0):,} |"
        )
    return lines


def allocation_table(
    before: dict[tuple[str, str, str, int, int], float],
    after: dict[tuple[str, str, str, int, int], float],
) -> list[str]:
    lines = [
        "| meter | probe | scenario | cells in | cells out | before | after | change |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for key in sorted(set(before) | set(after)):
        meter, probe, scenario, cells_in, cells_out = key
        b, a = before.get(key), after.get(key)
        lines.append(
            f"| {meter} | {probe} | {scenario} | {cells_in:,} | {cells_out:,} | "
            f"{'' if b is None else f'{b:,.0f}'} | {'' if a is None else f'{a:,.0f}'} | "
            f"{change(b, a) if b is not None and a is not None else ''} |"
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Every row of two measurement sessions side by side."
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--before-label", default="before")
    parser.add_argument("--after-label", default="after")
    args = parser.parse_args()
    before_dir: Path = args.before
    after_dir: Path = args.after
    before_label: str = args.before_label
    after_label: str = args.after_label

    time_lines, summary = timing_table(timings(before_dir), timings(after_dir))
    lines = [
        "# Before and after, every row",
        "",
        f"Before: {before_label} (revision {revisions(before_dir)}). "
        f"After: {after_label} (revision {revisions(after_dir)}).",
        "",
        "## Time, microseconds per call: median (min..max) of the batch means",
        "",
        "Moved means the two batch spreads do not overlap. A change with no effect still moves "
        "rows by a few percent within one session, so read a move as real when it is large, "
        "consistent across sizes, and where the change aimed. Layers are separate clocks.",
        "",
        *time_lines,
        "",
        summary,
        "",
        "## Counts the host reported, where they differ",
        "",
        *count_table(counts(before_dir), counts(after_dir)),
        "",
        "## Allocation, bytes per call: Python's peak and the host's managed median",
        "",
        *allocation_table(allocation(before_dir), allocation(after_dir)),
    ]
    report = after_dir.parent / "compare.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary)
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
