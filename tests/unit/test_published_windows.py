"""A month chosen by code and the same month typed as dates on a published index, issue #271's
first convention: a contract code selects the prints whose rows name its month, whatever their
dates, and a window of dates the prints dated in it, whatever month their rows name, a window
that fills a calendar month as much as a part of one. The schedule here counts August's last
Monday toward September and September's last toward October, so the two are different prints,
and every expected number is hand arithmetic over them. docs/library/trades/create-trades.md
and docs/library/quoting/quote.md are the pages."""

import numpy as np
import pytest
from holiday_fixtures import index_on
from numpy.typing import NDArray
from test_create_trades import created, key_of, refused
from test_quote import WEEKENDS_ONLY, financial
from test_rfq import request

from catalyst.calendar.calendar import calendar
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import valuation_date
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.index_definitions.published_schedule import published_schedule
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market, market
from catalyst.market.market_history import market_history
from catalyst.market_data.price_vector import price_vector
from catalyst.market_data.published_fixings import published_fixings
from catalyst.quoting.quote import quote, quote_by_dates
from catalyst.quoting.rfq import quote_rfq
from catalyst.quoting.template import QuoteTemplate
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


# Six weekly prints. The schedule's author counts a print toward the month of the Friday that
# follows it: Monday 31 August toward September, and Monday 28 September toward October.
PRINTS = ("2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05")
WEEKLY = index_on(
    "WEEKLY",
    "A weekly index whose months do not follow its dates",
    published_schedule(("U26", "U26", "U26", "U26", "V26", "V26"), dates(*PRINTS)),
    index_conventions("DOLLAR", "GAL", "DOLLAR", "VOLUME", "GAL", UNITS),
    contract_specifications(
        ("gal",), np.array([1.0]), ("GAL",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    None,
    "gal",
    UNITS,
)
AUG_18 = "2026-08-18"
SEPTEMBER, OCTOBER = 4.0, 5.0  # the two months' quotes, every print still to come


def on_aug_18() -> Market:
    """The index's market on 18 August 2026, before any print: no fixing, September quoted at 4
    and October at 5."""
    made = calendar(valuation_date(day(AUG_18), 0.5), WEEKLY)
    history = market_history(made, published_fixings(dates(), np.array([]), WEEKLY))
    return market(history, price_vector("WEEKLY", np.array([SEPTEMBER, OCTOBER])))


def by_code(code: str, template: QuoteTemplate | None = None) -> float:
    return quote(on_aug_18(), code, template or financial(), "flat", None, WorkCounter())


def by_dates(start: str, end: str) -> float:
    return quote_by_dates(
        on_aug_18(), day(start), day(end), financial(), "flat", None, WorkCounter()
    )


# --- the quote -----------------------------------------------------------------------------------


# U26 by its code is the four prints whose rows say U26, 31 August among them, all at
# September's quote. September typed as two dates is the four prints dated in it: three of
# U26's at 4 and the 28th, a V26 print, at 5, so (4 + 4 + 4 + 5) / 4 = 4.25. No print is dated
# 1 September, so the window from the 2nd holds the same four.
def test_a_month_by_code_and_the_same_month_by_dates_are_different_prints() -> None:
    assert by_code("U26") == SEPTEMBER
    assert by_dates("2026-09-01", "2026-09-30") == pytest.approx(4.25, rel=1e-12)
    assert by_dates("2026-09-02", "2026-09-30") == pytest.approx(4.25, rel=1e-12)
    # October by code is its two prints, the 28th of September among them; by dates the one
    # print dated in October. Both are at October's quote, and neither reads a September print.
    assert by_code("V26") == OCTOBER
    assert by_dates("2026-10-01", "2026-10-31") == OCTOBER


# The balance of a label is a window of dates, from the valuation day or the label's first day,
# whichever is later: asked before September begins it is 1 to 30 September by dates, the price
# of the two dates above and not the code's.
def test_the_balance_of_a_month_is_a_window_of_dates() -> None:
    assert by_code("BALU26") == pytest.approx(4.25, rel=1e-12)
    assert by_code("BALU26") == by_dates("2026-09-01", "2026-09-30")
    assert by_code("BALU26") != by_code("U26")


# A strip by code is each month's own prints; the same two months by dates are the prints dated
# in each, per month: September's four at 4.25 and October's one at 5, a month weighing one.
def test_a_strip_by_code_and_a_window_across_months_each_take_their_own_prints() -> None:
    assert by_code("U26-V26") == pytest.approx((4.0 + 5.0) / 2, rel=1e-12)
    assert by_dates("2026-09-01", "2026-10-31") == pytest.approx((4.25 + 5.0) / 2, rel=1e-12)


# --- the trade -----------------------------------------------------------------------------------

TEMPLATE: dict[str, object] = {
    "quantity_unit": "gal",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "asian",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "TEST_CLEARER",
    "payment_day": "+5bd",
    "payment_holiday_key": key_of(WEEKENDS_ONLY),
}
BOOKED: dict[str, list[object]] = {
    "trade_id": [1001],
    "trade_date": ["2026-08-10"],
    "quantity": [40_000],
    "fixed_price": [3.10],
}


def coded(code: str) -> Trades:
    return created(WEEKLY, {**BOOKED, "contract_code": [code]}, TEMPLATE)[0]


def dated(start: str, end: str) -> Trades:
    return created(WEEKLY, {**BOOKED, "start_date": [start], "end_date": [end]}, TEMPLATE)[0]


def observed_days(batch: Trades) -> list[list[str]]:
    """Each component's observation days, in component order."""
    made = batch.encoded.legs[0].observations
    count = int(made.component[-1]) + 1
    return [[str(d) for d in made.date[made.component == k]] for k in range(count)]


def mark_of(batch: Trades) -> float:
    quoted = on_aug_18()
    prepared = prepared_trades(batch.encoded, (quoted.market_history,), WorkCounter())
    return trade_results(prepared, (quoted,), WorkCounter()).mark


# 40,000 gallons of September at a fixed 3.10. Booked by its code it is U26's four prints at 4:
# 40,000 * (4 - 3.10) = 36,000. Booked by two dates it is the four prints dated in September,
# 4.25: 40,000 * (4.25 - 3.10) = 46,000, whether the window opens on the 1st or the 2nd.
def test_a_dated_september_trade_marks_on_the_prints_dated_in_september() -> None:
    assert observed_days(coded("U26")) == [list(PRINTS[:4])]
    assert mark_of(coded("U26")) == pytest.approx(36_000.0, rel=1e-12)
    for start in ("2026-09-01", "2026-09-02"):
        booked = dated(start, "2026-09-30")
        assert observed_days(booked) == [list(PRINTS[1:5])]
        assert mark_of(booked) == pytest.approx(46_000.0, rel=1e-12)
    # A print prices off its own row's month wherever it is observed: the 28th's reference is
    # October in the dated September component, the three before it September.
    leg = dated("2026-09-01", "2026-09-30").encoded.legs[0]
    assert [WEEKLY.schedule.codes[int(r)] for r in leg.slot_reference] == ["U26"] * 3 + ["V26"]
    assert leg.observations.weight.tolist() == [0.25] * 4


# A window across a month end is a part of each month by dates, each month a component. Every
# print dated in the window is observed once and no other: the 31st of August, outside every
# window here, never; the 28th of September once, in September's component and not again in
# October's, whether or not a component fills its calendar month.
@pytest.mark.parametrize(
    ("start", "end", "days"),
    [
        ("2026-09-01", "2026-10-31", [list(PRINTS[1:5]), [PRINTS[5]]]),
        ("2026-09-02", "2026-10-31", [list(PRINTS[1:5]), [PRINTS[5]]]),
        ("2026-09-08", "2026-10-05", [list(PRINTS[2:5]), [PRINTS[5]]]),
        ("2026-09-22", "2026-10-31", [[PRINTS[4]], [PRINTS[5]]]),
    ],
    ids=[
        "two whole calendar months",
        "a part of September and the whole of October",
        "a part of each month",
        "September's part holding one print, a V26 print",
    ],
)
def test_a_window_across_months_observes_each_print_dated_in_it_once(
    start: str, end: str, days: list[list[str]]
) -> None:
    booked = dated(start, end)
    assert observed_days(booked) == days
    seen = [d for component in days for d in component]
    assert len(seen) == len(set(seen))
    assert seen == [d for d in PRINTS if start <= d <= end]


# The strip by code beside it: each month the prints its rows name, six prints in all, each
# once, the 31st of August in September and the 28th of September in October.
def test_a_strip_by_code_observes_each_months_own_prints() -> None:
    assert observed_days(coded("U26-V26")) == [list(PRINTS[:4]), list(PRINTS[4:])]
    # 40,000 a month: September at 4 and October at 5 against 3.10.
    assert mark_of(coded("U26-V26")) == pytest.approx(40_000 * (0.9 + 1.9), rel=1e-12)
    # The same two months by dates: September at 4.25, October's one print at 5.
    assert mark_of(dated("2026-09-01", "2026-10-31")) == pytest.approx(
        40_000 * (1.15 + 1.9), rel=1e-12
    )


# --- lastday, a month's one print ----------------------------------------------------------------


# Under lastday a row is a whole month holding one print, and the prints are counted as the row
# was entered. V26 by its code holds two prints here and is refused by its count; October typed
# as two dates holds one, dated the 5th, and is that print at October's quote.
def test_lastday_counts_a_months_prints_as_the_row_was_entered() -> None:
    last = {**TEMPLATE, "schedule_method": "lastday"}
    assert refused(WEEKLY, {**BOOKED, "contract_code": ["V26"]}, last) == (
        "schedule_method of trade 1001 at row 1 is 'lastday' on V26, a month of 2 prints, "
        "expected a month of one print; lastday is a month's one print, and asian averages "
        "several"
    )
    window: dict[str, list[object]] = {
        **BOOKED,
        "start_date": ["2026-10-01"],
        "end_date": ["2026-10-31"],
    }
    october = created(WEEKLY, window, last)[0]
    assert observed_days(october) == [[PRINTS[5]]]
    assert mark_of(october) == pytest.approx(40_000 * (OCTOBER - 3.10), rel=1e-12)


# --- a request for quote -------------------------------------------------------------------------


# A request's rows are by code or by dates row by row, as a ticket's are: U26 by code beside
# September by dates, one unit each, are the two prices above, 4 and 4.25.
def test_a_requests_rows_select_their_prints_by_code_or_by_dates_row_by_row() -> None:
    asked = request(
        codes=["U26", None],
        quantities=[1.0, 1.0],
        template=financial(),
        ix=WEEKLY,
        starts=[None, "2026-09-01"],
        ends=[None, "2026-09-30"],
    )
    made = asked.request.observations
    assert [[str(d) for d in made.date[made.component == k]] for k in range(2)] == [
        list(PRINTS[:4]),
        list(PRINTS[1:5]),
    ]
    # One unit of each: (4 + 4.25) / 2, each row its own average.
    assert quote_rfq(on_aug_18(), asked, "flat", None, WorkCounter()) == pytest.approx(
        (4.0 + 4.25) / 2, rel=1e-12
    )
