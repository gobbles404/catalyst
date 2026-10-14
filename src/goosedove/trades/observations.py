"""The observations of a batch: which days' settles price each component, and with what weight.
A schedule method is a rule from a component to its observations; the two built, lastday and
penultimate, give each component one observation with the whole weight, its contract's expiry day
and the business day before it. Tests supply observations of their own through the same builder,
a daily toy among them, without a public method naming them. docs/library/trades/kernel.md is the
page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import open_days
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import with_holiday_calendar
from goosedove.trades.terms import ScheduleMethod, futures_schedule_of

# How far the weights of a component may miss one, a few units in the last place: 1/3 three
# times is one exactly, 1/7 seven times is not.
WEIGHT_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class Observations:
    """Per observation, aligned by position and read-only: component[j], the component it
    prices; date[j], the day whose settle it takes; weight[j], the share of the component's
    quantity it carries, the weights of one component summing to one. In component order, each
    component's observations together and its dates increasing."""

    component: NDArray[np.intp]
    date: NDArray[np.datetime64]
    weight: NDArray[np.float64]


def observations(
    component: NDArray[np.intp],
    date: NDArray[np.datetime64],
    weight: NDArray[np.float64],
    components: int,
) -> Observations:
    """The one way to make Observations: aligned, in component order with each component's dates
    increasing, every component of the batch holding at least one, every weight positive and each
    component's weights summing to one within rounding; the columns copied and frozen."""
    count = component.size
    for name, column in (("date", date), ("weight", weight)):
        if column.size != count:
            raise ValueError(f"{name} has {column.size}, expected {count}, one per observation")
    if count == 0:
        raise ValueError("component has 0 observations, expected at least one per component")
    outside = (component < 0) | (component >= components)
    if outside.any():
        j = int(outside.argmax())
        raise ValueError(
            f"observation {j + 1} is of component {component[j]}, "
            f"expected a component, 0 to {components - 1}"
        )
    if (np.diff(component) < 0).any():
        j = int((np.diff(component) < 0).argmax()) + 1
        raise ValueError(
            f"observation {j + 1} is of component {component[j]}, after one of "
            f"component {component[j - 1]}; expected component order"
        )
    same = component[1:] == component[:-1]
    backwards = same & (date[1:] <= date[:-1])
    if backwards.any():
        j = int(backwards.argmax()) + 1
        raise ValueError(
            f"observation {j + 1} of component {component[j]} is on {date[j]}, "
            f"expected a day after {date[j - 1]}, the observation before it"
        )
    held = np.bincount(component, minlength=components)
    if (held == 0).any():
        k = int((held == 0).argmax())
        raise ValueError(f"component {k} has no observation, expected at least one")
    if not (weight > 0).all():
        j = int((~(weight > 0)).argmax())
        raise ValueError(f"weight {j + 1} is {float(weight[j])!r}, expected a positive share")
    sums = np.bincount(component, weights=weight, minlength=components)
    off = np.abs(sums - 1.0) > WEIGHT_TOLERANCE
    if off.any():
        k = int(off.argmax())
        raise ValueError(
            f"the weights of component {k} sum to {float(sums[k])!r}, expected 1, the whole "
            "quantity shared out"
        )
    columns = (
        np.array(component, dtype=np.intp),
        np.array(date, dtype="datetime64[D]"),
        np.array(weight, dtype=np.float64),
    )
    for array in columns:
        array.setflags(write=False)
    return Observations(*columns)


def observed(method: ScheduleMethod, index: Index, contract: NDArray[np.intp]) -> Observations:
    """The observations a schedule method gives a batch's components, each a row of the index's
    futures schedule, one per component with the whole weight, the components in order: lastday,
    the contract's expiry day; penultimate, the business day before it, Monday to Friday less the
    index's holiday calendar, one business-day offset over the components. An expiry the index's
    market is closed on is refused by its contract under penultimate, since the day before a
    closed expiry is not the last day the market priced the contract, and rolling the expiry
    would change the schedule the desk gave; under lastday the encoding refuses the observation
    itself. The method is the resolution's to read before any payment is counted, so that a
    payment day counts from the component's observation day."""
    schedule = futures_schedule_of(index)
    expiry = schedule.future_expiry[contract]
    count = contract.size
    match method:
        case ScheduleMethod.LASTDAY:
            date = expiry
        case ScheduleMethod.PENULTIMATE:
            holidays = with_holiday_calendar(index.holiday_calendar)
            closed = ~open_days(holidays, expiry)
            if closed.any():
                k = int(closed.argmax())
                raise ValueError(
                    f"{schedule.codes[contract[k]]} expires on {expiry[k]}, a day the index's "
                    "market is closed; the penultimate method takes the business day before an "
                    "expiry the market prices"
                )
            date = np.busday_offset(expiry, -1, roll="raise", holidays=holidays.holiday)
        case _:
            assert_never(method)
    return observations(np.arange(count, dtype=np.intp), date, np.ones(count), count)
