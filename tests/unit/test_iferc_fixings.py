"""The IFERC fixings: a series given newest first and kept oldest first, the six rules of meaning
on the rows as the sheet gave them, the codes and prices retained and aligned, and the index
kept."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.gas_daily_schedule import gas_daily_schedule
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.index_definitions.iferc_schedule import IfercSchedule, iferc_schedule
from catalyst.index_definitions.index import Index, index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.market_data.iferc_fixings import iferc_fixings


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def prices(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


CONVENTIONS = index_conventions("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS)
SPECIFICATIONS = contract_specifications(
    ("ICE",), np.array([2500.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
)


def an_index(schedule: object, name: str = "Waha IFERC") -> Index:
    """The index of that schedule with one set of conventions and specifications throughout,
    since nothing here reads either, and no holiday calendar, as an IFERC or a Gas Daily index
    has none."""
    return index(name, f"{name} index", schedule, CONVENTIONS, SPECIFICATIONS, None, None, UNITS)


# The page's sample: Waha IFERC, the first four months of 2026, the codes as the desk keeps
# them, the newest month in the first row, and an illustrative index beside each, over the index
# of those four months and Platts' publication days, January's index having printed on the 5th.
# The schedule runs the other way, as schedules do, the oldest first, and so do the columns the
# fixings keep.
CODES = ("J26", "H26", "G26", "F26")
PRICES = prices(1.60, 1.95, 2.10, 1.85)
KEPT_CODES = ("F26", "G26", "H26", "J26")
KEPT_PRICES = prices(1.85, 2.10, 1.95, 1.60)
SCHEDULE = iferc_schedule(KEPT_CODES, dates("2026-01-05", "2026-02-02", "2026-03-02", "2026-04-01"))
INDEX = an_index(SCHEDULE)
FUTURES_INDEX = index(
    "WTI NYMEX",
    "West Texas Intermediate crude oil - NYMEX",
    futures_schedule(("m26", "n26"), dates("2026-05-19", "2026-06-22"), None),
    CONVENTIONS,
    SPECIFICATIONS,
    holiday_calendar(dates("2026-05-25")),
    None,
    UNITS,
)
GAS_DAILY_INDEX = an_index(
    gas_daily_schedule(("U26",), dates("2026-09-01"), dates("2026-09-30")), "Henry Hub Gas Daily"
)


def months_of(*codes: str) -> Index:
    """An IFERC index whose schedule holds exactly those months in that order, each published a
    day after the one before, so that a series over it runs the other way."""
    published = np.datetime64("2027-01-04", "D") + np.arange(len(codes)).astype("timedelta64[D]")
    return an_index(iferc_schedule(codes, published))


def scheduled(*months: tuple[str, str]) -> Index:
    """An IFERC index whose schedule holds those months as given, each a code and the day its
    index prints, in that row order whatever the days say."""
    codes = tuple(code for code, _ in months)
    published = dates(*(day for _, day in months))
    return an_index(iferc_schedule(codes, published))


# --- what is kept -------------------------------------------------------------


def test_the_sample_is_kept_oldest_first_with_every_price_beside_its_code_and_the_index() -> None:
    fixings = iferc_fixings(CODES, PRICES, INDEX)
    assert fixings.codes == KEPT_CODES
    assert np.array_equal(fixings.prices, KEPT_PRICES)
    assert fixings.prices.dtype == np.dtype(np.float64)
    assert fixings.prices.ndim == 1
    assert fixings.index is INDEX


def test_the_fixings_of_one_month_are_a_series() -> None:
    fixings = iferc_fixings(CODES[:1], PRICES[:1], INDEX)
    assert fixings.codes == ("J26",)
    assert np.array_equal(fixings.prices, prices(1.60))


# Twelve months given newest first, December down to January, over a schedule that runs January
# to December: kept the other way up, in the schedule's order, each price still beside its code.
def test_twelve_months_given_newest_first_are_kept_the_other_way_up() -> None:
    schedule_order = tuple(f"{letter}27" for letter in "FGHJKMNQUVXZ")
    given_prices = prices(*(2.0 + 0.1 * i for i in range(12)))
    fixings = iferc_fixings(schedule_order[::-1], given_prices, months_of(*schedule_order))
    assert fixings.codes == schedule_order
    assert fixings.codes[0] == "F27" and fixings.codes[-1] == "Z27"
    assert np.array_equal(fixings.prices, given_prices[::-1])
    assert dict(zip(fixings.codes, fixings.prices.tolist(), strict=True)) == dict(
        zip(schedule_order[::-1], given_prices.tolist(), strict=True)
    )


def test_a_price_below_zero_and_a_zero_are_kept_as_given() -> None:
    fixings = iferc_fixings(CODES[:3], prices(-1.25, 0.0, 1.95), INDEX)
    assert fixings.codes == ("G26", "H26", "J26")
    assert np.array_equal(fixings.prices, prices(1.95, 0.0, -1.25))


# A month left out: whether a month's index has printed by a given day and whether every
# published month has its index are the history's rules. The fixings keep what was given, the
# months still newest first and so still kept the other way up.
def test_a_month_left_out_is_the_historys_concern() -> None:
    fixings = iferc_fixings(("J26", "G26", "F26"), prices(1.60, 2.10, 1.85), INDEX)
    assert fixings.codes == ("F26", "G26", "J26")
    assert np.array_equal(fixings.prices, prices(1.85, 2.10, 1.60))


# The library's own callers make the fixings of no months, for a calendar with nothing published.
def test_a_series_of_no_rows_is_fixings_of_no_rows() -> None:
    fixings = iferc_fixings((), prices(), INDEX)
    assert fixings.codes == ()
    assert fixings.prices.size == 0 and fixings.prices.dtype == np.dtype(np.float64)
    assert not fixings.prices.flags.writeable
    assert fixings.index is INDEX


# The order is read from the publication days the schedule holds beside the months, and from
# nothing else: not from the codes' spelling, which runs the other way across a year's end, and
# not from the months' rows in the schedule, which a calendar would refuse but a fixing does not
# read.
def test_the_order_is_the_publication_days_not_the_codes_or_the_rows() -> None:
    year_end = scheduled(("Z26", "2026-12-01"), ("F27", "2027-01-04"))
    fixings = iferc_fixings(("F27", "Z26"), prices(3.1, 2.9), year_end)
    assert fixings.codes == ("Z26", "F27") and fixings.prices.tolist() == [2.9, 3.1]
    with pytest.raises(ValueError) as failure:
        iferc_fixings(("Z26", "F27"), prices(2.9, 3.1), year_end)
    assert str(failure.value) == (
        "contract_code row 2 is 'F27', published 2027-01-04, "
        "expected a month published before row 1's 'Z26', published 2026-12-01"
    )
    rows_backwards = scheduled(("later", "2027-02-01"), ("earlier", "2027-01-04"))
    fixings = iferc_fixings(("later", "earlier"), prices(2.0, 1.0), rows_backwards)
    assert fixings.codes == ("earlier", "later") and fixings.prices.tolist() == [1.0, 2.0]
    with pytest.raises(ValueError) as failure:
        iferc_fixings(("earlier", "later"), prices(1.0, 2.0), rows_backwards)
    assert str(failure.value) == (
        "contract_code row 2 is 'later', published 2027-02-01, "
        "expected a month published before row 1's 'earlier', published 2027-01-04"
    )


# --- what is rejected ---------------------------------------------------------


# The kind is the first rule: a count the columns would refuse is not reached.
def test_an_index_of_another_kind_is_refused_before_the_columns_are_looked_at() -> None:
    for other, what in ((FUTURES_INDEX, "a futures index"), (GAS_DAILY_INDEX, "a Gas Daily index")):
        with pytest.raises(ValueError) as failure:
            iferc_fixings(CODES, PRICES[:3], other)
        assert str(failure.value) == f"index is {what}, expected an IFERC index"


@pytest.mark.parametrize(
    ("codes", "given_prices", "message"),
    [
        (CODES, PRICES[:3], "price has 3 prices, expected 4, one per contract_code"),
        (
            CODES,
            np.append(PRICES, 1.5),
            "price has 5 prices, expected 4, one per contract_code",
        ),
        (CODES, PRICES[:1], "price has 1 price, expected 4, one per contract_code"),
        (CODES[:1], PRICES, "price has 4 prices, expected 1, one per contract_code"),
        (
            ("K26", "G26"),
            PRICES[:2],
            "contract_code row 1 is 'K26', expected one of the index's months",
        ),
        (
            ("J26", "H26", "K26"),
            PRICES[:3],
            "contract_code row 3 is 'K26', expected one of the index's months",
        ),
        (
            ("J26", "K26", "G26"),
            PRICES[:3],
            "contract_code row 2 is 'K26', expected one of the index's months",
        ),
        (
            ("f26",),
            PRICES[:1],
            "contract_code row 1 is 'f26', expected one of the index's months",
        ),
        (
            ("J26", "H26", "H26", "F26"),
            PRICES,
            "contract_code row 3 is 'H26', already given at row 2",
        ),
        (
            ("F26", "F26", "F26"),
            PRICES[:3],
            "contract_code row 2 is 'F26', already given at row 1",
        ),
        (
            ("J26", "K26", "J26"),
            PRICES[:3],
            "contract_code row 2 is 'K26', expected one of the index's months",
        ),
        (
            ("J26", "J26", "K26"),
            PRICES[:3],
            "contract_code row 2 is 'J26', already given at row 1",
        ),
        (
            ("J26", "H26", "H26"),
            PRICES,
            "price has 4 prices, expected 3, one per contract_code",
        ),
        (
            ("K26", "G26"),
            PRICES,
            "price has 4 prices, expected 2, one per contract_code",
        ),
        (
            KEPT_CODES,
            KEPT_PRICES,
            "contract_code row 2 is 'G26', published 2026-02-02, "
            "expected a month published before row 1's 'F26', published 2026-01-05",
        ),
        (
            ("J26", "F26", "H26"),
            PRICES[:3],
            "contract_code row 3 is 'H26', published 2026-03-02, "
            "expected a month published before row 2's 'F26', published 2026-01-05",
        ),
        (
            ("H26", "J26"),
            PRICES[:2],
            "contract_code row 2 is 'J26', published 2026-04-01, "
            "expected a month published before row 1's 'H26', published 2026-03-02",
        ),
        (
            ("F26", "G26", "G26"),
            PRICES[:3],
            "contract_code row 3 is 'G26', already given at row 2",
        ),
        (
            ("F26", "K26"),
            PRICES[:2],
            "contract_code row 2 is 'K26', expected one of the index's months",
        ),
        (
            ("F26", "G26"),
            PRICES,
            "price has 4 prices, expected 2, one per contract_code",
        ),
    ],
    ids=[
        "a price column one row short",
        "a price column one row long",
        "one price for four codes",
        "four prices for one code",
        "a code the index does not hold, first",
        "a code the index does not hold, last",
        "a code the index does not hold, between",
        "a code in another case than the schedule's",
        "a code given twice",
        "a code given three times, the second named",
        "an unknown code before a repeat, the unknown named",
        "a repeat before an unknown code, the repeat named",
        "a code twice and the count wrong, the count named first",
        "an unknown code and the count wrong, the count named first",
        "the months oldest first, the schedule's own order, the second row named",
        "the months in neither order, the first row published after the one above named",
        "two months the wrong way up",
        "the months oldest first and a code twice, the repeat named",
        "the months oldest first and an unknown code, the unknown named",
        "the months oldest first and the count wrong, the count named",
    ],
)
def test_fixings_that_cannot_be_made_say_why(
    codes: tuple[str, ...], given_prices: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        iferc_fixings(codes, given_prices, INDEX)
    assert str(failure.value) == message


# Two months the schedule says printed on one day cannot be newest first in either order: the
# second row is refused, whichever month it holds, since the rule is strict.
def test_two_months_published_on_one_day_are_refused_at_the_second_row() -> None:
    same_day = scheduled(("A", "2026-01-05"), ("B", "2026-01-05"))
    for codes in (("A", "B"), ("B", "A")):
        with pytest.raises(ValueError) as failure:
            iferc_fixings(codes, prices(1.0, 2.0), same_day)
        assert str(failure.value) == (
            f"contract_code row 2 is {codes[1]!r}, published 2026-01-05, "
            f"expected a month published before row 1's {codes[0]!r}, published 2026-01-05"
        )
    assert iferc_fixings(("A",), prices(1.0), same_day).codes == ("A",)


# A schedule that holds a month at two rows is a calendar's to refuse, not a fixing's, until a
# code names that month: then the code names two days, and the row is refused naming both of
# the schedule's, whether the two rows agree on the day or not. A code the schedule holds once
# passes over such a schedule. The unknown and repeated codes are named first, in row order,
# and the two days before the order of the months.
def test_a_month_the_schedule_holds_twice_is_refused_when_a_code_names_it() -> None:
    twice = scheduled(
        ("F26", "2026-01-05"),
        ("G26", "2026-02-02"),
        ("G26", "2026-02-02"),
        ("J26", "2026-04-01"),
    )
    disagreeing = scheduled(
        ("F26", "2026-01-05"),
        ("G26", "2026-02-02"),
        ("G26", "2026-03-02"),
        ("J26", "2026-04-01"),
    )
    for over in (twice, disagreeing):
        with pytest.raises(ValueError) as failure:
            iferc_fixings(("G26",), prices(2.10), over)
        assert str(failure.value) == (
            "contract_code row 1 is 'G26', a month the index's schedule holds at rows 2 and 3, "
            "expected a month it holds once"
        )
        fixings = iferc_fixings(("J26", "F26"), prices(1.60, 1.85), over)
        assert fixings.codes == ("F26", "J26") and fixings.prices.tolist() == [1.85, 1.60]
    for codes, message in (
        (("G26", "K26"), "contract_code row 2 is 'K26', expected one of the index's months"),
        (("J26", "J26", "G26"), "contract_code row 2 is 'J26', already given at row 1"),
        (
            ("F26", "G26"),
            "contract_code row 2 is 'G26', a month the index's schedule holds at rows 2 and 3, "
            "expected a month it holds once",
        ),
    ):
        with pytest.raises(ValueError) as failure:
            iferc_fixings(codes, prices(*range(len(codes))), twice)
        assert str(failure.value) == message
    thrice = scheduled(
        ("F26", "2026-01-05"),
        ("G26", "2026-02-02"),
        ("G26", "2026-02-02"),
        ("J26", "2026-04-01"),
        ("G26", "2026-02-02"),
    )
    with pytest.raises(ValueError) as failure:
        iferc_fixings(("J26", "G26"), prices(1.60, 2.10), thrice)
    assert str(failure.value) == (
        "contract_code row 2 is 'G26', a month the index's schedule holds at rows 2, 3 and 5, "
        "expected a month it holds once"
    )


# --- the general rule ---------------------------------------------------------


def a_schedule_and_a_series(
    data: st.DataObject,
) -> tuple[Index, IfercSchedule, tuple[str, ...], NDArray[np.float64]]:
    """An IFERC index of one to sixty months with opaque labels and strictly increasing
    publication days, up to sixty days apart, starting anywhere in sixty years so that a year's
    end falls between months, its rows in any order; and a series over it, any one or more of
    its months given newest first by their publication days with any price beside each."""
    count = data.draw(st.integers(1, 60))
    labels = tuple(
        data.draw(
            st.lists(st.text(min_size=1, max_size=8), min_size=count, max_size=count, unique=True)
        )
    )
    gaps = np.array(
        data.draw(st.lists(st.integers(1, 60), min_size=count, max_size=count)), dtype=np.int64
    )
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 21_900)), "D"
    )
    published = start + np.cumsum(gaps).astype("timedelta64[D]")
    rows = data.draw(st.permutations(range(count)))  # the schedule's rows, in any order
    schedule = iferc_fixings_schedule(labels, published, rows)
    over = an_index(schedule)
    chosen = sorted(data.draw(st.sets(st.integers(0, count - 1), min_size=1)))  # oldest first
    codes = tuple(labels[i] for i in reversed(chosen))
    given_prices = np.array(
        data.draw(
            st.lists(
                st.floats(-100, 100, allow_nan=False, allow_infinity=False),
                min_size=len(chosen),
                max_size=len(chosen),
            )
        ),
        dtype=np.float64,
    )
    return over, schedule, codes, given_prices


def iferc_fixings_schedule(
    labels: tuple[str, ...], published: NDArray[np.datetime64], rows: list[int]
) -> IfercSchedule:
    """The schedule of those months laid out in that row order, each month keeping its own
    publication day."""
    return iferc_schedule(tuple(labels[i] for i in rows), published[rows])


@settings(deadline=None)
@given(data=st.data())
def test_any_months_given_newest_first_are_kept_the_other_way_up_each_price_beside_its_code(
    data: st.DataObject,
) -> None:
    over, schedule, codes, given_prices = a_schedule_and_a_series(data)
    fixings = iferc_fixings(codes, given_prices, over)
    assert fixings.codes == codes[::-1]
    assert np.array_equal(fixings.prices, given_prices[::-1])
    assert dict(zip(fixings.codes, fixings.prices.tolist(), strict=True)) == dict(
        zip(codes, given_prices.tolist(), strict=True)
    )
    assert fixings.index is over
    kept_rows = [schedule.codes.index(code) for code in fixings.codes]
    assert (np.diff(schedule.publication_date[kept_rows]) > np.timedelta64(0, "D")).all()


@settings(deadline=None)
@given(data=st.data())
def test_any_two_or_more_months_given_oldest_first_are_refused_at_their_second_row(
    data: st.DataObject,
) -> None:
    over, schedule, codes, given_prices = a_schedule_and_a_series(data)
    if len(codes) < 2:
        return
    oldest_first = codes[::-1]
    first, second = (
        schedule.publication_date[schedule.codes.index(code)] for code in oldest_first[:2]
    )
    with pytest.raises(ValueError) as failure:
        iferc_fixings(oldest_first, given_prices[::-1], over)
    assert str(failure.value) == (
        f"contract_code row 2 is {oldest_first[1]!r}, published {second}, "
        f"expected a month published before row 1's {oldest_first[0]!r}, published {first}"
    )


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_columns_and_leave_the_inputs_as_given() -> None:
    given_prices = PRICES.copy()
    fixings = iferc_fixings(CODES, given_prices, INDEX)
    given_prices[0] = 9.99
    assert fixings.prices[-1] == 1.60
    assert not fixings.prices.flags.writeable
    with pytest.raises(ValueError):
        fixings.prices[0] = 9.99
    assert fixings.codes == KEPT_CODES
    assert fixings.codes is not CODES and CODES == ("J26", "H26", "G26", "F26")
    assert fixings.index is INDEX
