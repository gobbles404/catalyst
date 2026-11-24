"""The observations of a batch: which days' settles price each component, and with what weight.
A schedule method is a rule from a component to its observations: lastday and penultimate give
each component one observation with the whole weight, its contract's expiry day and the business
day before it; last3day gives it three with a third each, the expiry day and the two business
days before it; asian gives it every pricing day of the days it covers, its contract's month or a
part of it, an equal share each; the three expiry-based methods take a component that covers its
whole month and refuse a part of one. A batch's components may follow different methods, each its
occurrence's: the rules are looked at over the components in their order, each method present
makes its components' observations, and the whole is put back in component order. Tests supply
observations of their own through the same builder, a daily toy among them, without a public
method naming them. docs/library/trades/kernel.md is the page."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from catalyst.calendar.calendar import open_days
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.kind import with_holiday_calendar
from catalyst.index_definitions.published_schedule import PublishedSchedule
from catalyst.trades.schedule_methods import (
    METHODS,
    ScheduleMethod,
    counts_back_from_expiry,
    requires_whole_month,
    supported_on_published,
)
from catalyst.trades.terms import TradeSchedule, trade_schedule_of

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
    method: NDArray[np.intp],
    index: Index,
    contract: NDArray[np.intp],
    start: NDArray[np.datetime64],
    end: NDArray[np.datetime64],
    named: Callable[[int], str],
    field: str = "schedule_method",
    booked: Callable[[int], str] | None = None,
) -> Observations:
    """The observations the schedule methods give a batch's components, each component's method
    its occurrence's, a position among METHODS, each component a row of the index's futures
    schedule covering the days from start to end inclusive, within its contract's calendar month
    or, since onetime-averaging.md, a onetime row's whole window, the components in order, `named`
    the words for a component's trade in a refusal, as ResolvedTrades.named gives them, `trade
    'B' at row 2`, and `booked` the words for what a component is booked under, its contract's
    code when None and `the window` for a onetime component: lastday, the contract's expiry day with
    the whole weight; penultimate, the business day before it, Monday to Friday less the index's
    holiday calendar, with the whole weight, one business-day offset over the components;
    last3day, the expiry day and the two business days before it, a third each, one business-day
    offset over the components and the three offsets at once, the three days of a component
    increasing; the three take a component that covers its whole month, since their observations
    are the contract's expiry days, which a part of a month has no share of, and refuse a part of
    one by its contract, its trade and its days; asian, every Monday to Friday of the days the
    component covers the index's market is open on, an equal share each, the whole month from a
    contract code and a booked period's share of it from dates: one business-day count over the
    components for the days of each, and one business-day offset over the observations, the first
    day covered rolled forward and counted on. An expiry the index's market is closed on is
    refused by its contract and no trade under penultimate and last3day, the schedule's day being
    every row's, since the days before a closed expiry are not the last days the market priced
    the contract, and rolling the expiry would change the schedule the desk gave; under lastday
    the encoding refuses the observation itself; under asian a closed day is simply no
    observation, and a component with no pricing day at all is refused by its contract, its trade
    and its days.

    The rules are looked at over the components in their order, whatever their methods, so that
    the first component at fault is the one named: the whole-month rule over the components of
    the three expiry-based methods, then the open-expiry rule over those of penultimate and
    last3day, the index's holiday calendar typed once for the methods that read it. Then each
    method present makes its components' observations, the finite set of methods dispatched over
    once and never the rows, and when the batch mixes methods the observations are put back in
    component order and by day, one lexsort over them, since the payment anchors are found by
    that order; a batch of one method is in order as made. Which contract prices each day is the
    encoding's to derive from the calendar: the component's own under the expiry-based methods,
    whichever the calendar gives under asian. The method is the resolution's to read before any
    payment is counted, so that a payment day counts from the component's last observation;
    a refusal names the field it came from, schedule_method or since two-index-fixed-float.md
    a second leg's second_schedule_method."""
    schedule = trade_schedule_of(index)
    count = contract.size
    if method.size != count:
        raise ValueError(f"method has {method.size}, expected {count}, one per component")
    match schedule:
        case PublishedSchedule():
            # The prints a component covers, an equal share each, and no calendar read. A whole
            # month is the prints that count toward it, the schedule's rows on its contract, one
            # run found by two searches of the column that says each print's month, so no date
            # is compared. A part of a month is a window of dates: the prints dated from its
            # first day to its last, two searches of the schedule's dates, each print pricing
            # off the month its own row names. A window holding no print is refused. Under
            # lastday a component is its whole month and that month has one print, the month of
            # a monthly index such as Inside FERC's: a part of a month and a month of several
            # prints are refused, the second by its count, since no one print is the month's.
            supported = supported_on_published(method)
            if not supported.all():
                k = int((~supported).argmax())
                raise ValueError(
                    f"{field} of {named(k)} is {METHODS[int(method[k])].value!r}, "
                    "expected 'asian' or 'lastday' on a published index; a published month "
                    "is the average of its prints, or its one print"
                )
            lastday = method == METHODS.index(ScheduleMethod.LASTDAY)
            single = bool(lastday.any())
            if single:
                _whole_months(
                    schedule, contract, start, end, method, lastday, named, PUBLISHED_LASTDAY
                )
            first, prints = _the_prints(schedule, contract, start, end)
            if (prints == 0).any():
                k = int((prints == 0).argmax())
                label = schedule.codes[int(contract[k])] if booked is None else booked(k)
                raise ValueError(
                    f"{label} of {named(k)} has no print from {start[k]} to {end[k]}, expected "
                    "a print dated in the days it covers; a published index prices on its "
                    "prints alone"
                )
            if single:
                several = lastday & (prints > 1)
                if several.any():
                    k = int(several.argmax())
                    raise ValueError(
                        f"{field} of {named(k)} is 'lastday' on "
                        f"{schedule.codes[int(contract[k])]}, a month of {int(prints[k])} "
                        "prints, expected a month of one print; lastday is a month's one "
                        "print, and asian averages several"
                    )
            total = int(prints.sum())
            place = np.arange(total) - np.repeat(np.cumsum(prints) - prints, prints)
            place += np.repeat(first, prints)
            return observations(
                np.repeat(np.arange(count, dtype=np.intp), prints),
                schedule.publication_date[place],
                np.repeat(1.0 / prints, prints),
                count,
            )
        case FuturesSchedule():
            pass
        case _:
            assert_never(schedule)
    expiry = schedule.future_expiry[contract]
    holidays = with_holiday_calendar(index.holiday_calendar)
    expiry_based = requires_whole_month(method)
    if expiry_based.any():
        _whole_months(schedule, contract, start, end, method, expiry_based, named, FUTURES_WHOLE)
    before_expiry = counts_back_from_expiry(method)
    if before_expiry.any():
        _with_expiries_priced(schedule, contract, expiry, method, before_expiry, holidays)
    parts = [
        _the_days(
            METHODS[int(code)],
            on,
            expiry[on],
            start[on],
            end[on],
            schedule,
            contract,
            holidays,
            named,
            booked,
        )
        for code in np.unique(method)
        for on in (np.flatnonzero(method == code),)
    ]
    component, date, weight = parts[0]
    if len(parts) > 1:
        component = np.concatenate([part[0] for part in parts])
        date = np.concatenate([part[1] for part in parts])
        weight = np.concatenate([part[2] for part in parts])
        order = np.lexsort((date.astype(np.int64), component))
        component, date, weight = component[order], date[order], weight[order]
    return observations(component, date, weight, count)


def _the_days(
    kind: ScheduleMethod,
    on: NDArray[np.intp],
    expiry: NDArray[np.datetime64],
    start: NDArray[np.datetime64],
    end: NDArray[np.datetime64],
    schedule: FuturesSchedule,
    contract: NDArray[np.intp],
    holidays: HolidayCalendar,
    named: Callable[[int], str],
    booked: Callable[[int], str] | None,
) -> tuple[NDArray[np.intp], NDArray[np.datetime64], NDArray[np.float64]]:
    """One method's observations for the components that chose it, `on`, in their order: each
    observation's component, its day and its weight by the method's rule, the days of the
    components given aligned with `on`, a component refused named through `named` and, under
    asian, by what it is booked under through `booked`, its contract's code when None."""
    count = on.size
    match kind:
        case ScheduleMethod.LASTDAY:
            return on, expiry, np.ones(count)
        case ScheduleMethod.PENULTIMATE:
            date = np.busday_offset(expiry, -1, roll="raise", holidays=holidays.holiday)
            return on, date, np.ones(count)
        case ScheduleMethod.LAST3DAY:
            days = np.busday_offset(
                expiry[:, None], LAST3DAY_OFFSETS[None, :], roll="raise", holidays=holidays.holiday
            )
            return (
                np.repeat(on, LAST3DAY_OFFSETS.size),
                days.ravel(),
                np.full(count * LAST3DAY_OFFSETS.size, 1 / LAST3DAY_OFFSETS.size),
            )
        case ScheduleMethod.ASIAN:
            days = np.busday_count(start, end + np.timedelta64(1, "D"), holidays=holidays.holiday)
            if (days == 0).any():
                k = int((days == 0).argmax())
                component = int(on[k])
                label = (
                    schedule.codes[int(contract[component])]
                    if booked is None
                    else booked(component)
                )
                raise ValueError(
                    f"{label} of {named(component)} has no pricing day from {start[k]} to "
                    f"{end[k]}, expected a Monday to Friday of the days it covers the index's "
                    "market is open on; the asian method averages the pricing days a component "
                    "covers"
                )
            total = int(days.sum())
            component = np.repeat(on, days)
            place = np.arange(total) - np.repeat(np.cumsum(days) - days, days)
            date = np.busday_offset(
                np.repeat(start, days), place, roll="forward", holidays=holidays.holiday
            )
            return component, date, np.repeat(1.0 / days, days)
        case _:
            assert_never(kind)


FUTURES_WHOLE = (
    "the expiry-based methods take the contract's month entire, and a part of it prices under asian"
)
PUBLISHED_LASTDAY = "under lastday a month's one print is the price of the whole month"


def _the_prints(
    schedule: PublishedSchedule,
    contract: NDArray[np.intp],
    start: NDArray[np.datetime64],
    end: NDArray[np.datetime64],
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """The run of prints each component covers on a published schedule: the row of its first
    print and how many follow, none where it covers no print. A component covering its whole
    calendar month takes the prints that count toward its contract, by the code on their rows;
    one covering a part of a month takes the prints dated from its first day to its last, by
    their dates. Four searches over the components, two of each column, and one choice."""
    month = start.astype("datetime64[M]")
    whole = (start == month.astype("datetime64[D]")) & (
        end == (month + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D")
    )
    dates = schedule.publication_date
    first = np.where(
        whole,
        np.searchsorted(schedule.contract, contract, side="left"),
        np.searchsorted(dates, start, side="left"),
    )
    last = np.where(
        whole,
        np.searchsorted(schedule.contract, contract, side="right"),
        np.searchsorted(dates, end, side="right"),
    )
    return first, last - first


def _whole_months(
    schedule: TradeSchedule,
    contract: NDArray[np.intp],
    start: NDArray[np.datetime64],
    end: NDArray[np.datetime64],
    method: NDArray[np.intp],
    expiry_based: NDArray[np.bool_],
    named: Callable[[int], str],
    reason: str,
) -> None:
    """Under the expiry-based methods each component covers its whole calendar month: their
    observations are the contract's expiry days, which a part of a month has no share of, so a
    part of a month is refused by its contract, its trade, its days and its own method rather than
    priced on the whole month's expiry as if it were the whole; two conversions and one look over
    the components, the first expiry-based component at fault named."""
    month = start.astype("datetime64[M]")
    first = month.astype("datetime64[D]")
    last = (month + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D")
    partial = expiry_based & ((start != first) | (end != last))
    if partial.any():
        k = int(partial.argmax())
        raise ValueError(
            f"{schedule.codes[contract[k]]} of {named(k)} is covered from {start[k]} to {end[k]}, "
            f"part of its month, expected the whole month under {METHODS[int(method[k])].value}; "
            f"{reason}"
        )


def _with_expiries_priced(
    schedule: FuturesSchedule,
    contract: NDArray[np.intp],
    expiry: NDArray[np.datetime64],
    method: NDArray[np.intp],
    before_expiry: NDArray[np.bool_],
    holidays: HolidayCalendar,
) -> None:
    """Every expiry a penultimate or last3day component counts back from is a day the index's
    market prices; the first that is not is refused by its contract, with its own method's rule
    as the reason."""
    closed = before_expiry & ~open_days(holidays, expiry)
    if closed.any():
        k = int(closed.argmax())
        match METHODS[int(method[k])]:
            case ScheduleMethod.PENULTIMATE:
                rule = (
                    "the penultimate method takes the business day before an expiry the market "
                    "prices"
                )
            case ScheduleMethod.LAST3DAY:
                rule = (
                    "the last3day method takes an expiry the market prices and the two business "
                    "days before it"
                )
            case ScheduleMethod.LASTDAY | ScheduleMethod.ASIAN:
                rule = "the expiry-based methods take an expiry the market prices"
            case _:
                assert_never(METHODS[int(method[k])])
        raise ValueError(
            f"{schedule.codes[contract[k]]} expires on {expiry[k]}, a day the index's market is "
            f"closed; {rule}"
        )
