"""The IFERC schedule: the one rule of meaning, and the columns retained as typed and aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.index_definitions.iferc_schedule import iferc_schedule

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# The page's sample: three contract months of the Waha basis, the codes as the desk typed them,
# the day each month's future stops trading and the day its index is published.
CODES = ("V26", "X26", "Z26")
LAST_TRADING = dates("2026-09-30", "2026-10-30", "2026-11-30")
PUBLICATIONS = dates("2026-10-01", "2026-11-02", "2026-12-01")


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_and_every_date_aligned_as_typed() -> None:
    schedule = iferc_schedule(CODES, LAST_TRADING, PUBLICATIONS)
    assert schedule.codes == CODES
    assert np.array_equal(schedule.last_trading_date, LAST_TRADING)
    assert np.array_equal(schedule.publication_date, PUBLICATIONS)
    assert schedule.last_trading_date.dtype == np.dtype("datetime64[D]")
    assert schedule.publication_date.dtype == np.dtype("datetime64[D]")
    assert schedule.last_trading_date.ndim == schedule.publication_date.ndim == 1


def test_a_one_row_schedule_is_a_schedule() -> None:
    schedule = iferc_schedule(CODES[:1], LAST_TRADING[:1], PUBLICATIONS[:1])
    assert schedule.codes == ("V26",)
    assert np.array_equal(schedule.last_trading_date, dates("2026-09-30"))
    assert np.array_equal(schedule.publication_date, dates("2026-10-01"))


def test_twelve_months_are_kept_in_their_order() -> None:
    codes = tuple(f"{letter}27" for letter in "FGHJKMNQUVXZ")
    last_trading = dates(
        *("2026-12-31" if m == 1 else f"2027-{m - 1:02d}-28" for m in range(1, 13))
    )
    published = dates(*(f"2027-{month:02d}-01" for month in range(1, 13)))
    schedule = iferc_schedule(codes, last_trading, published)
    assert schedule.codes == codes
    assert np.array_equal(schedule.last_trading_date, last_trading)
    assert np.array_equal(schedule.publication_date, published)


# Codes in either case, a code twice, dates out of order, two months sharing a date and an
# index published before its future stops trading: a reader's rules, written when the reader
# is. The schedule keeps them as given.
def test_nothing_else_is_checked() -> None:
    codes = ("v26", "V26", "V26", "Z26")
    last_trading = dates("2026-11-30", "2026-09-30", "2026-09-30", "2026-10-30")
    published = dates("2026-11-02", "2026-10-01", "2026-10-01", "2026-10-01")
    schedule = iferc_schedule(codes, last_trading, published)
    assert schedule.codes == codes
    assert np.array_equal(schedule.last_trading_date, last_trading)
    assert np.array_equal(schedule.publication_date, published)


# --- what is rejected, naming the count ---------------------------------------


@pytest.mark.parametrize(
    ("codes", "last_trading", "published", "message"),
    [
        (
            CODES,
            LAST_TRADING[:2],
            PUBLICATIONS,
            "last_trading_date has 2 dates, expected 3, one per contract_code",
        ),
        (
            CODES,
            np.append(LAST_TRADING, LAST_TRADING[:1]),
            PUBLICATIONS,
            "last_trading_date has 4 dates, expected 3, one per contract_code",
        ),
        (
            CODES,
            LAST_TRADING,
            PUBLICATIONS[:2],
            "publication_date has 2 dates, expected 3, one per contract_code",
        ),
        (
            CODES,
            LAST_TRADING,
            np.append(PUBLICATIONS, PUBLICATIONS[:1]),
            "publication_date has 4 dates, expected 3, one per contract_code",
        ),
        (
            CODES,
            LAST_TRADING[:1],
            PUBLICATIONS,
            "last_trading_date has 1 date, expected 3, one per contract_code",
        ),
        (
            CODES,
            LAST_TRADING,
            PUBLICATIONS[:1],
            "publication_date has 1 date, expected 3, one per contract_code",
        ),
        (
            CODES[:1],
            LAST_TRADING,
            PUBLICATIONS[:1],
            "last_trading_date has 3 dates, expected 1, one per contract_code",
        ),
        (
            CODES,
            LAST_TRADING[:2],
            PUBLICATIONS[:1],
            "last_trading_date has 2 dates, expected 3, one per contract_code",
        ),
    ],
    ids=[
        "a last trading column one row short",
        "a last trading column one row long",
        "a publication column one row short",
        "a publication column one row long",
        "one last trading date for three codes",
        "one publication date for three codes",
        "three last trading dates for one code",
        "both columns wrong, the last trading dates named first",
    ],
)
def test_a_column_without_one_row_per_code_is_rejected(
    codes: tuple[str, ...],
    last_trading: NDArray[np.datetime64],
    published: NDArray[np.datetime64],
    message: str,
) -> None:
    with pytest.raises(ValueError) as failure:
        iferc_schedule(codes, last_trading, published)
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
    last_trading = EPOCH + np.array(data.draw(serials)).astype("timedelta64[D]")
    published = EPOCH + np.array(data.draw(serials)).astype("timedelta64[D]")
    schedule = iferc_schedule(codes, last_trading, published)
    assert schedule.codes == codes
    assert schedule.last_trading_date.size == schedule.publication_date.size == count
    assert np.array_equal(schedule.last_trading_date, last_trading)
    assert np.array_equal(schedule.publication_date, published)


# --- ownership ----------------------------------------------------------------


def test_the_schedule_owns_its_dates_and_keeps_the_codes_that_arrived() -> None:
    last_trading, published = LAST_TRADING.copy(), PUBLICATIONS.copy()
    schedule = iferc_schedule(CODES, last_trading, published)
    last_trading[0] = np.datetime64("2030-01-01")
    published[0] = np.datetime64("2030-01-01")
    assert schedule.last_trading_date[0] == np.datetime64("2026-09-30")
    assert schedule.publication_date[0] == np.datetime64("2026-10-01")
    assert not schedule.last_trading_date.flags.writeable
    assert not schedule.publication_date.flags.writeable
    with pytest.raises(ValueError):
        schedule.last_trading_date[0] = np.datetime64("2030-01-01")
    with pytest.raises(ValueError):
        schedule.publication_date[0] = np.datetime64("2030-01-01")
    assert schedule.codes is CODES
