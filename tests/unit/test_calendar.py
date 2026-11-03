"""The calendar: the index's kind choosing which is made, each kind's rules on the index's
schedule, and the four columns made once."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.calendar.calendar import Calendar, calendar
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import ValuationDate, valuation_date
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from catalyst.index_definitions.gas_daily_schedule import GasDailySchedule, gas_daily_schedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from catalyst.index_definitions.iferc_schedule import IfercSchedule, iferc_schedule
from catalyst.index_definitions.index import Index, index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.index_definitions.kind import Kind


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def a_schedule(*contracts: tuple[str, str]) -> FuturesSchedule:
    codes = tuple(code for code, _ in contracts)
    return futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)


def codes_of(made: Calendar) -> list[str]:
    return [made.index.schedule.codes[row] for row in made.contract.tolist()]


# The page's sample: three contracts of one index, the valuation date 25 May 2026 at midday,
# and that day, a Monday, a holiday.
SCHEDULE = a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"))
MAY_25 = valuation_date(day("2026-05-25"), 0.5)
CLOSED_MAY_25 = holiday_calendar(dates("2026-05-25"))
# A calendar of one day, New Year's Day, outside every calendar built here.
ELSEWHERE = holiday_calendar(dates("2026-01-01"))

CONVENTIONS = index_conventions("USD", "BBL", "USD", "VOLUME", "BBL", UNITS)
SPECIFICATIONS = contract_specifications(
    ("NYMEX",), np.array([1000.0]), ("BBL",), np.array([0.0]), np.array([0.0]), UNITS
)


def an_index(
    schedule: object = SCHEDULE, holidays: HolidayCalendar | None = CLOSED_MAY_25
) -> Index:
    """The index of that schedule and holiday calendar, with one set of conventions and
    specifications throughout, since nothing here reads either."""
    return index(
        "sample",
        "Sample futures index",
        schedule,
        CONVENTIONS,
        SPECIFICATIONS,
        holidays,
        None,
        UNITS,
    )


def a_calendar(
    valuation: ValuationDate = MAY_25,
    schedule: FuturesSchedule = SCHEDULE,
    holidays: HolidayCalendar | None = CLOSED_MAY_25,
) -> Calendar:
    return calendar(valuation, an_index(schedule, holidays))


# --- the sample ---------------------------------------------------------------


def test_the_sample_runs_from_the_day_after_the_first_expiry_to_the_last() -> None:
    made = a_calendar()
    assert made.dates.size == 63
    assert made.dates[0] == day("2026-05-20")
    assert made.dates[-1] == day("2026-07-21")
    assert np.all(np.diff(made.dates) == np.timedelta64(1, "D"))
    assert made.dates.dtype == np.dtype("datetime64[D]")
    assert made.contract.dtype == np.dtype(np.intp)
    assert made.is_priced.dtype == np.dtype(bool)
    assert made.is_fixed.dtype == np.dtype(bool)
    assert made.contract.size == made.is_priced.size == made.is_fixed.size == 63
    assert made.index.kind is Kind.FUTURES
    assert made.first_unfixed == 5  # the days before the valuation day, 25 May


def test_the_rows_the_page_shows() -> None:
    made = a_calendar()
    shown = {
        str(date): (code, bool(open_), bool(past))
        for date, code, open_, past in zip(
            made.dates, codes_of(made), made.is_priced, made.is_fixed, strict=True
        )
    }
    assert shown["2026-05-20"] == ("n26", True, True)
    assert shown["2026-05-22"] == ("n26", True, True)
    assert shown["2026-05-23"] == ("n26", False, True)
    assert shown["2026-05-24"] == ("n26", False, True)
    assert shown["2026-05-25"] == ("n26", False, False)
    assert shown["2026-05-26"] == ("n26", True, False)
    assert shown["2026-06-22"] == ("n26", True, False)
    assert shown["2026-06-23"] == ("q26", True, False)
    assert shown["2026-07-21"] == ("q26", True, False)


def test_the_boundary_contract_is_never_prompt() -> None:
    made = a_calendar()
    assert 0 not in made.contract
    assert "m26" not in codes_of(made)
    assert made.contract.min() == 1


# Every interior expiry keeps its contract, and the next calendar day switches to the next one;
# each contract after the boundary holds exactly the days from the expiry before its own to its
# own, weekends and holidays counted like any day.
def test_prompt_transitions_fall_the_day_after_each_expiry() -> None:
    schedule = a_schedule(
        ("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"), ("u26", "2026-08-20")
    )
    made = a_calendar(schedule=schedule)
    shown = dict(zip((str(d) for d in made.dates), codes_of(made), strict=True))
    assert shown["2026-05-20"] == "n26"
    assert shown["2026-06-22"] == "n26"
    assert shown["2026-06-23"] == "q26"
    assert shown["2026-07-21"] == "q26"
    assert shown["2026-07-22"] == "u26"
    assert shown["2026-08-20"] == "u26"
    assert np.bincount(made.contract, minlength=4).tolist() == [0, 34, 29, 30]


def test_two_expiries_a_day_apart_make_one_row_for_the_second_contract() -> None:
    made = a_calendar(schedule=a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-20")))
    assert made.dates.tolist() == [day("2026-05-20")]
    assert codes_of(made) == ["n26"]
    assert made.is_priced.tolist() == [True]
    assert made.is_fixed.tolist() == [True]


# --- what is rejected, in the order the rules run -----------------------------


@pytest.mark.parametrize(
    ("schedule", "message"),
    [
        (a_schedule(("m26", "2026-05-19")), "index has 1 contract, expected at least 2"),
        (
            futures_schedule((), dates(), None),
            "index has 0 contracts, expected at least 2",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("m26", "2026-06-22")),
            "contract_code row 2 is 'm26', already given at row 1",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("m26", "2026-07-21")),
            "contract_code row 3 is 'm26', already given at row 1",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("n26", "2026-07-21")),
            "contract_code row 3 is 'n26', already given at row 2",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-19")),
            "future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-05-19",
        ),
        (
            a_schedule(("m26", "2026-06-22"), ("n26", "2026-05-19")),
            "future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-06-01")),
            "future_expiry row 3 is 2026-06-01, expected a date after row 2's 2026-06-22",
        ),
        (
            a_schedule(("m26", "2026-06-22"), ("m26", "2026-05-19")),
            "contract_code row 2 is 'm26', already given at row 1",
        ),
        (
            a_schedule(("M26", "2026-05-19"), ("m26", "2026-06-22")),
            "future_expiry row 2 is 2026-06-22, expected a date after row 1's 2026-05-19",
        ),
    ],
    ids=[
        "one contract",
        "no contract",
        "the boundary code given again",
        "the boundary code given a third row",
        "a code given twice after the boundary",
        "two expiries equal",
        "expiries backwards",
        "a later expiry before the one above",
        "the codes are checked before the expiries",
        "M26 and m26 are two codes",
    ],
)
def test_a_schedule_that_cannot_make_a_calendar_says_why(
    schedule: FuturesSchedule, message: str
) -> None:
    if message.startswith("future_expiry row 2 is 2026-06-22"):
        a_calendar(schedule=schedule)  # two codes, so the calendar is made
        return
    with pytest.raises(ValueError) as failure:
        a_calendar(schedule=schedule)
    assert str(failure.value) == message


# The bound the discount curve holds too: a calendar of a sheet's rows less the two heading rows
# is read back in full, and one day longer is refused, naming both expiries.
def test_the_longest_calendar_a_sheet_shows_is_made_and_one_day_longer_is_refused() -> None:
    longest = a_calendar(schedule=a_schedule(("a", "2026-05-19"), ("b", "4897-04-11")))
    assert longest.dates.size == 1_048_574
    assert longest.dates[-1] == day("4897-04-11")
    with pytest.raises(ValueError) as failure:
        a_calendar(schedule=a_schedule(("a", "2026-05-19"), ("b", "4897-04-12")))
    assert str(failure.value) == (
        "future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19"
    )
    with pytest.raises(ValueError) as failure:
        a_calendar(
            schedule=a_schedule(("a", "2026-05-19"), ("b", "2026-06-22"), ("c", "9999-12-31"))
        )
    assert str(failure.value) == (
        "future_expiry row 3 is 9999-12-31, expected within 1048574 days of row 1's 2026-05-19"
    )


# --- calendar arithmetic ------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        ("2026-04-30", "2026-05-31", [f"2026-05-{d:02d}" for d in range(1, 32)]),
        ("2026-12-30", "2027-01-02", ["2026-12-31", "2027-01-01", "2027-01-02"]),
        ("2028-02-27", "2028-03-01", ["2028-02-28", "2028-02-29", "2028-03-01"]),
        ("2027-02-27", "2027-03-01", ["2027-02-28", "2027-03-01"]),
        ("1900-03-01", "1900-03-02", ["1900-03-02"]),
        ("9999-12-30", "9999-12-31", ["9999-12-31"]),
        ("1900-03-01", "1900-03-04", ["1900-03-02", "1900-03-03", "1900-03-04"]),
    ],
    ids=[
        "a month end",
        "a year end",
        "a leap day",
        "no leap day",
        "the first days a cell holds",
        "the last days a cell holds",
        "a short range at the start of the sheet's calendar",
    ],
)
def test_every_calendar_day_between_the_expiries_is_a_row(
    first: str, last: str, expected: list[str]
) -> None:
    made = a_calendar(schedule=a_schedule(("a", first), ("b", last)), holidays=ELSEWHERE)
    assert [str(date) for date in made.dates] == expected
    assert codes_of(made) == ["b"] * len(expected)


# --- the business-day flag ----------------------------------------------------


def flags(made: Calendar) -> dict[str, tuple[bool, bool]]:
    return {
        str(date): (bool(open_), bool(past))
        for date, open_, past in zip(made.dates, made.is_priced, made.is_fixed, strict=True)
    }


def test_weekdays_are_business_days_and_both_weekend_days_are_not() -> None:
    open_ = {date: open_ for date, (open_, _) in flags(a_calendar(holidays=ELSEWHERE)).items()}
    assert [open_[f"2026-05-{d}"] for d in range(20, 27)] == [
        True,  # Wednesday
        True,
        True,  # Friday
        False,  # Saturday
        False,  # Sunday
        True,  # Monday
        True,
    ]


def test_a_holiday_on_a_weekday_closes_it_and_one_on_a_weekend_changes_nothing() -> None:
    weekday = flags(a_calendar())
    assert weekday["2026-05-25"][0] is False
    assert weekday["2026-05-26"][0] is True
    on_a_saturday = flags(a_calendar(holidays=holiday_calendar(dates("2026-05-23"))))
    assert on_a_saturday == flags(a_calendar(holidays=ELSEWHERE))


def test_consecutive_holidays_close_each_day() -> None:
    closed = holiday_calendar(dates("2026-05-25", "2026-05-26", "2026-05-27"))
    shown = flags(a_calendar(holidays=closed))
    assert [shown[f"2026-05-{d}"][0] for d in (22, 25, 26, 27, 28)] == [
        True,
        False,
        False,
        False,
        True,
    ]


# --- holiday invariance -------------------------------------------------------


def test_duplicate_unordered_and_out_of_range_holidays_change_nothing() -> None:
    plain = a_calendar(holidays=holiday_calendar(dates("2026-05-25", "2026-06-19")))
    messy = a_calendar(
        holidays=holiday_calendar(
            dates(
                "2026-06-19",
                "2026-05-25",
                "2026-05-25",
                "2025-01-01",
                "2027-12-25",
                "2026-05-19",
                "2026-07-22",
            )
        )
    )
    assert np.array_equal(plain.is_priced, messy.is_priced)
    assert np.array_equal(plain.dates, messy.dates)
    assert np.array_equal(plain.contract, messy.contract)
    assert np.array_equal(plain.is_fixed, messy.is_fixed)


def test_a_holiday_on_an_expiry_changes_the_business_day_flag_alone() -> None:
    plain = a_calendar(holidays=ELSEWHERE)
    closed = a_calendar(holidays=holiday_calendar(dates("2026-06-22")))
    assert np.array_equal(plain.dates, closed.dates)
    assert np.array_equal(plain.contract, closed.contract)
    assert np.array_equal(plain.is_fixed, closed.is_fixed)
    changed = plain.is_priced != closed.is_priced
    assert plain.dates[changed].tolist() == [day("2026-06-22")]
    assert flags(closed)["2026-06-22"][0] is False
    assert codes_of(closed)[33] == "n26"


# --- the past flag ------------------------------------------------------------


@pytest.mark.parametrize(
    ("as_of", "past_days"),
    [
        ("2026-01-01", 0),
        ("2026-05-19", 0),
        ("2026-05-20", 0),
        ("2026-05-21", 1),
        ("2026-05-25", 5),
        ("2026-07-21", 62),
        ("2026-07-22", 63),
        ("2027-01-01", 63),
    ],
    ids=[
        "before the calendar",
        "the boundary expiry, the day before the calendar",
        "the first day",
        "the second day",
        "inside",
        "the last day",
        "the day after the calendar",
        "well after the calendar",
    ],
)
def test_the_days_before_the_valuation_date_are_past_and_the_day_itself_is_not(
    as_of: str, past_days: int
) -> None:
    made = a_calendar(valuation=valuation_date(day(as_of), 0.5))
    assert int(made.is_fixed.sum()) == past_days
    assert made.first_unfixed == past_days
    assert made.is_fixed.tolist() == [bool(date < day(as_of)) for date in made.dates]
    if past_days:
        assert made.is_fixed[:past_days].all() and not made.is_fixed[past_days:].any()


def test_the_fraction_of_the_valuation_day_changes_nothing() -> None:
    whole = [a_calendar(valuation=valuation_date(day("2026-05-25"), f)) for f in (0.0, 0.5, 1.0)]
    for made in whole[1:]:
        assert np.array_equal(made.is_fixed, whole[0].is_fixed)
    assert not flags(whole[0])["2026-05-25"][1]
    assert not flags(whole[2])["2026-05-25"][1]


def test_the_two_flags_are_independent() -> None:
    shown = flags(a_calendar())
    assert shown["2026-05-23"] == (False, True)  # a past Saturday
    assert shown["2026-05-25"] == (False, False)  # the valuation date, a holiday
    assert shown["2026-05-22"] == (True, True)  # a past Friday
    assert shown["2026-05-26"] == (True, False)  # a Tuesday to come


# --- what the schedule's other columns do: nothing ---------------------------------


def test_option_expiries_change_nothing() -> None:
    codes = ("m26", "n26", "q26")
    futures = dates("2026-05-19", "2026-06-22", "2026-07-21")
    options = dates("2026-05-14", "2026-06-16", "2026-07-16")
    plain = a_calendar()
    for schedule in (
        futures_schedule(codes, futures, options),
        futures_schedule(codes, futures, dates("2027-01-01", "2027-01-02", "2027-01-03")),
    ):
        made = a_calendar(schedule=schedule)
        assert np.array_equal(made.dates, plain.dates)
        assert np.array_equal(made.contract, plain.contract)
        assert np.array_equal(made.is_priced, plain.is_priced)
        assert np.array_equal(made.is_fixed, plain.is_fixed)


# --- the general rule ---------------------------------------------------------


def any_schedule(data: st.DataObject) -> FuturesSchedule:
    count = data.draw(st.integers(2, 40))
    codes = tuple(
        data.draw(
            st.lists(st.text(min_size=1, max_size=6), unique=True, min_size=count, max_size=count)
        )
    )
    gaps = data.draw(st.lists(st.integers(1, 60), min_size=count, max_size=count))
    offsets = np.cumsum(gaps, dtype=np.int64)
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    return futures_schedule(codes, start + offsets.astype("timedelta64[D]"), None)


@settings(deadline=None)
@given(data=st.data())
def test_every_day_between_the_first_expiry_and_the_last_is_one_row_with_one_prompt(
    data: st.DataObject,
) -> None:
    schedule = any_schedule(data)
    expiries = schedule.future_expiry
    listed = expiries[0] + np.array(
        data.draw(st.lists(st.integers(-10, 2500), max_size=30)), dtype="timedelta64[D]"
    )
    as_of = expiries[0] + np.timedelta64(data.draw(st.integers(-10, 2500)), "D")
    made = calendar(valuation_date(as_of, 0.5), an_index(schedule, holiday_calendar(listed)))
    span = int((expiries[-1] - expiries[0]).astype(np.int64))
    assert made.dates.size == span
    assert np.all(np.diff(made.dates) == np.timedelta64(1, "D"))
    assert made.dates[0] == expiries[0] + np.timedelta64(1, "D")
    assert made.dates[-1] == expiries[-1]
    before = expiries[made.contract - 1]
    own = expiries[made.contract]
    assert np.all((before < made.dates) & (made.dates <= own))
    assert made.contract.min() >= 1
    days_per_contract = np.diff(expiries).astype(np.int64)
    assert (
        np.bincount(made.contract, minlength=expiries.size)[1:].tolist()
        == days_per_contract.tolist()
    )
    assert np.array_equal(made.is_fixed, made.dates < as_of)
    assert made.first_unfixed == int(np.count_nonzero(made.is_fixed))


# --- ownership ----------------------------------------------------------------


def test_the_calendar_keeps_its_sources_by_reference_and_its_columns_read_only() -> None:
    made = a_calendar()
    assert made.valuation_date is MAY_25
    assert made.index.schedule is SCHEDULE
    assert made.index.holiday_calendar is CLOSED_MAY_25
    the_index = an_index()
    assert calendar(MAY_25, the_index).index is the_index
    for column in (made.dates, made.contract, made.is_priced, made.is_fixed):
        assert not column.flags.writeable
    with pytest.raises(ValueError):
        made.dates[0] = day("2030-01-01")
    with pytest.raises(ValueError):
        made.is_fixed[0] = False
    field = "first_unfixed"
    with pytest.raises(AttributeError):
        setattr(made, field, 0)


def test_making_a_calendar_changes_no_source_and_a_second_calendar_leaves_the_first() -> None:
    holidays = holiday_calendar(dates("2026-06-19", "2026-05-25", "2026-05-25"))
    listed_before = holidays.holiday.copy()
    first = a_calendar(holidays=holidays)
    assert np.array_equal(holidays.holiday, listed_before)
    assert np.array_equal(SCHEDULE.future_expiry, dates("2026-05-19", "2026-06-22", "2026-07-21"))
    assert SCHEDULE.codes == ("m26", "n26", "q26")
    past_before = first.is_fixed.copy()
    second = a_calendar(valuation=valuation_date(day("2026-07-01"), 0.0), holidays=holidays)
    assert np.array_equal(first.is_fixed, past_before)
    assert second.is_fixed.sum() > first.is_fixed.sum()
    assert first.dates is not second.dates


# --- a Gas Daily schedule: every flow day, its month on each ------------------------


def a_gas_daily_schedule(*months: tuple[str, str, str]) -> GasDailySchedule:
    codes = tuple(code for code, _, _ in months)
    firsts = dates(*(first for _, first, _ in months))
    lasts = dates(*(last for _, _, last in months))
    return gas_daily_schedule(codes, firsts, lasts)


# The Gas Daily schedule page's sample, three months of one index, valued on 25 September 2026.
U26 = ("U26", "2026-09-01", "2026-09-30")
V26 = ("V26", "2026-10-01", "2026-10-31")
Z26 = ("Z26", "2026-12-01", "2026-12-31")
F27 = ("F27", "2027-01-01", "2027-01-31")
GAS_DAILY = a_gas_daily_schedule(
    U26,
    V26,
    ("X26", "2026-11-01", "2026-11-30"),
)
SEP_25 = valuation_date(day("2026-09-25"), 0.5)


def test_the_gas_daily_sample_runs_from_the_first_months_first_day_to_the_lasts_last() -> None:
    made = calendar(SEP_25, an_index(GAS_DAILY, None))
    assert made.index.kind is Kind.GAS_DAILY
    assert made.dates.size == 91
    assert made.dates[0] == day("2026-09-01") and made.dates[-1] == day("2026-11-30")
    assert np.all(np.diff(made.dates) == np.timedelta64(1, "D"))
    assert codes_of(made)[:30] == ["U26"] * 30
    assert codes_of(made)[30:61] == ["V26"] * 31
    assert codes_of(made)[61:] == ["X26"] * 30
    assert made.is_priced.all()
    assert made.is_fixed.tolist() == [bool(date <= day("2026-09-25")) for date in made.dates]
    assert int(made.is_fixed.sum()) == 25
    assert made.first_unfixed == 25
    assert made.index.schedule is GAS_DAILY and made.index.holiday_calendar is None
    assert made.valuation_date is SEP_25


def test_a_gas_daily_schedule_of_one_month_or_of_one_day_is_a_calendar() -> None:
    one = calendar(SEP_25, an_index(a_gas_daily_schedule(U26), None))
    assert one.dates.size == 30 and codes_of(one) == ["U26"] * 30
    day_long = calendar(
        SEP_25, an_index(a_gas_daily_schedule(("U26", "2026-09-01", "2026-09-01")), None)
    )
    assert day_long.dates.tolist() == [day("2026-09-01")] and codes_of(day_long) == ["U26"]


def test_gas_daily_months_across_a_month_end_and_a_year_end_are_a_row_per_day() -> None:
    made = calendar(SEP_25, an_index(a_gas_daily_schedule(Z26, F27), None))
    assert made.dates.size == 62
    assert codes_of(made)[30:32] == ["Z26", "F27"]
    assert not made.is_fixed.any()


def test_a_gas_daily_calendar_prices_every_day_wherever_the_valuation_date_falls() -> None:
    before = calendar(valuation_date(day("2026-01-01"), 0.5), an_index(GAS_DAILY, None))
    assert before.is_priced.all() and not before.is_fixed.any()
    assert before.first_unfixed == 0
    after = calendar(valuation_date(day("2027-01-01"), 0.0), an_index(GAS_DAILY, None))
    assert after.is_priced.all() and after.is_fixed.all()
    assert after.first_unfixed == 91
    on_the_first = calendar(valuation_date(day("2026-09-01"), 0.0), an_index(GAS_DAILY, None))
    assert on_the_first.is_fixed.tolist()[:2] == [True, False]
    assert on_the_first.first_unfixed == 1


@pytest.mark.parametrize(
    ("schedule", "message"),
    [
        (
            a_gas_daily_schedule(U26, ("U26", "2026-10-01", "2026-10-31")),
            "contract_code row 2 is 'U26', already given at row 1",
        ),
        (
            a_gas_daily_schedule(U26, ("V26", "2026-10-01", "2026-09-30")),
            "last_date row 2 is 2026-09-30, expected a date on or after row 2's first_date "
            "2026-10-01",
        ),
        (
            a_gas_daily_schedule(U26, ("V26", "2026-10-02", "2026-10-31")),
            "first_date row 2 is 2026-10-02, expected 2026-10-01, "
            "the day after row 1's last_date 2026-09-30",
        ),
        (
            a_gas_daily_schedule(U26, ("V26", "2026-09-30", "2026-10-31")),
            "first_date row 2 is 2026-09-30, expected 2026-10-01, "
            "the day after row 1's last_date 2026-09-30",
        ),
        (
            a_gas_daily_schedule(V26, U26),
            "first_date row 2 is 2026-09-01, expected 2026-11-01, "
            "the day after row 1's last_date 2026-10-31",
        ),
        (
            a_gas_daily_schedule(U26, ("V26", "2026-10-01", "4897-07-26")),
            "last_date row 2 is 4897-07-26, "
            "expected within 1048573 days of row 1's first_date 2026-09-01",
        ),
        (gas_daily_schedule((), dates(), dates()), "index has 0 contracts, expected at least 1"),
    ],
    ids=[
        "a code twice",
        "a month whose last day precedes its first",
        "a gap of a day between two months",
        "an overlap of a day",
        "months out of order",
        "a span no sheet could show",
        "no month",
    ],
)
def test_a_gas_daily_schedule_that_cannot_make_a_calendar_says_why(
    schedule: GasDailySchedule, message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        calendar(SEP_25, an_index(schedule, None))
    assert str(failure.value) == message


# Both ends are rows here, so the longest Gas Daily calendar a sheet shows ends a day before the
# longest futures calendar from the same first day, and one day longer is refused.
def test_the_longest_gas_daily_calendar_a_sheet_shows_is_made_and_one_day_longer_is_refused() -> (
    None
):
    made = calendar(SEP_25, an_index(a_gas_daily_schedule(("a", "2026-09-01", "4897-07-24")), None))
    assert made.dates.size == 1_048_574
    assert codes_of(made)[-1] == "a"
    with pytest.raises(ValueError) as failure:
        calendar(SEP_25, an_index(a_gas_daily_schedule(("a", "2026-09-01", "4897-07-25")), None))
    assert str(failure.value) == (
        "last_date row 1 is 4897-07-25, expected within 1048573 days of row 1's first_date "
        "2026-09-01"
    )


# --- an IFERC schedule: one row per month, dated by its publication day ----------------


def an_iferc_schedule(*months: tuple[str, str]) -> IfercSchedule:
    codes = tuple(code for code, _ in months)
    published = dates(*(publication for _, publication in months))
    return iferc_schedule(codes, published)


# The IFERC schedule page's sample, three months of one index, valued on 15 November 2026,
# when one of the three has been published.
V26_IFERC = ("V26", "2026-10-01")
X26_IFERC = ("X26", "2026-11-02")
IFERC = an_iferc_schedule(V26_IFERC, X26_IFERC, ("Z26", "2026-12-01"))
NOV_15 = valuation_date(day("2026-11-15"), 0.5)


def test_the_iferc_sample_is_one_row_per_month_dated_by_its_publication_day() -> None:
    made = calendar(NOV_15, an_index(IFERC, None))
    assert made.index.kind is Kind.IFERC
    assert [str(date) for date in made.dates] == ["2026-10-01", "2026-11-02", "2026-12-01"]
    assert codes_of(made) == ["V26", "X26", "Z26"]
    assert made.contract.tolist() == [0, 1, 2]
    assert made.is_priced.all()
    assert made.is_fixed.tolist() == [True, True, False]
    assert made.first_unfixed == 2
    assert made.index.schedule is IFERC and made.index.holiday_calendar is None


def test_an_iferc_month_is_fixed_the_day_after_its_publication_day() -> None:
    on_the_day = calendar(valuation_date(day("2026-11-02"), 1.0), an_index(IFERC, None))
    assert on_the_day.is_fixed.tolist() == [True, False, False]
    assert on_the_day.first_unfixed == 1
    the_day_after = calendar(valuation_date(day("2026-11-03"), 0.0), an_index(IFERC, None))
    assert the_day_after.is_fixed.tolist() == [True, True, False]
    before_any = calendar(valuation_date(day("2026-10-01"), 0.5), an_index(IFERC, None))
    assert not before_any.is_fixed.any()


def test_an_iferc_schedule_of_one_month_is_a_calendar() -> None:
    one = calendar(NOV_15, an_index(an_iferc_schedule(V26_IFERC), None))
    assert codes_of(one) == ["V26"] and one.is_fixed.tolist() == [True]
    assert one.dates.tolist() == [day("2026-10-01")]


@pytest.mark.parametrize(
    ("schedule", "message"),
    [
        (
            an_iferc_schedule(V26_IFERC, ("V26", "2026-11-02")),
            "contract_code row 2 is 'V26', already given at row 1",
        ),
        (
            an_iferc_schedule(X26_IFERC, V26_IFERC),
            "publication_date row 2 is 2026-10-01, expected a date after row 1's 2026-11-02",
        ),
        (
            an_iferc_schedule(V26_IFERC, ("X26", "2026-10-01")),
            "publication_date row 2 is 2026-10-01, expected a date after row 1's 2026-10-01",
        ),
        (iferc_schedule((), dates()), "index has 0 contracts, expected at least 1"),
    ],
    ids=["a code twice", "publication days out of order", "two publication days equal", "no month"],
)
def test_an_iferc_schedule_that_cannot_make_a_calendar_says_why(
    schedule: IfercSchedule, message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        calendar(NOV_15, an_index(schedule, None))
    assert str(failure.value) == message


# --- the general rules of the two new kinds ---------------------------------------------


@settings(deadline=None)
@given(data=st.data())
def test_every_flow_day_of_gas_daily_months_laid_end_to_end_is_one_row_on_its_month(
    data: st.DataObject,
) -> None:
    count = data.draw(st.integers(1, 40))
    codes = tuple(
        data.draw(
            st.lists(st.text(min_size=1, max_size=6), unique=True, min_size=count, max_size=count)
        )
    )
    lengths = np.array(
        data.draw(st.lists(st.integers(1, 40), min_size=count, max_size=count)), dtype=np.int64
    )
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    one_day = np.timedelta64(1, "D")
    lasts = start + np.cumsum(lengths).astype("timedelta64[D]") - one_day
    firsts = lasts - lengths.astype("timedelta64[D]") + one_day
    schedule = gas_daily_schedule(codes, firsts, lasts)
    as_of = start + np.timedelta64(data.draw(st.integers(-10, 2000)), "D")
    made = calendar(valuation_date(as_of, 0.5), an_index(schedule, None))
    assert made.dates.size == int(lengths.sum())
    assert np.all(np.diff(made.dates) == one_day)
    assert made.dates[0] == firsts[0] and made.dates[-1] == lasts[-1]
    assert np.all((firsts[made.contract] <= made.dates) & (made.dates <= lasts[made.contract]))
    assert np.bincount(made.contract, minlength=count).tolist() == lengths.tolist()
    assert made.is_priced.all()
    assert np.array_equal(made.is_fixed, made.dates <= as_of)


@settings(deadline=None)
@given(data=st.data())
def test_every_iferc_month_is_one_row_dated_by_its_publication_day(data: st.DataObject) -> None:
    count = data.draw(st.integers(1, 40))
    codes = tuple(
        data.draw(
            st.lists(st.text(min_size=1, max_size=6), unique=True, min_size=count, max_size=count)
        )
    )
    gaps = np.array(
        data.draw(st.lists(st.integers(1, 60), min_size=count, max_size=count)), dtype=np.int64
    )
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    published = start + np.cumsum(gaps).astype("timedelta64[D]")
    schedule = iferc_schedule(codes, published)
    as_of = start + np.timedelta64(data.draw(st.integers(-10, 2500)), "D")
    made = calendar(valuation_date(as_of, 0.5), an_index(schedule, None))
    assert np.array_equal(made.dates, published)
    assert made.dates is not schedule.publication_date
    assert made.contract.tolist() == list(range(count))
    assert made.is_priced.all()
    assert np.array_equal(made.is_fixed, published < as_of)
    for column in (made.dates, made.contract, made.is_priced, made.is_fixed):
        assert not column.flags.writeable


# --- the prompt code: the contract of the first unfixed period ----------------------------


# The ticket's examples, each kind's own rule: on a futures calendar the contract prompt on the
# valuation day, the expiring one on its expiry day and the next from the day after; on a Gas
# Daily calendar the month of the day after the valuation day, the next month from a month's
# last day; on an IFERC calendar the first month not yet published, the month itself on its
# publication day. Nothing here is a new rule: it is the row the calendar counted and the
# contract on it, read as the market reads them.
@pytest.mark.parametrize(
    ("schedule", "holidays", "as_of", "code"),
    [
        (SCHEDULE, CLOSED_MAY_25, "2026-06-22", "n26"),
        (SCHEDULE, CLOSED_MAY_25, "2026-06-23", "q26"),
        (SCHEDULE, CLOSED_MAY_25, "2026-05-23", "n26"),
        (SCHEDULE, CLOSED_MAY_25, "2026-05-25", "n26"),
        (SCHEDULE, CLOSED_MAY_25, "2026-05-01", "n26"),
        (SCHEDULE, CLOSED_MAY_25, "2026-05-19", "n26"),
        (SCHEDULE, CLOSED_MAY_25, "2026-07-21", "q26"),
        (GAS_DAILY, None, "2026-09-18", "U26"),
        (GAS_DAILY, None, "2026-09-30", "V26"),
        (GAS_DAILY, None, "2026-10-31", "X26"),
        (GAS_DAILY, None, "2026-11-29", "X26"),
        (GAS_DAILY, None, "2026-08-15", "U26"),
        (
            an_iferc_schedule(("U26", "2026-09-01"), ("V26", "2026-10-01")),
            None,
            "2026-09-01",
            "U26",
        ),
        (
            an_iferc_schedule(("U26", "2026-09-01"), ("V26", "2026-10-01")),
            None,
            "2026-09-02",
            "V26",
        ),
        (IFERC, None, "2026-11-15", "Z26"),
        (IFERC, None, "2026-11-02", "X26"),
        (IFERC, None, "2026-12-01", "Z26"),
        (IFERC, None, "2026-09-15", "V26"),
    ],
    ids=[
        "futures, the expiry day: the expiring contract",
        "futures, the day after the expiry: the next contract",
        "futures, a Saturday: the contract prompt that day, no day skipped",
        "futures, a holiday: the same",
        "futures, before the calendar: its first contract, never the boundary contract",
        "futures, the boundary expiry itself, the day before the calendar: the same",
        "futures, the last day: the last contract",
        "Gas Daily, inside a month: that month",
        "Gas Daily, a month's last day: the next month, the last flow day having fixed",
        "Gas Daily, the second month's last day: the third month",
        "Gas Daily, the day before the last flow day: the last month",
        "Gas Daily, before the calendar: the first month",
        "IFERC, the publication day: the month publishing, not yet fixed",
        "IFERC, the day after publication: the next month",
        "IFERC, two months published: the third",
        "IFERC, the second publication day: the second month",
        "IFERC, the last publication day: the last month",
        "IFERC, before any publication: the first month",
    ],
)
def test_the_prompt_code_is_the_contract_of_the_first_unfixed_period(
    schedule: object, holidays: HolidayCalendar | None, as_of: str, code: str
) -> None:
    made = calendar(valuation_date(day(as_of), 0.5), an_index(schedule, holidays))
    assert made.prompt_code() == code
    assert made.prompt_code() == made.index.schedule.codes[int(made.contract[made.first_unfixed])]


def test_the_fraction_of_the_valuation_day_changes_the_prompt_code_of_no_kind() -> None:
    for schedule, holidays, as_of in (
        (SCHEDULE, CLOSED_MAY_25, "2026-06-22"),
        (GAS_DAILY, None, "2026-09-30"),
        (IFERC, None, "2026-11-02"),
    ):
        codes = {
            calendar(valuation_date(day(as_of), f), an_index(schedule, holidays)).prompt_code()
            for f in (0.0, 0.5, 1.0)
        }
        assert len(codes) == 1


# A calendar whose every period has fixed has no first price to name, and says so in its own
# words; the market over its history says the same of the history.
@pytest.mark.parametrize(
    ("schedule", "holidays", "as_of"),
    [
        (SCHEDULE, CLOSED_MAY_25, "2026-07-22"),
        (GAS_DAILY, None, "2026-11-30"),
        (IFERC, None, "2026-12-02"),
    ],
    ids=[
        "futures, the day after the last expiry",
        "Gas Daily, the last flow day",
        "IFERC, the day after the last publication",
    ],
)
def test_a_calendar_whose_every_period_has_fixed_has_no_prompt_code(
    schedule: object, holidays: HolidayCalendar | None, as_of: str
) -> None:
    made = calendar(valuation_date(day(as_of), 0.5), an_index(schedule, holidays))
    assert made.first_unfixed == made.dates.size
    with pytest.raises(ValueError) as failure:
        made.prompt_code()
    assert str(failure.value) == "calendar has no unfixed period, expected at least one to quote"


# The code comes back as the schedule spells it, whatever the desk typed: a lowercase month, a
# label with a space, a year in full.
def test_the_prompt_code_is_the_schedules_spelling() -> None:
    labels = a_schedule(("front", "2026-05-19"), ("Jul 2026", "2026-06-22"), ("q-26", "2026-07-21"))
    made = calendar(valuation_date(day("2026-06-22"), 0.5), an_index(labels, CLOSED_MAY_25))
    assert made.prompt_code() == "Jul 2026"
    assert (
        calendar(
            valuation_date(day("2026-06-23"), 0.5), an_index(labels, CLOSED_MAY_25)
        ).prompt_code()
        == "q-26"
    )
