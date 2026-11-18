"""The quote by dates, dated-quotes.md: the WTI trade month of onetime-averaging.md quoted from its
two dates under the template's frequency, one average across its months under onetime and a
dated strip split at month ends under monthly, the owner's four numbers by hand; part fixed on
10 June and fully fixed on the 26th; the window on a schedule without the start month's
contract, which the dated strip needs; cleared and bilateral alike on one payment and apart on
two; the booking twin at the quote marking zero on either route; the payment by date and by
rule from the window's final observation; the refusals by name; and the worksheet function
through the seam. docs/library/quoting/quote-by-dates.md is the page."""

import re
from collections.abc import Mapping

import numpy as np
import pytest
from test_bilateral_kernel import CLOSE, curve_of, curve_set
from test_create_trades import an_index, created
from test_onetime_average import (
    CL,
    CL_CONTRACTS,
    CL_HOLIDAYS,
    PROJECTED,
    TMA_TEMPLATE,
    TMA_TICKET,
    WINDOW,
)
from test_quote import WAHA, a_template, priced
from test_trade_valuation import a_history as seam_history
from test_trade_valuation import a_market as seam_market
from test_trade_valuation import an_index as seam_index
from test_trade_valuation import row, serial
from test_trades import day, numbers, quoted

from catalyst.calendar.calendar import calendar
from catalyst.excel import bridge
from catalyst.globals.discount_curve_set import DiscountCurveSet
from catalyst.globals.valuation_date import valuation_date
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market
from catalyst.market.market_history import market_history
from catalyst.market_data.iferc_fixings import iferc_fixings
from catalyst.quoting.quote import quote, quote_by_dates
from catalyst.quoting.template import QuoteTemplate
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.template import DayOrRule

ENTRY = {
    name: bridge.entry(name)
    for name in ("_QuoteByDates", "_Quote", "_CreateQuoteTemplate", "_CreateHolidayCalendar")
}

# The trade month, 26 May to 25 June 2026, valued 20 May with N26 at 70 and Q26 at 72 before any
# day fixes: 22 pricing days, four of May and eighteen of June, N26's nineteen through its expiry
# on 22 June and Q26's three. The owner's table of 1 November 2026: the same dates under each
# frequency and basis.
MAY_20, JUNE_10, JUNE_26 = "2026-05-20", "2026-06-10", "2026-06-26"
START, END, JUNE_29 = day("2026-05-26"), day("2026-06-25"), day("2026-06-29")
JUNE_PORTION = (15 * 70.0 + 3 * 72.0) / 18  # June's eighteen days, fifteen N26's and three Q26's
BY_MONTH = (70.0 + JUNE_PORTION) / 2  # 70.166667: May's four days at 70 and June, alike
BY_CALDAY = (6 * 70.0 + 25 * JUNE_PORTION) / 31  # 70.268817: the portions weighted 6 and 25 days
MARKET = priced(CL, MAY_20, 70.0, 70.0, 72.0, 74.0)
# The curve from the valuation day with the two portions' +2bd payment days on it, 2 June from
# 29 May and 29 June from 25 June, at 0.995 and 0.99: two factors on a dated strip, one on a window.
SOFR = curve_of((MAY_20, 1.0), ("2026-06-02", 0.995), ("2026-06-29", 0.99), ("2026-07-31", 0.98))
RATES = curve_set(SOFR)
RULE = DayOrRule(None, "+2bd")
ON_JUNE_29 = DayOrRule(JUNE_29, None)


def terms(
    frequency: str = "onetime",
    per: str = "period",
    method: str = "asian",
    route: str = "cleared",
    payment: DayOrRule = ON_JUNE_29,
    settlement: str = "financial",
) -> QuoteTemplate:
    values: dict[str, object] = {
        "route": route,
        "settlement_method": settlement,
        "schedule_method": method,
        "quantity_per": per,
        "settlement_frequency": frequency,
        "nearby": 1.0,
    }
    if settlement == "financial":
        values["payment_day"] = payment
        values["payment_holiday_calendar"] = CL.holiday_calendar
    if route == "bilateral":
        values["discount_curve_key"] = "SOFR"
    return a_template(**values)


def dated(
    market: Market,
    template: QuoteTemplate,
    curves: DiscountCurveSet | None = None,
    start: np.datetime64 = START,
    end: np.datetime64 = END,
    counter: WorkCounter | None = None,
) -> float:
    return quote_by_dates(market, start, end, template, "flat", curves, counter or WorkCounter())


def counts_of(
    market: Market, template: QuoteTemplate, curves: DiscountCurveSet | None = None
) -> dict[str, int]:
    counter = WorkCounter()
    dated(market, template, curves, counter=counter)
    return counter.freeze().as_dict()


def refused(
    message: str,
    market: Market = MARKET,
    template: QuoteTemplate | None = None,
    curves: DiscountCurveSet | None = None,
    start: np.datetime64 = START,
    end: np.datetime64 = END,
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        dated(market, terms() if template is None else template, curves, start, end)


def marked(
    ticket: Mapping[str, list[object]],
    template: Mapping[str, object],
    market: Market,
    curves: DiscountCurveSet | None = None,
) -> float:
    """The mark of the ticket booked under the template and valued on the market."""
    batch, _ = created(CL, ticket, template)
    prepared = prepared_trades(batch.encoded, (market.market_history,), WorkCounter())
    return trade_results(prepared, (market,), WorkCounter(), curves).mark


# --- the trade month by hand ----------------------------------------------------------------------


def test_the_same_dates_quote_by_the_templates_frequency() -> None:
    # The window one average of 22 fixings whatever its basis; the dated strip two months, May's
    # four days at 70 and June's eighteen at 70.333333, in equal quantities or weighted 6 and 25.
    assert dated(MARKET, terms("onetime", "period")) == pytest.approx(PROJECTED, **CLOSE)
    assert dated(MARKET, terms("onetime", "calday")) == pytest.approx(PROJECTED, **CLOSE)
    assert dated(MARKET, terms("monthly", "month")) == pytest.approx(BY_MONTH, **CLOSE)
    assert dated(MARKET, terms("monthly", "calday")) == pytest.approx(BY_CALDAY, **CLOSE)
    assert pytest.approx(70.272727, abs=5e-7) == PROJECTED
    assert pytest.approx(70.166667, abs=5e-7) == BY_MONTH
    assert pytest.approx(70.268817, abs=5e-7) == BY_CALDAY
    # The work: the window resolved once to the contract pricing its first day, no code read for
    # a month; the strip's two months resolved against the schedule's twelve codes; the same 22
    # observations, two live contracts, one payment day or two.
    assert counts_of(MARKET, terms()) == {
        "fixings_read": 0,
        "live_prices_read": 2,
        "observations_made": 22,
        "payment_days_made": 1,
        "payment_rules_read": 0,
        "payment_shifts": 0,
        "price_reductions": 4,
        "template_fields_read": 8,
        "windows_resolved": 1,
    }
    assert counts_of(MARKET, terms("monthly", "month")) == {
        "fixings_read": 0,
        "live_prices_read": 2,
        "months_resolved": 2,
        "observations_made": 22,
        "payment_days_made": 2,
        "payment_rules_read": 0,
        "payment_shifts": 0,
        "price_reductions": 4,
        "schedule_codes_read": 12,
        "template_fields_read": 8,
    }


def test_the_window_keeps_its_original_weights_as_days_fix() -> None:
    # 10 June, eleven days fixed at 69, eight N26 days and three Q26 days ahead; 26 June, every
    # day fixed, nothing live read, the quote the realized average.
    june = priced(CL, JUNE_10, 69.0, 70.0, 72.0, 74.0)
    assert dated(june, terms()) == pytest.approx((11 * 69.0 + 8 * 70.0 + 3 * 72.0) / 22, **CLOSE)
    assert dated(june, terms()) == pytest.approx(69.772727, abs=5e-7)
    assert dated(june, terms("monthly", "month")) == pytest.approx(
        (69.0 + (7 * 69.0 + 8 * 70.0 + 3 * 72.0) / 18) / 2, **CLOSE
    )
    counts = counts_of(june, terms())
    assert (counts["fixings_read"], counts["live_prices_read"]) == (11, 2)
    fixed = priced(CL, JUNE_26, 69.0, 70.0, 72.0, 74.0)
    assert dated(fixed, terms()) == pytest.approx(69.0, **CLOSE)
    assert counts_of(fixed, terms())["live_prices_read"] == 0


def test_the_window_needs_no_contract_for_the_month_it_opens_in_and_the_strip_does() -> None:
    # Without K26 the window prices the same, its contract N26, the first pricing on or after 26
    # May; the dated strip's May portion is May's component and needs May's contract. A window
    # opening after the last day the schedule's contracts price has nothing to price it.
    without_k26 = an_index(
        "CL", CL_CONTRACTS[1:], CL_HOLIDAYS, (("BBL", 1.0, "BBL"),), ("VOLUME", "BBL")
    )
    market = priced(without_k26, MAY_20, 70.0, 70.0, 72.0, 74.0)
    assert dated(market, terms()) == pytest.approx(PROJECTED, **CLOSE)
    refused(
        "start_date is 2026-05-26 and end_date 2026-06-25, expected months the index's schedule "
        "has a contract for; it has none for 2026-05",
        market,
        terms("monthly", "month"),
    )
    refused(
        "start_date is 2027-04-01 and end_date 2027-04-30, expected a window priced by the "
        "contracts of the index's schedule; it opens on 2027-04-01, after the last day they "
        "price, 2027-03-22",
        start=day("2027-04-01"),
        end=day("2027-04-30"),
    )


def test_one_payment_cancels_its_factor_and_two_carry_theirs() -> None:
    # The window pays once, by date or by rule, so the bilateral quote is the cleared one; the
    # dated strip's portions paying by rule pay on 2 June and 29 June, 0.995 and 0.99, each
    # weighing its average, and paying together on one explicit date weigh alike again.
    assert dated(MARKET, terms(route="bilateral"), RATES) == pytest.approx(PROJECTED, **CLOSE)
    assert dated(MARKET, terms(route="bilateral", payment=RULE), RATES) == pytest.approx(
        PROJECTED, **CLOSE
    )
    by_rule = terms("monthly", "month", route="bilateral", payment=RULE)
    assert dated(MARKET, by_rule, RATES) == pytest.approx(
        (0.995 * 70.0 + 0.99 * JUNE_PORTION) / (0.995 + 0.99), **CLOSE
    )
    by_days = terms("monthly", "calday", route="bilateral", payment=RULE)
    assert dated(MARKET, by_days, RATES) == pytest.approx(
        (6 * 0.995 * 70.0 + 25 * 0.99 * JUNE_PORTION) / (6 * 0.995 + 25 * 0.99), **CLOSE
    )
    assert dated(MARKET, terms("monthly", "month", route="bilateral"), RATES) == pytest.approx(
        BY_MONTH, **CLOSE
    )
    assert dated(MARKET, terms("monthly", "month", payment=RULE)) == pytest.approx(
        BY_MONTH, **CLOSE
    )
    counts = counts_of(MARKET, by_rule, RATES)
    assert (counts["payment_days_made"], counts["payment_factors_read"]) == (2, 2)
    assert (
        counts_of(MARKET, terms(route="bilateral", payment=RULE), RATES)["payment_factors_read"]
        == 1
    )


# --- the booking twin -----------------------------------------------------------------------------

BILATERAL_BOOKING: dict[str, object] = {
    **{name: value for name, value in TMA_TEMPLATE.items() if name != "clearing_house"},
    "route": "bilateral",
    "counterparty": "ACME Trading",
    "discount_curve_key": "SOFR",
}


def test_a_trade_booked_at_the_quote_marks_zero_on_either_route() -> None:
    # The same dates, index, method, basis, frequency, payment rule and curve booked at the
    # quote: the window as one onetime row, the strip as one monthly row split at the month
    # end, each paying +2bd from its last observation; zero on either route while every payment
    # is ahead, and the window fully fixed at 69 on 26 June booked at 69 flat before it pays.
    for frequency, per, quantity in (
        ("onetime", "period", 2_200.0),
        ("onetime", "calday", 100.0),
        ("monthly", "month", 2_200.0),
        ("monthly", "calday", 100.0),
    ):
        for booking, route, curves in (
            (TMA_TEMPLATE, "cleared", None),
            (BILATERAL_BOOKING, "bilateral", RATES),
        ):
            k = dated(MARKET, terms(frequency, per, route=route, payment=RULE), curves)
            booked = {
                **booking,
                "quantity_per": per,
                "settlement_frequency": frequency,
                "nearby": 1.0,
                "payment_day": "+2bd",
            }
            ticket: dict[str, list[object]] = {
                **TMA_TICKET,
                "quantity": [quantity],
                "fixed_price": [k],
            }
            assert marked(ticket, booked, MARKET, curves) == pytest.approx(0.0, abs=1e-6)
    fixed = priced(CL, JUNE_26, 69.0, 70.0, 72.0, 74.0)
    assert marked({**TMA_TICKET, "fixed_price": [69.0]}, TMA_TEMPLATE, fixed) == pytest.approx(
        0.0, abs=1e-9
    )


# --- the payment and the refusals -----------------------------------------------------------------


def test_the_payment_counts_from_the_windows_final_observation() -> None:
    # A date on the final observation is refused naming the window by its dates; +2bd from 25
    # June is 29 June, past a curve ending on the 26th; the strip's June portion, named by June's
    # contract, pays after its own last observation.
    refused(
        f"{WINDOW} pays on 2026-06-25, expected a day after its last observation, 2026-06-25, "
        "when its final price exists",
        template=terms(payment=DayOrRule(END, None)),
    )
    short = curve_set(curve_of((MAY_20, 1.0), ("2026-06-26", 0.99)))
    refused(
        f"the payment of {WINDOW} on 2026-06-29 on SOFR is past the discount curve 'SOFR', which "
        "runs from 2026-05-20 to 2026-06-26; expected every payment day after the valuation "
        "date covered",
        template=terms(route="bilateral", payment=RULE),
        curves=short,
    )
    refused(
        "M26 pays on 2026-06-01, expected a day after its last observation, 2026-06-25, when "
        "its final price exists",
        template=terms("monthly", "month", payment=DayOrRule(day("2026-06-01"), None)),
    )


def test_the_dates_and_the_terms_are_refused_by_name() -> None:
    refused(
        "end_date is 2026-05-26, expected a day on or after start_date, 2026-06-25",
        start=END,
        end=START,
    )
    # The kernel's rule over the frequency, the quote named in the trade's place: the basis, the
    # method, a physical settlement and an IFERC index under onetime; period under monthly.
    refused(
        "quantity_per of the quote is 'month', expected 'period' or 'calday' under "
        "settlement_frequency = onetime; month says nothing of a window, period is its total "
        "and calday its days",
        template=terms(per="month"),
    )
    refused(
        "schedule_method of the quote is 'lastday', expected 'asian' under settlement_frequency "
        "= onetime; a onetime period averages every pricing day it covers, and the expiry-based "
        "methods take their contract's month",
        template=terms(method="lastday"),
    )
    refused(
        "settlement_method is 'physical', expected 'financial' with settlement_frequency = "
        "onetime of the quote; a onetime period is cash settled on its average",
        template=terms(method="lastday", settlement="physical"),
    )
    refused(
        "quantity_per of the quote is 'period', expected 'month' or 'calday' under "
        "settlement_frequency = monthly; period is the total of a onetime period and says "
        "nothing of a month",
        template=terms("monthly", "period"),
    )
    cal = calendar(valuation_date(day("2026-11-15"), 0.5), WAHA)
    waha = quoted(market_history(cal, iferc_fixings(("X26",), numbers(0.5), WAHA)), -0.4, -0.3)
    refused(
        "settlement_frequency of the quote is 'onetime', expected 'monthly' on an IFERC index; "
        "an IFERC month has one index, published once, and a onetime period averages the "
        "pricing days of a futures index",
        waha,
        terms(method="lastday", payment=RULE),
        start=day("2026-12-01"),
        end=day("2026-12-31"),
    )
    # A window over a weekend alone has no pricing day, the observations' rule for a dated row.
    refused(
        "the window of the quote has no pricing day from 2026-05-30 to 2026-05-31, expected a "
        "Monday to Friday of the days it covers the index's market is open on; the asian method "
        "averages the pricing days a component covers",
        start=day("2026-05-30"),
        end=day("2026-05-31"),
    )
    # A label names months: _Quote refuses the onetime template and names the function that
    # prices a window.
    with pytest.raises(ValueError) as by_label:
        quote(MARKET, "K26-M26", terms(), "flat", None, WorkCounter())
    assert str(by_label.value) == (
        "settlement_frequency is 'onetime', expected 'monthly'; a quote by contract code prices "
        "by the month, and _QuoteByDates prices a onetime period across two dates"
    )


# --- the worksheet function -----------------------------------------------------------------------


def test_the_page_example_through_the_seam_and_the_seams_refusals() -> None:
    ix, holidays = seam_index(
        "CL", list(CL_CONTRACTS), list(CL_HOLIDAYS), [("BBL", 1.0)], ("VOLUME", "BBL")
    )
    history = seam_history(ix, "2026-04-22", MAY_20, list(CL_HOLIDAYS), {})
    market = seam_market(history, "CL", 70.0, 72.0, 74.0)
    fields = row(
        "route",
        "settlement_method",
        "schedule_method",
        "quantity_per",
        "payment_day",
        "payment_holiday_calendar",
        "settlement_frequency",
        "nearby",
    )
    onetime = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        fields,
        row("cleared", "financial", "asian", "period", "+2bd", holidays, "onetime", 1.0),
    )
    monthly = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        fields,
        row("cleared", "financial", "asian", "month", "+2bd", holidays, "monthly", 1.0),
    )
    start, end = serial("2026-05-26"), serial("2026-06-25")
    assert ENTRY["_QuoteByDates"](
        market, start, end, onetime, "flat", bridge.MISSING
    ) == pytest.approx(PROJECTED, **CLOSE)
    assert ENTRY["_QuoteByDates"](
        market, start, end, monthly, "flat", bridge.MISSING
    ) == pytest.approx(BY_MONTH, **CLOSE)
    # The seam's refusals in signature order, then the library's with its prefix.
    assert ENTRY["_QuoteByDates"](None, start, end, onetime, "flat", bridge.MISSING) == (
        "#ERROR _QuoteByDates: market is blank, expected market handle"
    )
    assert ENTRY["_QuoteByDates"](market, None, end, onetime, "flat", bridge.MISSING) == (
        "#ERROR _QuoteByDates: start_date is blank, expected date"
    )
    assert ENTRY["_QuoteByDates"](market, start, "2026-06-25", onetime, "flat", bridge.MISSING) == (
        "#ERROR _QuoteByDates: end_date is text '2026-06-25', expected date"
    )
    assert ENTRY["_QuoteByDates"](market, end, start, onetime, "flat", bridge.MISSING) == (
        "#ERROR _QuoteByDates: ValueError: end_date is 2026-05-26, expected a day on or after "
        "start_date, 2026-06-25"
    )
    assert ENTRY["_Quote"](market, "K26-M26", onetime, "flat", bridge.MISSING) == (
        "#ERROR _Quote: ValueError: settlement_frequency is 'onetime', expected 'monthly'; a "
        "quote by contract code prices by the month, and _QuoteByDates prices a onetime period "
        "across two dates"
    )
