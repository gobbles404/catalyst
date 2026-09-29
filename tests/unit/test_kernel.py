"""The kernel: the whiteboard's ten rows and four more, three ways; a day fixing, a print
missing, a print corrected; a three-year synthetic ethane market against exact fractions; and
the general rules under random terms and bindings.

The ethane rows follow ICE's Ethane, OPIS Mt. Belvieu Non-TET Future (ETE): 1,000 barrels a lot,
42 gallons a barrel, quoted in cents per gallon, cash settled to the average of the OPIS purity
ethane price on each day OPIS reports one for the contract month. So one lot is 42,000 gallons
and 0.01 USD a cent, 420 USD per cent per gallon, and an average over n days puts 420 times the
lots divided by n on each day. Every price, print and date here is synthetic.
"""

from fractions import Fraction

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.valuation.binding import Binding, binding
from goosedove.valuation.kernel import amounts, compressed, compressed_amounts, dense
from goosedove.valuation.terms import Terms, terms


def floats(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def ints(*values: int) -> NDArray[np.intp]:
    return np.array(values, dtype=np.intp)


def span(start: int, count: int) -> NDArray[np.intp]:
    return np.arange(start, start + count, dtype=np.intp)


LOT = 1_000 * 42 * 0.01  # USD per cent per gallon, per lot of ethane

Component = tuple[float, NDArray[np.intp], NDArray[np.float64]]
"""A component as its constant, the observations it reads and the coefficient on each."""


def outright(lots: float, lot_size: float, agreed: float, observation: int) -> Component:
    quantity = lots * lot_size
    return -quantity * agreed, ints(observation), floats(quantity)


def average(quantity: float, agreed: float, observations: NDArray[np.intp]) -> Component:
    n = observations.size
    return -quantity * agreed, observations, np.full(n, quantity / n)


def spread(
    quantity: float, agreed: float, long_leg: NDArray[np.intp], short_leg: NDArray[np.intp]
) -> Component:
    coefficient = np.concatenate(
        [
            np.full(long_leg.size, quantity / long_leg.size),
            np.full(short_leg.size, -quantity / short_leg.size),
        ]
    )
    return -quantity * agreed, np.concatenate([long_leg, short_leg]), coefficient


def a_terms(*components: Component) -> Terms:
    constant = floats(*(c for c, _, _ in components))
    component = np.concatenate(
        [np.full(o.size, i, dtype=np.intp) for i, (_, o, _) in enumerate(components)]
    )
    observation = np.concatenate([o for _, o, _ in components])
    coefficient = np.concatenate([k for _, _, k in components])
    return terms(constant, component, observation, coefficient)


def three_ways(made: Terms, bound: Binding) -> NDArray[np.float64]:
    """The amounts by the terms, checked against the dense view and the compressed view."""
    by_terms = amounts(made, bound, WorkCounter())
    by_dense = dense(made, bound, WorkCounter()) @ bound.price + made.constant
    view = compressed(made, bound, WorkCounter())
    by_view = compressed_amounts(view, bound.marks, WorkCounter())
    np.testing.assert_allclose(by_dense, by_terms, rtol=1e-12, atol=1e-9)
    np.testing.assert_allclose(by_view, by_terms, rtol=1e-12, atol=1e-9)
    return by_terms


# --- the whiteboard's ten rows ------------------------------------------------------------------
# Observations, counted from zero: 0 and 1 the NG Z26 and F27 expiry rows; 2 a CL expiry row at a
# negative mark; 3 and 4 two Waha basis months; 5 to 24 twenty Mont Belvieu ethane days, the first
# ten printed; 25 to 46 twenty-two CL settle days for WTI Financial, the first seven printed, the
# first fifteen priced by F27 and the last seven by G27. Marks in the same order as the rows name
# them; the CL row at -37.63 is its own scenario, not the F27 of the WTI Financial row.
NG_Z26, NG_F27, CL_NEGATIVE, WAHA_X26, WAHA_Z26, MB_BALMO, CL_F27, CL_G27 = range(8)
MARKS = floats(3.20, 3.50, -37.63, -1.20, -1.45, 26.10, 60.20, 59.20)
MB_DAYS = span(5, 20)
CL_DAYS = span(25, 22)
MB_PRINTS = [24.50, 24.80, 25.00, 25.30, 25.10, 24.90, 25.40, 25.60, 25.20, 25.20]
CL_PRINTS = [58.10, 58.60, 59.00, 59.40, 59.30, 59.20, 59.40]


def ten_rows_market() -> tuple[NDArray[np.bool_], NDArray[np.float64], NDArray[np.intp]]:
    """The 47 observations: whether each has fixed, its print or none, and its mark."""
    is_fixed = np.zeros(47, dtype=np.bool_)
    prints = np.full(47, np.nan)
    mark_of = np.zeros(47, dtype=np.intp)
    mark_of[:5] = [NG_Z26, NG_F27, CL_NEGATIVE, WAHA_X26, WAHA_Z26]
    mark_of[MB_DAYS] = MB_BALMO
    mark_of[CL_DAYS[:15]] = CL_F27
    mark_of[CL_DAYS[15:]] = CL_G27
    is_fixed[MB_DAYS[:10]] = True
    prints[MB_DAYS[:10]] = MB_PRINTS
    is_fixed[CL_DAYS[:7]] = True
    prints[CL_DAYS[:7]] = CL_PRINTS
    return is_fixed, prints, mark_of


TEN = [
    outright(10, 10_000, 3.10, 0),
    outright(-4, 10_000, 3.15, 0),
    outright(7, 10_000, 3.40, 1),
    outright(-12, 10_000, 3.35, 1),
    outright(-5, 1_000, 20.00, 2),
    outright(2, 1_000, 25.00, 2),
    outright(8, 2_500, -1.30, 3),
    outright(-8, 2_500, -1.30, 4),
    average(3 * LOT, 25.10, MB_DAYS),
    average(4 * 1_000, 59.00, CL_DAYS),
]
TEN_AMOUNTS = [10_000, -2_000, 7_000, -18_000, 288_150, -125_260, 2_000, 3_000, 630.00, 2_000.00]
TEN_SENSITIVITY = [60_000, -50_000, -3_000, 20_000, -20_000, 630.0, 8 * 4_000 / 22, 7 * 4_000 / 22]


def test_the_ten_rows_give_the_hand_worked_amounts_three_ways() -> None:
    bound = binding(*ten_rows_market(), MARKS, WorkCounter())
    got = three_ways(a_terms(*TEN), bound)
    np.testing.assert_allclose(got, TEN_AMOUNTS, rtol=0, atol=1e-6)


def test_the_book_sensitivity_per_mark_is_the_compressed_column_sum_and_matches_a_bump() -> None:
    is_fixed, prints, mark_of = ten_rows_market()
    made = a_terms(*TEN)
    bound = binding(is_fixed, prints, mark_of, MARKS, WorkCounter())
    view = compressed(made, bound, WorkCounter())
    np.testing.assert_allclose(view.coefficient.sum(axis=0), TEN_SENSITIVITY, rtol=0, atol=1e-6)
    before = amounts(made, bound, WorkCounter())
    for m in range(MARKS.size):
        bumped = MARKS.copy()
        bumped[m] += 0.01
        after = amounts(
            made, binding(is_fixed, prints, mark_of, bumped, WorkCounter()), WorkCounter()
        )
        assert abs((after - before).sum() - TEN_SENSITIVITY[m] * 0.01) < 1e-6


def test_a_zero_net_position_keeps_its_constant_at_any_mark() -> None:
    made = a_terms(outright(10, 10_000, 3.10, 0), outright(-10, 10_000, 3.20, 0))
    for mark in (2.0, 3.2, 9.9, -1.0):
        bound = binding(
            ints(0).astype(np.bool_), floats(np.nan), ints(0), floats(mark), WorkCounter()
        )
        assert abs(amounts(made, bound, WorkCounter()).sum() - 10_000) < 1e-9


# --- four more components -----------------------------------------------------------------------
# A second index, Conway ethane, on observations 47 to 66, its own twenty days with the first ten
# printed and its own balance-of-month mark; then a constant-only component, a genuine two-index
# spread, and a pair of swaps with identical exposures, the T1 and T7 of the sheet.
CONWAY_BALMO = 8
MARKS_MORE = np.append(MARKS, 23.20)
CW_DAYS = span(47, 20)
CW_PRINTS = [21.40, 21.70, 22.10, 22.30, 22.00, 21.90, 22.50, 22.60, 22.30, 22.20]


def more_market() -> tuple[NDArray[np.bool_], NDArray[np.float64], NDArray[np.intp]]:
    is_fixed, prints, mark_of = ten_rows_market()
    is_fixed = np.concatenate([is_fixed, np.zeros(20, dtype=np.bool_)])
    prints = np.concatenate([prints, np.full(20, np.nan)])
    mark_of = np.concatenate([mark_of, np.full(20, CONWAY_BALMO, dtype=np.intp)])
    is_fixed[CW_DAYS[:10]] = True
    prints[CW_DAYS[:10]] = CW_PRINTS
    return is_fixed, prints, mark_of


MORE = [
    average(2 * LOT, 24.90, MB_DAYS[:10]),  # every day fixed: 840 x (25.10 - 24.90)
    spread(2 * LOT, 3.00, MB_DAYS, CW_DAYS),  # 840 x (1.50 + 1.45 - 3.00)
    average(3 * LOT, 25.10, MB_DAYS),  # T1: 1,260 x (25.60 - 25.10)
    average(-3 * LOT, 25.40, MB_DAYS),  # T7: -1,260 x (25.60 - 25.40)
]
MORE_AMOUNTS = [168.00, -42.00, 630.00, -252.00]


def test_the_four_more_components_give_their_hand_worked_amounts_three_ways() -> None:
    bound = binding(*more_market(), MARKS_MORE, WorkCounter())
    got = three_ways(a_terms(*TEN, *MORE), bound)
    np.testing.assert_allclose(got[10:], MORE_AMOUNTS, rtol=0, atol=1e-6)
    np.testing.assert_allclose(got[:10], TEN_AMOUNTS, rtol=0, atol=1e-6)


def test_the_sensitivities_of_the_four_are_per_index_and_read_in_lots() -> None:
    view = compressed(
        a_terms(*TEN, *MORE), binding(*more_market(), MARKS_MORE, WorkCounter()), WorkCounter()
    )
    lots = view.coefficient[10:] / LOT
    np.testing.assert_allclose(lots[:, MB_BALMO], [0.0, 1.0, 1.5, -1.5], rtol=0, atol=1e-12)
    np.testing.assert_allclose(lots[:, CONWAY_BALMO], [0.0, -1.0, 0.0, 0.0], rtol=0, atol=1e-12)
    assert abs(view.coefficient[:, MB_BALMO].sum() / LOT - 2.5) < 1e-12


def test_a_component_with_every_day_fixed_prices_with_no_mark_at_all() -> None:
    made = a_terms(average(2 * LOT, 24.90, span(0, 10)))
    bound = binding(
        np.ones(10, dtype=np.bool_),
        floats(*MB_PRINTS),
        np.zeros(10, dtype=np.intp),
        floats(),
        WorkCounter(),
    )
    view = compressed(made, bound, WorkCounter())
    assert view.coefficient.shape == (1, 0)
    got = three_ways(made, bound)
    assert abs(got[0] - 168.00) < 1e-9


def test_one_component_alone_and_in_the_batch_agree_through_the_same_path() -> None:
    bound = binding(*more_market(), MARKS_MORE, WorkCounter())
    alone = amounts(a_terms(MORE[2]), bound, WorkCounter())
    batch = amounts(a_terms(*TEN, *MORE), bound, WorkCounter())
    assert alone[0] == batch[12]


# --- a day fixes, a print is missing, a print is corrected -------------------------------------


def test_a_day_that_fixes_changes_the_binding_and_not_the_terms() -> None:
    made = a_terms(*TEN, *MORE)
    is_fixed, prints, mark_of = more_market()
    before = compressed(
        made, binding(is_fixed, prints, mark_of, MARKS_MORE, WorkCounter()), WorkCounter()
    )
    is_fixed[MB_DAYS[10]] = True
    prints[MB_DAYS[10]] = 26.00
    is_fixed[CW_DAYS[10]] = True
    prints[CW_DAYS[10]] = 23.10
    bound = binding(is_fixed, prints, mark_of, MARKS_MORE, WorkCounter())
    after = compressed(made, bound, WorkCounter())
    got = three_ways(made, bound)
    change = np.zeros(14)
    change[8] = change[12] = -6.30  # 63 x (26.00 - 26.10) on three lots
    change[13] = 6.30
    np.testing.assert_allclose(
        got, np.array(TEN_AMOUNTS + MORE_AMOUNTS) + change, rtol=0, atol=1e-9
    )
    assert abs(before.coefficient[8, MB_BALMO] - 630.0) < 1e-9
    assert abs(after.coefficient[8, MB_BALMO] - 567.0) < 1e-9
    assert abs(after.coefficient[11, CONWAY_BALMO] + 378.0) < 1e-9
    changed = np.flatnonzero((after.coefficient != before.coefficient).any(axis=1))
    assert changed.tolist() == [8, 11, 12, 13]


def test_a_day_that_has_passed_without_a_print_is_refused_before_any_amount() -> None:
    is_fixed, prints, mark_of = more_market()
    is_fixed[MB_DAYS[10]] = True
    counter = WorkCounter()
    with pytest.raises(ValueError) as caught:
        binding(is_fixed, prints, mark_of, MARKS_MORE, counter)
    assert str(caught.value) == (
        "prints row 16 is nan, expected a finite number, since observation 16 has fixed"
    )
    assert counter.freeze().as_dict() == {}


def test_a_corrected_print_moves_only_the_constants() -> None:
    made = a_terms(*TEN, *MORE)
    is_fixed, prints, mark_of = more_market()
    before = compressed(
        made, binding(is_fixed, prints, mark_of, MARKS_MORE, WorkCounter()), WorkCounter()
    )
    prints[MB_DAYS[2]] = 25.05  # day 3 revised from 25.00
    after = compressed(
        made, binding(is_fixed, prints, mark_of, MARKS_MORE, WorkCounter()), WorkCounter()
    )
    np.testing.assert_array_equal(after.coefficient, before.coefficient)
    moved = after.constant - before.constant
    expected = np.zeros(14)
    expected[8] = expected[12] = 63 * 0.05
    expected[10] = 84 * 0.05
    expected[11] = 42 * 0.05
    expected[13] = -63 * 0.05
    np.testing.assert_allclose(moved, expected, rtol=0, atol=1e-9)


# --- the kernel's own rules ----------------------------------------------------------------------


def test_the_binding_must_cover_every_observation_the_terms_read() -> None:
    made = a_terms(*TEN, *MORE)
    short = binding(*ten_rows_market(), MARKS, WorkCounter())
    message = (
        "binding has 47 observations, expected 67 or more, since the terms read observation row 67"
    )
    for call in (
        lambda: amounts(made, short, WorkCounter()),
        lambda: compressed(made, short, WorkCounter()),
        lambda: dense(made, short, WorkCounter()),
    ):
        with pytest.raises(ValueError) as caught:
            call()
        assert str(caught.value) == message


def test_the_marks_given_to_a_compressed_view_are_one_per_column() -> None:
    view = compressed(
        a_terms(*TEN), binding(*ten_rows_market(), MARKS, WorkCounter()), WorkCounter()
    )
    with pytest.raises(ValueError) as caught:
        compressed_amounts(view, MARKS_MORE, WorkCounter())
    assert (
        str(caught.value) == "marks has 9 rows, expected 8, one per mark as the compressed view has"
    )


def test_the_compressed_view_is_frozen_and_every_result_is_a_new_array() -> None:
    made = a_terms(*TEN)
    bound = binding(*ten_rows_market(), MARKS, WorkCounter())
    view = compressed(made, bound, WorkCounter())
    assert not view.constant.flags.writeable and not view.coefficient.flags.writeable
    first = amounts(made, bound, WorkCounter())
    second = amounts(made, bound, WorkCounter())
    assert first is not second and first.flags.writeable
    np.testing.assert_array_equal(first, second)
    assert (
        made.constant[0] == -310_000.0
    )  # the add of the constants was into the sums, not into the terms


# --- a three-year synthetic ethane market, against exact fractions ------------------------------
# Every business day from 1 December 2026 to 31 December 2029, Monday to Friday less three
# synthetic holidays a year, is an observation; each month from December 2026 to December 2029 is a
# mark, 37 in all, the first the balance of December; the valuation date is 16 December 2026, so
# the eleven days before it have printed. Prices are whole cents so that fractions are exact.
FIRST, LAST, AS_OF = (
    np.datetime64("2026-12-01"),
    np.datetime64("2029-12-31"),
    np.datetime64("2026-12-16"),
)
HOLIDAYS = np.array(
    [f"{year}-{day}" for year in (2026, 2027, 2028, 2029) for day in ("01-01", "07-04", "12-25")],
    dtype="datetime64[D]",
)


def business_days(first: np.datetime64, last: np.datetime64) -> NDArray[np.datetime64]:
    every = np.arange(first, last + np.timedelta64(1, "D"), dtype="datetime64[D]")
    return every[np.is_busday(every, holidays=HOLIDAYS)]


DAYS = business_days(FIRST, LAST)
MONTH = (DAYS.astype("datetime64[M]") - FIRST.astype("datetime64[M]")).astype(np.intp)
MARK_CENTS = 2_610 - 4 * np.arange(37)  # 26.10 for the balance of December, four cents less a month
PRINT_CENTS = 2_500 + 10 * (np.arange(DAYS.size) % 7)  # 25.00 to 25.60, day by day


def three_year_binding() -> Binding:
    is_fixed = DAYS < AS_OF
    prints = np.where(is_fixed, PRINT_CENTS / 100, np.nan)
    return binding(is_fixed, prints, MONTH, MARK_CENTS / 100, WorkCounter())


def exact_average(
    quantity: int, agreed_cents: int, days: NDArray[np.intp], bound: Binding
) -> Fraction:
    """The amount of an average in exact arithmetic: quantity times the mean price less the
    agreed price, prices in cents, the quantity in USD per cent per gallon."""
    cents = [
        Fraction(int(PRINT_CENTS[d]) if bound.is_fixed[d] else int(MARK_CENTS[MONTH[d]]), 100)
        for d in days.tolist()
    ]
    return quantity * (sum(cents, Fraction(0)) / len(cents) - Fraction(agreed_cents, 100))


def test_the_three_year_market_has_a_representative_size() -> None:
    bound = three_year_binding()
    assert bound.observations == DAYS.size and 780 <= DAYS.size <= 810
    assert bound.marks.size == 37
    assert int(bound.is_fixed.sum()) == 11


def test_a_year_long_average_over_the_curve_is_within_a_millionth_of_a_cent_of_exact() -> None:
    bound = three_year_binding()
    year = np.flatnonzero(DAYS.astype("datetime64[Y]") == np.datetime64("2029")).astype(np.intp)
    assert year.size == 258  # 261 weekdays in 2029 less New Year, 4 July and Christmas
    quantity = 100 * LOT  # a hundred lots, 42,000 USD per cent per gallon
    made = a_terms(average(quantity, 24.00, year))
    got = three_ways(made, bound)
    exact = exact_average(int(quantity), 2_400, year, bound)
    assert abs(got[0] - float(exact)) < 1e-8
    view = compressed(made, bound, WorkCounter())
    assert int(np.count_nonzero(view.coefficient)) == 12  # one cell per month of the year


def test_a_month_partly_fixed_over_the_curve_is_within_a_millionth_of_a_cent_of_exact() -> None:
    bound = three_year_binding()
    december = np.flatnonzero(MONTH == 0).astype(np.intp)
    assert december.size == 22
    made = a_terms(average(3 * LOT, 25.10, december), average(-3 * LOT, 25.40, december))
    got = three_ways(made, bound)
    for c, (lots, agreed) in enumerate(((3, 2_510), (-3, 2_540))):
        exact = exact_average(int(lots * LOT), agreed, december, bound)
        assert abs(got[c] - float(exact)) < 1e-8
    assert (
        abs(got.sum() - 3 * LOT * 0.30) < 1e-8
    )  # the pair's constant survives its zero net position


# --- the general rules, under random terms and bindings -----------------------------------------


@st.composite
def terms_and_market(
    draw: st.DrawFn,
) -> tuple[Terms, NDArray[np.bool_], NDArray[np.float64], NDArray[np.intp], NDArray[np.float64]]:
    components = draw(st.integers(1, 4))
    observations = draw(st.integers(1, 12))
    marks = draw(st.integers(0, 3))
    count = draw(st.integers(0, 30))
    number = st.floats(-1e4, 1e4, allow_nan=False, allow_infinity=False)
    made = terms(
        floats(*draw(st.lists(number, min_size=components, max_size=components))),
        ints(*draw(st.lists(st.integers(0, components - 1), min_size=count, max_size=count))),
        ints(*draw(st.lists(st.integers(0, observations - 1), min_size=count, max_size=count))),
        floats(*draw(st.lists(number, min_size=count, max_size=count))),
    )
    fixed = draw(st.lists(st.booleans(), min_size=observations, max_size=observations))
    is_fixed = np.array([True] * observations if marks == 0 else fixed, dtype=np.bool_)
    prints = floats(*draw(st.lists(number, min_size=observations, max_size=observations)))
    mark_of = ints(
        *draw(
            st.lists(
                st.integers(0, max(marks - 1, 0)), min_size=observations, max_size=observations
            )
        )
    )
    vector = floats(*draw(st.lists(number, min_size=marks, max_size=marks)))
    return made, is_fixed, prints, mark_of, vector


@settings(deadline=None)
@given(case=terms_and_market())
def test_the_three_ways_agree_for_any_terms_and_binding(
    case: tuple[
        Terms, NDArray[np.bool_], NDArray[np.float64], NDArray[np.intp], NDArray[np.float64]
    ],
) -> None:
    made, is_fixed, prints, mark_of, vector = case
    bound = binding(is_fixed, prints, mark_of, vector, WorkCounter())
    by_terms = amounts(made, bound, WorkCounter())
    by_dense = dense(made, bound, WorkCounter()) @ bound.price + made.constant
    by_view = compressed_amounts(compressed(made, bound, WorkCounter()), vector, WorkCounter())
    np.testing.assert_allclose(by_dense, by_terms, rtol=1e-12, atol=1e-6)
    np.testing.assert_allclose(by_view, by_terms, rtol=1e-12, atol=1e-6)


@settings(deadline=None)
@given(case=terms_and_market(), bump=st.floats(-10, 10, allow_nan=False, allow_infinity=False))
def test_a_move_in_a_mark_moves_each_amount_by_its_compressed_coefficient(
    case: tuple[
        Terms, NDArray[np.bool_], NDArray[np.float64], NDArray[np.intp], NDArray[np.float64]
    ],
    bump: float,
) -> None:
    made, is_fixed, prints, mark_of, vector = case
    bound = binding(is_fixed, prints, mark_of, vector, WorkCounter())
    view = compressed(made, bound, WorkCounter())
    before = amounts(made, bound, WorkCounter())
    for m in range(vector.size):
        moved = vector.copy()
        moved[m] += bump
        after = amounts(
            made, binding(is_fixed, prints, mark_of, moved, WorkCounter()), WorkCounter()
        )
        np.testing.assert_allclose(
            after - before, view.coefficient[:, m] * bump, rtol=1e-12, atol=1e-6
        )
