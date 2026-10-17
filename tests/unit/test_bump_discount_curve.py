"""A discount curve bumped by a parallel shift of its continuously compounded zero rates,
bump-discount-curve.md: every stored day's factor times exp(-b tau), tau the day's ACT/365F time
from the curve's own start, built through the ordinary constructor so that the curve's rules
judge the result. The figures are the ticket's: anchors on 4 January 2027 at 1 and 4 January
2028 at 0.95, the payment 365 days out, 0.9499050047498416 under +1 bp and 0.9500950047501583
under -1 bp, numerical targets to a stated tolerance. The production code is never asked for an
expected answer: the centered checks compare the evaluator's own numbers on the bumped curves
with the analytic risks it saved. The seam makes the handle and refuses in its own words.
docs/library/utilities/bump-discount-curve.md is the page."""

import math
import re

import numpy as np
import pytest
from test_bilateral_kernel import A_YEAR, AS_OF, CLOSE, TIGHT, curve_of, prepared_on, valued
from test_cross_gamma import CURVE, HNG, LAGS, PAYS, QUOTES, ticket_batch, trades_on
from test_trade_valuation import ENTRY, serial, spilled

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells
from goosedove.globals.discount_curve import DiscountCurve, bump_discount_curve
from goosedove.instrumentation.work_counts import WorkCounter

SOURCE = curve_of((AS_OF, 1.0), (A_YEAR, 0.95))  # 366 days, the ticket's worked anchors
UP_ONE, DOWN_ONE = 0.9499050047498416, 0.9500950047501583  # the ticket's targets a year out


def bumped(
    curve: DiscountCurve, bump_bps: float, counter: WorkCounter | None = None
) -> DiscountCurve:
    return bump_discount_curve(curve, bump_bps, counter or WorkCounter())


def refused(curve: DiscountCurve, bump_bps: float) -> str:
    with pytest.raises(ValueError) as caught:
        bumped(curve, bump_bps)
    return str(caught.value)


# --- the worked bumps -----------------------------------------------------------------------------


def test_the_worked_bumps_move_the_factor_a_year_out_and_keep_the_first_at_one() -> None:
    before = SOURCE.factors.copy()
    for bump, target in ((1.0, UP_ONE), (-1.0, DOWN_ONE), (0.5, 0.95 * math.exp(-0.00005))):
        counter = WorkCounter()
        made = bumped(SOURCE, bump, counter)
        assert isinstance(made, DiscountCurve) and made is not SOURCE
        np.testing.assert_array_equal(made.dates, SOURCE.dates)
        assert made.factors.size == 366
        assert made.factors[0] == 1.0  # exactly, exp(0) being 1
        assert made.factors[-1] == pytest.approx(target, rel=0, abs=1e-15)
        assert made.factors.dtype == np.float64
        assert not made.factors.flags.writeable and not made.dates.flags.writeable
        assert not np.shares_memory(made.factors, SOURCE.factors)
        assert counter.freeze().as_dict() == {"factors_shifted": 366}
    np.testing.assert_array_equal(SOURCE.factors, before)  # the source read, never written
    assert not SOURCE.factors.flags.writeable


def test_a_bump_of_nothing_moves_nothing_bit_for_bit() -> None:
    made = bumped(SOURCE, 0.0)
    np.testing.assert_array_equal(made.factors, SOURCE.factors)
    np.testing.assert_array_equal(made.dates, SOURCE.dates)
    assert made is not SOURCE and not np.shares_memory(made.factors, SOURCE.factors)


def test_every_stored_day_is_shifted_directly_and_not_an_interpolation_of_bumped_anchors() -> None:
    # 4 July 2027, day 181 of 365: the source's own line a year out shifted by exp(-0.0001 tau),
    # which is not the line between 1 and the bumped anchor, the two apart by a millionth.
    tau = 181.0 / 365.0
    day = 1.0 + tau * (0.95 - 1.0)
    direct = day * math.exp(-0.0001 * tau)
    through_anchors = 1.0 + tau * (UP_ONE - 1.0)
    made = bumped(SOURCE, 1.0)
    assert str(made.dates[181]) == "2027-07-04"
    assert made.factors[181] == pytest.approx(direct, rel=0, abs=1e-15)
    assert abs(made.factors[181] - through_anchors) > 1e-6
    # Every day along the curve: the source's factor times the shift of its own day.
    taus = np.arange(366) / 365.0
    np.testing.assert_allclose(made.factors, SOURCE.factors * np.exp(-0.0001 * taus), **TIGHT)


def test_a_leap_year_interval_counts_its_three_hundred_and_sixty_six_days() -> None:
    # 4 January 2028 to 4 January 2029 spans the leap day: 366 of 365, not one year.
    leap = curve_of(("2028-01-04", 1.0), ("2029-01-04", 0.95))
    assert leap.factors.size == 367
    made = bumped(leap, 1.0)
    assert made.factors[-1] == pytest.approx(
        0.95 * math.exp(-0.0001 * 366.0 / 365.0), rel=0, abs=1e-15
    )


def test_a_bump_bumps_again_and_the_bumps_add() -> None:
    twice = bumped(bumped(SOURCE, 1.0), 1.0)
    once = bumped(SOURCE, 2.0)
    np.testing.assert_allclose(twice.factors, once.factors, **TIGHT)
    back = bumped(bumped(SOURCE, 1.0), -1.0)
    np.testing.assert_allclose(back.factors, SOURCE.factors, **TIGHT)


def test_ordinary_bumps_down_are_accepted_within_the_rules() -> None:
    # The ticket's three-anchor curve bumped twenty-five down still falls day by day: the line
    # drops about 1.4e-4 a day where the shift lifts a day by 7e-6 of its factor.
    made = bumped(CURVE, -25.0)
    assert made.factors[365] == pytest.approx(0.95 * math.exp(0.0025), rel=0, abs=1e-15)
    assert made.factors[730] == pytest.approx(0.90 * math.exp(0.005), rel=0, abs=1e-15)
    assert (made.factors[1:] <= made.factors[:-1]).all()
    # A one-day curve has nothing to move but its first factor, which stays 1.
    one = bumped(curve_of((AS_OF, 1.0)), -1000.0)
    assert one.factors.tolist() == [1.0]


# --- the rules ------------------------------------------------------------------------------------


def test_a_curve_of_ones_bumped_down_is_refused_by_the_row_that_rose() -> None:
    ones = curve_of((AS_OF, 1.0), (A_YEAR, 1.0))
    assert re.fullmatch(
        r"discount_factor rises at row 2, from 1\.0 to 1\.00000027397\d+", refused(ones, -1.0)
    )
    # Bumped up, or by nothing, the same curve is accepted: nothing rises.
    assert bumped(ones, 1.0).factors[-1] == pytest.approx(math.exp(-0.0001), rel=0, abs=1e-15)
    np.testing.assert_array_equal(bumped(ones, 0.0).factors, ones.factors)


def test_a_bump_past_the_largest_number_or_down_to_nothing_is_refused_by_its_row() -> None:
    # A billion basis points: the factor a year out underflows to nothing, refused as the last
    # factor is; a billion down: the fourth day's factor overflows, the first that is not finite.
    assert refused(SOURCE, 1e9) == "discount_factor row 366 is 0.0, expected greater than 0"
    assert refused(SOURCE, -1e9) == "discount_factor row 4 is inf, expected a finite number"


def test_a_bump_that_is_no_finite_number_is_refused_by_name() -> None:
    assert refused(SOURCE, math.nan) == "bump_bps is nan, expected a finite number of basis points"
    assert refused(SOURCE, math.inf) == "bump_bps is inf, expected a finite number of basis points"
    assert refused(SOURCE, -math.inf) == (
        "bump_bps is -inf, expected a finite number of basis points"
    )


# --- the centered checks against the saved risks --------------------------------------------------


def test_one_lot_a_year_out_centers_on_its_cross_gamma_and_an_amount_of_a_hundred_on_its_dv01() -> (
    None
):
    # One live lot of G27 bought at 70, paid a year out at 0.95: 0.95 of discounted delta and
    # -0.000095 of cross-gamma; the curve a basis point each way, half the difference of the
    # deltas is the ticket's -0.0000950000001583, the derivative plus the difference's own
    # truncation, 0.95 times the cube of 0.0001 over 6. Quoted 170, the payment is 100, the NPV
    # 95 and the DV01 -0.0095; half the difference of the marks -0.0095000000158.
    one = prepared_on(trades_on(HNG, (1.0,), (70.0,), PAYS[:1], LAGS[:1]))
    analytic = valued(one, QUOTES, CURVE)
    assert analytic.discounted_lot_delta_total == pytest.approx(0.95, **CLOSE)
    assert analytic.cross_gamma_total == pytest.approx(-0.000095, **CLOSE)
    up, down = valued(one, QUOTES, bumped(CURVE, 1.0)), valued(one, QUOTES, bumped(CURVE, -1.0))
    assert up.discounted_lot_delta_total == pytest.approx(0.95 * math.exp(-0.0001), **CLOSE)
    centered = (up.discounted_lot_delta_total - down.discounted_lot_delta_total) / 2
    assert centered == pytest.approx(-0.0000950000001583, rel=0, abs=1e-16)
    assert centered == pytest.approx(analytic.cross_gamma_total, rel=0, abs=2e-13)
    paid = valued(one, (170.0, 50.0), CURVE)
    assert paid.mark == pytest.approx(95.0, **CLOSE)
    assert paid.dv01 == pytest.approx(-0.0095, **CLOSE)
    up, down = (
        valued(one, (170.0, 50.0), bumped(CURVE, 1.0)),
        valued(one, (170.0, 50.0), bumped(CURVE, -1.0)),
    )
    centered = (up.mark - down.mark) / 2
    assert centered == pytest.approx(-0.0095000000158, rel=0, abs=1e-13)
    assert centered == pytest.approx(paid.dv01, rel=0, abs=2e-11)


def test_the_ticket_batch_centers_on_its_saved_dv01_and_cross_gamma_at_a_tenth_of_a_point() -> None:
    # A and B on the three-anchor curve: 28 of mark, -0.0037 of DV01 and -0.00005 of cross-gamma
    # saved; the curve bumped h each way, the differences over 2h, the denominator in basis
    # points already. At h = 0.1 the truncation is h squared over 6 times the third derivative,
    # some 1e-15 on the DV01 and 1e-17 on the cross-gamma; roundoff, the marks near 28 known to
    # 1e-14 over 0.2, some 1e-13: within 1e-12. At h = 1 the truncation grows a hundredfold,
    # 1.5e-11 on the DV01 and 4e-12 on the cross-gamma: within 1e-10.
    prep = ticket_batch()
    analytic = valued(prep, QUOTES, CURVE)
    assert analytic.mark == pytest.approx(28.0, **CLOSE)
    assert analytic.dv01 == pytest.approx(-0.0037, **CLOSE)
    assert analytic.cross_gamma_total == pytest.approx(-0.00005, **CLOSE)
    for h, tolerance in ((0.1, 1e-12), (1.0, 1e-10)):
        up, down = valued(prep, QUOTES, bumped(CURVE, h)), valued(prep, QUOTES, bumped(CURVE, -h))
        assert (up.mark - down.mark) / (2 * h) == pytest.approx(analytic.dv01, rel=0, abs=tolerance)
        assert (up.discounted_lot_delta_total - down.discounted_lot_delta_total) / (2 * h) == (
            pytest.approx(analytic.cross_gamma_total, rel=0, abs=tolerance)
        )
        assert up.lot_delta_total == down.lot_delta_total == 5.0  # the nominal lots never move
        assert up.mark < analytic.mark < down.mark  # up lowers the factors and the mark
    # The saved results on the source stand: the bump reads the curve and writes nothing.
    again = valued(prep, QUOTES, CURVE)
    assert again.mark == analytic.mark and again.dv01 == analytic.dv01


# --- through the seam -----------------------------------------------------------------------------

HEADERS = Cells.from_rows([["date", "discount_factor"]])
ANCHORS = Cells.from_rows([[serial(AS_OF), 1.0], [serial(A_YEAR), 0.95]])
HANDLE = re.compile(r"^\d+:discount_curve:\d+$")


def a_curve() -> str:
    text = ENTRY["_CreateDiscountCurve"](HEADERS, ANCHORS)
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def test_the_seam_makes_an_ordinary_curve_handle_that_reads_back_and_bumps_again() -> None:
    source = a_curve()
    live = bridge.live_handles()[0]  # the live count, then the price bytes
    made = ENTRY["util_BumpDiscountCurve"](source, 1.0)
    assert isinstance(made, str) and HANDLE.fullmatch(made) and made != source
    assert bridge.live_handles()[0] == live + 1  # one publication
    rows = spilled(ENTRY["util_ReadHandle"](made))
    assert rows[0] == ["date", "discount_factor"]
    assert rows[1] == ["datetime64[D]", "float64"]
    assert len(rows) == 368
    assert rows[2] == [serial(AS_OF), 1.0]
    assert rows[367][0] == serial(A_YEAR)
    assert rows[367][1] == pytest.approx(UP_ONE, rel=0, abs=1e-15)
    down = ENTRY["util_BumpDiscountCurve"](source, -1.0)
    assert spilled(ENTRY["util_ReadHandle"](down))[367][1] == pytest.approx(
        DOWN_ONE, rel=0, abs=1e-15
    )
    # A bumped curve bumps again, and a bump of nothing reads back as the source does.
    twice = ENTRY["util_BumpDiscountCurve"](made, 1.0)
    assert isinstance(twice, str) and HANDLE.fullmatch(twice)
    nothing = ENTRY["util_BumpDiscountCurve"](source, 0.0)
    assert spilled(ENTRY["util_ReadHandle"](nothing)) == spilled(ENTRY["util_ReadHandle"](source))
    # The source reads back as it was.
    assert spilled(ENTRY["util_ReadHandle"](source))[367] == [serial(A_YEAR), 0.95]


def test_the_seam_refuses_in_its_own_words_and_relays_the_library_s() -> None:
    source = a_curve()
    live = bridge.live_handles()[0]  # the live count, then the price bytes
    date = ENTRY["_CreateValuationDate"](serial(AS_OF), 0.5)
    assert ENTRY["util_BumpDiscountCurve"](MISSING, 1.0) == (
        "#ERROR util_BumpDiscountCurve: curve is missing, expected discount curve handle"
    )
    assert ENTRY["util_BumpDiscountCurve"]("x", 1.0) == (
        "#ERROR util_BumpDiscountCurve: curve is text 'x' naming no live object, expected "
        "discount curve handle"
    )
    assert ENTRY["util_BumpDiscountCurve"](46391.0, 1.0) == (
        "#ERROR util_BumpDiscountCurve: curve is number 46391.0, expected discount curve handle"
    )
    assert ENTRY["util_BumpDiscountCurve"](date, 1.0) == (
        f"#ERROR util_BumpDiscountCurve: curve is valuation date handle '{date}', expected "
        "discount curve handle"
    )
    failure = "#ERROR _CreateDiscountCurve: ValueError: x"
    assert ENTRY["util_BumpDiscountCurve"](failure, 1.0) == (
        "#ERROR util_BumpDiscountCurve: curve is the creator's failure, expected discount curve "
        f"handle: {failure}"
    )
    assert ENTRY["util_BumpDiscountCurve"](source, "1bp") == (
        "#ERROR util_BumpDiscountCurve: bump_bps is text '1bp', expected number"
    )
    assert ENTRY["util_BumpDiscountCurve"](source, True) == (
        "#ERROR util_BumpDiscountCurve: bump_bps is boolean TRUE, expected number"
    )
    assert ENTRY["util_BumpDiscountCurve"](source, MISSING) == (
        "#ERROR util_BumpDiscountCurve: bump_bps is missing, expected number"
    )
    ones = ENTRY["_CreateDiscountCurve"](
        HEADERS, Cells.from_rows([[serial(AS_OF), 1.0], [serial(A_YEAR), 1.0]])
    )
    assert re.fullmatch(
        r"#ERROR util_BumpDiscountCurve: ValueError: discount_factor rises at row 2, "
        r"from 1\.0 to 1\.00000027397\d+",
        str(ENTRY["util_BumpDiscountCurve"](ones, -1.0)),
    )
    assert ENTRY["util_BumpDiscountCurve"](source, 1e9) == (
        "#ERROR util_BumpDiscountCurve: ValueError: discount_factor row 366 is 0.0, expected "
        "greater than 0"
    )
    assert bridge.live_handles()[0] == live + 2  # the date and the ones; no refusal published
