"""The display axes of the month and year risk reports, since #NN, risk-contract-month-bucketing.md:
consecutive calendar months or years from the one holding the valuation day through the farthest
saved period, so that a report begins at the valuation month and shows the current period even
when nothing stands in it, the periods between filled with zero; and the facts of a saved risk
before that start, found where the vector is made, which a report words with the measure asked
for and raises, scanning nothing. A batch's axes are made once when it is prepared, the valuation
day being the history's, and a collection's once when it is made; a held result keeps its axes
whatever the sheet's valuation date does after. docs/library/trades/report-risk.md is the page."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

Unit = Literal["M", "Y"]


@dataclass(frozen=True, slots=True)
class PeriodAxis:
    """One bucket's display axis for a batch, a month or a year report's: periods, the consecutive
    calendar months or years from the one holding the valuation day through the farthest saved
    period, the deltas' last contract period or the DV01's last payment period, as first days;
    delta_rows, how many of them a delta report shows, through the last contract period and at
    least one, the valuation day's own; dv01_rows, how many a DV01 report shows, through the last
    payment period, at least one for a batch with a payment axis and none for one whose DV01 has
    no dated axis; contract_from, the first saved contract period on or after the start, the ones
    before it left out of the display, their lots zero or the report refused, and contract_in,
    each shown contract period's place on the axis; paid_from and paid_in likewise for the payment
    periods. A report copies saved vectors through these places and sorts, searches and discovers
    nothing."""

    periods: NDArray[np.datetime64]
    delta_rows: int
    dv01_rows: int
    contract_from: int
    contract_in: NDArray[np.intp]
    paid_from: int
    paid_in: NDArray[np.intp]


@dataclass(frozen=True, slots=True)
class EarlyFact:
    """A saved risk standing in a period before the valuation day's, the facts a refused month or
    year report is worded from: whose risk it is, the index or the curve, the kind of period, a
    contract's or a payment's, the period and the value, the report's first period, the valuation
    day and the unit the value is counted in. The measure is the reader's to say, the nominal delta
    and the delta of a cleared result sharing one set of facts."""

    owner: str
    kind: str
    unit: Unit
    period: np.datetime64
    value: float
    start: np.datetime64
    as_of: np.datetime64
    what: str

    def words(self, measure: str) -> str:
        """The refusal, naming the measure asked for."""
        label = "month" if self.unit == "M" else "year"
        return (
            f"the {measure} of {self.owner} in the {self.kind} {label} from {self.period} is "
            f"{self.value!r} {self.what}, before the report's first {label}, {self.start}, the "
            f"{label} of as_of {self.as_of}; the day view shows where it stands"
        )


@dataclass(frozen=True, slots=True)
class EarlyRisk:
    """Why a month or a year report of one vector is refused, prepared where the vector is made:
    the facts of its first entry before the start by month and by year, or None when every such
    entry is zero. A report words the saved facts with the measure asked for and scans nothing."""

    month: EarlyFact | None
    year: EarlyFact | None

    def refuse(self, measure: str, unit: Unit) -> None:
        """Raises the refusal for the bucket, when a saved value stands before the start."""
        fact = self.month if unit == "M" else self.year
        if fact is not None:
            raise ValueError(fact.words(measure))


NO_PLACES: NDArray[np.intp] = np.empty(0, dtype=np.intp)
NO_PLACES.setflags(write=False)
NONE_EARLY = EarlyRisk(None, None)


def period_start(as_of: np.datetime64, unit: Unit) -> np.datetime64:
    """The period holding the valuation day, as numpy counts months or years."""
    return as_of.astype(f"datetime64[{unit}]")


def places_from(
    axis: NDArray[np.datetime64], start: np.datetime64, unit: Unit
) -> tuple[int, NDArray[np.intp]]:
    """A saved axis's periods on or after the start: the first such entry's position and each one's
    place on a display axis beginning at the start, one search and one subtraction; the entries
    before the start are not placed."""
    keys = axis.astype(f"datetime64[{unit}]")
    first = int(np.searchsorted(keys, start))
    return first, (keys[first:] - start).astype(np.intp)


def rows_through(places: NDArray[np.intp]) -> int:
    """How many periods a view shows: through the last saved place, and the start's own period
    alone when no saved period is on or after the start."""
    return int(places[-1]) + 1 if places.size else 1


def display_periods(start: np.datetime64, rows: int) -> NDArray[np.datetime64]:
    """That many consecutive periods from the start, as first days."""
    return (start + np.arange(rows)).astype("datetime64[D]")


def period_axis(
    as_of: np.datetime64,
    contract: NDArray[np.datetime64],
    paid: NDArray[np.datetime64] | None,
    unit: Unit,
) -> PeriodAxis:
    """The one way to make a PeriodAxis: the start, the valuation day's period; the contract
    periods' places from it and the delta rows through the last; the payment periods' places and
    the DV01 rows through the last, none when the batch has no payment axis; the display periods
    through the farther of the two. Two searches at most, every array frozen."""
    start = period_start(as_of, unit)
    contract_from, contract_in = places_from(contract, start, unit)
    delta_rows = rows_through(contract_in)
    if paid is None:
        paid_from, paid_in, dv01_rows = 0, NO_PLACES, 0
    else:
        paid_from, paid_in = places_from(paid, start, unit)
        dv01_rows = rows_through(paid_in)
    periods = display_periods(start, max(delta_rows, dv01_rows))
    for array in (periods, contract_in, paid_in):
        array.setflags(write=False)
    return PeriodAxis(
        periods, delta_rows, dv01_rows, contract_from, contract_in, paid_from, paid_in
    )


def early_fact(
    owner: str,
    kind: str,
    unit: Unit,
    periods: NDArray[np.datetime64],
    vector: NDArray[np.float64],
    shown_from: int,
    as_of: np.datetime64,
    what: str,
) -> EarlyFact | None:
    """The first entry of a saved vector that is other than zero in a period before the valuation
    day's, as the facts a refusal is worded from; None when every earlier entry is zero. Exactly
    zero, no epsilon: a value the desk's inputs put there is never rounded away."""
    early = np.flatnonzero(vector[:shown_from] != 0.0)
    if early.size == 0:
        return None
    b = int(early[0])
    start = period_start(as_of, unit).astype("datetime64[D]")
    return EarlyFact(owner, kind, unit, periods[b], float(vector[b]), start, as_of, what)


def early_risk(
    owner: str,
    kind: str,
    as_of: np.datetime64,
    what: str,
    months: NDArray[np.datetime64],
    monthly: NDArray[np.float64],
    month_from: int,
    years: NDArray[np.datetime64],
    yearly: NDArray[np.float64],
    year_from: int,
) -> EarlyRisk:
    """One vector's refusals by month and by year, or none."""
    return EarlyRisk(
        early_fact(owner, kind, "M", months, monthly, month_from, as_of, what),
        early_fact(owner, kind, "Y", years, yearly, year_from, as_of, what),
    )
