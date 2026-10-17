"""The words a risk report shares between a single result and a collection, and the placing of a
saved vector onto a report's axis. Risk and Bucket are _ReportRisk's two selectors; RiskView is
the content a report formats, dates, labels, saved totals and columns, temporary and never saved;
NO_DAYS and NOTHING are the empty axis and column a report without a dated row shows; placed
copies a saved vector through its saved places onto an axis, zero elsewhere. results.py selects a
single result's saved vectors with these and aggregation.py a collection's; this module selects
nothing, calculates nothing and imports nothing of theirs, so both read one definition.
docs/library/trades/report-risk.md is the page."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

import numpy as np
from numpy.typing import NDArray


class Bucket(Enum):
    """What a risk report sums by: the day, or since #186 the calendar month or year, the pricing
    contract's for the deltas and the payment's for the DV01, _ReportRisk's three choices, a
    quarter none of them."""

    DAY = "day"
    MONTH = "month"
    YEAR = "year"


class Risk(Enum):
    """What a risk report shows, since #178: the nominal delta, the delta weighted by the route's
    valuation treatment, the DV01, or all three on one axis, _ReportRisk's four choices; a
    summary none of them."""

    NOMINAL_DELTA = "nominal_delta"
    DELTA = "delta"
    DV01 = "dv01"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class RiskView:
    """One risk report's content, since #178, selected by reference and placed through saved
    places: dates, the bucket starts, increasing, observation days under the deltas, payment days
    under the DV01 and their union under all; labels, one heading per risk column, the index's
    name and its reporting lot's for a delta, the curve's group and the currency for a DV01;
    totals, the saved scalars, one per label; and columns, one dated vector per label, the saved
    vector itself where the axis is its own and a copy placed on the shared axis under all, zero
    where that axis has no entry of its kind. Nothing is summed, sorted or converted here."""

    dates: NDArray[np.datetime64]
    labels: tuple[str, ...]
    totals: tuple[float, ...]
    columns: tuple[NDArray[np.float64], ...]


NO_DAYS: NDArray[np.datetime64] = np.empty(0, dtype="datetime64[D]")
NOTHING: NDArray[np.float64] = np.empty(0)
NO_DAYS.setflags(write=False)
NOTHING.setflags(write=False)


Period = Literal[Bucket.MONTH, Bucket.YEAR]


def placed(size: int, places: NDArray[np.intp], vector: NDArray[np.float64]) -> NDArray[np.float64]:
    """A saved vector copied onto a report axis through its saved places, zero elsewhere."""
    column = np.zeros(size)
    column[places] = vector
    return column
