"""A named holiday calendar and the collection of them, payment-calendar-keys.md: the name a
calendar may carry and its rule, a calendar with none as it always was; the collection, the
calendars as they are, by reference, in the order given, every one named and each name once;
through the seam, the handle that shows a name, the two readbacks and the refusals in the seam's
words and the library's. docs/library/index-definitions/collect-payment-calendars.md is the page."""

import os
import re
from typing import cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.index_definitions.holiday_calendar import (
    HolidayCalendar,
    calendar_name,
    combine_holiday_calendars,
    holiday_calendar,
)
from catalyst.index_definitions.payment_calendars import (
    PaymentCalendars,
    collect_payment_calendars,
)
from catalyst.instrumentation.work_counts import WorkCounter

PID = os.getpid()
ENTRY = {
    name: bridge.entry(name)
    for name in (
        "_CreateHolidayCalendar",
        "_CombineHolidayCalendars",
        "_CollectPaymentCalendars",
        "_CreateFuturesSchedule",
        "util_ReadHandle",
    )
}


def days(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def serial(text: str) -> float:
    return float((np.datetime64(text, "D") - np.datetime64("1899-12-30", "D")).astype(np.int64))


def column(*values: object) -> Cells:
    return Cells.from_rows([[value] for value in values])


# Two synthetic calendars, claiming no market's convention: Thanksgiving 2026 under one name, the
# two days after it under another.
NYFED = holiday_calendar(days("2026-11-26"), "NYFED")
LON = holiday_calendar(days("2026-11-27", "2026-11-30"), "LON")
UNNAMED = holiday_calendar(days("2026-12-25"))


def collected(*calendars: HolidayCalendar, counter: WorkCounter | None = None) -> PaymentCalendars:
    return collect_payment_calendars(calendars, counter or WorkCounter())


def refused(*calendars: HolidayCalendar) -> str:
    counter = WorkCounter()
    with pytest.raises(ValueError) as caught:
        collect_payment_calendars(calendars, counter)
    assert counter.freeze().as_dict() == {}  # a refusal counts nothing
    return str(caught.value)


def spilled(handle: object) -> list[list[object]]:
    kinds, slots, text = cast(
        tuple[NDArray[np.uint8], NDArray[np.float64], str], ENTRY["util_ReadHandle"](handle)
    )
    texts = iter(text.split("\0"))
    return [
        [
            next(texts) if kinds[r, c] == bridge.TEXT_CODE else slots[r, c]
            for c in range(kinds.shape[1])
        ]
        for r in range(kinds.shape[0])
    ]


# --- the name -------------------------------------------------------------------------------------


def test_a_calendar_carries_the_name_it_was_made_with_and_none_where_it_had_none() -> None:
    assert NYFED.name == "NYFED" and LON.name == "LON"
    assert UNNAMED.name is None
    np.testing.assert_array_equal(NYFED.holiday, days("2026-11-26"))
    # A name changes nothing of the days: the same listed days with a name and without.
    np.testing.assert_array_equal(
        holiday_calendar(days("2026-12-25"), "XMAS").holiday, UNNAMED.holiday
    )
    # Names as the desk types them: case kept, digits, marks other than the plus sign.
    for name in ("nyfed", "NYFed", "NY_FED", "LME-2", "US.NY", "a b"):
        assert holiday_calendar(days("2026-12-25"), name).name == name


@pytest.mark.parametrize(
    ("name", "message"),
    [
        (" ", "name is ' ', expected a name, not whitespace alone"),
        ("\t", "name is '\\t', expected a name, not whitespace alone"),
        (" NYFED", "name is ' NYFED', expected a name with no whitespace around it"),
        ("NYFED ", "name is 'NYFED ', expected a name with no whitespace around it"),
        (
            "NYFED+LON",
            "name is 'NYFED+LON', expected a name without '+', which joins names in a key",
        ),
        ("+", "name is '+', expected a name without '+', which joins names in a key"),
    ],
)
def test_a_name_no_key_could_select_is_refused_when_the_calendar_is_made(
    name: str, message: str
) -> None:
    with pytest.raises(ValueError) as caught:
        holiday_calendar(days("2026-12-25"), name)
    assert str(caught.value) == message
    with pytest.raises(ValueError) as again:
        calendar_name("name", name)
    assert str(again.value) == message


def test_a_combination_has_no_name_whatever_its_sources_are_called() -> None:
    both = combine_holiday_calendars((NYFED, LON), WorkCounter())
    assert both.name is None
    np.testing.assert_array_equal(both.holiday, days("2026-11-26", "2026-11-27", "2026-11-30"))


# --- what a collection is -------------------------------------------------------------------------


def test_a_collection_keeps_the_calendars_as_given_in_order_by_reference() -> None:
    counter = WorkCounter()
    both = collected(NYFED, LON, counter=counter)
    assert both.calendars == (NYFED, LON) and both.names == ("NYFED", "LON")
    assert both.calendars[0] is NYFED and both.calendars[1] is LON
    assert counter.freeze().as_dict() == {"calendars_collected": 2}
    assert collected(LON, NYFED).names == ("LON", "NYFED")  # the order given, not the names'
    one = WorkCounter()
    assert collected(NYFED, counter=one).names == ("NYFED",)  # one follows the same path
    assert one.freeze().as_dict() == {"calendars_collected": 1}
    # Nothing of the days is read: two calendars listing the same days are two members.
    twin = holiday_calendar(NYFED.holiday, "FED_TWIN")
    assert collected(NYFED, twin).names == ("NYFED", "FED_TWIN")


def test_every_member_has_a_name_and_each_name_once() -> None:
    assert refused(NYFED, UNNAMED) == (
        "calendar_handles cell 2 is a calendar with no name, expected one made with a name, the "
        "word a payment calendar key selects it by"
    )
    assert refused(UNNAMED) == (
        "calendar_handles cell 1 is a calendar with no name, expected one made with a name, the "
        "word a payment calendar key selects it by"
    )
    again = holiday_calendar(days("2027-01-01"), "NYFED")
    assert refused(NYFED, LON, again) == (
        "calendar_handles cell 1 and cell 3 are both named 'NYFED', expected each name once"
    )
    # The same calendar given twice is a repeat too.
    assert refused(LON, NYFED, NYFED) == (
        "calendar_handles cell 2 and cell 3 are both named 'NYFED', expected each name once"
    )
    # Names match exactly, so two that differ in case are two names.
    assert collected(NYFED, holiday_calendar(days("2027-01-01"), "nyfed")).names == (
        "NYFED",
        "nyfed",
    )
    # A combination has no name, so it is no member.
    assert refused(combine_holiday_calendars((NYFED, LON), WorkCounter())) == (
        "calendar_handles cell 1 is a calendar with no name, expected one made with a name, the "
        "word a payment calendar key selects it by"
    )


@given(st.lists(st.sampled_from(["NYFED", "LON", "TOK", "SIN", "nyfed"]), min_size=1, max_size=8))
def test_any_names_collect_exactly_when_each_is_given_once(names: list[str]) -> None:
    calendars = tuple(holiday_calendar(days("2027-01-01"), name) for name in names)
    counter = WorkCounter()
    if len(set(names)) == len(names):
        made = collect_payment_calendars(calendars, counter)
        assert made.names == tuple(names)
        assert all(mine is given for mine, given in zip(made.calendars, calendars, strict=True))
        assert counter.freeze().as_dict() == {"calendars_collected": len(names)}
    else:
        with pytest.raises(ValueError, match=r"are both named '.+', expected each name once$"):
            collect_payment_calendars(calendars, counter)
        assert counter.freeze().as_dict() == {}


# --- through the seam -----------------------------------------------------------------------------


def a_named(name: object, *holidays: str) -> object:
    return ENTRY["_CreateHolidayCalendar"](column(*(serial(day) for day in holidays)), name)


def test_the_creator_takes_a_name_and_the_handle_shows_it() -> None:
    nyfed = a_named("NYFED", "2026-11-26")
    assert re.fullmatch(rf"{PID}:holiday_calendar:NYFED:\d+", str(nyfed))
    # Left out, the calendar and its handle are as they always were.
    plain = a_named(bridge.MISSING, "2026-11-26")
    assert re.fullmatch(rf"{PID}:holiday_calendar:\d+", str(plain))
    # The readbacks: the days, and beside each the name where there is one.
    assert spilled(nyfed) == [
        ["holiday", "name"],
        ["datetime64[D]", "str"],
        [serial("2026-11-26"), "NYFED"],
    ]
    assert spilled(plain) == [["holiday"], ["datetime64[D]"], [serial("2026-11-26")]]
    lon = a_named("LON", "2026-11-27", "2026-11-30")
    assert spilled(lon)[2:] == [[serial("2026-11-27"), "LON"], [serial("2026-11-30"), "LON"]]
    # A combination of named calendars is an ordinary calendar with no name.
    both = ENTRY["_CombineHolidayCalendars"](column(nyfed, lon))
    assert re.fullmatch(rf"{PID}:holiday_calendar:\d+", str(both))
    assert spilled(both)[0] == ["holiday"]


def test_the_creator_refuses_a_name_in_the_seams_words_and_the_librarys() -> None:
    create = ENTRY["_CreateHolidayCalendar"]
    holidays = column(serial("2026-11-26"))
    assert create(holidays, 7.0) == (
        "#ERROR _CreateHolidayCalendar: name is number 7.0, expected text"
    )
    assert create(holidays, None) == "#ERROR _CreateHolidayCalendar: name is blank, expected text"
    assert create(holidays, "") == (
        "#ERROR _CreateHolidayCalendar: name is empty text, expected text"
    )
    assert create(holidays, " NYFED") == (
        "#ERROR _CreateHolidayCalendar: ValueError: name is ' NYFED', expected a name with no "
        "whitespace around it"
    )
    assert create(holidays, "NYFED+LON") == (
        "#ERROR _CreateHolidayCalendar: ValueError: name is 'NYFED+LON', expected a name "
        "without '+', which joins names in a key"
    )


def test_the_collection_on_the_sheet_reads_back_each_name_and_its_count_of_days() -> None:
    nyfed = a_named("NYFED", "2026-11-26")
    lon = a_named("LON", "2026-11-27", "2026-11-30")
    collection = ENTRY["_CollectPaymentCalendars"](column(nyfed, lon))
    assert re.fullmatch(rf"{PID}:payment_calendars:\d+", str(collection))
    assert spilled(collection) == [
        ["name", "holidays"],
        ["str", "int64"],
        ["NYFED", 1.0],
        ["LON", 2.0],
    ]
    # A row, a column and a single cell are one form; the order given is the order kept.
    across = ENTRY["_CollectPaymentCalendars"](Cells.from_rows([[lon, nyfed]]))
    assert [line[0] for line in spilled(across)[2:]] == ["LON", "NYFED"]
    assert [line[0] for line in spilled(ENTRY["_CollectPaymentCalendars"](lon))[2:]] == ["LON"]


def test_the_collection_refuses_in_the_seams_words_and_the_librarys() -> None:
    collect = ENTRY["_CollectPaymentCalendars"]
    nyfed = a_named("NYFED", "2026-11-26")
    plain = a_named(bridge.MISSING, "2026-12-25")
    assert collect(column(nyfed, plain)) == (
        "#ERROR _CollectPaymentCalendars: ValueError: calendar_handles cell 2 is a calendar with "
        "no name, expected one made with a name, the word a payment calendar key selects it by"
    )
    assert collect(column(nyfed, nyfed)) == (
        "#ERROR _CollectPaymentCalendars: ValueError: calendar_handles cell 1 and cell 2 are "
        "both named 'NYFED', expected each name once"
    )
    schedule = ENTRY["_CreateFuturesSchedule"](
        column("F27"), column(serial("2026-12-29")), bridge.MISSING
    )
    assert collect(column(nyfed, schedule)) == (
        f"#ERROR _CollectPaymentCalendars: calendar_handles cell (2, 1) is futures schedule "
        f"handle {schedule!r}, expected holiday calendar handle"
    )
    assert collect(column(nyfed, None)) == (
        "#ERROR _CollectPaymentCalendars: calendar_handles cell (2, 1) is blank, expected "
        "holiday calendar handle"
    )
    assert collect(column(nyfed, "NYFED")) == (
        "#ERROR _CollectPaymentCalendars: calendar_handles cell (2, 1) is text 'NYFED' naming "
        "no live object, expected holiday calendar handle"
    )
