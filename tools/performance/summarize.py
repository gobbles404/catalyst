"""One table from whatever timing CSVs are under profiles/: a row per scenario, a column per layer.

Run with `uv run python tools/performance/summarize.py`. Each cell is the median of that
layer's batch means with the batch min and max beside it, in microseconds per call. Layers are
timed separately and are not slices of one execution; read them side by side, never subtract
one from another.
"""

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "profiles"
SOURCES = {
    "python": REPORTS / "python-timing.csv",
    "host": REPORTS / "host-measure" / "batches.csv",
    "excel": REPORTS / "excel-timing.csv",
}

Key = tuple[str, str, int, int]


def read(path: Path) -> dict[Key, list[float]]:
    """Batch means per (probe, scenario, cells in, cells out)."""
    means: dict[Key, list[float]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if not row["per_call_us"]:  # a row with no formula has no per-call figure
                continue
            key = (row["probe"], row["scenario"], int(row["cells_in"]), int(row["cells_out"]))
            means[key].append(float(row["per_call_us"]))
    return means


def cell(means: list[float]) -> str:
    ordered = sorted(means)
    return f"{ordered[len(ordered) // 2]:.2f} ({ordered[0]:.2f}..{ordered[-1]:.2f})"


def main() -> None:
    layers = {name: read(path) for name, path in SOURCES.items() if path.exists()}
    if not layers:
        raise SystemExit("no timing CSVs under profiles/; run a measurement first")
    keys = sorted({key for means in layers.values() for key in means})
    lines = [
        "# Timings, microseconds per call: median of batch means (min..max)",
        "",
        "Layers are separate clocks, not slices of one call. "
        + "Sources: "
        + ", ".join(
            f"{name} = {path.relative_to(ROOT)}" for name, path in SOURCES.items() if name in layers
        ),
        "",
        "| probe | scenario | cells in | cells out | " + " | ".join(layers) + " |",
        "|---|---|---:|---:|" + "|".join("---:" for _ in layers) + "|",
    ]
    for probe, scenario, cells_in, cells_out in keys:
        row = [probe, scenario, str(cells_in), str(cells_out)]
        for means in layers.values():
            batch_means = means.get((probe, scenario, cells_in, cells_out))
            row.append(cell(batch_means) if batch_means else "")
        lines.append("| " + " | ".join(row) + " |")
    (REPORTS / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Summary: {REPORTS / 'summary.md'}")


if __name__ == "__main__":
    main()
