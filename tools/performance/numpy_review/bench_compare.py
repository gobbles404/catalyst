"""As-is against proposed, every scenario, interleaved so that load noise lands on both sides.

Written for the numpy review of 2026-10-01 (docs/reviews/numpy-review.md). Run with

    .venv/bin/python tools/performance/numpy_review/bench_compare.py --proposed <tree> \\
        --scenarios NAME[,NAME...] [--asis .] [--rounds 3] [--batches 7] [--batch-ms 20] \\
        [--out report.md]

It runs bench_harness.py in a fresh process per side per round, with PYTHONPATH=<tree>/src so
that tree's own package is imported (the "tree" line of the report proves it), alternating the
order of the two sides between rounds, and reports per scenario the best of the per-call medians
with the spread across rounds, the tracemalloc peak, and the numpy and package ledger diffs. A
timing move is called real only when the proposed side's spread lies wholly outside the as-is
side's, the repo's own rule for reading a move; the counts are deterministic.
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PYTHON = sys.executable
Row = dict[str, Any]


def run_side(
    tree: Path, label: str, scenarios: str, batches: int, batch_ms: float, ledger: bool
) -> list[Row]:
    env = dict(os.environ, PYTHONPATH=str(tree / "src"))
    cmd = [
        PYTHON,
        str(HERE / "bench_harness.py"),
        "--scenarios",
        scenarios,
        "--label",
        label,
        "--batches",
        str(batches),
        "--batch-ms",
        str(batch_ms),
    ]
    if not ledger:
        cmd.append("--no-ledger")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=tree, check=False)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"{label} run failed on {tree}")
    return [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]


def diff(before: dict[str, int], after: dict[str, int]) -> str:
    keys = sorted(set(before) | set(after))
    parts = [
        f"{k}: {before.get(k, 0)}->{after.get(k, 0)}"
        for k in keys
        if before.get(k, 0) != after.get(k, 0)
    ]
    return "; ".join(parts) if parts else "same"


def spread(rows: list[Row]) -> tuple[float, float, float]:
    medians = sorted(float(r["us_median"]) for r in rows)
    return medians[0], medians[0], medians[-1]


def ledger(rows: list[Row], name: str) -> dict[str, int]:
    for r in rows:
        if name in r:
            return dict(r[name])
    return {}


def report_line(name: str, asis: list[Row], proposed: list[Row]) -> str:
    a_best, a_low, a_high = spread(asis)
    b_best, b_low, b_high = spread(proposed)
    moved = "down" if b_high < a_low else ("up" if b_low > a_high else "")
    change = f"{(b_best - a_best) / a_best:+.0%}" if a_best else ""
    a_peak = min(int(r["peak_bytes"]) for r in asis)
    b_peak = min(int(r["peak_bytes"]) for r in proposed)
    peak = (
        f"{a_peak:,} -> {b_peak:,} ({(b_peak - a_peak) / a_peak:+.0%})"
        if a_peak
        else f"{a_peak} -> {b_peak}"
    )
    numpy_diff = diff(ledger(asis, "numpy_ledger"), ledger(proposed, "numpy_ledger"))
    package_diff = diff(ledger(asis, "package_ledger"), ledger(proposed, "package_ledger"))
    return (
        f"| {name} | {a_best:.2f} ({a_low:.2f}..{a_high:.2f}) "
        f"| {b_best:.2f} ({b_low:.2f}..{b_high:.2f}) | {change} | {moved} | {peak} "
        f"| {numpy_diff} | {package_diff} |"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--proposed", required=True, type=Path)
    parser.add_argument("--asis", default=Path.cwd(), type=Path)
    parser.add_argument("--scenarios", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--batches", type=int, default=7)
    parser.add_argument("--batch-ms", type=float, default=20.0)
    parser.add_argument("--out", default="")
    a = parser.parse_args()
    asis, proposed = Path(a.asis).resolve(), Path(a.proposed).resolve()
    scenarios, rounds, batches, batch_ms = (
        str(a.scenarios),
        int(a.rounds),
        int(a.batches),
        float(a.batch_ms),
    )

    rows: dict[str, dict[str, list[Row]]] = defaultdict(lambda: {"asis": [], "proposed": []})
    for r in range(rounds):
        sides = [("asis", asis), ("proposed", proposed)]
        if r % 2:
            sides.reverse()
        for label, tree in sides:
            for row in run_side(tree, label, scenarios, batches, batch_ms, ledger=(r == 0)):
                rows[str(row["scenario"])][label].append(row)

    lines = [
        "| scenario | as-is us median (spread) | proposed us median (spread) | change | moved "
        "| peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |",
        "|---|---:|---:|---:|---|---:|---|---|",
    ]
    for name, sides in rows.items():
        if sides["asis"] and sides["proposed"]:
            lines.append(report_line(name, sides["asis"], sides["proposed"]))
    trees = {
        label: sorted({str(r["tree"]) for s in rows.values() for r in s[label]})
        for label in ("asis", "proposed")
    }
    header = [
        f"as-is tree: {', '.join(trees['asis'])}",
        f"proposed tree: {', '.join(trees['proposed'])}",
        f"rounds: {rounds}, batches: {batches}, batch target: {batch_ms} ms; 'moved' means the "
        "proposed spread lies wholly outside the as-is spread",
        "",
    ]
    report = "\n".join(header + lines) + "\n"
    print(report)
    if a.out:
        Path(str(a.out)).write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
