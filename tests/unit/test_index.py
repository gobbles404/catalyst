"""The index: the schedule's kind read off the object, the holiday calendar as the kind requires,
and four objects bound by reference, nothing copied and nothing checked again."""

import dataclasses

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.calendar.calendar import calendar
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.contract_specifications import (
    ContractSpecifications,
    contract_specifications,
)
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.gas_daily_schedule import gas_daily_schedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.index_definitions.kind import Kind
from goosedove.market_data.futures_fixings import futures_fixings


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


# The page's sample: three Henry Hub indices, one per market, sharing one conventions object,
# USD per MMBTU with quantities in MMBTU, and the specifications page's two lots.
FUTURES = futures_schedule(
    tuple(f"c{i}" for i in range(12)),
    dates(
        "2026-01-28",
        "2026-02-25",
        "2026-03-27",
        "2026-04-28",
        "2026-05-27",
        "2026-06-26",
        "2026-07-29",
        "2026-08-27",
        "2026-09-28",
        "2026-10-28",
        "2026-11-24",
        "2026-12-29",
    ),
    None,
)
IFERC = iferc_schedule(
    ("V26", "X26", "Z26"),
    dates("2026-09-30", "2026-10-30", "2026-11-30"),
    dates("2026-10-01", "2026-11-02", "2026-12-01"),
)
GAS_DAILY = gas_daily_schedule(
    ("U26", "V26", "X26"),
    dates("2026-09-01", "2026-10-01", "2026-11-01"),
    dates("2026-09-30", "2026-10-31", "2026-11-30"),
)
HOLIDAYS = holiday_calendar(dates("2026-01-01", "2026-01-19", "2026-02-16"))
CONVENTIONS = index_conventions("USD", "MMBTU", "USD", "energy", "MMBTU")
SPECIFICATIONS = contract_specifications(
    ("NYMEX NG", "ICE NG"),
    np.array([10000.0, 2500.0]),
    np.array([3.0, 0.75]),
    np.array([2.0, 0.5]),
)


def an_index(
    name: str = "Henry Hub NYMEX",
    schedule: object = FUTURES,
    specifications: ContractSpecifications = SPECIFICATIONS,
    holidays: HolidayCalendar | None = HOLIDAYS,
) -> Index:
    return index(name, schedule, CONVENTIONS, specifications, holidays)


# --- the sample ---------------------------------------------------------------


def test_the_futures_sample_binds_its_four_objects_and_reads_its_kind_off_the_schedule() -> None:
    made = an_index()
    assert made.name == "Henry Hub NYMEX"
    assert made.kind is Kind.FUTURES
    assert made.schedule is FUTURES
    assert made.holiday_calendar is HOLIDAYS
    assert made.conventions is CONVENTIONS
    assert made.specifications is SPECIFICATIONS


def test_the_iferc_and_gas_daily_samples_carry_no_holiday_calendar() -> None:
    monthly = index("Henry Hub IFERC", IFERC, CONVENTIONS, SPECIFICATIONS, None)
    assert monthly.kind is Kind.IFERC
    assert monthly.schedule is IFERC and monthly.holiday_calendar is None
    daily = index("Henry Hub Gas Daily", GAS_DAILY, CONVENTIONS, SPECIFICATIONS, None)
    assert daily.kind is Kind.GAS_DAILY
    assert daily.schedule is GAS_DAILY and daily.holiday_calendar is None
    assert monthly.conventions is daily.conventions is CONVENTIONS


# --- what is rejected, in the order the rules run -----------------------------


def test_an_object_that_is_not_a_schedule_is_refused_naming_what_it_is() -> None:
    made = calendar(valuation_date(day("2026-06-01"), 0.5), an_index())
    fixings = futures_fixings(dates("2026-05-29"), np.array([2.9]), an_index())
    for wrong, what in (
        (HOLIDAYS, "a holiday calendar"),
        (made, "a calendar"),
        (fixings, "futures fixings"),
        (CONVENTIONS, "index conventions"),
        (an_index(), "an index"),
    ):
        with pytest.raises(ValueError) as failure:
            index("Henry Hub NYMEX", wrong, CONVENTIONS, SPECIFICATIONS, None)
        assert str(failure.value) == (
            f"schedule is {what}, expected a futures, IFERC or Gas Daily schedule"
        )


def test_a_futures_index_needs_its_holiday_calendar_and_the_other_two_refuse_one() -> None:
    with pytest.raises(ValueError) as failure:
        index("Henry Hub NYMEX", FUTURES, CONVENTIONS, SPECIFICATIONS, None)
    assert str(failure.value) == (
        "holiday_calendar is missing, expected holiday calendar handle with a futures schedule"
    )
    with pytest.raises(ValueError) as failure:
        index("Henry Hub IFERC", IFERC, CONVENTIONS, SPECIFICATIONS, HOLIDAYS)
    assert str(failure.value) == (
        "holiday_calendar is a holiday calendar, expected none with an IFERC schedule"
    )
    with pytest.raises(ValueError) as failure:
        index("Henry Hub Gas Daily", GAS_DAILY, CONVENTIONS, SPECIFICATIONS, HOLIDAYS)
    assert str(failure.value) == (
        "holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule"
    )


def test_the_schedule_is_checked_before_the_holiday_calendar() -> None:
    with pytest.raises(ValueError) as failure:
        index("Henry Hub NYMEX", HOLIDAYS, CONVENTIONS, SPECIFICATIONS, HOLIDAYS)
    assert str(failure.value).startswith("schedule is a holiday calendar")


# --- the name and the specifications are labels ----------------------------------------


def test_the_name_is_kept_as_typed_and_two_indices_may_share_it() -> None:
    for name in ("henry hub nymex", "HENRY HUB NYMEX", " Henry Hub NYMEX ", "Henry  Hub"):
        assert an_index(name).name == name
    first, second = an_index(), an_index()
    assert first.name == second.name and first is not second


# The specifications name the contracts the index trades as, not the schedule's months: one
# row against twelve contracts, or three against three, and neither name is a code.
def test_specifications_need_not_answer_to_the_schedules_codes_or_count() -> None:
    one = contract_specifications(
        ("ICE basis",), np.array([2500.0]), np.array([0.5]), np.array([0.25])
    )
    made = an_index(specifications=one)
    assert made.specifications is one
    assert len(made.specifications.names) == 1 and len(made.schedule.codes) == 12
    three = contract_specifications(
        ("V26", "X26", "Z26"), np.array([1.0, 1.0, 1.0]), np.zeros(3), np.zeros(3)
    )
    assert index("Henry Hub IFERC", IFERC, CONVENTIONS, three, None).specifications is three


# --- ownership ----------------------------------------------------------------


def test_the_index_keeps_its_objects_themselves_and_refuses_writes() -> None:
    made = an_index()
    assert Index.__slots__ == (
        "name",
        "kind",
        "schedule",
        "holiday_calendar",
        "conventions",
        "specifications",
    )
    field = "name"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(made, field, "other")


def test_making_an_index_changes_no_input_and_a_second_index_leaves_the_first() -> None:
    expiries_before = FUTURES.future_expiry.copy()
    holidays_before = HOLIDAYS.holiday.copy()
    lots_before = SPECIFICATIONS.lot_sizes.copy()
    codes_before = dataclasses.astuple(CONVENTIONS)
    first = an_index()
    second = an_index("Henry Hub NYMEX again")
    assert np.array_equal(FUTURES.future_expiry, expiries_before)
    assert np.array_equal(HOLIDAYS.holiday, holidays_before)
    assert np.array_equal(SPECIFICATIONS.lot_sizes, lots_before)
    assert dataclasses.astuple(CONVENTIONS) == codes_before
    assert first.name == "Henry Hub NYMEX" and second.name == "Henry Hub NYMEX again"
    assert first.schedule is second.schedule is FUTURES


# --- the general rule ---------------------------------------------------------


@given(
    name=st.text(min_size=1, max_size=30),
    kind=st.sampled_from(tuple(Kind)),
    count=st.integers(1, 6),
)
def test_any_kind_of_schedule_and_any_name_make_an_index_of_that_kind(
    name: str, kind: Kind, count: int
) -> None:
    schedule: object = {Kind.FUTURES: FUTURES, Kind.IFERC: IFERC, Kind.GAS_DAILY: GAS_DAILY}[kind]
    specifications = contract_specifications(
        tuple(f"contract {i}" for i in range(count)),
        np.full(count, 1000.0),
        np.zeros(count),
        np.zeros(count),
    )
    holidays = HOLIDAYS if kind is Kind.FUTURES else None
    made = index(name, schedule, CONVENTIONS, specifications, holidays)
    assert made.name == name and made.kind is kind
    assert made.schedule is schedule and made.holiday_calendar is holidays
    assert made.conventions is CONVENTIONS and made.specifications is specifications
    with pytest.raises(ValueError):
        index(name, schedule, CONVENTIONS, specifications, None if holidays else HOLIDAYS)
