"""The quote: one whole-period indicative fixed price for a contract or strip on one market from a
quote template's static terms, template-based-quoting.md's worked acceptance by hand: the cleared
and bilateral strip, the key and its curve, fixings and methods, an IFERC month, CAL27 in June27,
the rules of the terms, the collection, the period and the market, an equivalent trade booked at
the quote marking zero, and the worksheet function through the seam.
docs/library/quoting/quote.md is the page."""

import re
from collections.abc import Callable
from types import MappingProxyType

import numpy as np
import pytest
from test_bilateral_kernel import CLOSE, curve_of, curve_set
from test_market import a_gas_daily_history
from test_trade_valuation import a_history as seam_history
from test_trade_valuation import a_market as seam_market
from test_trade_valuation import an_index as seam_index
from test_trade_valuation import column, row, serial
from test_trade_valuation import rows as cells_of
from test_trades import (
    an_index,
    bounds_of,
    dates,
    day,
    ids,
    numbers,
    observed_of,
    picks,
    quoted,
    rows,
    spec,
)

from goosedove.calendar.calendar import calendar
from goosedove.excel import bridge
from goosedove.globals.discount_curve import bump_discount_curve
from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.globals.payments import factors_on
from goosedove.globals.unit_conversions import UNITS
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.index_definitions.periods import end_date, start_date
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT
from goosedove.market.market import Market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.futures_fixings import futures_fixings
from goosedove.market_data.iferc_fixings import iferc_fixings
from goosedove.quoting.quote import quote
from goosedove.quoting.template import QuoteTemplate
from goosedove.trades.encoding import encoded
from goosedove.trades.evaluation import trade_results
from goosedove.trades.preparation import prepared_trades
from goosedove.trades.schedule_methods import ScheduleMethod
from goosedove.trades.terms import PaymentTerms, QuantityPer, Route, Settlement, resolved_trades

ENTRY = {
    name: bridge.entry(name)
    for name in (
        "_Quote",
        "_CreateQuoteTemplate",
        "_CreateTradeTemplate",
        "_CreateHolidayCalendar",
        "_CreateDiscountCurve",
        "_CollectDiscountCurves",
    )
}

# The ticket's strip: a futures index quoted in dollars a barrel, Z26 bounding the calendar, F27
# and G27 month-matching, the market closed on weekends and New Year's Day, so that January's last
# observation is Friday the 29th and February's Friday the 26th; a payment calendar closing on
# weekends alone within these years; valued on 31 December 2026 with both months entirely live.
LETTERS = "FGHJKMNQUVXZ"
DEC_31 = "2026-12-31"
STRIP = an_index(
    "STRIP",
    (("Z26", "2026-12-15"), ("F27", "2027-01-29"), ("G27", "2027-02-26")),
    ("2027-01-01",),
    ("USD", "BBL"),
    ("VOLUME", "BBL"),
    ("BBL", 1.0, "BBL"),
)
WEEKENDS_ONLY = holiday_calendar(dates("2030-01-01"))
# The ordinary named curve: 1 on the valuation day, 0.99 on 1 February and 0.98 on 1 March, the
# two payment days of +1bd; a second with visibly different factors; a flat one.
SOFR = curve_of((DEC_31, 1.0), ("2027-02-01", 0.99), ("2027-03-01", 0.98))
FFOIS = curve_of((DEC_31, 1.0), ("2027-02-01", 0.95), ("2027-03-01", 0.90), name="FFOIS")
FLAT = curve_of((DEC_31, 1.0), ("2027-02-01", 0.98), ("2027-03-01", 0.98), name="FLAT")
RATES = curve_set(SOFR)
MONTH_CLEARED, MONTH_BILATERAL = 45.0, 88.5 / 1.97
CALDAY_CLEARED, CALDAY_BILATERAL = 2610 / 59, 2567.1 / 58.13


def a_template(**values: object) -> QuoteTemplate:
    return QuoteTemplate(FIXED_FLOAT, tuple(values), MappingProxyType(dict(values)))


def financial(
    route: str = "cleared",
    method: str = "asian",
    per: str = "month",
    lag: str = "+1bd",
    payment_calendar: object = WEEKENDS_ONLY,
    key: str | None = None,
) -> QuoteTemplate:
    values: dict[str, object] = {
        "route": route,
        "settlement_method": "financial",
        "schedule_method": method,
        "quantity_per": per,
        "payment_time_lag": lag,
        "payment_holiday_calendar": payment_calendar,
    }
    if key is not None:
        values["discount_curve_key"] = key
    return a_template(**values)


def bilateral(
    key: str = "SOFR",
    method: str = "asian",
    per: str = "month",
    lag: str = "+1bd",
    payment_calendar: object = WEEKENDS_ONLY,
) -> QuoteTemplate:
    return financial("bilateral", method, per, lag, payment_calendar, key)


def physical(method: str = "lastday", per: str = "month") -> QuoteTemplate:
    return a_template(
        route="cleared", settlement_method="physical", schedule_method=method, quantity_per=per
    )


Settle = Callable[[np.datetime64], float] | float


def a_history(ix: Index, as_of: str, settle: Settle) -> MarketHistory:
    """The index's history valued on that day: a settle on every fixed business day of its
    calendar, the number given or the number a function gives each day, newest first as the
    fixings creator takes them."""
    cal = calendar(valuation_date(day(as_of), 0.5), ix)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = np.array(
        [settle(d) if callable(settle) else settle for d in priced], dtype=np.float64
    )
    return market_history(cal, futures_fixings(priced[::-1].copy(), settles[::-1].copy(), ix))


def priced(ix: Index, as_of: str, settle: Settle, *quotes: float) -> Market:
    """The index's market on that day: the history and the quotes from the prompt contract on."""
    return quoted(a_history(ix, as_of, settle), *quotes)


def quote_on(
    market: Market,
    code: str,
    template: QuoteTemplate,
    curves: DiscountCurveSet | None = None,
    counter: WorkCounter | None = None,
) -> float:
    return quote(market, code, template, curves, counter or WorkCounter())


def refused(
    market: Market,
    code: str,
    template: QuoteTemplate,
    message: str,
    curves: DiscountCurveSet | None = None,
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        quote_on(market, code, template, curves)


def counts_of(
    market: Market, code: str, template: QuoteTemplate, curves: DiscountCurveSet | None = None
) -> dict[str, int]:
    counter = WorkCounter()
    quote_on(market, code, template, curves, counter)
    return counter.freeze().as_dict()


# --- the cleared and bilateral strip --------------------------------------------------------------


def test_the_cleared_and_bilateral_strip_by_hand() -> None:
    # January 30 and February 60, entirely live; month weights 1 and 1, calendar-day weights 31
    # and 28; the factors 0.99 and 0.98 on 1 February and 1 March, where +1bd pays.
    m = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    assert quote_on(m, "F27-G27", financial()) == pytest.approx(MONTH_CLEARED, **CLOSE)
    assert quote_on(m, "F27-G27", bilateral(), RATES) == pytest.approx(MONTH_BILATERAL, **CLOSE)
    assert quote_on(m, "F27-G27", financial(per="calday")) == pytest.approx(CALDAY_CLEARED, **CLOSE)
    assert quote_on(m, "F27-G27", bilateral(per="calday"), RATES) == pytest.approx(
        CALDAY_BILATERAL, **CLOSE
    )
    # January alone quotes 30 under both routes and both bases: one payment's factor cancels.
    for template, curves in (
        (financial(), None),
        (bilateral(), RATES),
        (financial(per="calday"), None),
        (bilateral(per="calday"), RATES),
    ):
        assert quote_on(m, "F27", template, curves) == pytest.approx(30.0, **CLOSE)
    assert quote_on(m, "f27-g27", financial()) == pytest.approx(MONTH_CLEARED, **CLOSE)
    # With the two prices reversed the equal-month cleared quote stands and the bilateral one
    # moves: a scalar cleared price cannot be passed on to recover the bilateral one.
    reverse = priced(STRIP, DEC_31, 3.0, 60.0, 30.0)
    assert quote_on(reverse, "F27-G27", financial()) == pytest.approx(MONTH_CLEARED, **CLOSE)
    assert quote_on(reverse, "F27-G27", bilateral(), RATES) == pytest.approx(88.8 / 1.97, **CLOSE)


def test_the_key_selects_its_curve_and_no_other_curve_is_read() -> None:
    m = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    both = curve_set(SOFR, FFOIS)
    on_ffois = (0.95 * 30 + 0.90 * 60) / (0.95 + 0.90)
    assert quote_on(m, "F27-G27", bilateral("FFOIS"), both) == pytest.approx(on_ffois, **CLOSE)
    assert quote_on(m, "F27-G27", bilateral("FFOIS"), curve_set(FFOIS, SOFR)) == pytest.approx(
        on_ffois, **CLOSE
    )
    assert quote_on(m, "F27-G27", bilateral(), both) == pytest.approx(MONTH_BILATERAL, **CLOSE)
    # One factor on every payment cancels: the bilateral quote is the cleared one.
    assert quote_on(m, "F27-G27", bilateral("FLAT"), curve_set(FLAT)) == pytest.approx(
        MONTH_CLEARED, **CLOSE
    )
    # Updating the selected curve alone reprices the quote over the same template and market.
    moved = curve_of((DEC_31, 1.0), ("2027-02-01", 0.97), ("2027-03-01", 0.95))
    assert quote_on(m, "F27-G27", bilateral(), curve_set(moved, FFOIS)) == pytest.approx(
        (0.97 * 30 + 0.95 * 60) / (0.97 + 0.95), **CLOSE
    )
    # An unused member starting on another day or stopping short fails nothing and is never
    # read: one curve selected, two factors read, the selected curve's.
    late = curve_of(("2027-01-04", 1.0), ("2027-02-01", 0.9), name="LATE")
    short = curve_of((DEC_31, 1.0), ("2027-02-15", 0.9), name="SHORT")
    counts = counts_of(m, "F27-G27", bilateral(), curve_set(late, short, SOFR))
    assert (counts["curves_selected"], counts["payment_factors_read"]) == (1, 2)
    refused(
        m,
        "F27-G27",
        bilateral("LATE"),
        "discount curve 'LATE' starts on 2027-01-04, expected 2026-12-31, the valuation date; a "
        "curve is never rebased",
        curve_set(late, SOFR),
    )
    refused(
        m,
        "F27-G27",
        bilateral("SHORT"),
        "the payment of G27 on 2027-03-01 on SHORT is past the discount curve 'SHORT', which "
        "runs from 2026-12-31 to 2027-02-15; expected every payment day after the valuation date "
        "covered",
        curve_set(short),
    )
    refused(
        m,
        "F27-G27",
        bilateral(),
        "discount_curve_key 'SOFR' names no curve of the collection, which holds 'FFOIS'; "
        "expected a curve of that name",
        curve_set(FFOIS),
    )
    # A bump scenario: bumped SOFR in a new collection in place of the base, the two never
    # together, since both are named SOFR and the collection refuses the repeat.
    bumped = bump_discount_curve(SOFR, 100.0, WorkCounter())
    assert quote_on(m, "F27-G27", bilateral(), curve_set(bumped, FFOIS)) != pytest.approx(
        MONTH_BILATERAL, **CLOSE
    )
    with pytest.raises(ValueError, match=r"^curve_handles cell 1 and cell 2 are both named 'SOFR'"):
        curve_set(SOFR, bumped)


def test_a_payment_holiday_moves_one_factor_and_the_cleared_price_stands() -> None:
    # 1 February closed on the payment calendar moves January's payment to the 2nd, whose factor
    # lies between the curve's anchors; February's stands, so the bilateral price moves alone.
    m = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    closed = holiday_calendar(dates("2027-02-01"))
    feb_2 = float(factors_on(SOFR, dates("2027-02-02"))[0])
    assert 0.98 < feb_2 < 0.99
    assert quote_on(m, "F27-G27", bilateral(payment_calendar=closed), RATES) == pytest.approx(
        (feb_2 * 30 + 0.98 * 60) / (feb_2 + 0.98), **CLOSE
    )
    assert quote_on(m, "F27-G27", financial(payment_calendar=closed)) == pytest.approx(
        MONTH_CLEARED, **CLOSE
    )


# --- fixings and methods --------------------------------------------------------------------------


def january(price: float) -> Callable[[np.datetime64], float]:
    """A settle on January's fixed days, 3.00 on December's, which no quote observes."""
    return lambda d: price if d >= day("2027-01-01") else 3.0


def test_fixings_and_live_prices_share_a_month() -> None:
    # Valued on Monday 11 January: five fixings, the 4th to the 8th, and fifteen live days.
    m = priced(STRIP, "2027-01-11", january(25.0), 29.0, 60.0)
    rates = curve_set(curve_of(("2027-01-11", 1.0), ("2027-02-01", 0.99)))
    assert quote_on(m, "F27", financial()) == pytest.approx(28.0, **CLOSE)
    assert quote_on(m, "F27", bilateral(), rates) == pytest.approx(28.0, **CLOSE)
    up = priced(STRIP, "2027-01-11", january(25.0), 30.0, 60.0)
    assert quote_on(up, "F27", financial()) == pytest.approx(28.75, **CLOSE)

    def corrected(d: np.datetime64) -> float:
        return 27.0 if d == day("2027-01-06") else january(25.0)(d)

    assert quote_on(priced(STRIP, "2027-01-11", corrected, 29.0, 60.0), "F27", financial()) == (
        pytest.approx(28.1, **CLOSE)
    )
    counts = counts_of(m, "F27", financial())
    assert (counts["observations_made"], counts["fixings_read"], counts["live_prices_read"]) == (
        20,
        5,
        1,
    )


# December 2026 has 22 pricing days, weekends and Christmas closed; F27 expires on Monday the
# 21st, its 15th, so the calendar prices the first fifteen by F27 and the last seven by G27.
ROLL = an_index(
    "ROLL",
    (("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-21"), ("G27", "2027-01-27")),
    ("2026-11-26", "2026-12-25"),
)


def test_an_asian_month_follows_the_calendars_pricing_contract_through_a_roll() -> None:
    live = priced(ROLL, "2026-12-01", 3.0, 70.0, 76.0)  # the prompt on 1 December is F27
    assert quote_on(live, "Z26", financial()) == pytest.approx(1582 / 22, **CLOSE)

    def settle(d: np.datetime64) -> float:
        return 70.0 if d <= day("2026-12-21") else 76.0

    # After the roll, valued on the 28th: eighteen fixed days off the history and four live days
    # off G27, the one quote the market carries; F27 has expired and is never requested.
    rolled = priced(ROLL, "2026-12-28", settle, 76.0)
    assert quote_on(rolled, "Z26", financial()) == pytest.approx(1582 / 22, **CLOSE)
    counts = counts_of(rolled, "Z26", financial())
    assert (counts["fixings_read"], counts["live_prices_read"]) == (18, 1)


# F27 expires Friday 29 January 2027 with Thursday the 28th a holiday on the index's calendar.
EXPIRY = an_index(
    "EXPIRY",
    (("Z26", "2026-12-15"), ("F27", "2027-01-29"), ("G27", "2027-02-26")),
    ("2027-01-01", "2027-01-28"),
)


def test_the_expiry_based_methods_by_hand_with_a_holiday_before_the_expiry() -> None:
    marks = {day("2027-01-26"): 31.0, day("2027-01-27"): 32.0, day("2027-01-29"): 33.0}

    def settle(d: np.datetime64) -> float:
        return marks.get(d, 3.0)

    m = priced(EXPIRY, "2027-02-01", settle, 40.0)  # the prompt on 1 February is G27
    rates = curve_set(curve_of(("2027-02-01", 1.0), ("2027-03-01", 0.98)))
    assert quote_on(m, "F27", financial(method="lastday")) == 33.0
    assert quote_on(m, "F27", financial(method="penultimate")) == 32.0  # the 27th, past the holiday
    assert quote_on(m, "F27", financial(method="last3day")) == pytest.approx(32.0, **CLOSE)
    # lastday pays +1bd from the 29th: 1 February, the valuation day, factor one and no read.
    assert quote_on(m, "F27", bilateral(method="lastday"), rates) == 33.0
    counts = counts_of(m, "F27", bilateral(method="lastday"), rates)
    assert (counts["fixings_read"], counts["payment_factors_read"]) == (1, 0)
    # The strip adds G27, live at 40 and paying 1 March at 0.98, through the same path.
    assert quote_on(m, "F27-G27", bilateral(method="lastday"), rates) == pytest.approx(
        (33 + 40 * 0.98) / 1.98, **CLOSE
    )
    assert quote_on(m, "F27-G27", financial(method="lastday")) == pytest.approx(36.5, **CLOSE)


# A Waha-like IFERC index: three months published on their first business days.
WAHA = index(
    "WAHA",
    "Waha basis - ICE",
    iferc_schedule(("X26", "Z26", "F27"), dates("2026-11-02", "2026-12-01", "2027-01-04")),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("LOT",), numbers(2500.0), ("MMBTU",), numbers(0.0), numbers(0.0), UNITS
    ),
    None,
    "LOT",
    UNITS,
)


def test_an_iferc_month_observes_its_publication_day_and_pays_from_it() -> None:
    cal = calendar(valuation_date(day("2026-11-15"), 0.5), WAHA)
    m = quoted(market_history(cal, iferc_fixings(("X26",), numbers(0.5), WAHA)), -0.4, -0.3)
    waha = financial(method="lastday", lag="+2bd")
    assert quote_on(m, "Z26", waha) == -0.4
    counts = counts_of(m, "Z26", waha)
    assert (counts["observations_made"], counts["live_prices_read"], counts["fixings_read"]) == (
        1,
        1,
        0,
    )
    assert quote_on(m, "X26", waha) == 0.5  # published 2 November, fixed: nothing live is read
    assert counts_of(m, "X26", waha)["live_prices_read"] == 0
    # The payment counts from the publication day: Z26's 1 December +2bd is the 3rd, discounted;
    # X26's 4 November has passed, factor one.
    rates = curve_set(curve_of(("2026-11-15", 1.0), ("2026-12-03", 0.99)))
    keyed = bilateral(method="lastday", lag="+2bd")
    assert quote_on(m, "X26-Z26", keyed, rates) == pytest.approx((0.5 - 0.4 * 0.99) / 1.99, **CLOSE)
    assert counts_of(m, "X26-Z26", keyed, rates)["payment_factors_read"] == 1
    refused(
        m,
        "Z26",
        financial(method="asian", lag="+2bd"),
        "schedule_method is 'asian', expected 'lastday' on an IFERC index; an IFERC month has one "
        "index, published once",
    )
    refused(
        m,
        "Z26",
        physical(),
        "settlement_method is 'physical', expected 'financial' on an IFERC index; an IFERC basis "
        "future is cash settled on its month's published index",
    )


LEAP = an_index("LEAP", (("Z27", "2027-12-31"), ("F28", "2028-01-31"), ("G28", "2028-02-29")), ())


def test_a_leap_february_counts_its_twenty_nine_days() -> None:
    m = priced(LEAP, "2028-01-03", 3.0, 10.0, 20.0)
    assert quote_on(m, "F28-G28", financial(per="calday")) == pytest.approx(890 / 60, **CLOSE)
    assert quote_on(m, "F28-G28", financial()) == pytest.approx(15.0, **CLOSE)


def test_a_fully_fixed_month_discounts_its_unpaid_payment_and_a_payment_today_takes_one() -> None:
    m = priced(STRIP, "2027-02-01", january(30.0), 60.0)  # the prompt on 1 February is G27
    # +3bd: January, fixed at 30 through the 29th, pays 3 February, after the valuation day, so
    # its factor is read; February's 3 March too.
    three = curve_of(("2027-02-01", 1.0), ("2027-02-03", 0.995), ("2027-03-03", 0.98))
    assert quote_on(m, "F27-G27", bilateral(lag="+3bd"), curve_set(three)) == pytest.approx(
        (0.995 * 30 + 0.98 * 60) / (0.995 + 0.98), **CLOSE
    )
    assert (
        counts_of(m, "F27-G27", bilateral(lag="+3bd"), curve_set(three))["payment_factors_read"]
        == 2
    )
    # +1bd: January pays 1 February, the valuation day itself, factor one and no read for it.
    one = curve_set(curve_of(("2027-02-01", 1.0), ("2027-03-01", 0.98)))
    assert quote_on(m, "F27-G27", bilateral(), one) == pytest.approx(
        (30 + 0.98 * 60) / 1.98, **CLOSE
    )
    assert counts_of(m, "F27-G27", bilateral(), one)["payment_factors_read"] == 1


def test_a_physical_quote_takes_lastday_before_the_expiry_alone() -> None:
    before = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    assert quote_on(before, "F27", physical()) == 30.0
    assert quote_on(before, "F27-G27", physical(per="calday")) == pytest.approx(
        CALDAY_CLEARED, **CLOSE
    )
    assert quote_on(priced(STRIP, "2027-01-29", 3.0, 30.0, 60.0), "F27", physical()) == 30.0
    refused(
        priced(STRIP, "2027-02-01", 3.0, 60.0),
        "F27",
        physical(),
        "F27 expired 2027-01-29, before valuation date 2027-02-01; a physical fixed_float after "
        "its expiry is not supported",
    )
    for method, settled in (
        ("asian", "an asian future is cash settled on the average of its month's pricing days"),
        (
            "last3day",
            "a last3day future is cash settled on the average of its last three pricing days",
        ),
        (
            "penultimate",
            "a penultimate future is cash settled on the business day before its contract's expiry",
        ),
    ):
        refused(
            before,
            "F27",
            physical(method=method),
            f"settlement_method is 'physical', expected 'financial' with the {method} method; "
            f"{settled}",
        )
    refused(
        before,
        "F27",
        a_template(
            route="bilateral",
            settlement_method="physical",
            schedule_method="lastday",
            quantity_per="month",
            discount_curve_key="SOFR",
        ),
        "settlement_method is 'physical', expected 'financial' with route = bilateral; a physical "
        "delivery has no payment to discount",
        RATES,
    )


# --- CAL27 in June27 ------------------------------------------------------------------------------

# Every month of 2027 expiring on its last calendar day, Z26 bounding the calendar, the market
# closed on weekends alone; valued on Wednesday 16 June 2027.
MONTH_ENDS = np.arange("2027-02", "2028-02", dtype="datetime64[M]").astype(
    "datetime64[D]"
) - np.timedelta64(1, "D")
CAL = an_index(
    "CAL",
    (("Z26", "2026-12-31"), *((f"{LETTERS[i]}27", str(MONTH_ENDS[i])) for i in range(12))),
    (),
)
JUNE_16 = "2027-06-16"


def june(fixed: float = 38.0, earlier: float = 30.0) -> Callable[[np.datetime64], float]:
    return lambda d: fixed if d >= day("2027-06-01") else earlier


def in_june(settle: Callable[[np.datetime64], float], *quotes: float) -> Market:
    """The market on 16 June: M27 at the first quote and N27 through Z27 at the rest."""
    return priced(CAL, JUNE_16, settle, *quotes)


def test_cal27_in_june27_by_hand() -> None:
    m = in_june(june(), 42.0, *[40.0] * 6)
    rates = curve_set(curve_of((JUNE_16, 1.0), ("2027-07-01", 0.98), ("2028-01-03", 0.98)))
    assert quote_on(m, "CAL27", financial()) == pytest.approx(430 / 12, **CLOSE)
    assert quote_on(m, "CAL27", bilateral(), rates) == pytest.approx(424.4 / 11.86, **CLOSE)
    assert quote_on(m, "CAL27", financial(per="calday")) == pytest.approx(13090 / 365, **CLOSE)
    assert quote_on(m, "CAL27", bilateral(per="calday"), rates) == pytest.approx(
        12918.8 / 360.72, **CLOSE
    )
    counts = counts_of(m, "CAL27", bilateral(), rates)
    assert counts["months_resolved"] == 12 and counts["observations_made"] == 261
    assert (counts["fixings_read"], counts["live_prices_read"]) == (118, 7)
    assert (counts["payment_days_made"], counts["payment_factors_read"]) == (12, 7)

    # A fixing correction moves January through May alone: one May day from 30 to 51 lifts May's
    # average of 21 days by one, the strip's sum by one.
    def corrected(d: np.datetime64) -> float:
        return 51.0 if d == day("2027-05-03") else june()(d)

    assert quote_on(in_june(corrected, 42.0, *[40.0] * 6), "CAL27", financial()) == pytest.approx(
        431 / 12, **CLOSE
    )
    # A live move: N27 to 52 lifts July alone.
    assert quote_on(
        in_june(june(), 42.0, 52.0, *[40.0] * 5), "CAL27", financial()
    ) == pytest.approx(442 / 12, **CLOSE)
    # The selected curve's future factors alone: 0.96 on every payment still ahead.
    lower = curve_set(curve_of((JUNE_16, 1.0), ("2027-07-01", 0.96), ("2028-01-03", 0.96)))
    assert quote_on(m, "CAL27", bilateral(), lower) == pytest.approx(
        (150 + 7 * 40 * 0.96) / (5 + 7 * 0.96), **CLOSE
    )
    # A past-month-only request returns the realized price with no live price and no factor
    # read; the bilateral set, key and start are still checked.
    assert quote_on(m, "F27-K27", bilateral(), rates) == pytest.approx(30.0, **CLOSE)
    counts = counts_of(m, "F27-K27", bilateral(), rates)
    assert (counts["live_prices_read"], counts["payment_factors_read"]) == (0, 0)
    assert counts["curves_selected"] == 1
    refused(
        m,
        "F27-K27",
        bilateral(),
        "discount_curve_key 'SOFR' names no curve of the collection, which holds 'FFOIS'; "
        "expected a curve of that name",
        curve_set(FFOIS),
    )
    # The curve need not cover January through May, paid; it must cover December's 3 January.
    refused(
        m,
        "CAL27",
        bilateral(),
        "the payment of Z27 on 2028-01-03 on SOFR is past the discount curve 'SOFR', which runs "
        "from 2027-06-16 to 2027-12-31; expected every payment day after the valuation date "
        "covered",
        curve_set(curve_of((JUNE_16, 1.0), ("2027-12-31", 0.98))),
    )


# --- the rules -----------------------------------------------------------------------------------


def test_the_templates_terms_are_complete_and_agree_before_anything_is_priced() -> None:
    m = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    in_template = "expected it in the quote template"
    refused(m, "F27", a_template(schedule_method="asian"), f"route is missing, {in_template}")
    refused(
        m,
        "F27",
        a_template(route="cleared", settlement_method="financial", quantity_per="month"),
        f"schedule_method is missing, {in_template}",
    )
    refused(
        m,
        "F27",
        financial(route="bilateral"),
        f"discount_curve_key is missing, {in_template} when route = bilateral",
        RATES,
    )
    refused(
        m,
        "F27",
        financial(key="SOFR"),
        "discount_curve_key is 'SOFR', expected none in the quote template unless route = "
        "bilateral",
    )
    refused(
        m,
        "F27",
        a_template(
            route="cleared",
            settlement_method="financial",
            schedule_method="asian",
            quantity_per="month",
            payment_time_lag="+1bd",
        ),
        f"payment_holiday_calendar is missing, {in_template} when settlement_method = financial",
    )
    refused(
        m,
        "F27",
        a_template(
            route="cleared",
            settlement_method="physical",
            schedule_method="lastday",
            quantity_per="month",
            payment_time_lag="+1bd",
        ),
        "payment_time_lag is '+1bd', expected none in the quote template unless "
        "settlement_method = financial",
    )
    refused(
        m,
        "F27",
        a_template(
            route="cleared",
            settlement_method="physical",
            schedule_method="lastday",
            quantity_per="month",
            payment_holiday_calendar=WEEKENDS_ONLY,
        ),
        "payment_holiday_calendar is a holiday calendar, expected none in the quote template "
        "unless settlement_method = financial",
    )
    # The collection: required with a bilateral quote, refused with a cleared one.
    refused(
        m,
        "F27",
        bilateral(),
        "discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' "
        "with route = bilateral, whose payments it discounts",
    )
    refused(
        m,
        "F27",
        financial(),
        "discount_curve_set is a collection of 1 curve, expected none with route = cleared; a "
        "cleared quote discounts nothing",
        RATES,
    )
    refused(
        m,
        "F27",
        financial(),
        "discount_curve_set is a collection of 2 curves, expected none with route = cleared; a "
        "cleared quote discounts nothing",
        curve_set(SOFR, FFOIS),
    )


def test_the_period_and_the_market_refuse_what_they_cannot_price() -> None:
    m = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    refused(
        m,
        "CAL28",
        financial(),
        "contract_code is 'CAL28', expected months the index's schedule has a contract for; it "
        "has none for 2028-01",
    )
    refused(
        m,
        "Z2027",
        financial(),
        "contract_code is 'Z2027', expected a contract or strip with two-digit years, such as "
        "F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28",
    )
    refused(
        priced(STRIP, DEC_31, 3.0, 30.0),
        "G27",
        financial(),
        "requested contract 'G27' is beyond live-price coverage ending at 'F27'",
    )
    # A fixed observation asks nothing of the market, so a quote of the paid month alone stands
    # on a market that quotes nothing of it.
    assert quote_on(priced(STRIP, "2027-02-01", january(30.0), 60.0), "F27", financial()) == 30.0
    closed = an_index(
        "CLOSED",
        (("Z26", "2026-12-15"), ("F27", "2027-01-28"), ("G27", "2027-02-26")),
        ("2027-01-01", "2027-01-28"),
    )
    refused(
        priced(closed, DEC_31, 3.0, 30.0, 60.0),
        "F27",
        financial(method="lastday"),
        "F27 observes 2027-01-28, a day the index's market is closed; no settle exists or will",
    )
    # A payment on or before the month's last observation, and one beyond the sheet's calendar.
    refused(
        m,
        "F27",
        financial(lag="+0bd"),
        "F27 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, when its "
        "final price exists",
    )
    refused(
        m,
        "F27",
        financial(lag="+9999999cd"),
        "payment_time_lag is '+9999999cd', counted from 2027-01-29 to 29406-02-23, expected a "
        "payment day within the sheet's calendar, 1900-03-01 to 9999-12-31",
    )
    # A Gas Daily index has no fixed_float and so no quote.
    with pytest.raises(
        ValueError, match=r"^index is .*, expected a futures or an IFERC index for a fixed_float$"
    ):
        quote_on(quoted(a_gas_daily_history("2026-10-15"), 2.9), "V26", financial())


def test_prices_may_be_zero_or_negative_and_the_quote_keeps_the_indexs_units() -> None:
    assert quote_on(priced(STRIP, DEC_31, 3.0, 0.0, -5.0), "F27-G27", financial()) == pytest.approx(
        -2.5, **CLOSE
    )
    cents = an_index(
        "RBOB",
        (("Z26", "2026-12-15"), ("F27", "2027-01-29"), ("G27", "2027-02-26")),
        ("2027-01-01",),
        ("CENT", "GAL"),
        ("VOLUME", "GAL"),
        ("GAL", 42_000.0, "GAL"),
    )
    assert quote_on(priced(cents, DEC_31, 3.0, 150.25, 160.75), "F27-G27", financial()) == (
        pytest.approx(155.5, **CLOSE)
    )


def test_extreme_but_finite_inputs_price_as_exact_convex_combinations() -> None:
    # Each month's share is its weight over the weights' sum and the price the shares' sum of
    # the months' prices, so a factor as small as the curve allows scales nothing away: one
    # month's share is one whatever its factor, and the price is the price. Nor does a sum run
    # past the largest number, each being a convex combination of finite inputs.
    tiny = curve_set(curve_of((DEC_31, 1.0), ("2027-02-01", 1e-300)))
    assert quote_on(priced(STRIP, DEC_31, 3.0, 1e-30, 60.0), "F27", bilateral(), tiny) == (
        pytest.approx(1e-30, rel=1e-12, abs=0)
    )
    both_tiny = curve_set(curve_of((DEC_31, 1.0), ("2027-02-01", 1e-300), ("2027-03-01", 1e-300)))
    assert quote_on(priced(STRIP, DEC_31, 3.0, 30.0, 60.0), "F27-G27", bilateral(), both_tiny) == (
        pytest.approx(MONTH_CLEARED, **CLOSE)
    )
    assert quote_on(priced(STRIP, DEC_31, 3.0, 1e308, 1e308), "F27-G27", financial()) == (
        pytest.approx(1e308, rel=1e-12, abs=0)
    )
    assert quote_on(
        priced(STRIP, DEC_31, 3.0, 1e308, 60.0), "F27-G27", financial(per="calday")
    ) == pytest.approx(1e308 * (31 / 59) + 60 * (28 / 59), rel=1e-12, abs=0)


# --- an equivalent trade booked at the quote ---------------------------------------------------


def test_an_equivalent_trade_booked_at_the_quote_marks_zero_with_every_payment_ahead() -> None:
    # The same index, months, method, basis, payment rule and curve: one barrel of each month
    # at the quote, asian, paying +1bd on the weekend calendar; the mark is zero on either route.
    m = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    for route, curves in ((Route.CLEARED, None), (Route.BILATERAL, RATES)):
        template = financial() if route is Route.CLEARED else bilateral()
        k = quote_on(m, "F27-G27", template, curves)
        contract = rows(1, 2)
        bilateral_only = route is Route.BILATERAL
        terms = resolved_trades(
            FIXED_FLOAT,
            STRIP,
            spec(2),
            route,
            Settlement.FINANCIAL,
            *picks(ScheduleMethod.ASIAN, QuantityPer.MONTH, 2),
            ids(1, 2),
            None,
            None,
            dates(DEC_31, DEC_31),
            np.arange(2, dtype=np.intp),
            contract,
            numbers(1.0, 1.0),
            *bounds_of(STRIP, contract),
            numbers(k, k),
            PaymentTerms(("+1bd", "+1bd"), (WEEKENDS_ONLY,) * 2, dates("2027-02-01", "2027-03-01")),
            counterparty=("ACME Trading",) * 2 if bilateral_only else None,
            discount_curve_key=("SOFR",) * 2 if bilateral_only else None,
        )
        prep = prepared_trades(
            encoded(terms, observed_of(terms), UNITS, WorkCounter()),
            m.market_history,
            WorkCounter(),
        )
        assert trade_results(prep, m, WorkCounter(), curves).mark == pytest.approx(0.0, abs=1e-9)


# --- the balance of a period, balance-of-period-quotes.md -----------------------------------------

JAN_11 = "2027-01-11"
RATES_JAN = curve_set(curve_of((JAN_11, 1.0), ("2027-02-01", 0.99), ("2027-03-01", 0.98)))
WHOLE = (
    "the expiry-based methods take the contract's month entire, and a part of it prices under asian"
)


def on_jan_11(*quotes: float) -> Market:
    """The strip's market on Monday 11 January: the 4th to the 8th fixed at 25, the rest live."""
    return priced(STRIP, JAN_11, january(25.0), *quotes)


def test_the_balance_of_a_period_runs_from_the_valuation_day_by_hand() -> None:
    # The whole January quotes 28 from five fixings and fifteen live days; its balance, the 11th
    # to the 31st, quotes the fifteen live days alone, 29, on either route and either basis. The
    # strip's balance weighs January's balance and February alike per month, as the booking model
    # weighs a partial month, and 21 days against 28 per calendar day.
    m = on_jan_11(29.0, 60.0)
    assert quote_on(m, "F27", financial()) == pytest.approx(28.0, **CLOSE)
    for template, curves in (
        (financial(), None),
        (bilateral(), RATES_JAN),
        (financial(per="calday"), None),
        (bilateral(per="calday"), RATES_JAN),
    ):
        assert quote_on(m, "BALF27", template, curves) == pytest.approx(29.0, **CLOSE)
    assert quote_on(m, "balf27-g27", financial()) == pytest.approx(44.5, **CLOSE)
    assert quote_on(m, "BALF27-G27", bilateral(), RATES_JAN) == pytest.approx(87.51 / 1.97, **CLOSE)
    assert quote_on(m, "BALF27-G27", financial(per="calday")) == pytest.approx(2289 / 49, **CLOSE)
    assert quote_on(m, "BALF27-G27", bilateral(per="calday"), RATES_JAN) == pytest.approx(
        2249.31 / 48.23, **CLOSE
    )
    counts = counts_of(m, "BALF27-G27", bilateral(), RATES_JAN)
    assert (counts["months_resolved"], counts["observations_made"], counts["fixings_read"]) == (
        2,
        35,
        0,
    )
    assert (counts["live_prices_read"], counts["payment_factors_read"]) == (2, 2)
    # The balance of a period still ahead is the period.
    assert quote_on(m, "BALG27", financial()) == pytest.approx(60.0, **CLOSE)


def test_balcal27_in_june_is_the_seven_months_left() -> None:
    # June from its eleven live days alone, 42, and the six months after at 40; on a curve at
    # 0.98 for every payment ahead the bilateral quotes equal the cleared ones, every payment now
    # carrying one factor, where CAL27's paid months at factor one keep it apart.
    m = in_june(june(), 42.0, *[40.0] * 6)
    rates = curve_set(curve_of((JUNE_16, 1.0), ("2027-07-01", 0.98), ("2028-01-03", 0.98)))
    assert quote_on(m, "BALCAL27", financial()) == pytest.approx(282 / 7, **CLOSE)
    assert quote_on(m, "BALCAL27", bilateral(), rates) == pytest.approx(282 / 7, **CLOSE)
    assert quote_on(m, "BALCAL27", financial(per="calday")) == pytest.approx(7990 / 199, **CLOSE)
    assert quote_on(m, "BALCAL27", bilateral(per="calday"), rates) == pytest.approx(
        7990 / 199, **CLOSE
    )
    assert quote_on(m, "CAL27", bilateral(), rates) == pytest.approx(424.4 / 11.86, **CLOSE)
    counts = counts_of(m, "BALCAL27", bilateral(), rates)
    assert (counts["months_resolved"], counts["observations_made"], counts["fixings_read"]) == (
        7,
        143,
        0,
    )
    assert (counts["live_prices_read"], counts["payment_factors_read"]) == (7, 7)


def test_a_balance_is_refused_as_a_dated_period_is() -> None:
    refused(
        priced(STRIP, "2027-02-01", january(30.0), 60.0),
        "BALF27",
        financial(),
        "valuation_date is 2027-02-01, after 'BALF27' ended on 2027-01-31, expected a valuation "
        "day on or before the period's last day",
    )
    m = on_jan_11(29.0, 60.0)
    for method in ("lastday", "penultimate", "last3day"):
        refused(
            m,
            "BALF27",
            financial(method=method),
            "F27 of the quote is covered from 2027-01-11 to 2027-01-31, part of its month, "
            f"expected the whole month under {method}; {WHOLE}",
        )
    refused(
        m,
        "BALZ2027",
        financial(),
        "contract_code is 'BALZ2027', expected a contract or strip with two-digit years, such as "
        "F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28",
    )
    # Saturday 30 January: the balance of January holds no pricing day, and the strip's first
    # component being empty refuses the strip, nothing dropped silently.
    saturday = priced(STRIP, "2027-01-30", january(30.0), 60.0)
    for code in ("BALF27", "BALF27-G27"):
        refused(
            saturday,
            code,
            financial(),
            "F27 of the quote has no pricing day from 2027-01-30 to 2027-01-31, expected a Monday "
            "to Friday of the days it covers the index's market is open on; the asian method "
            "averages the pricing days a component covers",
        )
    # An IFERC month is one price for the whole month: its balance in progress is refused.
    cal = calendar(valuation_date(day("2026-11-15"), 0.5), WAHA)
    waha = quoted(market_history(cal, iferc_fixings(("X26",), numbers(0.5), WAHA)), -0.4, -0.3)
    assert quote_on(waha, "BALZ26", financial(method="lastday", lag="+2bd")) == -0.4
    refused(
        waha,
        "BALX26",
        financial(method="lastday", lag="+2bd"),
        "X26 of the quote is covered from 2026-11-15 to 2026-11-30, part of its month, expected "
        "the whole month under lastday; an IFERC month's index is one price for the whole month",
    )


def test_an_equivalent_trade_booked_on_the_balances_dates_marks_zero() -> None:
    # The balance's own dates from the two utilities, the quote as the fixed price, a barrel of
    # each month under asian paying +1bd on the weekend calendar: zero mark on either route under
    # either basis, the hand numbers above standing on their own beside this comparison.
    m = on_jan_11(29.0, 60.0)
    first, last = start_date("BALF27-G27", day(JAN_11)), end_date("BALF27-G27", day(JAN_11))
    assert (first, last) == (day("2027-01-11"), day("2027-02-28"))
    starts, ends = dates(str(first), "2027-02-01"), dates("2027-01-31", str(last))
    for route, curves in ((Route.CLEARED, None), (Route.BILATERAL, RATES_JAN)):
        for basis in (QuantityPer.MONTH, QuantityPer.CALDAY):
            template = (
                financial(per=basis.value) if route is Route.CLEARED else bilateral(per=basis.value)
            )
            k = quote_on(m, "BALF27-G27", template, curves)
            keyed = route is Route.BILATERAL
            terms = resolved_trades(
                FIXED_FLOAT,
                STRIP,
                spec(2),
                route,
                Settlement.FINANCIAL,
                *picks(ScheduleMethod.ASIAN, basis, 2),
                ids(1, 2),
                None,
                None,
                dates(JAN_11, JAN_11),
                np.arange(2, dtype=np.intp),
                rows(1, 2),
                numbers(1.0, 1.0),
                starts,
                ends,
                numbers(k, k),
                PaymentTerms(
                    ("+1bd", "+1bd"), (WEEKENDS_ONLY,) * 2, dates("2027-02-01", "2027-03-01")
                ),
                counterparty=("ACME Trading",) * 2 if keyed else None,
                discount_curve_key=("SOFR",) * 2 if keyed else None,
            )
            prep = prepared_trades(
                encoded(terms, observed_of(terms), UNITS, WorkCounter()),
                m.market_history,
                WorkCounter(),
            )
            assert trade_results(prep, m, WorkCounter(), curves).mark == pytest.approx(
                0.0, abs=1e-9
            )


# --- the worksheet function -----------------------------------------------------------------------


def test_the_page_example_through_the_seam_and_the_seams_refusals() -> None:
    ix, _ = seam_index(
        "SEAM",
        [("Z26", "2026-12-15"), ("F27", "2027-01-29"), ("G27", "2027-02-26")],
        ["2027-01-01"],
        [("BBL", 1.0)],
        ("VOLUME", "BBL"),
    )
    history = seam_history(ix, "2026-12-16", DEC_31, ["2027-01-01"], {})
    market = seam_market(history, "SEAM", 30.0, 60.0)
    weekends = ENTRY["_CreateHolidayCalendar"](column([serial("2030-01-01")]))
    fields = row(
        "route",
        "settlement_method",
        "schedule_method",
        "quantity_per",
        "payment_time_lag",
        "payment_holiday_calendar",
        "discount_curve_key",
    )
    otc = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        fields,
        row("bilateral", "financial", "asian", "calday", "+1bd", weekends, "SOFR"),
    )
    cleared = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        row(
            "route",
            "settlement_method",
            "schedule_method",
            "quantity_per",
            "payment_time_lag",
            "payment_holiday_calendar",
        ),
        row("cleared", "financial", "asian", "calday", "+1bd", weekends),
    )
    sofr = ENTRY["_CreateDiscountCurve"](
        "SOFR",
        row("date", "discount_factor"),
        cells_of([serial(DEC_31), 1.0], [serial("2027-02-01"), 0.99], [serial("2027-03-01"), 0.98]),
    )
    rates = ENTRY["_CollectDiscountCurves"](cells_of([sofr]))
    assert ENTRY["_Quote"](market, "F27-G27", cleared, bridge.MISSING) == pytest.approx(
        CALDAY_CLEARED, **CLOSE
    )
    assert ENTRY["_Quote"](market, "F27-G27", otc, rates) == pytest.approx(
        CALDAY_BILATERAL, **CLOSE
    )
    # The seam's refusals in signature order, then the library's with its prefix; a trade
    # template is refused by its kind, and a blank fourth cell is not a left-out one.
    assert (
        ENTRY["_Quote"](None, "F27", cleared, bridge.MISSING)
        == "#ERROR _Quote: market is blank, expected market handle"
    )
    assert ENTRY["_Quote"](market, 1.0, cleared, bridge.MISSING) == (
        "#ERROR _Quote: contract_code is number 1.0, expected text"
    )
    trade = ENTRY["_CreateTradeTemplate"]("fixed_float", row("route"), row("cleared"))
    assert ENTRY["_Quote"](market, "F27", trade, bridge.MISSING) == (
        f"#ERROR _Quote: template is trade template handle {trade!r}, expected quote template "
        "handle"
    )
    assert ENTRY["_Quote"](market, "F27", otc, None) == (
        "#ERROR _Quote: discount_curve_set is blank, expected discount curve set handle"
    )
    assert ENTRY["_Quote"](market, "F27", otc, bridge.MISSING) == (
        "#ERROR _Quote: ValueError: discount_curve_set is missing, expected a collection of "
        "discount curves holding 'SOFR' with route = bilateral, whose payments it discounts"
    )
    assert ENTRY["_Quote"](market, "CAL28", cleared, bridge.MISSING) == (
        "#ERROR _Quote: ValueError: contract_code is 'CAL28', expected months the index's "
        "schedule has a contract for; it has none for 2028-01"
    )
