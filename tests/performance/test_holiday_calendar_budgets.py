"""What naming and collecting holiday calendars costs, holiday-keys.md: a name is one
rule read once when the calendar is made, and nothing of its days; a collection counts one
calendar per calendar given, the names read once each, no day read or copied, so the work and
the peak follow the calendars and never their days; through the seam, each handle resolved once,
one publication and a readback of one row per calendar."""

from collections.abc import Callable

import numpy as np
import pytest
from test_seam_allocation import ENTRY, SLACK, least_peak, retained_numpy_bytes

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from catalyst.index_definitions.holiday_calendars import collect_holiday_calendars
from catalyst.instrumentation.work_counts import WorkCounter

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
FIRST = np.datetime64("2026-01-01", "D")
SIZES = [1, 2, 24]
IDS = ["one calendar", "two calendars", "two dozen"]


def a_calendar(name: str, holidays: int) -> HolidayCalendar:
    listed = np.arange(FIRST, FIRST + np.timedelta64(holidays, "D"), dtype="datetime64[D]")
    return holiday_calendar(name, listed)


def calendars(count: int, holidays: int) -> tuple[HolidayCalendar, ...]:
    return tuple(a_calendar(f"CAL_{i}", holidays) for i in range(count))


# --- the library ----------------------------------------------------------------------------------


# A name is its rule, read once, and the curve name's rule inside it; the days are copied and
# frozen once, whatever their number: one copy and one freeze at one day and at a thousand.
@pytest.mark.parametrize("holidays", [1, 1_000], ids=["one day", "a thousand days"])
def test_a_name_is_one_rule_read_once_and_nothing_of_the_days(
    call_profile: CallProfile, numpy_calls: CallProfile, holidays: int
) -> None:
    listed = a_calendar("LISTED", holidays).holiday
    assert call_profile(lambda: holiday_calendar("NYFED", listed)) == {
        "holiday_calendar": 1,
        "calendar_name": 1,
        "curve_name": 1,  # the text rule the two kinds of name share
        "_owning": 1,  # the days copied and frozen
    }
    assert numpy_calls(lambda: holiday_calendar("NYFED", listed)) == {
        "numpy.array": 1,
        "ndarray.setflags": 1,
    }


@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_the_counter_reports_one_calendar_collected_per_calendar_given(count: int) -> None:
    counter = WorkCounter()
    made = collect_holiday_calendars(calendars(count, 300), counter)
    assert len(made.calendars) == count
    assert counter.freeze().as_dict() == {"calendars_collected": count}


# One pass over the calendars for the two rules and one count: no numpy call at all, whatever
# the calendars' lengths, since no day is read.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_collecting_runs_no_numpy_whatever_the_calendars_lengths(
    call_profile: CallProfile, numpy_calls: CallProfile, count: int
) -> None:
    given = calendars(count, 300)
    assert call_profile(lambda: collect_holiday_calendars(given, WorkCounter())) == {
        "collect_holiday_calendars": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 1,
    }
    assert numpy_calls(lambda: collect_holiday_calendars(given, WorkCounter())) == {}


# The peak is the dictionary of names and the record, as the curve collection's is: within a
# slack of small objects and 48 bytes a calendar, whatever the calendars' lengths; the
# collection keeps no array of its own.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_the_peak_follows_the_calendars_and_nothing_of_their_days(count: int) -> None:
    given = calendars(count, 3_000)
    assert least_peak(lambda: collect_holiday_calendars(given, WorkCounter())) <= (
        SLACK + 48 * count
    )


# --- through the seam -----------------------------------------------------------------------------


def handles(count: int, holidays: int) -> Cells:
    body = Cells.from_rows([[46023.0 + i] for i in range(holidays)])
    return Cells.from_rows(
        [[ENTRY["_CreateHolidayCalendar"](f"CAL_{i}", body)] for i in range(count)]
    )


# The vector's shape checked once, the cells decoded in one pass, each resolved once, the
# library's one pass and one publication: the seam's calls grow with the handles and nothing
# else does, and no numpy runs. The curve collection's ledger, name for name.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_a_collection_resolves_each_calendar_once_and_publishes_once(
    call_profile: CallProfile, numpy_calls: CallProfile, count: int
) -> None:
    given = handles(count, 8)
    ENTRY["_CollectHolidayCalendars"](given)
    assert call_profile(lambda: ENTRY["_CollectHolidayCalendars"](given)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve_each": 1,
        "_values": 1,
        "_decoded": count,
        "_text": count,
        "_resolve": count,
        "_CollectHolidayCalendars": 1,
        "WorkCounter.__init__": 1,
        "collect_holiday_calendars": 1,
        "WorkCounter.hit": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: ENTRY["_CollectHolidayCalendars"](given)) == {}


# Through the seam a collection pays the vector's decoding and its publication and keeps no
# numpy bytes of its own: the calendars are theirs, made before and held by reference, and
# release frees nothing because nothing was kept. The curve collection's ceiling.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_a_collection_costs_small_objects_and_keeps_no_bytes_of_its_own(count: int) -> None:
    given = handles(count, 300)
    assert least_peak(lambda: ENTRY["_CollectHolidayCalendars"](given)) <= 6 * SLACK + 16 * count
    assert retained_numpy_bytes(lambda: ENTRY["_CollectHolidayCalendars"](given)) == (0, 0)


# Reading a collection back lays out one row per calendar, its name and its count of days;
# nothing is published. The curve collection's ceiling, which has two more columns.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_reading_a_collection_back_is_one_row_per_calendar(count: int) -> None:
    collection = ENTRY["_CollectHolidayCalendars"](handles(count, 300))
    live = bridge.live_handles()
    assert least_peak(lambda: ENTRY["util_ReadHandle"](collection)) <= 2 * SLACK + 96 * count
    assert bridge.live_handles() == live
