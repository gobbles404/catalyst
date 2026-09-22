"""The delivery schedule: three rules of meaning, and the columns retained as typed and aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.index_definitions.delivery_schedule import delivery_schedule

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# The page's sample: the last two contract months of 2026 of one reference index, the codes as
# the desk typed them, and the first and last day each one delivers.
CODES = ("X26", "Z26")
STARTS = dates("2026-11-01", "2026-12-01")
ENDS = dates("2026-11-30", "2026-12-31")


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_and_both_dates_aligned_as_typed() -> None:
    schedule = delivery_schedule(CODES, STARTS, ENDS)
    assert schedule.codes == CODES
    assert np.array_equal(schedule.delivery_start, STARTS)
    assert np.array_equal(schedule.delivery_end, ENDS)
    assert schedule.delivery_start.dtype == np.dtype("datetime64[D]")
    assert schedule.delivery_end.dtype == np.dtype("datetime64[D]")
    assert schedule.delivery_start.ndim == schedule.delivery_end.ndim == 1


def test_a_one_row_schedule_is_a_schedule() -> None:
    schedule = delivery_schedule(CODES[:1], STARTS[:1], ENDS[:1])
    assert schedule.codes == ("X26",)
    assert np.array_equal(schedule.delivery_start, dates("2026-11-01"))
    assert np.array_equal(schedule.delivery_end, dates("2026-11-30"))


# Both days are included, so equal days are a period of one day; and a period is any run of
# calendar days, a week, a fortnight from a Wednesday, a quarter, not only a month.
def test_a_single_day_and_periods_that_are_not_months_are_kept_as_given() -> None:
    codes = ("day", "week", "wed", "quarter")
    starts = dates("2026-12-01", "2026-11-02", "2026-11-11", "2026-10-01")
    ends = dates("2026-12-01", "2026-11-08", "2026-11-24", "2026-12-31")
    schedule = delivery_schedule(codes, starts, ends)
    assert np.array_equal(schedule.delivery_start, starts)
    assert np.array_equal(schedule.delivery_end, ends)


def test_twelve_rows_are_kept_in_their_order() -> None:
    codes = tuple(f"{letter}27" for letter in "FGHJKMNQUVXZ")
    starts = dates(*(f"2027-{month:02d}-01" for month in range(1, 13)))
    ends = dates(*(f"2027-{month:02d}-28" for month in range(1, 13)))
    schedule = delivery_schedule(codes, starts, ends)
    assert schedule.codes == codes
    assert np.array_equal(schedule.delivery_start, starts)
    assert np.array_equal(schedule.delivery_end, ends)


# Codes in either case and a code twice, a period twice, periods that overlap, a gap between
# periods and rows out of order: a reader's rules, written when the reader is. The schedule
# keeps them as given.
def test_nothing_else_is_checked() -> None:
    codes = ("x26", "X26", "X26", "Z26", "V26")
    starts = dates("2026-11-01", "2026-11-01", "2026-11-15", "2026-12-10", "2026-10-01")
    ends = dates("2026-11-30", "2026-11-30", "2026-12-05", "2026-12-31", "2026-10-31")
    schedule = delivery_schedule(codes, starts, ends)
    assert schedule.codes == codes
    assert np.array_equal(schedule.delivery_start, starts)
    assert np.array_equal(schedule.delivery_end, ends)


# --- what is rejected, naming the count or the row ------------------------------


@pytest.mark.parametrize(
    ("codes", "starts", "ends", "message"),
    [
        (
            CODES,
            STARTS[:1],
            ENDS,
            "delivery_start has 1 date, expected 2, one per contract_code",
        ),
        (
            CODES,
            np.append(STARTS, STARTS[:1]),
            ENDS,
            "delivery_start has 3 dates, expected 2, one per contract_code",
        ),
        (
            CODES,
            STARTS,
            ENDS[:1],
            "delivery_end has 1 date, expected 2, one per contract_code",
        ),
        (
            CODES,
            STARTS,
            np.append(ENDS, ENDS[:1]),
            "delivery_end has 3 dates, expected 2, one per contract_code",
        ),
        (
            CODES[:1],
            STARTS,
            ENDS,
            "delivery_start has 2 dates, expected 1, one per contract_code",
        ),
        (
            CODES,
            STARTS[:1],
            ENDS[:1],
            "delivery_start has 1 date, expected 2, one per contract_code",
        ),
        (
            CODES,
            STARTS,
            dates("2026-11-30", "2026-11-30"),
            "delivery_end row 2 is 2026-11-30, "
            "expected a date on or after row 2's delivery_start 2026-12-01",
        ),
        (
            CODES,
            ENDS,
            STARTS,
            "delivery_end row 1 is 2026-11-01, "
            "expected a date on or after row 1's delivery_start 2026-11-30",
        ),
        (
            CODES,
            dates("2026-11-01", "2026-12-02"),
            dates("2026-11-30", "2026-12-01"),
            "delivery_end row 2 is 2026-12-01, "
            "expected a date on or after row 2's delivery_start 2026-12-02",
        ),
        (
            CODES,
            STARTS[:1],
            dates("2026-10-31", "2026-11-30"),
            "delivery_start has 1 date, expected 2, one per contract_code",
        ),
        (
            CODES,
            dates("2026-11-02", "2026-12-01"),
            dates("2026-11-01"),
            "delivery_end has 1 date, expected 2, one per contract_code",
        ),
    ],
    ids=[
        "a start column one row short",
        "a start column one row long",
        "an end column one row short",
        "an end column one row long",
        "two dates for one code",
        "both columns short, the starts named first",
        "an end before its start, the second row",
        "the columns swapped, the first row",
        "the ticket's example, a day before its start",
        "a short start column before an end before its start",
        "a short end column before an end before its start",
    ],
)
def test_a_column_without_one_row_per_code_or_an_end_before_its_start_is_rejected(
    codes: tuple[str, ...],
    starts: NDArray[np.datetime64],
    ends: NDArray[np.datetime64],
    message: str,
) -> None:
    with pytest.raises(ValueError) as failure:
        delivery_schedule(codes, starts, ends)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 400), data=st.data())
def test_any_columns_with_one_row_per_code_and_no_reversed_period_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    codes = tuple(
        data.draw(st.lists(st.text(min_size=1, max_size=8), min_size=count, max_size=count))
    )
    firsts = data.draw(st.lists(st.integers(61, 2958000), min_size=count, max_size=count))
    lengths = data.draw(st.lists(st.integers(0, 400), min_size=count, max_size=count))
    starts = EPOCH + np.array(firsts).astype("timedelta64[D]")
    ends = starts + np.array(lengths).astype("timedelta64[D]")
    schedule = delivery_schedule(codes, starts, ends)
    assert schedule.codes == codes
    assert schedule.delivery_start.size == schedule.delivery_end.size == count
    assert np.array_equal(schedule.delivery_start, starts)
    assert np.array_equal(schedule.delivery_end, ends)
    assert bool(np.all(schedule.delivery_end >= schedule.delivery_start))


# --- ownership ----------------------------------------------------------------


def test_the_schedule_owns_its_dates_and_keeps_the_codes_that_arrived() -> None:
    starts, ends = STARTS.copy(), ENDS.copy()
    schedule = delivery_schedule(CODES, starts, ends)
    starts[0] = np.datetime64("2030-01-01")
    ends[0] = np.datetime64("2030-01-01")
    assert schedule.delivery_start[0] == np.datetime64("2026-11-01")
    assert schedule.delivery_end[0] == np.datetime64("2026-11-30")
    assert not schedule.delivery_start.flags.writeable
    assert not schedule.delivery_end.flags.writeable
    with pytest.raises(ValueError):
        schedule.delivery_start[0] = np.datetime64("2030-01-01")
    with pytest.raises(ValueError):
        schedule.delivery_end[0] = np.datetime64("2030-01-01")
    assert schedule.codes is CODES
