"""The fit-to-curve prices of a saved request, ftc-monthly-prices.md: each component's own
price moved by the same amount, the agreed price less the request's fit-to-curve quote, and
rounded alone to the allowed decimals; the average the fixed prices come back to and its
difference from the agreed price beside them. The issue's example by hand and one of unequal
quantities; at the request's own quote the curve's prices and a difference of exactly zero; the
rounding as the sheet's ROUND rounds, a half step away from zero on the digits a cell shows;
prices at zero and below; a request of windows and one per calendar day; no curve taken and no
factor read; the refusals; and the worksheet function through the seam.
docs/library/quoting/quote-ftc-prices.md owns the calculation."""

import re

import numpy as np
import pytest
from holiday_fixtures import a_name
from hypothesis import given
from hypothesis import strategies as st
from test_bilateral_kernel import CLOSE
from test_create_trades import seam_key, with_calendars
from test_fit_to_curve import CODES, EXAMPLE, FIELDS, PRICES, RATES, by_request
from test_quote import DEC_31, STRIP, bilateral, financial, physical, priced
from test_rfq import LONGER, WINDOW_PRICE, WINDOW_WORDS, request, windows
from test_rfq import MARKET as STRIP_MARKET
from test_trade_valuation import a_history as seam_history
from test_trade_valuation import a_market as seam_market
from test_trade_valuation import an_index as seam_index
from test_trade_valuation import column, row, serial, spilled
from test_trade_valuation import rows as cells_of

from catalyst.excel import bridge
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market
from catalyst.quoting.ftc_prices import FtcPrices, as_shown, ftc_prices, rounded
from catalyst.quoting.rfq import Rfq

ENTRY = {
    name: bridge.entry(name)
    for name in (
        "_QuoteFTCPrices",
        "_QuoteRFQ",
        "_CreateRFQ",
        "_CreateQuoteTemplate",
        "_CreateHolidayCalendar",
    )
}
# A batch or a quote template made on the sheet names the tests' collection of payment
# calendars, payment-calendar-keys.md.
ENTRY["_CreateQuoteTemplate"] = with_calendars(ENTRY["_CreateQuoteTemplate"])

# The issue's example: January, February and March 2027 at 4.50, 4.30 and 3.00, the same quantity
# each month, agreed at 3.95 with two decimals allowed. The request's fit-to-curve quote is
# 11.80 / 3 = 3.9333, so every month takes 1.67 cents: 4.5167, 4.3167 and 3.0167, which round to
# 4.52, 4.32 and 3.02 and come back to 11.86 / 3 = 3.9533, a third of a cent over.
EQUAL = (10_000.0, 10_000.0, 10_000.0)
AGREED = 3.95


def fitted(
    market: Market, saved: Rfq, price: float, decimals: int, counter: WorkCounter | None = None
) -> FtcPrices:
    return ftc_prices(market, saved, price, decimals, counter or WorkCounter())


def the_months(quantities: tuple[float, ...] = EQUAL, per: str = "month") -> Rfq:
    return request(CODES, quantities, bilateral(per=per), ix=LONGER)


def refused(
    message: str, price: float = AGREED, decimals: int = 2, market: Market = EXAMPLE
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        fitted(market, the_months(), price, decimals)


# --- the worked examples --------------------------------------------------------------------------


def test_the_issues_example_by_hand() -> None:
    got = fitted(EXAMPLE, the_months(), AGREED, 2)
    assert got.period == CODES
    assert got.quantity.tolist() == list(EQUAL)
    assert got.curve_price == pytest.approx(PRICES, **CLOSE)
    assert got.fixed_price.tolist() == [4.52, 4.32, 3.02]
    assert got.agreed == AGREED
    assert got.average == pytest.approx(11.86 / 3, **CLOSE)
    assert got.difference == pytest.approx(11.86 / 3 - AGREED, abs=1e-12)
    # One more decimal and the same months: 4.517, 4.317 and 3.017, a thirtieth of a cent over.
    finer = fitted(EXAMPLE, the_months(), AGREED, 3)
    assert finer.fixed_price.tolist() == [4.517, 4.317, 3.017]
    assert finer.difference == pytest.approx(11.851 / 3 - AGREED, abs=1e-12)
    # No decimals: 5, 4 and 3, which come back to 4.
    assert fitted(EXAMPLE, the_months(), AGREED, 0).fixed_price.tolist() == [5.0, 4.0, 3.0]


def test_unequal_quantities_weigh_the_quote_and_the_average_alike() -> None:
    # January at 10,000 and March at 20,000: the quote is 105,000 / 30,000 = 3.50. Agreed at
    # 3.516 each month takes 1.6 cents, 4.516 and 3.016, which round to 4.52 and 3.02 and come
    # back to 105,600 / 30,000 = 3.52, four tenths of a cent over.
    two = request(("F27", "H27"), (10_000.0, 20_000.0), bilateral(), ix=LONGER)
    got = fitted(EXAMPLE, two, 3.516, 2)
    assert got.period == ("F27", "H27")
    assert got.fixed_price.tolist() == [4.52, 3.02]
    assert got.average == pytest.approx(3.52, **CLOSE)
    assert got.difference == pytest.approx(0.004, abs=1e-12)
    # The other way round the quote is 4.00, and an agreed 4.00 moves nothing.
    turned = request(("F27", "H27"), (20_000.0, 10_000.0), bilateral(), ix=LONGER)
    assert fitted(EXAMPLE, turned, 4.0, 2).fixed_price.tolist() == [4.5, 3.0]
    # A common scale of the quantities changes nothing but the column that shows them.
    scaled = request(("F27", "H27"), (1.0, 2.0), bilateral(), ix=LONGER)
    assert fitted(EXAMPLE, scaled, 3.516, 2).fixed_price.tolist() == [4.52, 3.02]
    assert fitted(EXAMPLE, scaled, 3.516, 2).average == got.average


def test_a_month_of_no_quantity_takes_a_fixed_price_and_no_share() -> None:
    # February at nothing: the quote is January's and March's alone, 3.75, and February is moved
    # and rounded as they are, its price in no average.
    got = fitted(EXAMPLE, the_months((1.0, 0.0, 1.0)), 3.76, 2)
    assert got.fixed_price.tolist() == [4.51, 4.31, 3.01]
    assert got.average == pytest.approx(3.76, **CLOSE)
    assert got.difference == 0.0


# --- the request's own quote ----------------------------------------------------------------------


def test_at_the_requests_own_quote_the_fixed_prices_are_the_curves_and_the_difference_is_zero() -> (
    None
):
    # The agreed price the cell of `_QuoteRFQ(market, rfq, "ftc", rates)` itself: nothing is
    # moved, the fixed prices are the curve's own at the decimals it is quoted to, and the
    # difference is zero exactly, not the sixteenth digit's dust, though a month's own price is
    # a sum of twenty weighted observations and carries it.
    for quantities in (EQUAL, (3_100_000.0, 280_000.0, 310_000.0), (1.0, 2.0, 3.0)):
        saved = the_months(quantities)
        quote = by_request(EXAMPLE, saved, "ftc", RATES)
        got = fitted(EXAMPLE, saved, quote, 2)
        assert got.fixed_price.tolist() == list(PRICES)
        assert got.difference == 0.0
        assert got.average == pytest.approx(quote, rel=1e-14)
        assert got.agreed == quote
    # A cleared request of the same rows is the same table: no curve is taken, and the route,
    # which says whether a quote discounts, says nothing here.
    route = request(CODES, EQUAL, financial(), ix=LONGER)
    assert fitted(EXAMPLE, route, AGREED, 2).fixed_price.tolist() == [4.52, 4.32, 3.02]
    assert (
        fitted(EXAMPLE, route, AGREED, 2).average
        == fitted(EXAMPLE, the_months(), AGREED, 2).average
    )


def test_every_component_is_moved_by_the_same_amount() -> None:
    saved = the_months((3.0, 1.0, 2.0))
    quote = by_request(EXAMPLE, saved, "ftc", RATES)
    for price in (quote + 0.25, quote - 1.0, 0.0, -7.5):
        got = fitted(EXAMPLE, saved, price, 12)
        assert got.fixed_price - got.curve_price == pytest.approx(price - quote, abs=1e-11)
        assert got.average == pytest.approx(price, abs=1e-11)
        assert got.difference == pytest.approx(0.0, abs=1e-11)


# --- the rounding ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("price", "decimals", "expected"),
    [
        (4.515, 2, 4.52),  # the cell holds a hair under 4.515; its hundredth by the bits is 4.51
        (4.505, 2, 4.51),
        (2.675, 2, 2.68),
        (-2.675, 2, -2.68),  # away from zero either side
        (1.005, 2, 1.01),
        (0.125, 2, 0.13),  # a half the bits hold exactly
        (0.135, 2, 0.14),
        (2.5, 0, 3.0),
        (-2.5, 0, -3.0),
        (0.5, 0, 1.0),
        (1.5, 0, 2.0),
        (3.4999999, 0, 3.0),  # under a half by more than a cell's fifteen digits
        (451.4999999, 0, 451.0),
        (4.51, 2, 4.51),  # already at the decimals
        (4.5, 2, 4.5),
        (82.51, 15, 82.51),  # more decimals than the number holds change nothing
        (35.784148397976395, 4, 35.7841),
        (0.0, 2, 0.0),
        (1e20, 2, 1e20),  # no digit at the hundredths: left as it is
        (-1e20, 0, -1e20),
        (1.7e308, 15, 1.7e308),  # in steps past the largest number: left as it is
        (1e-320, 15, 0.0),
    ],
)
def test_a_price_rounds_as_the_sheets_round_rounds(
    price: float, decimals: int, expected: float
) -> None:
    assert rounded(np.array([price]), decimals).tolist() == [expected]


def test_a_price_that_rounds_to_nothing_is_zero_and_never_minus_zero() -> None:
    got = rounded(np.array([-0.001, -0.004, 0.004, -0.0]), 2)
    assert got.tolist() == [0.0, 0.0, 0.0, 0.0]
    assert not np.signbit(got).any()


def test_a_number_is_read_to_the_fifteen_digits_a_cell_shows() -> None:
    # The reading the rounding and the check share: the nearest number of fifteen significant
    # digits, a typed number itself, a sum's dust gone, the sign kept and a large number left.
    dusty = 4.299999999999999  # February's own price above: twenty weighted settles of 4.30
    assert dusty != 4.3
    assert as_shown(np.array([dusty, 3.95, -dusty, 0.0, 1e15, 3.9333333333333336])).tolist() == [
        4.3,
        3.95,
        -4.3,
        0.0,
        1e15,
        3.93333333333333,
    ]


@given(
    prices=st.lists(
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=30,
    ),
    decimals=st.integers(min_value=0, max_value=8),
)
def test_every_rounded_price_is_at_the_decimals_and_within_half_a_step(
    prices: list[float], decimals: int
) -> None:
    price = np.array(prices)
    got = rounded(price, decimals)
    step = 10.0**-decimals
    # Within half a step, and a hair for the fifteenth digit the reading may move.
    assert (np.abs(got - price) <= step / 2 + np.abs(price) * 1e-14 + 1e-300).all()
    # A whole number of steps: the same number typed at those decimals.
    assert got.tolist() == [float(f"{value:.{decimals}f}") for value in got.tolist()]
    # Rounded once is rounded.
    assert rounded(got, decimals).tolist() == got.tolist()
    # Away from zero or toward it alike either side of it.
    assert rounded(-price, decimals).tolist() == (-got + 0.0).tolist()


@given(
    price=st.floats(min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    decimals=st.integers(min_value=0, max_value=6),
    quantities=st.tuples(*[st.floats(min_value=0.5, max_value=1e6)] * 3),
)
def test_the_average_is_within_half_a_step_of_the_agreed_price(
    price: float, decimals: int, quantities: tuple[float, float, float]
) -> None:
    # Each fixed price is within half a step of its unrounded one, and the unrounded ones average
    # to the agreed price, so the fixed prices' average is within half a step of it too.
    saved = the_months(quantities)
    got = fitted(EXAMPLE, saved, price, decimals)
    step = 10.0**-decimals
    moved = got.curve_price + (price - by_request(EXAMPLE, saved, "ftc", RATES))
    assert (np.abs(got.fixed_price - moved) <= step / 2 + 1e-12).all()
    assert abs(got.difference) <= step / 2 + 1e-12


# --- prices at zero and below, windows and calendar days ------------------------------------------


def test_prices_at_zero_and_below_are_moved_and_rounded_as_any() -> None:
    # A basis strip at 0.02, -0.50 and 0.00: the quote is -0.48 / 3 = -0.16, and agreed at -0.15
    # each month takes a cent, 0.03, -0.49 and 0.01, which come back to -0.15 exactly. A
    # percentage would have had no meaning here.
    basis = priced(LONGER, DEC_31, 3.0, 0.02, -0.50, 0.0)
    got = fitted(basis, the_months(), -0.15, 2)
    assert got.curve_price == pytest.approx([0.02, -0.50, 0.0], abs=1e-15)
    assert got.fixed_price.tolist() == [0.03, -0.49, 0.01]
    assert got.average == pytest.approx(-0.15, **CLOSE)
    assert got.difference == 0.0
    # Agreed at zero: 0.18, -0.34 and 0.16.
    assert fitted(basis, the_months(), 0.0, 2).fixed_price.tolist() == [0.18, -0.34, 0.16]


def test_a_request_of_windows_takes_a_fixed_price_per_window() -> None:
    # The two windows of the request tests, 100,000 from 11 January to 26 February at 39/35 and
    # 300,000 over February's at 1.20: the quote is their average by quantity, and each window
    # is a row under its two dates.
    saved = windows()
    quote = (100_000 * WINDOW_PRICE + 300_000 * 1.2) / 400_000
    got = fitted(STRIP_MARKET, saved, quote + 0.01, 4)
    assert got.period[0] == WINDOW_WORDS
    assert got.quantity.tolist() == [100_000.0, 300_000.0]
    assert got.curve_price == pytest.approx([WINDOW_PRICE, 1.2], **CLOSE)
    assert got.fixed_price.tolist() == [round(WINDOW_PRICE + 0.01, 4), 1.21]


def test_a_request_per_calendar_day_weighs_each_month_by_its_days() -> None:
    # 100 a day: 3,100, 2,800 and 3,100, the quantities the quote weighs and the column shows.
    saved = the_months((100.0, 100.0, 100.0), per="calday")
    got = fitted(EXAMPLE, saved, AGREED, 2)
    assert got.quantity.tolist() == [3_100.0, 2_800.0, 3_100.0]
    quote = (31 * 4.50 + 28 * 4.30 + 31 * 3.00) / 90
    assert got.fixed_price.tolist() == [round(p + AGREED - quote, 2) for p in PRICES]
    assert got.average == pytest.approx(float(got.quantity @ got.fixed_price) / 9_000, **CLOSE)


# --- the work and the refusals --------------------------------------------------------------------


def test_no_curve_is_taken_and_no_factor_read() -> None:
    counter = WorkCounter()
    fitted(EXAMPLE, the_months(), AGREED, 2, counter)
    assert counter.freeze().as_dict() == {
        "fixings_read": 0,
        "live_prices_read": 3,
        "price_reductions": 5,
        "prices_rounded": 3,
    }


def test_the_decimals_are_from_none_to_fifteen() -> None:
    assert fitted(EXAMPLE, the_months(), AGREED, 15).fixed_price == pytest.approx(
        [4.5 + AGREED - 11.8 / 3, 4.3 + AGREED - 11.8 / 3, 3.0 + AGREED - 11.8 / 3], abs=1e-12
    )
    refused(
        "decimals is -1, expected a whole number from 0 to 15, the decimals a fixed price may hold",
        decimals=-1,
    )
    refused(
        "decimals is 16, expected a whole number from 0 to 15, the decimals a fixed price may hold",
        decimals=16,
    )


def test_the_market_is_the_requests_and_its_rules_stand() -> None:
    refused(
        "market is over another index, 'STRIP', expected the request's, 'LONGER'",
        market=STRIP_MARKET,
    )
    # The decimals are read before the market, and the market before any price.
    refused(
        "decimals is 99, expected a whole number from 0 to 15, the decimals a fixed price may hold",
        decimals=99,
        market=STRIP_MARKET,
    )
    # A physical request's contracts have not expired, as its quote holds them.
    delivered = request(("F27",), (1.0,), physical(), ix=STRIP)
    with pytest.raises(ValueError, match=r"^F27 expired 2027-01-29, before valuation date"):
        fitted(priced(STRIP, "2027-02-01", 3.0, 60.0), delivered, 60.0, 2)
    assert fitted(STRIP_MARKET, delivered, 1.004, 2).fixed_price.tolist() == [1.0]


def test_a_price_the_curves_cannot_be_moved_to_is_refused_by_its_month() -> None:
    # Prices of 1e308 either side of nothing quote zero; moved up by 1e308 the first is past the
    # largest number.
    wide = priced(LONGER, DEC_31, 3.0, 1e308, -1e308, 0.0)
    with pytest.raises(
        ValueError,
        match=(
            r"^price is 1e\+308, expected a price the request's own can be moved to; F27 at "
            r"\S+, moved by the price less the fit-to-curve quote of \S+, outruns the largest "
            r"number$"
        ),
    ):
        fitted(wide, the_months(), 1e308, 2)
    assert np.isfinite(fitted(wide, the_months(), 0.0, 2).fixed_price).all()


# --- through the seam -----------------------------------------------------------------------------


def test_the_worksheet_function_spills_the_check_over_the_months_through_the_seam() -> None:
    ix, _ = seam_index(
        "SEAM",
        [
            ("Z26", "2026-12-15"),
            ("F27", "2027-01-29"),
            ("G27", "2027-02-26"),
            ("H27", "2027-03-31"),
        ],
        ["2027-01-01"],
        [("BBL", 1.0)],
        ("VOLUME", "BBL"),
    )
    history = seam_history(ix, "2026-12-16", DEC_31, ["2027-01-01"], {})
    market = seam_market(history, "SEAM", *PRICES)
    weekends = seam_key(ENTRY["_CreateHolidayCalendar"](a_name(), column([serial("2030-01-01")])))
    template = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        row(*FIELDS),
        row("cleared", "financial", "asian", "month", "+1bd", weekends, "monthly", 1.0),
    )
    ticket = cells_of(*[[code, quantity] for code, quantity in zip(CODES, EQUAL, strict=True)])
    saved = ENTRY["_CreateRFQ"](ix, row("contract_code", "quantity"), ticket, template)
    table = spilled(ENTRY["_QuoteFTCPrices"](market, saved, AGREED, 2.0))
    assert table[0][0] == "agreed_price" and table[0][1] == AGREED
    assert table[1][0] == "average_fixed_price"
    assert table[1][1] == pytest.approx(11.86 / 3, **CLOSE)
    assert table[2][0] == "difference"
    assert table[2][1] == pytest.approx(11.86 / 3 - AGREED, abs=1e-12)
    assert [each[2:] for each in table[:3]] == [["-", "-"]] * 3
    assert table[3] == ["period", "quantity", "curve_price", "fixed_price"]
    assert table[4] == ["str", "float64", "float64", "float64"]
    assert [each[0] for each in table[5:]] == list(CODES)
    assert [each[1] for each in table[5:]] == list(EQUAL)
    assert [each[2] for each in table[5:]] == pytest.approx(PRICES, **CLOSE)
    assert [each[3] for each in table[5:]] == [4.52, 4.32, 3.02]
    assert len(table) == 8 and {len(each) for each in table} == {4}
    # The agreed price the quote's own cell: the curve's prices and a difference of zero.
    quote = ENTRY["_QuoteRFQ"](market, saved, "ftc", bridge.MISSING)
    at_quote = spilled(ENTRY["_QuoteFTCPrices"](market, saved, quote, 2.0))
    assert at_quote[2][1] == 0.0
    assert [each[3] for each in at_quote[5:]] == list(PRICES)
    # The seam's refusals of each argument alone, by type and shape, then the library's.
    assert ENTRY["_QuoteFTCPrices"](market, saved, None, 2.0) == (
        "#ERROR _QuoteFTCPrices: price is blank, expected number"
    )
    assert ENTRY["_QuoteFTCPrices"](market, saved, "3.95", 2.0) == (
        "#ERROR _QuoteFTCPrices: price is text '3.95', expected number"
    )
    assert ENTRY["_QuoteFTCPrices"](market, saved, AGREED, bridge.MISSING) == (
        "#ERROR _QuoteFTCPrices: decimals is missing, expected whole number"
    )
    assert ENTRY["_QuoteFTCPrices"](market, saved, AGREED, 2.5) == (
        "#ERROR _QuoteFTCPrices: decimals is number 2.5, expected whole number"
    )
    assert ENTRY["_QuoteFTCPrices"](market, saved, AGREED, True) == (
        "#ERROR _QuoteFTCPrices: decimals is boolean TRUE, expected whole number"
    )
    assert ENTRY["_QuoteFTCPrices"](market, saved, AGREED, 16.0) == (
        "#ERROR _QuoteFTCPrices: ValueError: decimals is 16, expected a whole number from 0 to "
        "15, the decimals a fixed price may hold"
    )
    assert str(ENTRY["_QuoteFTCPrices"](saved, saved, AGREED, 2.0)).startswith(
        "#ERROR _QuoteFTCPrices: market is "
    )
    assert str(ENTRY["_QuoteFTCPrices"](market, market, AGREED, 2.0)).startswith(
        "#ERROR _QuoteFTCPrices: rfq is "
    )
