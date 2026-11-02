"""A request for quote, rfq-quoting.md: the ticket's worked acceptance by hand on the quote tests'
strip, a month-matching asian index valued on 31 December 2026 with January at 1.00 and
February at 1.20, paying +5bd on the weekend calendar or on the request's own dates; the
quantities' meaning under both bases; equality with _Quote on the whole strip; the rows' order,
repeats and zeros; the market's states through the request's reuse; a trade booked at the price
marking zero; the precedence of the request's dates over the template's day; the rules in the
seam's words and the library's. docs/library/quoting/rfq.md is the page."""

import os
import re
from collections.abc import Sequence
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest
from test_bilateral_kernel import CLOSE, curve_of, curve_set
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


def request(
    codes: Sequence[str] = CODES,
    quantities: Sequence[float] = QUANTITIES,
    template: QuoteTemplate | None = None,
    pays: Sequence[str] | None = None,
    ix: Index = STRIP,
    counter: WorkCounter | None = None,
) -> Rfq:
    return rfq(
        ix,
        tuple(codes),
        np.array(quantities, dtype=np.float64),
        cleared() if template is None else template,
        None if pays is None else dates(*pays),
        counter or WorkCounter(),
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
    # The readback shows the effective dates and their source, the entered quantities and the
    # resolved months, and prices nothing.
    table = grid(explicit)
    assert table[0] == [
        "row",
        "contract_code",
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
    ]
    assert table[1][:7] == ["int64", "str", "float64", "str", "float64", "str", "datetime64[D]"]
    assert under(table, "row") == [1.0, 2.0]
    assert under(table, "contract_code") == ["F27", "G27"]
    assert under(table, "quantity") == [100_000.0, 300_000.0]
    assert under(table, "component_quantity") == [100_000.0, 300_000.0]
    assert under(table, "payment_source") == ["request", "request"]
    assert under(table, "payment_date") == [serial("2027-02-08"), serial("2027-03-08")]
    assert under(table, "index") == ["STRIP", "STRIP"]
    assert under(table, "quote_unit") == ["USD per BBL"] * 2
    assert under(table, "discount_curve_key") == ["SOFR", "SOFR"]
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
    # Per month the entered quantity is the month's, by reference.
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


def test_rows_in_any_order_repeated_and_zero() -> None:
    reversed_rows = request(("G27", "F27"), (300_000.0, 100_000.0), otc(), EXPLICIT[::-1])
    assert price(MARKET, reversed_rows, RATES) == pytest.approx(EXPLICIT_PRICE, **CLOSE)
    assert under(grid(reversed_rows), "contract_code") == ["G27", "F27"]
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
        "contract_codes row 1 is 'H27', expected months the index's schedule has a contract for; "
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
        "financial, or payment_dates with the request",
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
    # A physical request takes no dates; it pays on no day and reads back dashes.
    refused(
        "payment_dates is supplied, expected none with settlement_method = physical; a physical "
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


# --- the rules ---------------------------------------------------------------------------------


def test_the_columns_align_and_each_code_is_one_month_of_the_schedule() -> None:
    refused(
        "contract_codes has 0 rows, expected one or more, a month per row", codes=(), quantities=()
    )
    refused("quantities has 3 rows, expected 2, one per contract code", quantities=(1.0, 2.0, 3.0))
    refused(
        "payment_dates has 1 rows, expected 2, one per contract code",
        template=otc(),
        pays=EXPLICIT[:1],
    )
    for bad in ("F27-G27", "BALF27", "CAL27", "1H27", "F2027", "Z6"):
        refused(
            f"contract_codes row 2 is {bad!r}, expected a month letter and a two-digit year, "
            "such as F26",
            codes=("F27", bad),
        )
    refused(
        "contract_codes row 1 is 'X26', expected months the index's schedule has a contract for; "
        "it has none for 2026-11",
        codes=("X26", "G27"),
    )
    lower = request(("f27", "g27"))
    assert under(grid(lower), "contract_code") == ["F27", "G27"]
    assert lower.contract_codes == ("f27", "g27")


def test_quantities_are_finite_nonnegative_and_not_all_zero() -> None:
    refused(
        "quantities row 2 is -1.0, expected a finite number of zero or more; a request is a "
        "weighted quote, not a spread or a net position",
        quantities=(1.0, -1.0),
    )
    for bad in (float("inf"), float("nan")):
        refused(
            f"quantities row 1 is {bad!r}, expected a finite number of zero or more; a request "
            "is a weighted quote, not a spread or a net position",
            quantities=(bad, 1.0),
        )
    refused(
        "quantities are all zero, expected at least one positive; a request of nothing has no "
        "price",
        quantities=(0.0, 0.0),
    )
    refused(
        "quantities row 1 is 1e+308 per calendar day, expected a finite quantity for the month; "
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


def test_the_template_the_index_and_the_market_refuse_as_a_quote_does() -> None:
    refused(
        "settlement_method is 'physical', expected 'financial' with the asian method; an asian "
        "future is cash settled on the average of its month's pricing days",
        template=physical("asian"),
    )
    # onetime-averaging.md's second slice: a request prices by the month, and a template holding
    # onetime, or period as its basis, is refused in so many words rather than quoted as monthly.
    refused(
        "settlement_frequency is 'onetime', expected 'monthly'; a quote prices by the month and "
        "does not price a onetime period across a window's dates as monthly",
        template=a_template(**{**dict(otc().values), "settlement_frequency": "onetime"}),
    )
    refused(
        "quantity_per is 'period', expected 'month' or 'calday'; period is the total of a "
        "onetime period, which a quote does not price",
        template=a_template(**{**dict(otc().values), "quantity_per": "period"}),
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
    codes = cells_of(["F27"], ["G27"])
    quantities = column([100_000.0, 300_000.0])
    explicit = column([serial("2027-02-08"), serial("2027-03-08")])
    saved = ENTRY["_CreateRFQ"](ix, codes, quantities, otc_template, bridge.MISSING)
    assert re.fullmatch(rf"{os.getpid()}:rfq:SEAM:\d+", str(saved))
    dated = ENTRY["_CreateRFQ"](ix, codes, quantities, otc_template, explicit)
    assert ENTRY["_QuoteRFQ"](market, saved, rates) == pytest.approx(DEFAULT_PRICE, **CLOSE)
    assert ENTRY["_QuoteRFQ"](market, dated, rates) == pytest.approx(EXPLICIT_PRICE, **CLOSE)
    one_cell = ENTRY["_CreateRFQ"](
        ix, cells_of(["G27"]), column([5.0]), cleared_template, bridge.MISSING
    )
    assert ENTRY["_QuoteRFQ"](market, one_cell, bridge.MISSING) == pytest.approx(1.2, **CLOSE)
    table = spilled(ENTRY["util_ReadHandle"](dated))
    assert table[0][:7] == [
        "row",
        "contract_code",
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
    ]
    assert table[3][5:7] == ["request", serial("2027-03-08")]
    assert spilled(ENTRY["util_ReadHandle"](saved))[2][5:7] == ["template", serial("2027-02-05")]
    # The seam's refusals in signature order, then the library's with its prefix.
    assert ENTRY["_CreateRFQ"](None, codes, quantities, otc_template, bridge.MISSING) == (
        "#ERROR _CreateRFQ: index is blank, expected index handle"
    )
    assert ENTRY["_CreateRFQ"](ix, row("F27", "G27"), quantities, otc_template, bridge.MISSING) == (
        "#ERROR _CreateRFQ: contract_codes is 1x2 array, expected column of text"
    )
    assert ENTRY["_CreateRFQ"](
        ix, cells_of(["F27"], [1.0]), quantities, otc_template, bridge.MISSING
    ) == ("#ERROR _CreateRFQ: contract_codes cell (2, 1) is number 1.0, expected text")
    assert ENTRY["_CreateRFQ"](
        ix, codes, cells_of([1.0], ["ten"]), otc_template, bridge.MISSING
    ) == ("#ERROR _CreateRFQ: quantities cell (2, 1) is text 'ten', expected number")
    assert ENTRY["_CreateRFQ"](ix, codes, quantities, market, bridge.MISSING) == (
        f"#ERROR _CreateRFQ: template is market handle {market!r}, expected quote template handle"
    )
    assert ENTRY["_CreateRFQ"](ix, codes, quantities, otc_template, None) == (
        "#ERROR _CreateRFQ: payment_dates is blank, expected column of dates"
    )
    assert ENTRY["_CreateRFQ"](
        ix, codes, quantities, otc_template, cells_of([serial("2027-02-08")], [None])
    ) == ("#ERROR _CreateRFQ: payment_dates cell (2, 1) is blank, expected date")
    assert ENTRY["_CreateRFQ"](
        ix, codes, column([1.0, 2.0, 3.0]), otc_template, bridge.MISSING
    ) == ("#ERROR _CreateRFQ: ValueError: quantities has 3 rows, expected 2, one per contract code")
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
