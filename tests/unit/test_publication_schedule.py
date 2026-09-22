"""The publication schedule: the one rule of meaning, and the columns retained as typed and
aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.index_definitions.publication_schedule import publication_schedule

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# The page's sample: the last two contract months of 2026 of one reference index, the codes as
# the desk typed them, and the day each month's reference price is published.
CODES = ("X26", "Z26")
PUBLICATIONS = dates("2026-11-02", "2026-12-01")


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_and_every_date_aligned_as_typed() -> None:
    schedule = publication_schedule(CODES, PUBLICATIONS)
    assert schedule.codes == CODES
    assert np.array_equal(schedule.publication_date, PUBLICATIONS)
    assert schedule.publication_date.dtype == np.dtype("datetime64[D]")
    assert schedule.publication_date.ndim == 1


def test_a_one_row_schedule_is_a_schedule() -> None:
    schedule = publication_schedule(CODES[:1], PUBLICATIONS[:1])
    assert schedule.codes == ("X26",)
    assert np.array_equal(schedule.publication_date, dates("2026-11-02"))


def test_twelve_rows_are_kept_in_their_order() -> None:
    codes = tuple(f"{letter}27" for letter in "FGHJKMNQUVXZ")
    published = dates(*(f"2027-{month:02d}-01" for month in range(1, 13)))
    schedule = publication_schedule(codes, published)
    assert schedule.codes == codes
    assert np.array_equal(schedule.publication_date, published)


# Codes in either case, a code twice, a date twice and dates out of order: a reader's rules,
# written when the reader is. The schedule keeps them as given.
def test_nothing_else_is_checked() -> None:
    codes = ("x26", "X26", "X26", "Z26")
    published = dates("2026-12-01", "2026-11-02", "2026-11-02", "2026-10-01")
    schedule = publication_schedule(codes, published)
    assert schedule.codes == codes
    assert np.array_equal(schedule.publication_date, published)


# --- what is rejected, naming the count ---------------------------------------


@pytest.mark.parametrize(
    ("codes", "published", "message"),
    [
        (
            CODES,
            PUBLICATIONS[:1],
            "publication_date has 1 date, expected 2, one per contract_code",
        ),
        (
            CODES,
            np.append(PUBLICATIONS, PUBLICATIONS[:1]),
            "publication_date has 3 dates, expected 2, one per contract_code",
        ),
        (
            CODES[:1],
            PUBLICATIONS,
            "publication_date has 2 dates, expected 1, one per contract_code",
        ),
        (
            ("F27", "G27", "H27"),
            PUBLICATIONS[:1],
            "publication_date has 1 date, expected 3, one per contract_code",
        ),
    ],
    ids=[
        "one date for two codes",
        "three dates for two codes",
        "two dates for one code",
        "one date for three codes",
    ],
)
def test_a_column_without_one_row_per_code_is_rejected(
    codes: tuple[str, ...], published: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        publication_schedule(codes, published)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 400), data=st.data())
def test_any_columns_with_one_row_per_code_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    codes = tuple(
        data.draw(st.lists(st.text(min_size=1, max_size=8), min_size=count, max_size=count))
    )
    serials = data.draw(st.lists(st.integers(61, 2958465), min_size=count, max_size=count))
    published = EPOCH + np.array(serials).astype("timedelta64[D]")
    schedule = publication_schedule(codes, published)
    assert schedule.codes == codes
    assert schedule.publication_date.size == count
    assert np.array_equal(schedule.publication_date, published)


# --- ownership ----------------------------------------------------------------


def test_the_schedule_owns_its_dates_and_keeps_the_codes_that_arrived() -> None:
    published = PUBLICATIONS.copy()
    schedule = publication_schedule(CODES, published)
    published[0] = np.datetime64("2030-01-01")
    assert schedule.publication_date[0] == np.datetime64("2026-11-02")
    assert not schedule.publication_date.flags.writeable
    with pytest.raises(ValueError):
        schedule.publication_date[0] = np.datetime64("2030-01-01")
    assert schedule.codes is CODES
