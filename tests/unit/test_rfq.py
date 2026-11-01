"""A request for quote, rfq-quoting.md and dated-quotes.md: the ticket's worked acceptance by hand
on the quote tests' strip, a month-matching asian index valued on 31 December 2026 with January
at 1.00 and February at 1.20, paying +5bd on the weekend calendar or on the request's own dates;
the quantities' meaning under both bases; equality with _Quote on the whole strip; the rows'
order, repeats and zeros; the market's states through the request's reuse; a trade booked at the
price marking zero; the precedence of the request's dates over the template's day; the rows by
dates, a window per row under onetime and its months under monthly, a one-row window against
_QuoteByDates, windows weighed by quantity and factor against the booked portfolio; the rules in
the seam's words and the library's. docs/library/quoting/rfq.md is the page."""

import os
import re
from collections.abc import Sequence
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest
from test_bilateral_kernel import CLOSE, curve_of, curve_set
from test_create_trades import a_ticket, created
from test_quote import (
    DEC_31,
    STRIP,
    WEEKENDS_ONLY,
    a_template,
    bilateral,
    financial,
    physical,
    priced,
    quote_on,
)
from test_quote import (
    ENTRY as QUOTE_ENTRY,
)
from test_trade_valuation import a_history as seam_history
from test_trade_valuation import a_market as seam_market
from test_trade_valuation import an_index as seam_index
from test_trade_valuation import column, row, serial, spilled
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

from goosedove.excel import bridge
from goosedove.excel.utilities import shown
from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.globals.payments import factors_on
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.index import Index
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT
from goosedove.instruments.fields import DatesOrTexts
from goosedove.market.market import Market
from goosedove.quoting.quote import quote_by_dates
from goosedove.quoting.rfq import PaymentSource, Rfq, quote_rfq, rfq
from goosedove.quoting.template import QuoteTemplate
from goosedove.trades.encoding import encoded
from goosedove.trades.evaluation import trade_results
from goosedove.trades.preparation import prepared_trades
from goosedove.trades.schedule_methods import ScheduleMethod
from goosedove.trades.terms import (
    FREQUENCIES,
    PaymentTerms,
    QuantityPer,
    Route,
    Settlement,
    SettlementFrequency,
    one_choice,
    resolved_trades,
)

# The ticket's curve: 1 on the valuation day and the four listed payment points, +5bd's days 5
# February and 5 March and the request's 8 February and 8 March, fixture data and no claim about
# any rate.
SOFR = curve_of(
    (DEC_31, 1.0),
    ("2027-02-05", 0.99),
    ("2027-02-08", 0.98),
    ("2027-03-05", 0.97),
    ("2027-03-08", 0.96),
)
RATES = curve_set(SOFR)
CODES = ("F27", "G27")
QUANTITIES = (100_000.0, 300_000.0)
EXPLICIT = ("2027-02-08", "2027-03-08")
CLEARED_PRICE = 1.15
DEFAULT_PRICE = 448_200 / 390_000
EXPLICIT_PRICE = 443_600 / 386_000


def market_on(as_of: str = DEC_31, *quotes: float, settle: float = 3.0) -> Market:
    """The strip's market on the day: January at 1.00 and February at 1.20 unless told otherwise,
    every fixed day settled at 3.00."""
    return priced(STRIP, as_of, settle, *(quotes or (1.0, 1.2)))


MARKET = market_on()


def cleared(per: str = "month", method: str = "asian") -> QuoteTemplate:
    return financial(method=method, per=per, lag="+5bd")


def otc(per: str = "month", method: str = "asian", day: str | None = None) -> QuoteTemplate:
    return bilateral(method=method, per=per, lag="+5bd", day=day)


def onetime(per: str = "period", route: str = "bilateral", pay: str | None = None) -> QuoteTemplate:
    """The ticket's template under onetime, bilateral on SOFR or cleared, paying +5bd or on the
    date given: the window's terms, period or calendar day."""
    base = (
        bilateral(per=per, lag="+5bd", day=pay)
        if route == "bilateral"
        else financial(per=per, lag="+5bd", day=pay)
    )
    return a_template(**{**dict(base.values), "settlement_frequency": "onetime"})


def request(
    codes: Sequence[str | None] | None = CODES,
    quantities: Sequence[float] = QUANTITIES,
    template: QuoteTemplate | None = None,
    pays: Sequence[str] | None = None,
    ix: Index = STRIP,
    counter: WorkCounter | None = None,
    starts: Sequence[str | None] | None = None,
    ends: Sequence[str | None] | None = None,
) -> Rfq:
    """The request from a ticket of the columns given, a None in a period column a cell the row
    left unsupplied, the payment days typed as dates."""
    columns: dict[str, list[object]] = {}
    if codes is not None:
        columns["contract_code"] = list(codes)
    if starts is not None:
        columns["start_date"] = [None if text is None else day(text) for text in starts]
    if ends is not None:
        columns["end_date"] = [None if text is None else day(text) for text in ends]
    columns["quantity"] = list(quantities)
    if pays is not None:
        columns["payment_day"] = [day(text) for text in pays]
    return rfq(
        ix, a_ticket(columns), cleared() if template is None else template, counter or WorkCounter()
    )


def price(
    market: Market,
    saved: Rfq,
    curves: DiscountCurveSet | None = None,
    counter: WorkCounter | None = None,
) -> float:
    return quote_rfq(market, saved, curves, counter or WorkCounter())


def refused(message: str, **made: Any) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        request(**made)


def refused_price(
    market: Market, saved: Rfq, message: str, curves: DiscountCurveSet | None = None
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        price(market, saved, curves)


def grid(saved: Rfq) -> list[list[object]]:
    """The readback as the sheet shows it: the headings, the types and the body rows."""
    table = shown(saved)
    kinds, slots, text = table.kinds, table.numeric_slots, "\0".join(table.texts)
    texts = iter(text.split("\0"))
    return [
        [
            next(texts) if kinds[r, c] == bridge.TEXT_CODE else slots[r, c]
            for c in range(kinds.shape[1])
        ]
        for r in range(kinds.shape[0])
    ]


def under(table: list[list[object]], heading: str) -> list[object]:
    at = table[0].index(heading)
    return [line[at] for line in table[2:]]


HEADINGS = [
    "row",
    "period",
    "quantity",
    "quantity_per",
    "component_quantity",
    "payment_source",
    "payment_date",
    "index",
    "schedule_method",
    "route",
    "settlement_method",
    "quote_unit",
    "discount_curve_key",
    "settlement_frequency",
]


# --- the ticket's worked acceptance --------------------------------------------------------------


def test_the_tickets_cases_by_hand() -> None:
    # Cleared, either payment input: the quantity-weighted price of the two live months.
    assert price(MARKET, request()) == pytest.approx(CLEARED_PRICE, **CLOSE)
    assert price(MARKET, request(pays=EXPLICIT)) == pytest.approx(CLEARED_PRICE, **CLOSE)
    # Bilateral on the template's +5bd, 5 February and 5 March at 0.99 and 0.97.
    assert price(MARKET, request(template=otc()), RATES) == pytest.approx(DEFAULT_PRICE, **CLOSE)
    # Bilateral on the request's own dates, 8 February and 8 March at 0.98 and 0.96, the
    # template's +5bd standing but unused.
    explicit = request(template=otc(), pays=EXPLICIT)
    assert price(MARKET, explicit, RATES) == pytest.approx(EXPLICIT_PRICE, **CLOSE)
    # Both payments deferred to 8 March: one factor on every month cancels.
    deferred = request(template=otc(), pays=("2027-03-08", "2027-03-08"))
    assert price(MARKET, deferred, RATES) == pytest.approx(CLEARED_PRICE, **CLOSE)
    # A tick on February to 1.30 reprices the same request: nothing of it is made again.
    assert price(market_on(DEC_31, 1.0, 1.3), explicit, RATES) == pytest.approx(
        472_400 / 386_000, **CLOSE
    )
    # The readback shows each row's period, the effective dates and their source, the entered
    # quantities and the resolved components, and prices nothing.
    table = grid(explicit)
    assert table[0] == HEADINGS
    assert table[1][:7] == ["int64", "str", "float64", "str", "float64", "str", "datetime64[D]"]
    assert under(table, "row") == [1.0, 2.0]
    assert under(table, "period") == ["F27", "G27"]
    assert under(table, "quantity") == [100_000.0, 300_000.0]
    assert under(table, "component_quantity") == [100_000.0, 300_000.0]
    assert under(table, "payment_source") == ["request", "request"]
    assert under(table, "payment_date") == [serial("2027-02-08"), serial("2027-03-08")]
    assert under(table, "index") == ["STRIP", "STRIP"]
    assert under(table, "quote_unit") == ["USD per BBL"] * 2
    assert under(table, "discount_curve_key") == ["SOFR", "SOFR"]
    assert under(table, "settlement_frequency") == ["monthly", "monthly"]
    by_template = grid(request(template=otc()))
    assert under(by_template, "payment_source") == ["template", "template"]
    assert under(by_template, "payment_date") == [serial("2027-02-05"), serial("2027-03-05")]
    assert under(grid(request()), "discount_curve_key") == ["-", "-"]


def test_a_single_month_quotes_its_floating_price_whatever_its_quantity() -> None:
    for per in ("month", "calday"):
        for template, curves in ((cleared(per), None), (otc(per), RATES)):
            assert price(MARKET, request(("G27",), (7.0,), template), curves) == pytest.approx(
                1.2, **CLOSE
            )
            assert price(MARKET, request(("F27",), (1e6,), template), curves) == pytest.approx(
                1.0, **CLOSE
            )
            dated = request(("G27",), (1.0,), template, EXPLICIT[1:])
            assert price(MARKET, dated, curves) == pytest.approx(1.2, **CLOSE)


def test_calday_quantities_count_each_months_calendar_days() -> None:
    # 100,000 and 300,000 a day over January's 31 and February's 28 days.
    per_day = request(template=cleared("calday"))
    assert per_day.component_quantity.tolist() == [3_100_000.0, 8_400_000.0]
    assert under(grid(per_day), "component_quantity") == [3_100_000.0, 8_400_000.0]
    assert under(grid(per_day), "quantity") == [100_000.0, 300_000.0]
    assert price(MARKET, per_day) == pytest.approx(13_180_000 / 11_500_000, **CLOSE)
    # Per month the entered quantity is the month's, by reference, every row one component.
    whole = request()
    assert whole.component_quantity is whole.quantity


@pytest.mark.parametrize("per", ["month", "calday"])
@pytest.mark.parametrize("method", ["asian", "lastday", "penultimate", "last3day"])
def test_an_equal_quantity_request_matches_the_quote_on_the_strip(per: str, method: str) -> None:
    # One of each month, under every method and both bases, on both routes: the same price as
    # the quote of the whole strip under the same template, the strip's months being the
    # request's rows and the quote's quantities one or the days.
    for route_template, curves in ((cleared(per, method), None), (otc(per, method), RATES)):
        expected = quote_on(MARKET, "F27-G27", route_template, curves)
        assert price(MARKET, request(CODES, (1.0, 1.0), route_template), curves) == (
            pytest.approx(expected, **CLOSE)
        )
        assert price(MARKET, request(CODES, (2.5, 2.5), route_template), curves) == (
            pytest.approx(expected, **CLOSE)
        )
        # A strip in one row is its months at the row's quantity, as a booking's strip row is.
        assert price(MARKET, request(("F27-G27",), (2.5,), route_template), curves) == (
            pytest.approx(expected, **CLOSE)
        )


def test_rows_in_any_order_repeated_and_zero() -> None:
    reversed_rows = request(("G27", "F27"), (300_000.0, 100_000.0), otc(), EXPLICIT[::-1])
    assert price(MARKET, reversed_rows, RATES) == pytest.approx(EXPLICIT_PRICE, **CLOSE)
    assert under(grid(reversed_rows), "period") == ["G27", "F27"]
    # A month twice counts twice: F27 at 100,000 twice is F27 at 200,000.
    twice = request(
        ("F27", "F27", "G27"),
        (100_000.0, 100_000.0, 300_000.0),
        otc(),
        EXPLICIT[:1] * 2 + EXPLICIT[1:],
    )
    once = request(CODES, (200_000.0, 300_000.0), otc(), EXPLICIT)
    assert price(MARKET, twice, RATES) == pytest.approx(price(MARKET, once, RATES), **CLOSE)
    # The same month paying on two days keeps two factors: February at 150,000 on 5 March and
    # 150,000 on 8 March beside January on 8 February.
    split = request(
        ("F27", "G27", "G27"),
        (100_000.0, 150_000.0, 150_000.0),
        otc(),
        ("2027-02-08", "2027-03-05", "2027-03-08"),
    )
    assert price(MARKET, split, RATES) == pytest.approx(445_400 / 387_500, **CLOSE)
    assert price(MARKET, split, RATES) != pytest.approx(EXPLICIT_PRICE, **CLOSE)
    # A zero row has no weight and is checked like any other: its month, its date.
    with_zero = request(("F27", "G27"), (0.0, 300_000.0), otc(), EXPLICIT)
    assert price(MARKET, with_zero, RATES) == pytest.approx(1.2, **CLOSE)
    assert under(grid(with_zero), "quantity") == [0.0, 300_000.0]
    refused(
        "contract_code row 1 is 'H27', expected months the index's schedule has a contract for; "
        "it has none for 2027-03",
        codes=("H27", "G27"),
        quantities=(0.0, 1.0),
    )
    refused(
        "F27 of row 1 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, "
        "when its final price exists",
        quantities=(0.0, 1.0),
        template=otc(),
        pays=("2027-01-29", "2027-03-08"),
    )


def rates_on(as_of: str) -> DiscountCurveSet:
    """The ticket's curve from a later valuation day, its points after that day kept, since a
    curve starts on the day it is used on and is never rebased."""
    points = [
        ("2027-02-05", 0.99),
        ("2027-02-08", 0.98),
        ("2027-03-05", 0.97),
        ("2027-03-08", 0.96),
        ("2027-04-01", 0.95),
    ]
    return curve_set(curve_of((as_of, 1.0), *[p for p in points if p[0] > as_of]))


# The strip with a March contract after it, so that a market stands once both months have paid.
LONGER = an_index(
    "LONGER",
    (
        ("Z26", "2026-12-15"),
        ("F27", "2027-01-29"),
        ("G27", "2027-02-26"),
        ("H27", "2027-03-31"),
    ),
    ("2027-01-01",),
    ("USD", "BBL"),
    ("VOLUME", "BBL"),
    ("BBL", 1.0, "BBL"),
)


def test_the_markets_states_reuse_the_request() -> None:
    # The same request priced as the days pass: January half fixed at 3.00, then fixed and
    # paying ahead, then both months paid; each equal to the quote on that day's market, the
    # request never shortened, and a corrected fixing read on the next call.
    saved = request(CODES, (1.0, 1.0), otc(), ix=LONGER)  # one of each month, the quote's weights
    for as_of, quotes in (
        ("2027-01-15", (1.0, 1.2, 1.3)),
        ("2027-02-02", (1.2, 1.3)),
        ("2027-03-10", (1.4,)),
    ):
        m, rates = priced(LONGER, as_of, 3.0, *quotes), rates_on(as_of)
        assert price(m, saved, rates) == pytest.approx(
            quote_on(m, "F27-G27", otc(), rates), **CLOSE
        )
    corrected = priced(LONGER, "2027-01-15", 4.0, 1.0, 1.2, 1.3)
    rates = rates_on("2027-01-15")
    assert price(corrected, saved, rates) == pytest.approx(
        quote_on(corrected, "F27-G27", otc(), rates), **CLOSE
    )
    assert price(corrected, saved, rates) > price(
        priced(LONGER, "2027-01-15", 3.0, 1.0, 1.2, 1.3), saved, rates
    )
    # Every payment paid: the cleared price, every factor one, whatever the curve's day.
    paid = priced(LONGER, "2027-03-10", 3.0, 1.4)
    flat = curve_set(curve_of(("2027-03-10", 1.0), ("2027-04-01", 0.9)))
    weighted = request(template=otc(), ix=LONGER)
    assert price(paid, weighted, flat) == pytest.approx(
        price(paid, request(template=cleared(), ix=LONGER)), **CLOSE
    )
    assert price(paid, weighted, flat) == pytest.approx(3.0, **CLOSE)  # both months at the settle


def test_a_trade_booked_at_the_request_price_marks_zero_with_every_payment_ahead() -> None:
    # The request's months and quantities booked as barrels at its price under the same terms,
    # the template's +5bd on the weekend calendar: the mark is zero on either route.
    for route, template, curves in (
        (Route.CLEARED, cleared(), None),
        (Route.BILATERAL, otc(), RATES),
    ):
        k = price(MARKET, request(template=template), curves)
        contract = rows(1, 2)
        bilateral_only = route is Route.BILATERAL
        terms = resolved_trades(
            FIXED_FLOAT,
            STRIP,
            spec(2),
            route,
            Settlement.FINANCIAL,
            *picks(ScheduleMethod.ASIAN, QuantityPer.MONTH, 2),
            one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, 2),
            ids(1, 2),
            None,
            None,
            dates(DEC_31, DEC_31),
            np.arange(2, dtype=np.intp),
            contract,
            numbers(*QUANTITIES),
            *bounds_of(STRIP, contract),
            numbers(k, k),
            PaymentTerms(
                DatesOrTexts.of_texts(("+5bd", "+5bd")),
                (WEEKENDS_ONLY,) * 2,
                dates("2027-02-05", "2027-03-05"),
            ),
            counterparty=("ACME Trading",) * 2 if bilateral_only else None,
            discount_curve_key=("SOFR",) * 2 if bilateral_only else None,
        )
        prep = prepared_trades(
            encoded(terms, (observed_of(terms),), UNITS, WorkCounter()),
            (MARKET.market_history,),
            WorkCounter(),
        )
        assert trade_results(prep, (MARKET,), WorkCounter(), curves).mark == pytest.approx(
            0.0, abs=1e-6
        )


# --- the request's dates against the template's day ----------------------------------------------


def no_payment_day(route: str = "cleared") -> QuoteTemplate:
    values: dict[str, object] = {
        "route": route,
        "settlement_method": "financial",
        "schedule_method": "asian",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "payment_holiday_calendar": WEEKENDS_ONLY,
    }
    if route == "bilateral":
        values["discount_curve_key"] = "SOFR"
    return QuoteTemplate(FIXED_FLOAT, tuple(values), MappingProxyType(values))


def test_the_requests_dates_take_precedence_and_stand_in_for_a_missing_day() -> None:
    # A template without a payment day serves a request with dates, and refuses one without,
    # naming both sources.
    dated = request(template=no_payment_day("bilateral"), pays=EXPLICIT)
    assert price(MARKET, dated, RATES) == pytest.approx(EXPLICIT_PRICE, **CLOSE)
    assert dated.request.terms.payment_day is None and dated.request.terms.payment_rule is None
    refused(
        "payment_day is missing, expected it in the quote template when settlement_method = "
        "financial, or a payment_day column in the request",
        template=no_payment_day(),
    )
    # A template's date that February's last observation outruns serves a request with dates.
    on_feb_15 = otc(day="2027-02-15")
    refused(
        "G27 of row 2 pays on 2027-02-15, expected a day after its last observation, "
        "2027-02-26, when its final price exists",
        template=on_feb_15,
    )
    assert price(MARKET, request(template=on_feb_15, pays=EXPLICIT), RATES) == pytest.approx(
        EXPLICIT_PRICE, **CLOSE
    )
    # A weekend date is kept exactly, never rolled: Saturday 6 February reads the curve's factor
    # on that day, and the readback shows it.
    saturday = request(template=otc(), pays=("2027-02-06", "2027-03-08"))
    assert under(grid(saturday), "payment_date")[0] == serial("2027-02-06")
    factor = float(factors_on(SOFR, dates("2027-02-06"))[0])
    assert 0.98 < factor < 0.99
    assert price(MARKET, saturday, RATES) == pytest.approx(
        (100_000 * factor * 1.0 + 300_000 * 0.96 * 1.2) / (100_000 * factor + 300_000 * 0.96),
        **CLOSE,
    )
    # Dates on or before the last observation are refused, by the month and its row.
    refused(
        "F27 of row 1 pays on 2027-01-29, expected a day after its last observation, "
        "2027-01-29, when its final price exists",
        template=otc(),
        pays=("2027-01-29", "2027-03-08"),
    )
    # A rule in the column is refused by its row: a request's rows pay on dates.
    with pytest.raises(ValueError) as ruled:
        rfq(
            STRIP,
            a_ticket(
                {
                    "contract_code": ["F27", "G27"],
                    "quantity": [1.0, 1.0],
                    "payment_day": [day("2027-02-08"), "+5bd"],
                }
            ),
            otc(),
            WorkCounter(),
        )
    assert str(ruled.value) == (
        "payment_day row 2 is '+5bd', expected a date; a request's rows pay on dates, and a rule "
        "is the template's to hold"
    )
    # A physical request takes no dates; it pays on no day and reads back dashes.
    refused(
        "payment_day is supplied, expected none with settlement_method = physical; a physical "
        "delivery pays on no day",
        template=physical(),
        pays=EXPLICIT,
    )
    delivered = request(template=physical())
    assert delivered.payment_source is None and delivered.request.payment_date is None
    table = grid(delivered)
    assert under(table, "payment_source") == ["-", "-"]
    assert under(table, "payment_date") == ["-", "-"] and table[1][6] == "str"
    assert price(MARKET, delivered) == pytest.approx(CLEARED_PRICE, **CLOSE)
    assert price(MARKET, request(CODES, (1.0, 1.0), physical())) == pytest.approx(
        quote_on(MARKET, "F27-G27", physical()), **CLOSE
    )


# --- the rows by dates, dated-quotes.md ---------------------------------------------------------

# The trade month of the strip: 11 January to 26 February 2027, fifteen F27 days at 1.00 through
# its expiry and twenty G27 days at 1.20, one average of 35; and a short window, 1 to 12 February,
# ten G27 days at 1.20.
WINDOW = ("2027-01-11", "2027-02-26")
SHORT = ("2027-02-01", "2027-02-12")
WINDOW_PRICE = (15 * 1.0 + 20 * 1.2) / 35
WINDOW_WORDS = "2027-01-11 to 2027-02-26"
PAYS = ("2027-03-08", "2027-03-05")  # the long window's and the short window's, 0.96 and 0.97
WINDOWS_PRICE = (100_000 * 0.96 * WINDOW_PRICE + 300_000 * 0.97 * 1.2) / (
    100_000 * 0.96 + 300_000 * 0.97
)


def windows(
    quantities: Sequence[float] = QUANTITIES,
    template: QuoteTemplate | None = None,
    pays: Sequence[str] | None = PAYS,
    spans: Sequence[tuple[str, str]] = (WINDOW, SHORT),
) -> Rfq:
    """A request of windows, one row each, by their two dates."""
    return request(
        None,
        quantities,
        onetime() if template is None else template,
        pays,
        starts=[start for start, _ in spans],
        ends=[end for _, end in spans],
    )


def test_a_one_row_window_quotes_as_the_quote_by_dates_does() -> None:
    # One window at any quantity, per period or per calendar day, cleared or bilateral: the
    # window's average, the price _QuoteByDates gives the same dates under the same template, one
    # payment's factor cancelling; its readback names it by its dates.
    for per in ("period", "calday"):
        for route, curves in (("cleared", None), ("bilateral", RATES)):
            template = onetime(per, route)
            saved = request(None, (7.0,), template, starts=[WINDOW[0]], ends=[WINDOW[1]])
            assert price(MARKET, saved, curves) == pytest.approx(WINDOW_PRICE, **CLOSE)
            assert price(MARKET, saved, curves) == pytest.approx(
                quote_by_dates(
                    MARKET, day(WINDOW[0]), day(WINDOW[1]), template, curves, WorkCounter()
                ),
                **CLOSE,
            )
    counter = WorkCounter()
    saved = request(
        None, (100.0,), onetime("calday"), starts=[WINDOW[0]], ends=[WINDOW[1]], counter=counter
    )
    assert saved.component_quantity.tolist() == [4_700.0]  # 47 calendar days
    counts = counter.freeze().as_dict()
    assert (counts["windows_resolved"], counts["observations_made"]) == (1, 35)
    assert "months_resolved" not in counts and counts["ticket_codes_read"] == 0
    table = grid(saved)
    assert under(table, "period") == [WINDOW_WORDS]
    assert under(table, "settlement_frequency") == ["onetime"]
    assert under(table, "payment_date") == [serial("2027-03-05")]  # +5bd from Friday 26 February


def test_windows_weigh_by_quantity_and_factor_and_match_the_booked_portfolio() -> None:
    # Two windows of unequal quantities, observation counts and payment days: the quantity-and-
    # factor-weighted mean of their averages, the same in either row order, a window repeated at
    # half its quantity the same as once, and the portfolio booked at the price marking zero on
    # either route while every payment is ahead.
    assert price(MARKET, windows(), RATES) == pytest.approx(WINDOWS_PRICE, **CLOSE)
    reordered = windows((300_000.0, 100_000.0), pays=PAYS[::-1], spans=(SHORT, WINDOW))
    assert price(MARKET, reordered, RATES) == pytest.approx(WINDOWS_PRICE, **CLOSE)
    repeated = windows(
        (100_000.0, 150_000.0, 150_000.0),
        pays=(PAYS[0], PAYS[1], PAYS[1]),
        spans=(WINDOW, SHORT, SHORT),
    )
    assert price(MARKET, repeated, RATES) == pytest.approx(WINDOWS_PRICE, **CLOSE)
    short_words = "2027-02-01 to 2027-02-12"
    assert under(grid(repeated), "period") == [WINDOW_WORDS, short_words, short_words]
    cleared_price = (100_000 * WINDOW_PRICE + 300_000 * 1.2) / 400_000
    assert price(MARKET, windows(template=onetime(route="cleared"))) == pytest.approx(
        cleared_price, **CLOSE
    )
    booking: dict[str, object] = {
        "quantity_unit": "BBL",
        "quantity_per": "period",
        "settlement_frequency": "onetime",
        "schedule_method": "asian",
        "settlement_method": "financial",
        "payment_holiday_calendar": WEEKENDS_ONLY,
    }
    ticket: dict[str, list[object]] = {
        "trade_id": [1, 2],
        "trade_date": [DEC_31, DEC_31],
        "start_date": [WINDOW[0], SHORT[0]],
        "end_date": [WINDOW[1], SHORT[1]],
        "quantity": list(QUANTITIES),
        "payment_day": [day(PAYS[0]), day(PAYS[1])],
    }
    for k, fields, curves in (
        (cleared_price, {"route": "cleared", "clearing_house": "CME Clearing"}, None),
        (
            WINDOWS_PRICE,
            {"route": "bilateral", "counterparty": "ACME Trading", "discount_curve_key": "SOFR"},
            RATES,
        ),
    ):
        batch, _ = created(STRIP, {**ticket, "fixed_price": [k, k]}, {**booking, **fields})
        prep = prepared_trades(batch.encoded, (MARKET.market_history,), WorkCounter())
        assert trade_results(prep, (MARKET,), WorkCounter(), curves).mark == pytest.approx(
            0.0, abs=1e-6
        )


def test_a_dated_row_follows_the_templates_frequency() -> None:
    # Under monthly a dated row is its months, each at the row's quantity, as a dated booking
    # row is: 11 January to 26 February at seven is F27 and G27 at seven, its readback two rows
    # from one, and per calendar day its portions weigh their 21 and 26 days. Under onetime a
    # code row is one window, the month's dates naming it; a code row and a dated row stand
    # together, each paying +5bd from its own last observation.
    dated = request(None, (7.0,), otc(), starts=[WINDOW[0]], ends=[WINDOW[1]])
    two = request(CODES, (7.0, 7.0), otc())
    assert price(MARKET, dated, RATES) == pytest.approx(price(MARKET, two, RATES), **CLOSE)
    table = grid(dated)
    assert under(table, "row") == [1.0, 1.0]
    assert under(table, "period") == ["F27", "G27"]
    assert under(table, "quantity") == [7.0, 7.0]
    assert under(table, "payment_date") == [serial("2027-02-05"), serial("2027-03-05")]
    per_day = request(None, (100.0,), otc("calday"), starts=[WINDOW[0]], ends=[WINDOW[1]])
    assert per_day.component_quantity.tolist() == [2_100.0, 2_600.0]
    by_code = request(("F27",), (5.0,), onetime())
    assert price(MARKET, by_code, RATES) == pytest.approx(1.0, **CLOSE)
    assert under(grid(by_code), "period") == ["2027-01-01 to 2027-01-31"]
    mixed = request(
        ("F27", None), QUANTITIES, onetime(), starts=[None, SHORT[0]], ends=[None, SHORT[1]]
    )
    first = float(factors_on(SOFR, dates("2027-02-05"))[0])  # +5bd from Friday 29 January
    second = float(factors_on(SOFR, dates("2027-02-19"))[0])  # +5bd from Friday 12 February
    assert price(MARKET, mixed, RATES) == pytest.approx(
        (100_000 * first * 1.0 + 300_000 * second * 1.2) / (100_000 * first + 300_000 * second),
        **CLOSE,
    )
    assert under(grid(mixed), "period") == ["2027-01-01 to 2027-01-31", "2027-02-01 to 2027-02-12"]
    # Both dates beside a code: the dates book the row and the code is never read.
    overridden = request(("nonsense",), (7.0,), otc(), starts=[WINDOW[0]], ends=[WINDOW[1]])
    assert price(MARKET, overridden, RATES) == pytest.approx(price(MARKET, two, RATES), **CLOSE)


# --- the rules ---------------------------------------------------------------------------------


def test_each_row_takes_its_period_by_the_bookings_rule() -> None:
    for bad in ("BALF27", "F2027", "Z6", "x"):
        refused(
            f"contract_code row 2 is {bad!r}, expected a contract or strip with two-digit years, "
            "such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28",
            codes=("F27", bad),
        )
    refused(
        "contract_code row 1 is 'X26', expected months the index's schedule has a contract for; "
        "it has none for 2026-11",
        codes=("X26", "G27"),
    )
    lower = request(("f27", "g27"))
    assert under(grid(lower), "period") == ["F27", "G27"]
    refused(
        "start_date row 1 is 2027-01-11 without end_date row 1, expected both dates, the "
        "period's first and last day, or neither and a contract_code",
        codes=(None, "G27"),
        quantities=(1.0, 1.0),
        starts=[WINDOW[0], None],
    )
    refused(
        "row 2 has no period, expected a contract_code or start_date with end_date on each row; "
        "contract_code, start_date and end_date are not supplied",
        codes=("F27", None),
        quantities=(1.0, 1.0),
    )
    refused(
        "end_date row 1 is 2027-01-11, expected a day on or after start_date row 1, 2027-02-26",
        codes=None,
        quantities=(1.0,),
        template=onetime(),
        starts=[WINDOW[1]],
        ends=[WINDOW[0]],
    )
    refused(
        "start_date row 1 is 2027-03-01 and end_date row 1 2027-03-31, expected a window priced "
        "by the contracts of the index's schedule; it opens on 2027-03-01, after the last day "
        "they price, 2027-02-26",
        codes=None,
        quantities=(1.0,),
        template=onetime(),
        starts=["2027-03-01"],
        ends=["2027-03-31"],
    )
    refused(
        "the window of row 1 has no pricing day from 2027-01-30 to 2027-01-31, expected a Monday "
        "to Friday of the days it covers the index's market is open on; the asian method averages "
        "the pricing days a component covers",
        codes=None,
        quantities=(1.0,),
        template=onetime(),
        starts=["2027-01-30"],
        ends=["2027-01-31"],
    )
    refused(
        f"{WINDOW_WORDS} of row 1 pays on 2027-02-26, expected a day after its last observation, "
        "2027-02-26, when its final price exists",
        codes=None,
        quantities=(1.0,),
        template=onetime(),
        pays=[WINDOW[1]],
        starts=[WINDOW[0]],
        ends=[WINDOW[1]],
    )
    with pytest.raises(ValueError) as booking_field:
        rfq(STRIP, a_ticket({"trade_id": [1.0], "quantity": [1.0]}), cleared(), WorkCounter())
    assert str(booking_field.value) == (
        "trade_id is a field of booking alone, expected one a request's rows hold: contract_code, "
        "start_date, end_date, quantity, payment_day"
    )
    with pytest.raises(ValueError) as unweighted:
        rfq(STRIP, a_ticket({"contract_code": ["F27"]}), cleared(), WorkCounter())
    assert str(unweighted.value) == (
        "quantity is missing, expected a column of the request, one per row"
    )


def test_quantities_are_finite_nonnegative_and_not_all_zero() -> None:
    refused(
        "quantity row 2 is -1.0, expected a finite number of zero or more; a request is a "
        "weighted quote, not a spread or a net position",
        quantities=(1.0, -1.0),
    )
    for bad in (float("inf"), float("nan")):
        refused(
            f"quantity row 1 is {bad!r}, expected a finite number of zero or more; a request "
            "is a weighted quote, not a spread or a net position",
            quantities=(bad, 1.0),
        )
    refused(
        "quantity is zero on every row, expected at least one positive; a request of nothing "
        "has no price",
        quantities=(0.0, 0.0),
    )
    refused(
        "quantity row 1 is 1e+308 per calendar day, expected a finite quantity for the period; "
        "times its 31 days it outruns the largest number",
        quantities=(1e308, 1.0),
        template=cleared("calday"),
    )
    # Scale invariance at the edges: the price is a convex combination whatever the scale, the
    # quantities kept as entered, and one month cancels at any scale.
    for scale in (1e-300, 1e-6, 1.0, 1e6, 1e300):
        scaled = request(CODES, (100_000.0 * scale, 300_000.0 * scale), otc(), EXPLICIT)
        assert price(MARKET, scaled, RATES) == pytest.approx(EXPLICIT_PRICE, **CLOSE)
        assert scaled.request.quantity is scaled.component_quantity
    tiny_beside_huge = request(CODES, (1e-300, 1e300), otc(), EXPLICIT)
    assert price(MARKET, tiny_beside_huge, RATES) == pytest.approx(1.2, **CLOSE)
    # Fractions stand: a request's quantities are weights, not a booking's whole counts.
    assert price(MARKET, request(CODES, (0.5, 1.5), otc(), EXPLICIT), RATES) == pytest.approx(
        EXPLICIT_PRICE, **CLOSE
    )


def test_the_template_the_index_and_the_market_refuse_as_a_quote_does() -> None:
    refused(
        "settlement_method is 'physical', expected 'financial' with the asian method; an asian "
        "future is cash settled on the average of its month's pricing days",
        template=physical("asian"),
    )
    # The kernel's rule over the frequency, the request named in the trade's place: period under
    # monthly and month under onetime, since onetime-averaging.md and dated-quotes.md.
    refused(
        "quantity_per of the request is 'period', expected 'month' or 'calday' under "
        "settlement_frequency = monthly; period is the total of a onetime period and says "
        "nothing of a month",
        template=a_template(**{**dict(otc().values), "quantity_per": "period"}),
    )
    refused(
        "quantity_per of the request is 'month', expected 'period' or 'calday' under "
        "settlement_frequency = onetime; month says nothing of a window, period is its total and "
        "calday its days",
        template=onetime("month"),
    )
    refused(
        "schedule_method of the request is 'lastday', expected 'asian' under settlement_frequency "
        "= onetime; a onetime period averages every pricing day it covers, and the expiry-based "
        "methods take their contract's month",
        template=a_template(
            **{**dict(otc(method="lastday").values), "settlement_frequency": "onetime"}
        ),
    )
    refused(
        "discount_curve_key is missing, expected it in the quote template when route = bilateral",
        template=a_template(
            route="bilateral",
            settlement_method="financial",
            schedule_method="asian",
            quantity_per="month",
            settlement_frequency="monthly",
            payment_day=otc().values["payment_day"],
            payment_holiday_calendar=WEEKENDS_ONLY,
        ),
    )
    assert price(MARKET, request()) == pytest.approx(CLEARED_PRICE, **CLOSE)  # the same index
    refused_price(
        MARKET,
        request(
            ix=an_index(
                "TWIN",
                contracts=(("Z26", "2026-12-15"), ("F27", "2027-01-29"), ("G27", "2027-02-26")),
                holidays=("2027-01-01",),
                quote=("USD", "BBL"),
                measure=("VOLUME", "BBL"),
                lot=("BBL", 1.0, "BBL"),
            )
        ),
        "market is over another index, 'STRIP', expected the request's, 'TWIN'",
    )
    saved = request(template=otc())
    refused_price(
        MARKET,
        saved,
        "discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' "
        "with route = bilateral, whose payments it discounts",
    )
    refused_price(
        MARKET,
        request(),
        "discount_curve_set is a collection of 1 curve, expected none with route = cleared; a "
        "cleared quote discounts nothing",
        RATES,
    )
    short = curve_set(curve_of((DEC_31, 1.0), ("2027-02-05", 0.99), ("2027-03-05", 0.97)))
    refused_price(
        MARKET,
        request(template=otc(), pays=EXPLICIT),
        "the payment of G27 on 2027-03-08 on SOFR is past the discount curve 'SOFR', which runs "
        "from 2026-12-31 to 2027-03-05; expected every payment day after the valuation date "
        "covered",
        short,
    )
    refused_price(
        MARKET,
        windows(),
        f"the payment of {WINDOW_WORDS} on 2027-03-08 on SOFR is past the discount curve 'SOFR', "
        "which runs from 2026-12-31 to 2027-03-05; expected every payment day after the "
        "valuation date covered",
        short,
    )
    assert price(MARKET, saved, short) == pytest.approx(DEFAULT_PRICE, **CLOSE)
    refused_price(
        quoted(MARKET.market_history, 1.0),
        request(),
        "requested contract 'G27' is beyond live-price coverage ending at 'F27'",
    )
    refused_price(
        market_on("2027-02-02", 1.2),
        request(template=physical()),
        "F27 expired 2027-01-29, before valuation date 2027-02-02; a physical fixed_float after "
        "its expiry is not supported",
    )


# --- the sheet ---------------------------------------------------------------------------------

ENTRY = {
    **QUOTE_ENTRY,
    **{name: bridge.entry(name) for name in ("_CreateRFQ", "_QuoteRFQ", "util_ReadHandle")},
}


def test_the_page_example_through_the_seam_and_the_seams_refusals() -> None:
    ix, _ = seam_index(
        "SEAM",
        [("Z26", "2026-12-15"), ("F27", "2027-01-29"), ("G27", "2027-02-26")],
        ["2027-01-01"],
        [("BBL", 1.0)],
        ("VOLUME", "BBL"),
    )
    history = seam_history(ix, "2026-12-16", DEC_31, ["2027-01-01"], {})
    market = seam_market(history, "SEAM", 1.0, 1.2)
    weekends = ENTRY["_CreateHolidayCalendar"](column([serial("2030-01-01")]))
    fields = row(
        "route",
        "settlement_method",
        "schedule_method",
        "quantity_per",
        "payment_day",
        "payment_holiday_calendar",
        "discount_curve_key",
        "settlement_frequency",
    )
    otc_template = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        fields,
        row("bilateral", "financial", "asian", "month", "+5bd", weekends, "SOFR", "monthly"),
    )
    cleared_template = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        row(
            "route",
            "settlement_method",
            "schedule_method",
            "quantity_per",
            "payment_day",
            "payment_holiday_calendar",
            "settlement_frequency",
        ),
        row("cleared", "financial", "asian", "month", "+5bd", weekends, "monthly"),
    )
    onetime_template = ENTRY["_CreateQuoteTemplate"](
        "fixed_float",
        fields,
        row("bilateral", "financial", "asian", "period", "+5bd", weekends, "SOFR", "onetime"),
    )
    sofr = ENTRY["_CreateDiscountCurve"](
        "SOFR",
        row("date", "discount_factor"),
        cells_of(
            [serial(DEC_31), 1.0],
            [serial("2027-02-05"), 0.99],
            [serial("2027-02-08"), 0.98],
            [serial("2027-03-05"), 0.97],
            [serial("2027-03-08"), 0.96],
        ),
    )
    rates = ENTRY["_CollectDiscountCurves"](cells_of([sofr]))
    by_code = row("contract_code", "quantity")
    ticket = cells_of(["F27", 100_000.0], ["G27", 300_000.0])
    saved = ENTRY["_CreateRFQ"](ix, by_code, ticket, otc_template)
    assert re.fullmatch(rf"{os.getpid()}:rfq:SEAM:\d+", str(saved))
    with_days = row("contract_code", "quantity", "payment_day")
    dated = ENTRY["_CreateRFQ"](
        ix,
        with_days,
        cells_of(
            ["F27", 100_000.0, serial("2027-02-08")], ["G27", 300_000.0, serial("2027-03-08")]
        ),
        otc_template,
    )
    assert ENTRY["_QuoteRFQ"](market, saved, rates) == pytest.approx(DEFAULT_PRICE, **CLOSE)
    assert ENTRY["_QuoteRFQ"](market, dated, rates) == pytest.approx(EXPLICIT_PRICE, **CLOSE)
    one_cell = ENTRY["_CreateRFQ"](ix, by_code, cells_of(["G27", 5.0]), cleared_template)
    assert ENTRY["_QuoteRFQ"](market, one_cell, bridge.MISSING) == pytest.approx(1.2, **CLOSE)
    by_dates = row("start_date", "end_date", "quantity", "payment_day")
    windowed = ENTRY["_CreateRFQ"](
        ix,
        by_dates,
        cells_of(
            [serial(WINDOW[0]), serial(WINDOW[1]), 100_000.0, serial(PAYS[0])],
            [serial(SHORT[0]), serial(SHORT[1]), 300_000.0, serial(PAYS[1])],
        ),
        onetime_template,
    )
    assert ENTRY["_QuoteRFQ"](market, windowed, rates) == pytest.approx(WINDOWS_PRICE, **CLOSE)
    table = spilled(ENTRY["util_ReadHandle"](dated))
    assert table[0][:7] == [
        "row",
        "period",
        "quantity",
        "quantity_per",
        "component_quantity",
        "payment_source",
        "payment_date",
    ]
    assert table[2] == [
        1.0,
        "F27",
        100_000.0,
        "month",
        100_000.0,
        "request",
        serial("2027-02-08"),
        "SEAM",
        "asian",
        "bilateral",
        "financial",
        "USD per BBL",
        "SOFR",
        "monthly",
    ]
    assert table[3][5:7] == ["request", serial("2027-03-08")]
    assert spilled(ENTRY["util_ReadHandle"](saved))[2][5:7] == ["template", serial("2027-02-05")]
    assert spilled(ENTRY["util_ReadHandle"](windowed))[2][1] == WINDOW_WORDS
    # The seam's refusals in signature order, then the library's with its prefix.
    assert ENTRY["_CreateRFQ"](None, by_code, ticket, otc_template) == (
        "#ERROR _CreateRFQ: index is blank, expected index handle"
    )
    assert str(
        ENTRY["_CreateRFQ"](ix, row("contract_codes", "quantity"), ticket, otc_template)
    ).startswith(
        "#ERROR _CreateRFQ: fields cell (1, 1) is text 'contract_codes', expected a field of "
        "fixed_float: "
    )
    assert ENTRY["_CreateRFQ"](
        ix, by_code, cells_of(["F27", 1.0], ["G27", "ten"]), otc_template
    ) == ("#ERROR _CreateRFQ: rows cell (2, 2) is text 'ten', expected number")
    assert ENTRY["_CreateRFQ"](
        ix, by_code, cells_of(["F27", 1.0], ["G27", None]), otc_template
    ) == ("#ERROR _CreateRFQ: rows cell (2, 2) is blank, expected number")
    assert ENTRY["_CreateRFQ"](ix, by_code, ticket, market) == (
        f"#ERROR _CreateRFQ: template is market handle {market!r}, expected quote template handle"
    )
    assert ENTRY["_CreateRFQ"](
        ix, row("trade_id", "quantity"), cells_of([1.0, 1.0]), otc_template
    ) == (
        "#ERROR _CreateRFQ: ValueError: trade_id is a field of booking alone, expected one a "
        "request's rows hold: contract_code, start_date, end_date, quantity, payment_day"
    )
    assert ENTRY["_CreateRFQ"](ix, with_days, cells_of(["F27", 1.0, "+5bd"]), otc_template) == (
        "#ERROR _CreateRFQ: ValueError: payment_day row 1 is '+5bd', expected a date; a request's "
        "rows pay on dates, and a rule is the template's to hold"
    )
    assert ENTRY["_QuoteRFQ"](market, saved, bridge.MISSING) == (
        "#ERROR _QuoteRFQ: ValueError: discount_curve_set is missing, expected a collection of "
        "discount curves holding 'SOFR' with route = bilateral, whose payments it discounts"
    )
    assert ENTRY["_QuoteRFQ"](market, otc_template, rates) == (
        f"#ERROR _QuoteRFQ: rfq is quote template handle {otc_template!r}, expected rfq handle"
    )
    assert ENTRY["_QuoteRFQ"](history, saved, rates) == (
        f"#ERROR _QuoteRFQ: market is market history handle {history!r}, expected market handle"
    )
    assert isinstance(saved, str) and PaymentSource.REQUEST.value == "request"


# --- a factor near the smallest number, the review's case ----------------------------------------


@pytest.mark.parametrize("tiny", [1e-300, 1e-310, 5e-324], ids=["normal", "subnormal", "smallest"])
def test_a_factor_as_small_as_the_curve_allows_weighs_every_month_exactly(tiny: float) -> None:
    # A curve at the review's factor on both payment days, down to the smallest positive number,
    # which the curve accepts: the factors cancel, and the request prices as its cleared self,
    # exactly, instead of losing the smaller month's weight below the smallest number; the quote
    # of the strip likewise.
    rates = curve_set(curve_of((DEC_31, 1.0), ("2027-02-05", tiny), ("2027-03-05", tiny)))
    for quantities, expected in (
        ((1.0, 2.0), 3.4 / 3),
        ((3.0, 1.0), 4.2 / 4),
        ((1e6, 3e6), 1.15),
        ((1.0, 1.0), 1.1),
    ):
        saved = request(CODES, quantities, otc())
        assert price(MARKET, saved, rates) == pytest.approx(expected, **CLOSE)
    assert quote_on(MARKET, "F27-G27", otc(), rates) == pytest.approx(1.1, **CLOSE)
    # One factor near the smallest beside one of one: the tiny month's share is nothing, the
    # price the other month's, and the scaled weights stay finite.
    lopsided = curve_set(curve_of((DEC_31, 1.0), ("2027-02-05", 1.0), ("2027-03-05", tiny)))
    assert price(MARKET, request(CODES, (1.0, 1.0), otc()), lopsided) == pytest.approx(1.0, **CLOSE)
    assert price(MARKET, request(CODES, (1.0, 1.0), otc(), EXPLICIT), RATES) == pytest.approx(
        (0.98 * 1.0 + 0.96 * 1.2) / (0.98 + 0.96), **CLOSE
    )


def test_the_reviews_cases_a_row_of_nothing_and_a_tiny_quantity_beside_the_smallest_factor() -> (
    None
):
    # The review's two cases on a curve at one on 5 February and the smallest positive number on
    # 5 March: a row of nothing beside a month at the smallest factor prices that month, where a
    # halved factor once became nothing; and a quantity of 1e-100 at factor one beside 1e224 at
    # the smallest factor keeps both months, their weights 1e-100 and 1e224 times 5e-324 apart,
    # where a quantity scaled by the largest once became nothing: 1.166333687 by hand.
    smallest = float(np.finfo(np.float64).smallest_subnormal)
    lopsided = curve_set(curve_of((DEC_31, 1.0), ("2027-02-05", 1.0), ("2027-03-05", smallest)))
    nothing_beside = request(CODES, (0.0, 1.0), otc())
    assert price(MARKET, nothing_beside, lopsided) == pytest.approx(1.2, **CLOSE)
    both = request(CODES, (1e-100, 1e224), otc())
    second = 1e224 * smallest
    assert price(MARKET, both, lopsided) == pytest.approx(
        (1e-100 * 1.0 + second * 1.2) / (1e-100 + second), **CLOSE
    )
    assert price(MARKET, both, lopsided) == pytest.approx(1.166333687, abs=5e-10)
    # The same two with the factors the other way round, and at the largest quantities.
    assert price(MARKET, request(CODES, (1.0, 0.0), otc()), lopsided) == pytest.approx(1.0, **CLOSE)
    huge = request(CODES, (1.7e308, 1.7e308), otc())
    assert price(MARKET, huge, lopsided) == pytest.approx(1.0, **CLOSE)
    assert price(MARKET, huge, RATES) == pytest.approx(
        (0.99 * 1.0 + 0.97 * 1.2) / (0.99 + 0.97), **CLOSE
    )
