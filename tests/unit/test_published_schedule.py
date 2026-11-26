"""The published schedule: its three rules of meaning, the months read off the rows where the
code changes, each print's month and the dates retained."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.index_definitions.published_schedule import published_schedule

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# The page's sample: the four weekly prints of September 2026, each dated its Monday and counted
# toward the one month, with the last print of August above them and the first of October below.
CODES = ("Q26", "U26", "U26", "U26", "U26", "V26")
PUBLICATIONS = dates(
    "2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"
)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_each_month_once_and_every_print_on_its_month() -> None:
    schedule = published_schedule(CODES, PUBLICATIONS)
    assert schedule.codes == ("Q26", "U26", "V26")
    assert schedule.contract.tolist() == [0, 1, 1, 1, 1, 2]
    assert schedule.contract.dtype == np.dtype(np.intp)
    assert np.array_equal(schedule.publication_date, PUBLICATIONS)
    assert schedule.publication_date.dtype == np.dtype("datetime64[D]")
    assert schedule.publication_date.ndim == 1


def test_a_one_row_schedule_is_a_schedule_of_one_month() -> None:
    schedule = published_schedule(CODES[:1], PUBLICATIONS[:1])
    assert schedule.codes == ("Q26",)
    assert schedule.contract.tolist() == [0]
    assert np.array_equal(schedule.publication_date, dates("2026-08-31"))


# One print a month is the IFERC shape: every row its own month.
def test_one_print_a_month_is_a_month_per_row() -> None:
    codes = tuple(f"{letter}27" for letter in "FGHJKMNQUVXZ")
    published = dates(*(f"2027-{month:02d}-01" for month in range(1, 13)))
    schedule = published_schedule(codes, published)
    assert schedule.codes == codes
    assert schedule.contract.tolist() == list(range(12))


# A month is the code on the row, never the date beside it: a print dated the last day of
# November counts toward December when its row says so, and four or five prints are a month
# alike.
def test_a_prints_month_is_the_code_on_its_row_and_never_its_date() -> None:
    codes = ("X26", "X26", "X26", "X26", "Z26", "Z26")
    published = dates(
        "2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23", "2026-11-30", "2026-12-07"
    )
    schedule = published_schedule(codes, published)
    assert schedule.codes == ("X26", "Z26")
    assert schedule.contract.tolist() == [0, 0, 0, 0, 1, 1]


# Codes are compared as typed: another case is another month, and no code is read for anything.
def test_codes_are_compared_as_typed_and_read_for_nothing() -> None:
    schedule = published_schedule(
        ("u26", "U26", "not a month"), dates("2026-09-07", "2026-09-14", "2026-09-21")
    )
    assert schedule.codes == ("u26", "U26", "not a month")
    assert schedule.contract.tolist() == [0, 1, 2]


def test_a_schedule_of_no_rows_is_a_schedule_of_no_months() -> None:
    schedule = published_schedule((), dates())
    assert schedule.codes == ()
    assert schedule.contract.size == 0 and schedule.publication_date.size == 0


# --- what is refused, in the order the rules run ------------------------------


@pytest.mark.parametrize(
    ("codes", "published", "message"),
    [
        (
            CODES,
            PUBLICATIONS[:5],
            "publication_date has 5 dates, expected 6, one per contract_code",
        ),
        (
            CODES,
            np.append(PUBLICATIONS, dates("2026-10-12")),
            "publication_date has 7 dates, expected 6, one per contract_code",
        ),
        (
            CODES[:3],
            PUBLICATIONS[:1],
            "publication_date has 1 date, expected 3, one per contract_code",
        ),
        (
            CODES[:1],
            PUBLICATIONS[:3],
            "publication_date has 3 dates, expected 1, one per contract_code",
        ),
    ],
    ids=[
        "a publication column one row short",
        "a publication column one row long",
        "one publication date for three codes",
        "three publication dates for one code",
    ],
)
def test_a_column_without_one_date_per_code_is_refused(
    codes: tuple[str, ...], published: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        published_schedule(codes, published)
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("codes", "message"),
    [
        (
            ("U26", "V26", "U26"),
            "contract_code row 3 is 'U26', a month whose prints ended at row 1, expected each "
            "month's prints in consecutive rows",
        ),
        (
            ("U26", "U26", "V26", "V26", "U26", "U26"),
            "contract_code row 5 is 'U26', a month whose prints ended at row 2, expected each "
            "month's prints in consecutive rows",
        ),
        (
            ("Q26", "U26", "V26", "X26", "V26", "Q26"),
            "contract_code row 5 is 'V26', a month whose prints ended at row 3, expected each "
            "month's prints in consecutive rows",
        ),
    ],
    ids=[
        "a month returns after one other",
        "a month of two prints returns, named at its first row back",
        "two months return: the first from the top is named",
    ],
)
def test_a_month_whose_code_returns_after_another_began_is_refused(
    codes: tuple[str, ...], message: str
) -> None:
    published = EPOCH + np.arange(40_000, 40_000 + len(codes)).astype("timedelta64[D]")
    with pytest.raises(ValueError) as failure:
        published_schedule(codes, published)
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("published", "message"),
    [
        (
            dates("2026-09-07", "2026-09-07", "2026-09-21"),
            "publication_date row 2 is 2026-09-07, expected a date after row 1's 2026-09-07",
        ),
        (
            dates("2026-09-07", "2026-09-21", "2026-09-14"),
            "publication_date row 3 is 2026-09-14, expected a date after row 2's 2026-09-21",
        ),
        (
            dates("2026-09-21", "2026-09-14", "2026-09-07"),
            "publication_date row 2 is 2026-09-14, expected a date after row 1's 2026-09-21",
        ),
    ],
    ids=[
        "a date listed twice",
        "a date before the one above",
        "a schedule pasted newest first fails at its second row",
    ],
)
def test_a_date_that_is_not_after_the_one_above_is_refused(
    published: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        published_schedule(("U26", "U26", "U26"), published)
    assert str(failure.value) == message


# The rules run in one order, the count, then the months, then the dates, so a schedule that
# breaks two is told of the earlier.
def test_the_months_are_checked_before_the_dates_and_the_count_before_both() -> None:
    backwards = dates("2026-09-14", "2026-09-07", "2026-09-01")
    with pytest.raises(ValueError) as months:
        published_schedule(("U26", "V26", "U26"), backwards)
    assert str(months.value).startswith("contract_code row 3 is 'U26'")
    with pytest.raises(ValueError) as count:
        published_schedule(("U26", "V26", "U26"), backwards[:2])
    assert str(count.value) == "publication_date has 2 dates, expected 3, one per contract_code"


# --- the general rules --------------------------------------------------------


@given(data=st.data())
def test_any_months_of_prints_in_date_order_are_kept_print_by_print(data: st.DataObject) -> None:
    months = data.draw(st.integers(1, 40))
    codes = data.draw(
        st.lists(st.text(min_size=1, max_size=6), unique=True, min_size=months, max_size=months)
    )
    prints = data.draw(st.lists(st.integers(1, 6), min_size=months, max_size=months))
    gaps = data.draw(st.lists(st.integers(1, 40), min_size=sum(prints), max_size=sum(prints)))
    by_print = tuple(code for code, count in zip(codes, prints, strict=True) for _ in range(count))
    published = EPOCH + np.cumsum(np.array(gaps) + 60).astype("timedelta64[D]")
    schedule = published_schedule(by_print, published)
    assert schedule.codes == tuple(codes)
    assert tuple(schedule.codes[int(row)] for row in schedule.contract) == by_print
    assert np.bincount(schedule.contract, minlength=months).tolist() == prints
    assert np.array_equal(schedule.publication_date, published)
    assert np.all(np.diff(schedule.contract) >= 0)


@given(data=st.data())
def test_any_code_that_returns_is_refused_at_the_row_it_returns(data: st.DataObject) -> None:
    months = data.draw(st.integers(2, 12))
    codes = data.draw(
        st.lists(st.text(min_size=1, max_size=4), unique=True, min_size=months, max_size=months)
    )
    again = data.draw(st.integers(0, months - 2))
    by_print = (*codes, codes[again])
    published = EPOCH + np.arange(40_000, 40_000 + len(by_print)).astype("timedelta64[D]")
    with pytest.raises(ValueError) as failure:
        published_schedule(by_print, published)
    assert str(failure.value) == (
        f"contract_code row {months + 1} is {codes[again]!r}, a month whose prints ended at row "
        f"{again + 1}, expected each month's prints in consecutive rows"
    )


# --- ownership ----------------------------------------------------------------


def test_the_schedule_owns_its_two_arrays_and_keeps_the_texts_that_arrived() -> None:
    published = PUBLICATIONS.copy()
    schedule = published_schedule(CODES, published)
    published[0] = np.datetime64("2030-01-01")
    assert schedule.publication_date[0] == np.datetime64("2026-08-31")
    for column in (schedule.publication_date, schedule.contract):
        assert not column.flags.writeable
    with pytest.raises(ValueError):
        schedule.publication_date[0] = np.datetime64("2030-01-01")
    with pytest.raises(ValueError):
        schedule.contract[0] = 2
    assert schedule.codes[1] is CODES[1]
