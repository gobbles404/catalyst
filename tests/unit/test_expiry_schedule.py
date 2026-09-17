"""The expiry schedule: the one rule of meaning, and the columns retained as typed and aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.index_definitions.expiry_schedule import expiry_schedule

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# The page's sample: six contracts of one index, the codes as the desk typed them.
CODES = ("m26", "n26", "q26", "u26", "V26", "X26")
FUTURES = dates("2026-05-19", "2026-06-22", "2026-07-21", "2026-08-20", "2026-09-22", "2026-10-20")
OPTIONS = dates("2026-05-14", "2026-06-16", "2026-07-16", "2026-08-17", "2026-09-17", "2026-10-15")


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_and_both_dates_aligned_as_typed() -> None:
    schedule = expiry_schedule(CODES, FUTURES, OPTIONS)
    assert schedule.codes == CODES
    assert np.array_equal(schedule.future_expiry, FUTURES)
    assert schedule.option_expiry is not None
    assert np.array_equal(schedule.option_expiry, OPTIONS)
    assert schedule.future_expiry.dtype == np.dtype("datetime64[D]")
    assert schedule.option_expiry.dtype == np.dtype("datetime64[D]")


def test_an_index_without_options_keeps_the_codes_and_the_futures_and_no_options() -> None:
    schedule = expiry_schedule(CODES, FUTURES, None)
    assert schedule.codes == CODES
    assert np.array_equal(schedule.future_expiry, FUTURES)
    assert schedule.option_expiry is None


def test_a_one_row_schedule_is_a_schedule() -> None:
    schedule = expiry_schedule(CODES[:1], FUTURES[:1], OPTIONS[:1])
    assert schedule.codes == ("m26",)
    assert np.array_equal(schedule.future_expiry, FUTURES[:1])
    assert schedule.option_expiry is not None
    assert np.array_equal(schedule.option_expiry, OPTIONS[:1])


# Repeated codes, dates out of order, an option expiring after its future: a reader's rules,
# written when the reader is. The schedule keeps them as given.
def test_nothing_else_is_checked() -> None:
    codes = ("m26", "m26", "f26")
    futures = dates("2026-10-20", "2026-05-19", "2026-05-19")
    options = dates("2026-10-25", "2026-05-14", "2026-05-14")
    schedule = expiry_schedule(codes, futures, options)
    assert schedule.codes == codes
    assert np.array_equal(schedule.future_expiry, futures)
    assert schedule.option_expiry is not None
    assert np.array_equal(schedule.option_expiry, options)


# --- what is rejected, naming the count ---------------------------------------


@pytest.mark.parametrize(
    ("futures", "options", "message"),
    [
        (FUTURES[:5], OPTIONS, "future_expiry has 5 dates, expected 6, one per future_code"),
        (
            FUTURES,
            np.append(OPTIONS, OPTIONS[:1]),
            "option_expiry has 7 dates, expected 6, one per future_code",
        ),
        (FUTURES[:1], OPTIONS, "future_expiry has 1 date, expected 6, one per future_code"),
        (FUTURES[:5], OPTIONS[:4], "future_expiry has 5 dates, expected 6, one per future_code"),
    ],
    ids=[
        "a futures column one row short",
        "an options column one row long",
        "one date for six codes",
        "both wrong, the futures column named first",
    ],
)
def test_a_column_without_one_row_per_code_is_rejected(
    futures: NDArray[np.datetime64], options: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        expiry_schedule(CODES, futures, options)
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
    futures = EPOCH + np.array(data.draw(serials)).astype("timedelta64[D]")
    options = EPOCH + np.array(data.draw(serials)).astype("timedelta64[D]")
    schedule = expiry_schedule(codes, futures, options)
    assert schedule.codes == codes
    assert schedule.option_expiry is not None
    assert schedule.future_expiry.size == schedule.option_expiry.size == count
    assert np.array_equal(schedule.future_expiry, futures)
    assert np.array_equal(schedule.option_expiry, options)


# --- ownership ----------------------------------------------------------------


def test_the_schedule_owns_its_dates() -> None:
    futures, options = FUTURES.copy(), OPTIONS.copy()
    schedule = expiry_schedule(CODES, futures, options)
    futures[0] = np.datetime64("2030-01-01")
    options[0] = np.datetime64("2030-01-01")
    assert schedule.future_expiry[0] == np.datetime64("2026-05-19")
    assert schedule.option_expiry is not None
    assert schedule.option_expiry[0] == np.datetime64("2026-05-14")
    assert not schedule.future_expiry.flags.writeable
    assert not schedule.option_expiry.flags.writeable
    with pytest.raises(ValueError):
        schedule.future_expiry[0] = np.datetime64("2030-01-01")
