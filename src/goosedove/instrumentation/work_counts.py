"""Explicitly reported work counts for one evaluation.

A WorkCounter collects named counts during an evaluation.
freeze() returns an immutable WorkCounts snapshot of the recorded counts.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

KERNEL: Final = "kernel"  # one vectorized pricing call over a whole group
HASH: Final = "hash"  # one identity digest computed
CACHE_HIT: Final = "cache_hit"
CACHE_MISS: Final = "cache_miss"
TERM: Final = "term"  # one coefficient times one price, added into its component
CELL: Final = "cell"  # one cell of a rectangle made or multiplied, the compressed or dense view
OBSERVATION: Final = "observation"  # one observation priced in a binding


@dataclass(frozen=True, slots=True)
class WorkCounts:
    """Recorded work counts for one evaluation."""

    counts: Mapping[str, int]

    def __getitem__(self, name: str) -> int:
        return self.counts.get(name, 0)

    def as_dict(self) -> dict[str, int]:
        return dict(self.counts)


class WorkCounter:
    """Mutable during one evaluation; freeze() at the end."""

    __slots__ = ("_counts",)

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def hit(self, name: str, n: int = 1) -> None:
        self._counts[name] += n

    def freeze(self) -> WorkCounts:
        return WorkCounts(MappingProxyType(dict(sorted(self._counts.items()))))
