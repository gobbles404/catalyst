"""The observations of a batch: which days' settles price each component, and with what weight.
A schedule method is a rule from a component to its observations: lastday and penultimate give
each component one observation with the whole weight, its contract's expiry day and the business
day before it; last3day gives it three with a third each, the expiry day and the two business
days before it; asian gives it every pricing day of the days it covers, its contract's month or a
part of it, an equal share each; the three expiry-based methods take a component that covers its
whole month and refuse a part of one. Tests supply observations of their own through the same
builder, a daily toy among them, without a public method naming them.
docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import open_days
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import with_holiday_calendar
from goosedove.trades.terms import ScheduleMethod, futures_schedule_of

# How far the weights of a component may miss one, a few units in the last place: 1/3 three
# times is one exactly, 1/7 seven times is not.
WEIGHT_TOLERANCE = 1e-9
# The last3day method's days, as business-day offsets from the expiry: the two before it and
# the expiry itself, increasing.
LAST3DAY_OFFSETS = np.array([-2, -1, 0])


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


def observed(
    method: ScheduleMethod,
    index: Index,
    contract: NDArray[np.intp],
    start: NDArray[np.datetime64],
    end: NDArray[np.datetime64],
) -> Observations:
    """The observations a schedule method gives a batch's components, each a row of the index's
    futures schedule covering the days from start to end inclusive, within its contract's calendar
    month, the components in order: lastday, the contract's expiry day with the whole
    weight; penultimate, the business day before it, Monday to Friday less the index's holiday
    calendar, with the whole weight, one business-day offset over the components; last3day, the
    expiry day and the two business days before it, a third each, one business-day offset over
    the components and the three offsets at once, the three days of a component increasing; the
    three take a component that covers its whole month, since their observations are the
    contract's expiry days, which a part of a month has no share of, and refuse a part of one by
    its contract and its days; asian, every Monday to Friday of the days the component covers the
    index's market is open on, an equal share each, the whole month from a contract code and a
    booked period's share of it from dates: one business-day count over the components for the
    days of each, and one business-day offset over the observations, the first day covered rolled
    forward and counted on. An expiry the index's market is closed on is refused by its contract
    under penultimate and last3day, since the days before a closed expiry are not the last days
    the market priced the contract, and rolling the expiry would change the schedule the desk
    gave; under lastday the encoding refuses the observation itself; under asian a closed day is
    simply no observation, and a component with no pricing day at all is refused by its contract
    and its days.
    Whether each day prices the component's own contract is the encoding's rule, under every
    method. The method is the resolution's to read before any payment is counted, so that a
    payment day counts from the component's last observation."""
    schedule = futures_schedule_of(index)
    expiry = schedule.future_expiry[contract]
    count = contract.size
    match method:
        case ScheduleMethod.LASTDAY:
            _whole_months(schedule, contract, start, end, "lastday")
            return observations(np.arange(count, dtype=np.intp), expiry, np.ones(count), count)
        case ScheduleMethod.PENULTIMATE:
            _whole_months(schedule, contract, start, end, "penultimate")
            holidays = _with_expiries_priced(
                index,
                schedule,
                contract,
                expiry,
                "the penultimate method takes the business day before an expiry the market prices",
            )
            date = np.busday_offset(expiry, -1, roll="raise", holidays=holidays.holiday)
            return observations(np.arange(count, dtype=np.intp), date, np.ones(count), count)
        case ScheduleMethod.LAST3DAY:
            _whole_months(schedule, contract, start, end, "last3day")
            holidays = _with_expiries_priced(
                index,
                schedule,
                contract,
                expiry,
                "the last3day method takes an expiry the market prices and the two business days "
                "before it",
            )
            days = np.busday_offset(
                expiry[:, None], LAST3DAY_OFFSETS[None, :], roll="raise", holidays=holidays.holiday
            )
            return observations(
                np.repeat(np.arange(count, dtype=np.intp), LAST3DAY_OFFSETS.size),
                days.ravel(),
                np.full(count * LAST3DAY_OFFSETS.size, 1 / LAST3DAY_OFFSETS.size),
                count,
            )
        case ScheduleMethod.ASIAN:
            holidays = with_holiday_calendar(index.holiday_calendar)
            days = np.busday_count(start, end + np.timedelta64(1, "D"), holidays=holidays.holiday)
            if (days == 0).any():
                k = int((days == 0).argmax())
                raise ValueError(
                    f"{schedule.codes[contract[k]]} has no pricing day from {start[k]} to "
                    f"{end[k]}, expected a Monday to Friday of the days it covers the index's "
                    "market is open on; the asian method averages the pricing days a component "
                    "covers"
                )
            total = int(days.sum())
            component = np.repeat(np.arange(count, dtype=np.intp), days)
            place = np.arange(total) - np.repeat(np.cumsum(days) - days, days)
            date = np.busday_offset(
                np.repeat(start, days), place, roll="forward", holidays=holidays.holiday
            )
            return observations(component, date, np.repeat(1.0 / days, days), count)
        case _:
            assert_never(method)


def _whole_months(
    schedule: FuturesSchedule,
    contract: NDArray[np.intp],
    start: NDArray[np.datetime64],
    end: NDArray[np.datetime64],
    method: str,
) -> None:
    """Under the expiry-based methods each component covers its whole calendar month: their
    observations are the contract's expiry days, which a part of a month has no share of, so a
    part of a month is refused by its contract and its days rather than priced on the whole
    month's expiry as if it were the whole; two conversions and one look over the components."""
    month = start.astype("datetime64[M]")
    first = month.astype("datetime64[D]")
    last = (month + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D")
    partial = (start != first) | (end != last)
    if partial.any():
        k = int(partial.argmax())
        raise ValueError(
            f"{schedule.codes[contract[k]]} is covered from {start[k]} to {end[k]}, part of its "
            f"month, expected the whole month under {method}; the expiry-based methods take the "
            "contract's month entire, and a part of it prices under asian"
        )


def _with_expiries_priced(
    index: Index,
    schedule: FuturesSchedule,
    contract: NDArray[np.intp],
    expiry: NDArray[np.datetime64],
    rule: str,
) -> HolidayCalendar:
    """The index's holiday calendar, once every expiry given is a day its market prices; the
    first that is not is refused by its contract, with the method's rule as the reason."""
    holidays = with_holiday_calendar(index.holiday_calendar)
    closed = ~open_days(holidays, expiry)
    if closed.any():
        k = int(closed.argmax())
        raise ValueError(
            f"{schedule.codes[contract[k]]} expires on {expiry[k]}, a day the index's market is "
            f"closed; {rule}"
        )
    return holidays
