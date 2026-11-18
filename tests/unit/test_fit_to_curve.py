"""The pricing of a quote, fit-to-curve-price.md: flat, one fixed price for the period, each
component weighed by its quantity and its payment's factor, and ftc, fit to curve, the
components' own prices averaged by quantity alone. The issue's worked example by hand on a
request, and the same prices and factors on a quote by code and by dates under their own
weights; a fit-to-curve price as the cleared quote of the same terms, to the last digit, on
every fixture the quote tests price; one payment quoting one price under either; the curve
taken alike under both and no factor read under ftc; any other text refused by name; each month
booked at its own price marking zero where the fit-to-curve price on every month does not; and
the three worksheet functions through the seam. docs/library/quoting/quote.md owns the
calculation."""

import re
from collections.abc import Callable

import numpy as np
import pytest
from test_bilateral_kernel import CLOSE, curve_of, curve_set
from test_quote import (
    DEC_31,
    MONTH_CLEARED,
    RATES_JAN,
    STRIP,
    WEEKENDS_ONLY,
    a_template,
    bilateral,
    financial,
    on_jan_11,
    physical,
    priced,
)
from test_quote import RATES as STRIP_RATES
from test_quote_by_dates import BY_MONTH, RULE, terms
from test_quote_by_dates import MARKET as TRADE_MONTH
from test_quote_by_dates import RATES as TRADE_MONTH_RATES
from test_rfq import LONGER, WINDOW_PRICE, cleared, onetime, otc, request, windows
from test_rfq import MARKET as STRIP_MARKET
from test_rfq import RATES as REQUEST_RATES
from test_trade_valuation import a_history as seam_history
from test_trade_valuation import a_market as seam_market
from test_trade_valuation import an_index as seam_index
from test_trade_valuation import column, row, serial
from test_trade_valuation import rows as cells_of
from test_trades import bounds_of, dates, day, ids, numbers, observed_of, picks, rows, spec

from catalyst.excel import bridge
from catalyst.globals.discount_curve_set import DiscountCurveSet
from catalyst.globals.unit_conversions import UNITS
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.instruments.fields import DatesOrTexts
from catalyst.market.market import Market
from catalyst.quoting.quote import quote, quote_by_dates
from catalyst.quoting.request import Pricing, pricing_of
from catalyst.quoting.rfq import Rfq, quote_rfq
from catalyst.quoting.template import QuoteTemplate
from catalyst.trades.encoding import encoded
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.schedule_methods import ScheduleMethod
from catalyst.trades.terms import (
    FREQUENCIES,
    PaymentTerms,
    QuantityPer,
    Route,
    Settlement,
    SettlementFrequency,
    one_choice,
    resolved_trades,
)

ENTRY = {
    name: bridge.entry(name)
    for name in (
        "_Quote",
        "_QuoteByDates",
        "_CreateRFQ",
        "_QuoteRFQ",
        "_CreateQuoteTemplate",
        "_CreateHolidayCalendar",
        "_CreateDiscountCurve",
        "_CollectDiscountCurves",
    )
}

# The issue's worked example: three months at 4.50, 4.30 and 3.00, quantities 3,100,000, 280,000
# and 310,000, payment factors 0.99, 0.95 and 0.90. January, February and March 2027 on the
# request tests' longer index, valued 31 December 2026 with every day live, each month priced by
# its own contract; +1bd on the weekend calendar pays 1 February, 1 March and 1 April, where the
# curve holds the three factors.
PRICES = (4.50, 4.30, 3.00)
QUANTITY = (3_100_000.0, 280_000.0, 310_000.0)
CODES = ("F27", "G27", "H27")
EXAMPLE = priced(LONGER, DEC_31, 3.0, *PRICES)
SOFR = curve_of((DEC_31, 1.0), ("2027-02-01", 0.99), ("2027-03-01", 0.95), ("2027-04-01", 0.90))
RATES = curve_set(SOFR)
FLAT = 15_791_300 / 3_614_000  # sum(q D P) / sum(q D), 4.36948
FTC = 16_084_000 / 3_690_000  # sum(q P) / sum(q), 4.35881
# The same prices and factors under a quote's own weights: one a month, and the months' calendar
# days, 31, 28 and 31, which are the request's quantities with its first at 310,000.
BY_MONTH_FLAT, BY_MONTH_FTC = 11.24 / 2.84, 11.8 / 3
BY_CALDAY_FLAT, BY_CALDAY_FTC = 336.185 / 85.19, 352.9 / 90
JAN_1, MAR_31 = day("2027-01-01"), day("2027-03-31")
# The fields of a cleared financial quote template on the sheet, in the order the seam test types.
FIELDS = (
    "route",
    "settlement_method",
    "schedule_method",
    "quantity_per",
    "payment_day",
    "payment_holiday_calendar",
    "settlement_frequency",
    "nearby",
)


def by_code(
    market: Market,
    code: str,
    template: QuoteTemplate,
    pricing: str,
    curves: DiscountCurveSet | None = None,
) -> float:
    return quote(market, code, template, pricing, curves, WorkCounter())


def by_dates(
    market: Market,
    start: np.datetime64,
    end: np.datetime64,
    template: QuoteTemplate,
    pricing: str,
    curves: DiscountCurveSet | None = None,
) -> float:
    return quote_by_dates(market, start, end, template, pricing, curves, WorkCounter())


def by_request(
    market: Market, saved: Rfq, pricing: str, curves: DiscountCurveSet | None = None
) -> float:
    return quote_rfq(market, saved, pricing, curves, WorkCounter())


def the_example(template: QuoteTemplate, quantities: tuple[float, ...] = QUANTITY) -> Rfq:
    return request(CODES, quantities, template, ix=LONGER)


# --- the worked example ---------------------------------------------------------------------------


def test_the_issues_worked_example_by_hand_on_a_request() -> None:
    saved = the_example(bilateral())
    flat, ftc = by_request(EXAMPLE, saved, "flat", RATES), by_request(EXAMPLE, saved, "ftc", RATES)
    assert flat == pytest.approx(FLAT, **CLOSE)
    assert ftc == pytest.approx(FTC, **CLOSE)
    assert (round(flat, 5), round(ftc, 5)) == (4.36948, 4.35881)  # the issue's own digits
    # Per calendar day the same three quantities are 100,000, 10,000 and 10,000 a day over 31, 28
    # and 31 days, and the same two prices.
    daily = the_example(bilateral(per="calday"), (100_000.0, 10_000.0, 10_000.0))
    assert by_request(EXAMPLE, daily, "flat", RATES) == pytest.approx(FLAT, **CLOSE)
    assert by_request(EXAMPLE, daily, "ftc", RATES) == pytest.approx(FTC, **CLOSE)
    # A common scale of the quantities cancels under either pricing.
    scaled = the_example(bilateral(), (31.0, 2.8, 3.1))
    assert by_request(EXAMPLE, scaled, "flat", RATES) == pytest.approx(FLAT, **CLOSE)
    assert by_request(EXAMPLE, scaled, "ftc", RATES) == pytest.approx(FTC, **CLOSE)


def test_the_examples_prices_and_factors_on_a_quote_by_code_and_by_dates() -> None:
    # A quote weighs by its template's basis and takes no quantities: one a month, or the months'
    # calendar days. The same three prices and factors under each, by hand, from a label and
    # from the quarter's two dates alike.
    for per, flat, ftc in (
        ("month", BY_MONTH_FLAT, BY_MONTH_FTC),
        ("calday", BY_CALDAY_FLAT, BY_CALDAY_FTC),
    ):
        template = bilateral(per=per)
        assert by_code(EXAMPLE, "F27-H27", template, "flat", RATES) == pytest.approx(flat, **CLOSE)
        assert by_code(EXAMPLE, "F27-H27", template, "ftc", RATES) == pytest.approx(ftc, **CLOSE)
        assert by_code(EXAMPLE, "1Q27", template, "ftc", RATES) == pytest.approx(ftc, **CLOSE)
        assert by_dates(EXAMPLE, JAN_1, MAR_31, template, "flat", RATES) == pytest.approx(
            flat, **CLOSE
        )
        assert by_dates(EXAMPLE, JAN_1, MAR_31, template, "ftc", RATES) == pytest.approx(
            ftc, **CLOSE
        )
    # The curve falls, so the early month, the dearest, weighs more under flat: flat is above ftc
    # here, and the difference is the time value of the one price standing off each month's own.
    assert BY_MONTH_FLAT > BY_MONTH_FTC and FLAT > FTC


# --- a fit-to-curve price is the cleared quote of the same terms ---------------------------------


def test_a_fit_to_curve_price_is_the_cleared_quote_of_the_same_terms_to_the_last_digit() -> None:
    # A cleared quote discounts nothing, every factor one, which is what ftc asks of a bilateral
    # one: the same calculation, so the same number exactly, and a cleared quote the same under
    # either pricing. On the strip live, part fixed and its balance, both bases:
    live = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    part = on_jan_11(29.0, 60.0)
    for market, code, curves in (
        (live, "F27-G27", STRIP_RATES),
        (part, "F27-G27", RATES_JAN),
        (part, "BALF27-G27", RATES_JAN),
    ):
        for per in ("month", "calday"):
            fit = by_code(market, code, bilateral(per=per), "ftc", curves)
            assert fit == by_code(market, code, financial(per=per), "flat")
            assert fit == by_code(market, code, financial(per=per), "ftc")
            assert fit != by_code(market, code, bilateral(per=per), "flat", curves)
    assert by_code(live, "F27-G27", bilateral(), "ftc", STRIP_RATES) == pytest.approx(
        MONTH_CLEARED, **CLOSE
    )
    # On the trade month's dated strip, two portions paying on two days:
    monthly = terms("monthly", "month", route="bilateral", payment=RULE)
    fit = by_dates(
        TRADE_MONTH, day("2026-05-26"), day("2026-06-25"), monthly, "ftc", TRADE_MONTH_RATES
    )
    assert fit == by_dates(
        TRADE_MONTH,
        day("2026-05-26"),
        day("2026-06-25"),
        terms("monthly", "month", payment=RULE),
        "flat",
    )
    assert fit == pytest.approx(BY_MONTH, **CLOSE)
    # On a request, by the template's days and by its own, and on a request of windows:
    for pays in (None, ("2027-02-08", "2027-03-08")):
        fit = by_request(STRIP_MARKET, request(template=otc(), pays=pays), "ftc", REQUEST_RATES)
        assert fit == by_request(STRIP_MARKET, request(template=cleared(), pays=pays), "flat")
        assert fit == pytest.approx(1.15, **CLOSE)
    fit = by_request(STRIP_MARKET, windows(), "ftc", REQUEST_RATES)
    assert fit == by_request(STRIP_MARKET, windows(template=onetime(route="cleared")), "flat")
    # Several windows of a onetime request weigh by quantity alone under ftc, and by quantity and
    # factor under flat: the two differ, which is why one payment is not refused by frequency.
    assert fit == pytest.approx((100_000 * WINDOW_PRICE + 300_000 * 1.2) / 400_000, **CLOSE)
    assert fit != by_request(STRIP_MARKET, windows(), "flat", REQUEST_RATES)


def test_a_physical_quote_is_the_same_under_either_pricing() -> None:
    # A physical delivery pays on no day and discounts nothing; its rules stand under ftc.
    live = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    assert by_code(live, "F27-G27", physical(), "ftc") == by_code(
        live, "F27-G27", physical(), "flat"
    )
    with pytest.raises(ValueError, match=r"^F27 expired 2027-01-29, before valuation date"):
        by_code(priced(STRIP, "2027-02-01", 3.0, 60.0), "F27", physical(), "ftc")


# --- one payment ----------------------------------------------------------------------------------


def test_one_payment_quotes_one_price_under_either_pricing() -> None:
    # One component's share is one whatever its factor: a month, a onetime window and a
    # one-component request quote the same number, exactly, flat or ftc.
    month = by_code(EXAMPLE, "G27", bilateral(), "ftc", RATES)
    assert month == by_code(EXAMPLE, "G27", bilateral(), "flat", RATES)
    assert month == pytest.approx(4.30, **CLOSE)
    window = onetime()
    start, end = day("2027-01-11"), day("2027-02-26")
    assert by_dates(STRIP_MARKET, start, end, window, "ftc", REQUEST_RATES) == by_dates(
        STRIP_MARKET, start, end, window, "flat", REQUEST_RATES
    )
    one_month = request(("H27",), (7.0,), bilateral(), ix=LONGER)
    assert by_request(EXAMPLE, one_month, "ftc", RATES) == by_request(
        EXAMPLE, one_month, "flat", RATES
    )
    # One row is one component only where it is one month or one window: a row of F27-H27 is
    # three months and three payments, and quotes as the strip by code does, the two differing.
    strip = request(("F27-H27",), (7.0,), bilateral(), ix=LONGER)
    assert by_request(EXAMPLE, strip, "flat", RATES) == pytest.approx(BY_MONTH_FLAT, **CLOSE)
    assert by_request(EXAMPLE, strip, "ftc", RATES) == pytest.approx(BY_MONTH_FTC, **CLOSE)
    # Several months paying on one day carry one factor, which cancels: the flat price is the
    # fit-to-curve one, to rounding.
    together = request(CODES, QUANTITY, bilateral(day="2027-04-01"), ix=LONGER)
    assert by_request(EXAMPLE, together, "flat", RATES) == pytest.approx(FTC, **CLOSE)
    assert by_request(EXAMPLE, together, "ftc", RATES) == pytest.approx(FTC, **CLOSE)


# --- the curve ------------------------------------------------------------------------------------


def counts_of(
    template: QuoteTemplate, pricing: str, curves: DiscountCurveSet | None
) -> dict[str, int]:
    counter = WorkCounter()
    quote(EXAMPLE, "F27-H27", template, pricing, curves, counter)
    return counter.freeze().as_dict()


def refused(message: str, priced_by: Callable[[], float]) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        priced_by()


def test_the_curve_is_taken_alike_and_a_fit_to_curve_price_reads_no_factor_of_it() -> None:
    template = bilateral()
    flat, ftc = counts_of(template, "flat", RATES), counts_of(template, "ftc", RATES)
    assert (flat["curves_selected"], flat["payment_factors_read"]) == (1, 3)
    assert ftc["curves_selected"] == 1 and "payment_factors_read" not in ftc
    assert {**ftc, "payment_factors_read": 3} == flat  # every other count the same
    assert counts_of(financial(), "ftc", None) == counts_of(financial(), "flat", None)
    # The collection is asked for, its key bound and its start checked under ftc as under flat,
    # so one formula serves both.
    for pricing in ("flat", "ftc"):
        refused(
            "discount_curve_set is missing, expected a collection of discount curves holding "
            "'SOFR' with route = bilateral, under flat and ftc alike",
            lambda pricing=pricing: by_code(EXAMPLE, "F27-H27", template, pricing),
        )
        refused(
            "discount_curve_key 'SOFR' names no curve of the collection, which holds 'FFOIS'; "
            "expected a curve of that name",
            lambda pricing=pricing: by_code(
                EXAMPLE,
                "F27-H27",
                template,
                pricing,
                curve_set(curve_of((DEC_31, 1.0), ("2027-04-01", 0.9), name="FFOIS")),
            ),
        )
        refused(
            "discount curve 'SOFR' starts on 2027-01-04, expected 2026-12-31, the valuation date; "
            "a curve is never rebased",
            lambda pricing=pricing: by_code(
                EXAMPLE,
                "F27-H27",
                template,
                pricing,
                curve_set(curve_of(("2027-01-04", 1.0), ("2027-04-01", 0.9))),
            ),
        )
        refused(
            "discount_curve_set is a collection of 1 curve, expected none with route = cleared; a "
            "cleared quote discounts nothing",
            lambda pricing=pricing: by_code(EXAMPLE, "F27-H27", financial(), pricing, RATES),
        )
    # A curve stopping short of a late payment refuses the flat price, which reads a factor
    # there, and not the fit-to-curve one, which reads none.
    short = curve_set(curve_of((DEC_31, 1.0), ("2027-02-15", 0.99)))
    refused(
        "the payment of G27 on 2027-03-01 on SOFR is past the discount curve 'SOFR', which runs "
        "from 2026-12-31 to 2027-02-15; expected every payment day after the valuation date "
        "covered",
        lambda: by_code(EXAMPLE, "F27-H27", template, "flat", short),
    )
    assert by_code(EXAMPLE, "F27-H27", template, "ftc", short) == pytest.approx(
        BY_MONTH_FTC, **CLOSE
    )
    saved = the_example(template)
    assert by_request(EXAMPLE, saved, "ftc", short) == pytest.approx(FTC, **CLOSE)
    # The payment terms stand under ftc as they do on a cleared quote, the request made the same
    # whatever the pricing: a payment on its month's last observation is refused all the same.
    refused(
        "F27 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, when its "
        "final price exists",
        lambda: by_code(EXAMPLE, "F27", bilateral(day="2027-01-29"), "ftc", RATES),
    )


# --- the word -------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["FTC", "Flat", " ftc", "flat ", "fit to curve", "", "TRUE"])
def test_any_other_pricing_is_refused_by_name_on_each_of_the_three(text: str) -> None:
    message = f"pricing is {text!r}, expected flat or ftc"
    saved = the_example(bilateral())
    refused(message, lambda: by_code(EXAMPLE, "F27-H27", bilateral(), text, RATES))
    refused(message, lambda: by_dates(EXAMPLE, JAN_1, MAR_31, bilateral(), text, RATES))
    refused(message, lambda: by_request(EXAMPLE, saved, text, RATES))


def test_the_pricing_is_read_first_and_once() -> None:
    assert (pricing_of("flat"), pricing_of("ftc")) == (Pricing.FLAT, Pricing.FTC)
    # Before the template's terms and before the market's index: a formula written before the
    # argument existed, its curve where the pricing now goes, is told so whatever else is wrong.
    no_terms = a_template(route="cleared")
    refused(
        "pricing is '4242:discount_curve_set:7', expected flat or ftc",
        lambda: by_code(EXAMPLE, "F27-H27", no_terms, "4242:discount_curve_set:7"),
    )
    other_index = the_example(bilateral())
    refused(
        "pricing is 'both', expected flat or ftc",
        lambda: by_request(STRIP_MARKET, other_index, "both", RATES),
    )


# --- the months booked at their own prices --------------------------------------------------------


def marked(*fixed: float) -> float:
    """The mark of the example's three months booked bilaterally at those fixed prices, a month a
    row at its quantity, asian, paying +1bd on the weekend calendar, valued on the example's
    market and curve."""
    contract = rows(1, 2, 3)
    booked = resolved_trades(
        FIXED_FLOAT,
        LONGER,
        spec(3),
        Route.BILATERAL,
        Settlement.FINANCIAL,
        *picks(ScheduleMethod.ASIAN, QuantityPer.MONTH, 3),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, 3),
        np.ones(3, dtype=np.intp),
        ids(1, 2, 3),
        None,
        None,
        dates(DEC_31, DEC_31, DEC_31),
        np.arange(3, dtype=np.intp),
        contract,
        numbers(*QUANTITY),
        *bounds_of(LONGER, contract),
        numbers(*fixed),
        PaymentTerms(
            DatesOrTexts.of_texts(("+1bd",) * 3),
            (WEEKENDS_ONLY,) * 3,
            dates("2027-02-01", "2027-03-01", "2027-04-01"),
        ),
        counterparty=("ACME Trading",) * 3,
        discount_curve_key=("SOFR",) * 3,
    )
    prepared = prepared_trades(
        encoded(booked, (observed_of(booked),), UNITS, WorkCounter()),
        (EXAMPLE.market_history,),
        WorkCounter(),
    )
    return trade_results(prepared, (EXAMPLE,), WorkCounter(), RATES).mark


def test_each_month_at_its_own_price_marks_zero_and_the_ftc_price_is_their_average() -> None:
    # A fit-to-curve deal fixes each month at that month's own price, a month's quote under
    # either pricing; booked so, as a regular swap of three rows, it marks nothing, and the
    # fit-to-curve price is those prices averaged by quantity.
    legs = [by_code(EXAMPLE, code, bilateral(), "ftc", RATES) for code in CODES]
    assert legs == pytest.approx(list(PRICES), **CLOSE)
    assert legs == [by_code(EXAMPLE, code, bilateral(), "flat", RATES) for code in CODES]
    assert float(np.dot(QUANTITY, legs)) / sum(QUANTITY) == pytest.approx(FTC, **CLOSE)
    assert marked(*legs) == pytest.approx(0.0, abs=1e-6)
    # One price on every month marks nothing at the flat price, which is what flat means; the
    # fit-to-curve price is a summary and not that price, and booked on every month it marks the
    # time value between them, the discounted quantity times the difference.
    assert marked(FLAT, FLAT, FLAT) == pytest.approx(0.0, abs=1e-6)
    assert marked(FTC, FTC, FTC) == pytest.approx(3_614_000 * (FLAT - FTC), rel=1e-9)
    assert abs(marked(FTC, FTC, FTC)) > 38_000


# --- the worksheet functions ----------------------------------------------------------------------


def test_the_three_worksheet_functions_take_the_pricing_through_the_seam() -> None:
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
    weekends = ENTRY["_CreateHolidayCalendar"](column([serial("2030-01-01")]))
    otc_template = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        row("discount_curve_key", *FIELDS),
        row("SOFR", "bilateral", "financial", "asian", "month", "+1bd", weekends, "monthly", 1.0),
    )
    cleared_template = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        row(*FIELDS),
        row("cleared", "financial", "asian", "month", "+1bd", weekends, "monthly", 1.0),
    )
    sofr = ENTRY["_CreateDiscountCurve"](
        "SOFR",
        row("date", "discount_factor"),
        cells_of(
            [serial(DEC_31), 1.0],
            [serial("2027-02-01"), 0.99],
            [serial("2027-03-01"), 0.95],
            [serial("2027-04-01"), 0.90],
        ),
    )
    rates = ENTRY["_CollectDiscountCurves"](cells_of([sofr]))
    ticket = cells_of(*[[code, quantity] for code, quantity in zip(CODES, QUANTITY, strict=True)])
    saved = ENTRY["_CreateRFQ"](ix, row("contract_code", "quantity"), ticket, otc_template)
    start, end = serial("2027-01-01"), serial("2027-03-31")
    # The two prices on each function, one formula but for the word.
    assert ENTRY["_QuoteRFQ"](market, saved, "flat", rates) == pytest.approx(FLAT, **CLOSE)
    assert ENTRY["_QuoteRFQ"](market, saved, "ftc", rates) == pytest.approx(FTC, **CLOSE)
    assert ENTRY["_Quote"](market, "F27-H27", otc_template, "flat", rates) == pytest.approx(
        BY_MONTH_FLAT, **CLOSE
    )
    assert ENTRY["_Quote"](market, "F27-H27", otc_template, "ftc", rates) == pytest.approx(
        BY_MONTH_FTC, **CLOSE
    )
    assert ENTRY["_QuoteByDates"](market, start, end, otc_template, "flat", rates) == pytest.approx(
        BY_MONTH_FLAT, **CLOSE
    )
    assert ENTRY["_QuoteByDates"](market, start, end, otc_template, "ftc", rates) == pytest.approx(
        BY_MONTH_FTC, **CLOSE
    )
    # A cleared quote, its curve left out, is the same number under either.
    for pricing in ("flat", "ftc"):
        assert ENTRY["_Quote"](
            market, "F27-H27", cleared_template, pricing, bridge.MISSING
        ) == pytest.approx(BY_MONTH_FTC, **CLOSE)
    # The seam's refusals of the argument alone, by type and shape: a blank cell, a left-out
    # argument, a number and a boolean are not text; then the library's, by name.
    assert ENTRY["_Quote"](market, "F27-H27", otc_template, None, rates) == (
        "#ERROR _Quote: pricing is blank, expected text"
    )
    assert ENTRY["_Quote"](market, "F27-H27", otc_template, bridge.MISSING, rates) == (
        "#ERROR _Quote: pricing is missing, expected text"
    )
    assert ENTRY["_QuoteByDates"](market, start, end, otc_template, 1.0, rates) == (
        "#ERROR _QuoteByDates: pricing is number 1.0, expected text"
    )
    assert ENTRY["_QuoteRFQ"](market, saved, True, rates) == (
        "#ERROR _QuoteRFQ: pricing is boolean TRUE, expected text"
    )
    assert ENTRY["_QuoteRFQ"](market, saved, "", rates) == (
        "#ERROR _QuoteRFQ: pricing is empty text, expected text"
    )
    assert ENTRY["_Quote"](market, "F27-H27", otc_template, "FTC", rates) == (
        "#ERROR _Quote: ValueError: pricing is 'FTC', expected flat or ftc"
    )
    # A formula written before the argument existed has its curve where the pricing now goes:
    # the handle's text is refused by name, a bilateral formula's, and a cleared one's, a cell
    # short, as a missing argument.
    assert ENTRY["_Quote"](market, "F27-H27", otc_template, rates, bridge.MISSING) == (
        f"#ERROR _Quote: ValueError: pricing is {rates!r}, expected flat or ftc"
    )
    assert ENTRY["_QuoteRFQ"](market, saved, rates, bridge.MISSING) == (
        f"#ERROR _QuoteRFQ: ValueError: pricing is {rates!r}, expected flat or ftc"
    )
