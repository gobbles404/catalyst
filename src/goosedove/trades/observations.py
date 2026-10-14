"""The observations of a batch: which days' settles price each component, and with what weight.
A schedule method is a rule from a component to its observations; lastday, the one built, gives
each component one observation, its contract's expiry day, with the whole weight. Tests supply
observations of their own through the same builder, a daily toy among them, without a public
method naming them. docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.trades.terms import ResolvedTrades, ScheduleMethod

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


def observed(terms: ResolvedTrades) -> Observations:
    """The observations the batch's schedule method gives its components: lastday, one per
    component on its contract's expiry day with the whole weight, the components in order."""
    match terms.schedule_method:
        case ScheduleMethod.LASTDAY:
            count = terms.contract.size
            return observations(
                np.arange(count, dtype=np.intp),
                terms.schedule.future_expiry[terms.contract],
                np.ones(count),
                count,
            )
        case _:
            assert_never(terms.schedule_method)
