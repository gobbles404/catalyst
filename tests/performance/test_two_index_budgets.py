"""The work of a pair of index legs, two-index-fixed-float.md, measured against the one-leg
baseline at one row and at many: creation counts each leg's components, observations and slots
and the trade's rows, groups, payment days and reserves once; preparation applies each history
to its own leg's slots; a tick reads each leg's live references off its own market and each
distinct factor once, serving both legs, and makes eight reductions a leg and four for the
trade. The peak of memory a pair holds at each step is at most twice a leg's, to the slack the
seam allows. The pair is the unit tests' synthetic A and B, made here again since a performance
test imports no unit test: A a futures index with a 10,000 MMBTU lot, B an IFERC index with a
2,500 MMBTU one, each defining one MMBTU per entered unit."""

from collections.abc import Callable, Mapping

import numpy as np
import pytest
from numpy.typing import NDArray
from test_seam_allocation import SLACK, least_peak

from goosedove.calendar.calendar import calendar
from goosedove.globals.discount_curve import DiscountCurve, discount_curve
from goosedove.globals.discount_curve_set import DiscountCurveSet, collect_discount_curves
from goosedove.globals.unit_conversions import UNITS
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter, WorkCounts
from goosedove.instruments.definitions import FIXED_FLOAT, FieldType, Instrument
from goosedove.instruments.fields import DatesOrTexts, FieldValues
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.futures_fixings import futures_fixings
from goosedove.market_data.iferc_fixings import iferc_fixings
from goosedove.market_data.price_vector import price_vector
from goosedove.trades.aggregation import aggregate_results
from goosedove.trades.evaluation import trade_results
from goosedove.trades.preparation import prepared_trades
from goosedove.trades.resolution import Trades, trades
from goosedove.trades.template import trade_template

ROWS = [pytest.param(1, id="one row"), pytest.param(500, id="500 rows")]
AS_OF = "2027-01-04"
PAY = "2028-01-04"


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def numbers(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def futures_index() -> Index:
    contracts = (
        ("X26", "2026-10-28"),
        ("Z26", "2026-11-25"),
        ("F27", "2026-12-29"),
        ("G27", "2027-01-27"),
        ("H27", "2027-02-24"),
        ("J27", "2027-03-29"),
    )
    sizes = numbers(10_000.0, 1.0)
    return index(
        "A",
        "Index A",
        futures_schedule(tuple(c for c, _ in contracts), dates(*(e for _, e in contracts)), None),
        index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
        contract_specifications(
            ("LOT", "MMBTU"), sizes, ("MMBTU", "MMBTU"), sizes * 0.01, sizes * 0.005, UNITS
        ),
        holiday_calendar(dates("2026-12-25", "2027-01-01")),
        "LOT",
        UNITS,
    )


def iferc_index() -> Index:
    sizes = numbers(2_500.0, 1.0)
    return index(
        "B",
        "Index B",
        iferc_schedule(
            ("Z26", "F27", "G27", "H27", "J27"),
            dates("2026-12-01", "2027-01-04", "2027-02-01", "2027-03-01", "2027-04-01"),
        ),
        index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
        contract_specifications(
            ("LOT", "MMBTU"), sizes, ("MMBTU", "MMBTU"), sizes * 0.5, sizes * 0.5, UNITS
        ),
        None,
        "LOT",
        UNITS,
    )


A = futures_index()
B = iferc_index()
SOFR = discount_curve("SOFR", dates(AS_OF, PAY), numbers(1.0, 0.95))
TEMPLATE: dict[str, object] = {
    "quantity_unit": "MMBTU",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "schedule_method": "lastday",
    "second_schedule_method": "lastday",
    "route": "bilateral",
    "settlement_method": "financial",
    "counterparty": "ACME Trading",
    "discount_curve_key": "SOFR",
    "payment_day": np.datetime64(PAY, "D"),
    "payment_holiday_calendar": holiday_calendar(dates()),
}
TICKET: dict[str, list[object]] = {
    "trade_id": [1],
    "trade_date": ["2026-12-15"],
    "contract_code": ["G27"],
    "quantity": [10_000],
    "fixed_price": [3.30],
    "second_fixed_price": [-0.30],
}


def typed(definition: Instrument, name: str, values: list[object]) -> object:
    """A column as the seam hands it over, typed by its field, as the unit tests type one."""
    match next(field for field in definition.fields if field.name == name).type:
        case FieldType.NUMBER:
            return np.array(values, dtype=np.float64)
        case FieldType.DATE:
            return np.array(values, dtype="datetime64[D]")
        case FieldType.TEXT | FieldType.CODE:
            return tuple(str(value) for value in values)
        case FieldType.HOLIDAY_CALENDAR:
            return tuple(values)
        case FieldType.DATE_OR_TEXT:
            return DatesOrTexts(
                np.array([not isinstance(value, str) for value in values]),
                np.array([v for v in values if not isinstance(v, str)], dtype="datetime64[D]"),
                tuple(v for v in values if isinstance(v, str)),
            )


def a_ticket(columns: Mapping[str, list[object]]) -> FieldValues:
    rows = len(next(iter(columns.values())))
    return FieldValues(
        FIXED_FLOAT,
        rows,
        tuple(columns),
        {name: typed(FIXED_FLOAT, name, values) for name, values in columns.items()},
        {},
    )


def rows_of(n: int, second: bool = True) -> dict[str, list[object]]:
    """n rows of the hand table's trade, each its own occurrence of G27."""
    return {
        name: list(values) * n
        for name, values in TICKET.items()
        if second or name != "second_fixed_price"
    }


def pair(n: int, counter: WorkCounter) -> Trades:
    template = trade_template(a_ticket({k: [v] for k, v in TEMPLATE.items()}))
    return trades((A, B), a_ticket(rows_of(n)), template, UNITS, counter)


def single(n: int, counter: WorkCounter) -> Trades:
    template = trade_template(
        a_ticket({k: [v] for k, v in TEMPLATE.items() if k != "second_schedule_method"})
    )
    return trades((A,), a_ticket(rows_of(n, second=False)), template, UNITS, counter)


def history_a() -> MarketHistory:
    """A's history on the day: 3.00 on every fixed business day, F27 settled at 3.55."""
    cal = calendar(valuation_date(np.datetime64(AS_OF, "D"), 0.5), A)
    schedule = A.schedule
    assert isinstance(schedule, FuturesSchedule)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = np.full(priced.size, 3.0)
    settles[priced == schedule.future_expiry[schedule.codes.index("F27")]] = 3.55
    return market_history(cal, futures_fixings(priced[::-1].copy(), settles[::-1].copy(), A))


def history_b() -> MarketHistory:
    """B's history on the day: Z26 published at -0.30, F27 publishing today and live."""
    cal = calendar(valuation_date(np.datetime64(AS_OF, "D"), 0.5), B)
    return market_history(cal, iferc_fixings(("Z26",), numbers(-0.30), B))


def quoted(history: MarketHistory, *quotes: float) -> Market:
    return market(history, price_vector(history.calendar.index.name, numbers(*quotes)))


def curve_set(curve: DiscountCurve) -> DiscountCurveSet:
    return collect_discount_curves((curve,), WorkCounter())


def counts_of(counter: WorkCounter) -> WorkCounts:
    """The counts, a name never hit read as zero."""
    return counter.freeze()


@pytest.mark.parametrize("n", ROWS)
def test_creation_counts_each_legs_arrays_and_the_trades_facts_once(n: int) -> None:
    both, one = WorkCounter(), WorkCounter()
    pair(n, both)
    single(n, one)
    two_legs, one_leg = counts_of(both), counts_of(one)
    # Per leg: the schedule's codes, the components, the observations and the slots; G27 on
    # every row makes one group of one payment day, one slot a leg, whatever the rows.
    assert two_legs["schedule_codes_read"] == 11 and one_leg["schedule_codes_read"] == 6
    assert two_legs["encoded_components"] == 2 * n == 2 * one_leg["encoded_components"]
    assert two_legs["encoded_observations"] == 2 * n == 2 * one_leg["encoded_observations"]
    assert two_legs["encoded_slots"] == 2 == 2 * one_leg["encoded_slots"]
    # Once for the trade: the rows, the groups, the payment days and the reserves' components.
    for name in (
        "resolved_occurrences",
        "resolved_components",
        "encoded_groups",
        "encoded_payment_days",
        "reserved_fee_components",
    ):
        assert two_legs[name] == one_leg[name], name
    assert two_legs["encoded_groups"] == 1 and two_legs["resolved_occurrences"] == n
    # The pair's observation-day union, the two legs' one day each; one leg makes none.
    assert two_legs["encoded_pair_days"] == 2 and one_leg["encoded_pair_days"] == 0


@pytest.mark.parametrize("n", ROWS)
def test_preparation_applies_each_history_to_its_own_leg(n: int) -> None:
    both, one = pair(n, WorkCounter()), single(n, WorkCounter())
    hist_a, hist_b = history_a(), history_b()
    two_counter, one_counter = WorkCounter(), WorkCounter()
    prepared = prepared_trades(both.encoded, (hist_a, hist_b), two_counter)
    prepared_trades(one.encoded, (hist_a,), one_counter)
    two_legs, one_leg = counts_of(two_counter), counts_of(one_counter)
    assert two_legs["prepared_slots"] == 2 == 2 * one_leg["prepared_slots"]
    assert two_legs["fixings_read"] == 0 == one_leg["fixings_read"]
    assert two_legs["payment_days_mapped"] == 1 == one_leg["payment_days_mapped"]
    assert two_legs["display_periods"] == sum(
        [leg.by_month.periods.size + leg.by_year.periods.size for leg in prepared.legs]
    )
    assert two_legs["display_periods"] == 2 * one_leg["display_periods"]


@pytest.mark.parametrize("n", ROWS)
def test_a_tick_reads_each_legs_quotes_and_one_factor_for_both(n: int) -> None:
    both, one = pair(n, WorkCounter()), single(n, WorkCounter())
    hist_a, hist_b = history_a(), history_b()
    prepared = prepared_trades(both.encoded, (hist_a, hist_b), WorkCounter())
    alone = prepared_trades(one.encoded, (hist_a,), WorkCounter())
    market_a, market_b = quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42)
    two_counter, one_counter = WorkCounter(), WorkCounter()
    trade_results(prepared, (market_a, market_b), two_counter, curve_set(SOFR))
    trade_results(alone, (market_a,), one_counter, curve_set(SOFR))
    two_legs, one_leg = counts_of(two_counter), counts_of(one_counter)
    assert two_legs["kernel"] == 1 == one_leg["kernel"]
    assert two_legs["live_prices_read"] == 2 == 2 * one_leg["live_prices_read"]
    assert two_legs["curves_selected"] == 1 == one_leg["curves_selected"]
    assert two_legs["payment_factors_read"] == 1 == one_leg["payment_factors_read"]
    assert two_legs["groups_valued"] == 1 == one_leg["groups_valued"]
    assert two_legs["slots_discounted"] == 2 == 2 * one_leg["slots_discounted"]
    assert two_legs["slots_weighted"] == 2 == 2 * one_leg["slots_weighted"]
    assert two_legs["risk_reductions"] == 20 and one_leg["risk_reductions"] == 12


def test_a_pair_holds_at_most_twice_a_legs_memory_at_each_step() -> None:
    n = 500
    hist_a, hist_b = history_a(), history_b()
    market_a, market_b = quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42)
    curves = curve_set(SOFR)
    one, both = single(n, WorkCounter()), pair(n, WorkCounter())
    alone = prepared_trades(one.encoded, (hist_a,), WorkCounter())
    prepared = prepared_trades(both.encoded, (hist_a, hist_b), WorkCounter())
    steps: tuple[tuple[str, Callable[[], object], Callable[[], object]], ...] = (
        ("creation", lambda: single(n, WorkCounter()), lambda: pair(n, WorkCounter())),
        (
            "preparation",
            lambda: prepared_trades(one.encoded, (hist_a,), WorkCounter()),
            lambda: prepared_trades(both.encoded, (hist_a, hist_b), WorkCounter()),
        ),
        (
            "evaluation",
            lambda: trade_results(alone, (market_a,), WorkCounter(), curves),
            lambda: trade_results(prepared, (market_a, market_b), WorkCounter(), curves),
        ),
    )
    for name, leg, legs in steps:
        assert least_peak(legs) <= 2 * least_peak(leg) + SLACK, name


@pytest.mark.parametrize("n", ROWS)
def test_a_pair_collects_as_two_legs_from_one_source(n: int) -> None:
    both, one = pair(n, WorkCounter()), single(n, WorkCounter())
    hist_a, hist_b = history_a(), history_b()
    market_a, market_b = quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42)
    curves = curve_set(SOFR)
    paired = trade_results(
        prepared_trades(both.encoded, (hist_a, hist_b), WorkCounter()),
        (market_a, market_b),
        WorkCounter(),
        curves,
    )
    alone = trade_results(
        prepared_trades(one.encoded, (hist_a,), WorkCounter()), (market_a,), WorkCounter(), curves
    )
    two_counter, one_counter = WorkCounter(), WorkCounter()
    aggregate_results((paired,), two_counter)
    aggregate_results((alone,), one_counter)
    two_legs, one_leg = counts_of(two_counter), counts_of(one_counter)
    # One source either way; the pair's contributions one rate and two cross, two index groups
    # and two cross groups against one of each, the one rate group alike.
    assert two_legs["sources_collected"] == 1 == one_leg["sources_collected"]
    assert two_legs["contributions_collected"] == 3 and one_leg["contributions_collected"] == 2
    assert two_legs["index_groups"] == 2 and one_leg["index_groups"] == 1
    assert two_legs["cross_groups"] == 2 and one_leg["cross_groups"] == 1
    assert two_legs["rate_groups"] == 1 == one_leg["rate_groups"]
