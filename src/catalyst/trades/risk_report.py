"""The words a risk report shares between a single result and a collection, and the placing of a
saved vector onto a report's axis. Risk and Bucket are _ReportRisk's two selectors, the
cross-gamma among the risks since #197; RiskView is
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

from catalyst.index_definitions.index import Index, ReportingLot


class Bucket(Enum):
    """What a risk report sums by: the day, or since #186 the calendar month or year, the pricing
    contract's for the deltas and the payment's for the DV01, _ReportRisk's three choices, a
    quarter none of them."""

    DAY = "day"
    MONTH = "month"
    YEAR = "year"


class Risk(Enum):
    """What a risk report shows, since #178: the nominal delta, the delta weighted by the route's
    valuation treatment, the DV01, since #197 the cross-gamma, the delta's sensitivity to the
    rates, or all four on one axis, _ReportRisk's five choices; a summary none of them."""

    NOMINAL_DELTA = "nominal_delta"
    DELTA = "delta"
    DV01 = "dv01"
    CROSS_GAMMA = "cross_gamma"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class RiskView:
    """One risk report's content, since #178, selected by reference and placed through saved
    places: dates, the bucket starts, increasing, observation days under the deltas, payment days
    under the DV01 and their union under all; labels, one heading per risk column, the index's
    name and its reporting lot's for a delta, the curve's group, the currency and the unit of
    it for a DV01, the index, the group and the lot per basis point for a cross-gamma;
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


def delta_labels(index: Index, reporting_lot: ReportingLot) -> tuple[str, str]:
    """The two delta columns' headings, the nominal delta's then the delta's: the index's short
    name as the desk typed it and the reporting lot's, `HNG nominal_delta [LOT]` and
    `HNG delta [LOT]`, read off the two records and nothing resolved or converted here."""
    return (
        f"{index.name} nominal_delta [{reporting_lot.name}]",
        f"{index.name} delta [{reporting_lot.name}]",
    )


def dv01_label(group: str, currency: str, currency_unit: str) -> str:
    """The DV01 column's heading over the group its caller named, the curve's word, its name or
    the name qualified where a collection holds two objects of it, or `cleared` where no curve
    values; then the currency, and in the brackets the unit of it the values are in, two facts
    since currency-and-currency-unit.md: `SOFR USD dv01 [DOLLAR per basis point]`, and `SOFR USD
    dv01 [CENT per basis point]` over an index settled in cents. Which group, which currency
    and which unit are the caller's."""
    return f"{group} {currency} dv01 [{currency_unit} per basis point]"


def cross_gamma_label(index: Index, group: str, reporting_lot: ReportingLot) -> str:
    """The cross-gamma column's heading, since #197: the index's short name as the desk typed it,
    the group its caller named, the curve's word or `cleared` where no curve values, the risk
    and the reporting lot's name per basis point in brackets, `HNG SOFR cross_gamma [LOT per
    basis point]`, read off the records and nothing resolved or converted here. Which group is
    the caller's."""
    return f"{index.name} {group} cross_gamma [{reporting_lot.name} per basis point]"
