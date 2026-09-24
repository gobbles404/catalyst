"""The Gas Daily schedule: the one rule of meaning, and the columns retained as typed and
aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.index_definitions.gas_daily_schedule import gas_daily_schedule

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# The page's sample: three contract months of Henry Hub Gas Daily, the codes as the desk typed
# them, and the first and last day of gas each month's price covers.
CODES = ("U26", "V26", "X26")
FIRST = dates("2026-09-01", "2026-10-01", "2026-11-01")
LAST = dates("2026-09-30", "2026-10-31", "2026-11-30")


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_and_every_date_aligned_as_typed() -> None:
    schedule = gas_daily_schedule(CODES, FIRST, LAST)
    assert schedule.codes == CODES
    assert np.array_equal(schedule.first_date, FIRST)
    assert np.array_equal(schedule.last_date, LAST)
    assert schedule.first_date.dtype == np.dtype("datetime64[D]")
    assert schedule.last_date.dtype == np.dtype("datetime64[D]")
    assert schedule.first_date.ndim == schedule.last_date.ndim == 1


def test_a_one_row_schedule_is_a_schedule() -> None:
    schedule = gas_daily_schedule(CODES[:1], FIRST[:1], LAST[:1])
    assert schedule.codes == ("U26",)
    assert np.array_equal(schedule.first_date, dates("2026-09-01"))
    assert np.array_equal(schedule.last_date, dates("2026-09-30"))


def test_twelve_months_are_kept_in_their_order() -> None:
    codes = tuple(f"{letter}27" for letter in "FGHJKMNQUVXZ")
    first = dates(*(f"2027-{month:02d}-01" for month in range(1, 13)))
    ends = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    last = dates(*(f"2027-{month:02d}-{end}" for month, end in enumerate(ends, start=1)))
    schedule = gas_daily_schedule(codes, first, last)
    assert schedule.codes == codes
    assert np.array_equal(schedule.first_date, first)
    assert np.array_equal(schedule.last_date, last)
    assert str(schedule.last_date[1]) == "2027-02-28"


# Codes in either case, a code twice, a last day before its first, dates that are not a month's
# bounds, two months sharing a day and months out of order: a reader's rules, written when the
# reader is. The schedule keeps them as given.
def test_nothing_else_is_checked() -> None:
    codes = ("u26", "U26", "U26", "X26")
    first = dates("2026-11-01", "2026-09-15", "2026-09-01", "2026-10-31")
    last = dates("2026-11-30", "2026-09-10", "2026-10-15", "2026-10-31")
    schedule = gas_daily_schedule(codes, first, last)
    assert schedule.codes == codes
    assert np.array_equal(schedule.first_date, first)
    assert np.array_equal(schedule.last_date, last)


# --- what is rejected, naming the count ---------------------------------------


@pytest.mark.parametrize(
    ("codes", "first", "last", "message"),
    [
        (CODES, FIRST[:2], LAST, "first_date has 2 dates, expected 3, one per contract_code"),
        (
            CODES,
            np.append(FIRST, FIRST[:1]),
            LAST,
            "first_date has 4 dates, expected 3, one per contract_code",
        ),
        (CODES, FIRST, LAST[:2], "last_date has 2 dates, expected 3, one per contract_code"),
        (
            CODES,
            FIRST,
            np.append(LAST, LAST[:1]),
            "last_date has 4 dates, expected 3, one per contract_code",
        ),
        (CODES, FIRST[:1], LAST, "first_date has 1 date, expected 3, one per contract_code"),
        (CODES, FIRST, LAST[:1], "last_date has 1 date, expected 3, one per contract_code"),
        (CODES[:1], FIRST, LAST[:1], "first_date has 3 dates, expected 1, one per contract_code"),
        (CODES, FIRST[:2], LAST[:1], "first_date has 2 dates, expected 3, one per contract_code"),
    ],
    ids=[
        "a first-date column one row short",
        "a first-date column one row long",
        "a last-date column one row short",
        "a last-date column one row long",
        "one first date for three codes",
        "one last date for three codes",
        "three first dates for one code",
        "both columns wrong, the first dates named first",
    ],
)
def test_a_column_without_one_row_per_code_is_rejected(
    codes: tuple[str, ...],
    first: NDArray[np.datetime64],
    last: NDArray[np.datetime64],
    message: str,
) -> None:
    with pytest.raises(ValueError) as failure:
        gas_daily_schedule(codes, first, last)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 400), data=st.data())
def test_any_columns_with_one_row_per_code_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    codes = tuple(
        data.draw(st.lists(st.text(min_size=1, max_size=8), min_size=count, max_size=count))
    )
    serials = st.lists(st.integers(61, 2958465), min_size=count, max_size=count)
    first = EPOCH + np.array(data.draw(serials)).astype("timedelta64[D]")
    last = EPOCH + np.array(data.draw(serials)).astype("timedelta64[D]")
    schedule = gas_daily_schedule(codes, first, last)
    assert schedule.codes == codes
    assert schedule.first_date.size == schedule.last_date.size == count
    assert np.array_equal(schedule.first_date, first)
    assert np.array_equal(schedule.last_date, last)


# --- ownership ----------------------------------------------------------------


def test_the_schedule_owns_its_dates_and_keeps_the_codes_that_arrived() -> None:
    first, last = FIRST.copy(), LAST.copy()
    schedule = gas_daily_schedule(CODES, first, last)
    first[0] = np.datetime64("2030-01-01")
    last[0] = np.datetime64("2030-01-01")
    assert schedule.first_date[0] == np.datetime64("2026-09-01")
    assert schedule.last_date[0] == np.datetime64("2026-09-30")
    assert not schedule.first_date.flags.writeable
    assert not schedule.last_date.flags.writeable
    with pytest.raises(ValueError):
        schedule.first_date[0] = np.datetime64("2030-01-01")
    with pytest.raises(ValueError):
        schedule.last_date[0] = np.datetime64("2030-01-01")
    assert schedule.codes is CODES
