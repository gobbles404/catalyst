"""A float_float whose spread price has a unit of its own, float-float-units.md: two indexes
that price in different units, RB in dollars a gallon less WTI in dollars a barrel, at a spread
price typed in dollars a barrel. Synthetic futures indexes over X26 to J27, each defining its
LOT and one BBL; the hand tables of the ticket, the issue's RB and C5 examples, the lifecycle
with the legs fixing on different days, averages over each leg's own days, the collection, the
first slice's pair to the last bit, and the rules: the unit typed and one for the batch, one
measure, one settlement unit, heat or electricity, one amount per entered unit. Every expected
number is the ticket's or hand arithmetic here; the production code is never asked for one."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import a_template, a_ticket
from test_float_float import BILATERAL as GAS_SPREAD
from test_float_float import FIELDS, NTO, PAN, TEMPLATE_FIELDS
from test_float_float import TICKET as GAS_TICKET
from test_float_float import booked as booked_gas
from test_float_float import valued as valued_gas
from test_trades import dates, day, history_on, numbers, quoted
from test_two_index import (
    AS_OF,
    CLOSE,
    PAY,
    PID,
    SEAM,
    SOFR,
    A,
    across,
    cell,
    close,
    down,
    grid,
    on,
    read,
    serial,
    spilled,
    under,
)
from test_two_index import BILATERAL as PAIR_BILATERAL

from catalyst.calendar.calendar import calendar
from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.globals.discount_curve import DiscountCurve
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import valuation_date
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.index_definitions.index import Index, index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FLOAT_FLOAT
from catalyst.market.market_history import MarketHistory, market_history
from catalyst.market_data.futures_fixings import futures_fixings
from catalyst.trades.aggregation import aggregate_results
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.results import TradeResults
from catalyst.trades.terms import ELECTRICITY, PriceUnit, spread_unit

# --- the indexes ----------------------------------------------------------------------------------
# Futures indexes over X26 to J27, F27 expiring 29 December 2026 and G27 27 January 2027 unless
# said, Christmas and New Year's Day closed, each reporting in its LOT and defining one more
# word for a quantity, a bare unit of size one, BBL unless said. No fee.

CODES = ("X26", "Z26", "F27", "G27", "H27", "J27")
EXPIRIES = ("2026-10-28", "2026-11-25", "2026-12-29", "2027-01-27", "2027-02-24", "2027-03-29")


def an_index(
    name: str,
    quote: tuple[str, str],
    lot: tuple[float, str],
    *,
    measure: str = "VOLUME",
    word: str = "BBL",
    settles: str = "DOLLAR",
    f27: str = "2026-12-29",
    holidays: tuple[str, ...] = ("2026-12-25", "2027-01-01"),
) -> Index:
    expiries = tuple(
        f27 if code == "F27" else expiry for code, expiry in zip(CODES, EXPIRIES, strict=True)
    )
    sizes = numbers(lot[0], 1.0)
    return index(
        name,
        f"Index {name}",
        futures_schedule(CODES, dates(*expiries), None),
        index_conventions(quote[0], quote[1], settles, measure, lot[1], UNITS),
        contract_specifications(
            ("LOT", word), sizes, (lot[1], word), sizes * 0.0, sizes * 0.0, UNITS
        ),
        holiday_calendar(dates(*holidays)),
        "LOT",
        UNITS,
    )


RB = an_index("RB", ("DOLLAR", "GAL"), (42_000.0, "GAL"))
WTI = an_index("WTI", ("DOLLAR", "BBL"), (1_000.0, "BBL"))
HO = an_index("HO", ("DOLLAR", "GAL"), (42_000.0, "GAL"))
C5 = an_index("C5", ("CENT", "GAL"), (42_000.0, "GAL"))

# The crack's template: the pair's, a quantity in barrels and the spread price in dollars a
# barrel; its row, 1,000 barrels of G27 at a spread price of 15.00.
CRACK: dict[str, object] = {
    **PAIR_BILATERAL,
    "quantity_unit": "BBL",
    "spread_price_currency_unit": "DOLLAR",
    "spread_price_quantity_unit": "BBL",
}
TICKET: dict[str, list[object]] = {
    "trade_id": [1],
    "trade_date": ["2026-12-15"],
    "contract_code": ["G27"],
    "quantity": [1_000],
    "spread_price": [15.00],
}
Prices = tuple[tuple[float, ...], tuple[float, ...]]
LIVE: Prices = ((2.10,), (70.00,))  # G27 on each, the first live contract on the table's day


def booked(
    template: Mapping[str, object] = CRACK,
    ticket: Mapping[str, list[object]] = TICKET,
    indexes: Sequence[Index] = (RB, WTI),
) -> Trades:
    return trades(
        indexes,
        a_ticket(ticket, FLOAT_FLOAT),
        a_template(template, FLOAT_FLOAT),
        UNITS,
        WorkCounter(),
    )


def refused(
    template: Mapping[str, object] = CRACK,
    ticket: Mapping[str, list[object]] = TICKET,
    indexes: Sequence[Index] = (RB, WTI),
) -> str:
    with pytest.raises(ValueError) as refusal:
        booked(template, ticket, indexes)
    return str(refusal.value)


def valued(
    batch: Trades,
    prices: Prices = LIVE,
    curve: DiscountCurve = SOFR,
    as_of: str = AS_OF,
    finals: tuple[Mapping[str, float], Mapping[str, float]] = ({}, {}),
) -> TradeResults:
    """The batch prepared and valued on the day: each leg's history, its finals standing on
    their expiry days, and its market quoted from its first live contract on."""
    histories = [
        history_on(leg.index, as_of, dict(final))
        for leg, final in zip(batch.resolved.legs, finals, strict=True)
    ]
    prepared = prepared_trades(batch.encoded, histories, WorkCounter())
    markets = [quoted(history, *quotes) for history, quotes in zip(histories, prices, strict=True)]
    return trade_results(prepared, markets, WorkCounter(), curve_set(curve))


def near(actual: NDArray[np.float64] | None, expected: list[float]) -> None:
    """An amount of dollars to a millionth of a cent, where a factor such as 0.01 or 1/42 leaves
    its roundoff on a sum that nets to nothing."""
    assert actual is not None
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-8)


# --- the hand-priced acceptance: RB less WTI ------------------------------------------------------


def test_the_hand_table_rb_less_wti_both_legs_live() -> None:
    # 1,000 BBL of RB less WTI at 15.00 DOLLAR/BBL, RB at 2.10 DOLLAR/GAL and WTI at 70.00
    # DOLLAR/BBL, one payment a year on at 0.95: 42,000 GAL at 2.10 is 88,200, less 70,000, less
    # 15,000, payment 3,200, mark 3,040, DV01 -0.304; one lot of RB and minus one of WTI, deltas
    # 0.95 and -0.95, cross-gammas -0.000095 and 0.000095. No price is converted: three quantities,
    # each in its own price's unit.
    batch = booked()
    terms = batch.resolved
    assert terms.instrument is FLOAT_FLOAT and terms.descriptor == "RB-WTI"
    assert terms.price_unit == PriceUnit("DOLLAR", "BBL")
    rb, wti = batch.encoded.legs
    assert rb.quote_quantity.tolist() == [42_000.0]  # gallons, RB's own quote unit
    assert wti.quote_quantity.tolist() == [-1_000.0]  # barrels, WTI's, the subtracted leg
    assert rb.coefficient.tolist() == [42_000.0] and wti.coefficient.tolist() == [-1_000.0]
    assert batch.encoded.offset.tolist() == [-15_000.0]  # the spread leg: 1,000 BBL at 15.00
    results = valued(batch)
    first, second = results.legs
    close(results.payment_amount, [3_200.0])
    close(results.payment_factor, [0.95])
    assert results.mark == pytest.approx(3_040.0, **CLOSE)
    assert results.dv01 == pytest.approx(-0.304, **CLOSE)
    close(first.dated_live_contribution, [88_200.0])
    close(second.dated_live_contribution, [-70_000.0])
    assert first.nominal_delta_total == pytest.approx(1.0, **CLOSE)
    assert second.nominal_delta_total == pytest.approx(-1.0, **CLOSE)
    assert first.delta_total == pytest.approx(0.95, **CLOSE)
    assert second.delta_total == pytest.approx(-0.95, **CLOSE)
    assert first.cross_gamma_total == pytest.approx(-0.000095, **CLOSE)
    assert second.cross_gamma_total == pytest.approx(0.000095, **CLOSE)
    assert results.cash == 0.0


def test_the_readbacks_show_the_unit_typed_and_each_legs_price_in_its_own() -> None:
    batch = booked()
    table = grid(batch)
    assert cell(table, 0, "spread_price") == 15.0
    assert cell(table, 0, "spread_price_currency_unit") == "DOLLAR"
    assert cell(table, 0, "spread_price_quantity_unit") == "BBL"
    assert cell(table, 0, "quantity_unit") == "BBL"
    assert cell(table, 0, "quote_quantity") == 42_000.0  # the first leg's, in its gallons
    assert cell(table, 0, "offset") == -15_000.0
    slots = grid(valued(batch))
    assert [cell(slots, r, "index") for r in (0, 1)] == ["RB", "WTI"]
    assert [cell(slots, r, "price_unit") for r in (0, 1)] == ["DOLLAR/GAL", "DOLLAR/BBL"]
    assert [cell(slots, r, "observation_price") for r in (0, 1)] == [2.10, 70.00]
    assert [cell(slots, r, "observation_coefficient") for r in (0, 1)] == [42_000.0, -1_000.0]
    # The ticket's 83,790, -66,500 and -14,250: each leg's floating contribution and the spread
    # leg, read back undiscounted, times the payment's factor, summing to the mark.
    factor = float(str(cell(slots, 0, "payment_factor")))
    sides = [float(str(cell(slots, r, "floating_contribution"))) * factor for r in (0, 1)]
    spread_leg = float(str(cell(table, 0, "offset"))) * factor
    assert sides == pytest.approx([83_790.0, -66_500.0], **CLOSE)
    assert spread_leg == pytest.approx(-14_250.0, **CLOSE)
    assert sum(sides) + spread_leg == pytest.approx(3_040.0, **CLOSE)
    # The floating spread in the spread price's unit is a reader's arithmetic and no column:
    # 2.10 a gallon is 88.20 a barrel, 18.20 over 70.00.
    assert not [h for h in (*table[0], *slots[0]) if "spread" in str(h) and "price" not in str(h)]


@pytest.mark.parametrize(
    ("template", "ticket"),
    [
        ({**CRACK, "quantity_unit": "LOT"}, {**TICKET, "quantity": [1]}),
        ({**CRACK, "spread_price_currency_unit": "CENT"}, {**TICKET, "spread_price": [1_500.0]}),
    ],
    ids=["one lot of each", "cents a barrel"],
)
def test_the_same_crack_entered_another_way_reads_the_same_numbers(
    template: Mapping[str, object], ticket: Mapping[str, list[object]]
) -> None:
    # One LOT is 42,000 GAL of RB and 1,000 BBL of WTI, one amount; 1,500 cents is 15 dollars.
    results = valued(booked(template, ticket))
    near(results.payment_amount, [3_200.0])
    assert results.mark == pytest.approx(3_040.0, rel=1e-12)
    assert [leg.nominal_delta_total for leg in results.legs] == pytest.approx([1.0, -1.0])


def test_a_spread_price_per_barrel_and_per_gallon_are_one_trade() -> None:
    # 21.00 a barrel is 0.50 a gallon: 88,200 less 70,000 less 21,000 either way.
    barrel = valued(booked(ticket={**TICKET, "spread_price": [21.00]}))
    gallon = valued(
        booked({**CRACK, "spread_price_quantity_unit": "GAL"}, {**TICKET, "spread_price": [0.50]})
    )
    close(barrel.payment_amount, [-2_800.0])
    close(gallon.payment_amount, [-2_800.0])


def test_a_sold_crack_reverses_cash_value_and_every_risk() -> None:
    sold = valued(booked(ticket={**TICKET, "quantity": [-1_000]}))
    close(sold.payment_amount, [-3_200.0])
    assert sold.mark == pytest.approx(-3_040.0, **CLOSE)
    assert sold.dv01 == pytest.approx(0.304, **CLOSE)
    assert [leg.nominal_delta_total for leg in sold.legs] == pytest.approx([-1.0, 1.0], **CLOSE)
    assert [leg.delta_total for leg in sold.legs] == pytest.approx([-0.95, 0.95], **CLOSE)


def test_heating_oil_less_wti_is_the_same_example_under_another_name() -> None:
    batch = booked(indexes=(HO, WTI))
    assert batch.resolved.descriptor == "HO-WTI"
    results = valued(batch)
    close(results.payment_amount, [3_200.0])
    assert results.mark == pytest.approx(3_040.0, **CLOSE)


# --- C5 natural gasoline in cents a gallon --------------------------------------------------------


@pytest.mark.parametrize(("crude", "payment"), [(70.00, 0.0), (69.00, 1_000.0)])
def test_c5_in_cents_a_gallon_less_wti_at_a_negative_spread_price(
    crude: float, payment: float
) -> None:
    # 1,000 BBL at -9.10 DOLLAR/BBL: C5 at 145 cents a gallon is 42,000 GAL at 1.45 dollars,
    # 60,900, the spread leg 9,100 received; against WTI at 70.00 nothing, at 69.00 1,000.
    batch = booked(ticket={**TICKET, "spread_price": [-9.10]}, indexes=(C5, WTI))
    c5, _ = batch.encoded.legs
    assert c5.quote_quantity.tolist() == [42_000.0]
    close(c5.coefficient, [420.0])  # dollars per cent a gallon
    close(batch.encoded.offset, [9_100.0])
    results = valued(batch, ((145.0,), (crude,)))
    close(results.legs[0].dated_live_contribution, [60_900.0])
    close(results.legs[1].dated_live_contribution, [-1_000.0 * crude])
    near(results.payment_amount, [payment])


# --- the lifecycle, the legs fixing on different days ---------------------------------------------
# A per gallon, F27 expiring 29 December 2026, and B per barrel, F27 expiring 4 January 2027;
# +2bd from the later pays 6 January. A less B, 1,000 BBL at a spread price of 15.00.

A_GAL = an_index("A", ("DOLLAR", "GAL"), (42_000.0, "GAL"))
B_BBL = an_index("B", ("DOLLAR", "BBL"), (1_000.0, "BBL"), f27="2027-01-04")
LIFECYCLE: dict[str, object] = {**CRACK, "payment_day": "+2bd"}
F27: dict[str, list[object]] = {**TICKET, "contract_code": ["F27"]}


def a_less_b() -> Trades:
    return booked(LIFECYCLE, F27, (A_GAL, B_BBL))


def test_the_crack_pays_two_business_days_after_the_later_fixing() -> None:
    batch = a_less_b()
    assert batch.resolved.payment is not None
    np.testing.assert_array_equal(batch.resolved.payment.date, dates("2027-01-06"))
    a, b = batch.encoded.legs
    np.testing.assert_array_equal(a.slot_date, dates("2026-12-29"))
    np.testing.assert_array_equal(b.slot_date, dates("2027-01-04"))


def test_the_lifecycle_both_live_on_28_december() -> None:
    results = valued(
        a_less_b(),
        ((2.10, 2.20, 2.30), (71.00, 72.00, 73.00)),
        on("2026-12-28", 0.99),
        "2026-12-28",
    )
    close(results.payment_amount, [2_200.0])  # 88,200 less 71,000 less 15,000
    assert results.mark == pytest.approx(2_200.0 * 0.99, **CLOSE)
    assert [leg.nominal_delta_total for leg in results.legs] == pytest.approx([1.0, -1.0])


def test_the_lifecycle_a_fixed_on_30_december_and_b_live() -> None:
    results = valued(
        a_less_b(),
        ((2.20, 2.30), (71.00, 72.00, 73.00)),
        on("2026-12-30", 0.995),
        "2026-12-30",
        ({"F27": 2.00}, {}),
    )
    a, b = results.legs
    close(results.payment_amount, [-2_000.0])  # 84,000 less 71,000 less 15,000
    close(a.prepared.fixed_contribution, [84_000.0])  # 42,000 GAL fixed at 2.00
    close(b.dated_live_contribution, [-71_000.0])
    assert (a.nominal_delta_total, b.nominal_delta_total) == (0.0, -1.0)


def test_the_lifecycle_both_fixed_on_5_january_and_a_fixing_corrected() -> None:
    fixed = ({"F27": 2.00}, {"F27": 70.00})
    results = valued(a_less_b(), ((2.20,), (72.00,)), on("2027-01-05", 0.9999), "2027-01-05", fixed)
    close(results.payment_amount, [-1_000.0])  # 84,000 less 70,000 less 15,000
    assert results.mark == pytest.approx(-1_000.0 * 0.9999, **CLOSE)
    assert [leg.nominal_delta_total for leg in results.legs] == [0.0, 0.0]
    assert results.cash == 0.0
    # A's fixing corrected to 2.05 moves A's side alone, and the one payment with it.
    corrected = valued(
        a_less_b(),
        ((2.20,), (72.00,)),
        on("2027-01-05", 0.9999),
        "2027-01-05",
        ({"F27": 2.05}, {"F27": 70.00}),
    )
    close(corrected.payment_amount, [1_100.0])  # 86,100 less 70,000 less 15,000
    close(corrected.legs[0].prepared.fixed_contribution, [86_100.0])
    close(corrected.legs[1].prepared.fixed_contribution, [-70_000.0])


def test_the_lifecycle_paid_on_6_january_is_one_cash_amount() -> None:
    results = valued(
        a_less_b(),
        ((2.20,), (72.00,)),
        curve_of(("2027-01-06", 1.0), ("2027-06-30", 0.98)),
        "2027-01-06",
        ({"F27": 2.00}, {"F27": 70.00}),
    )
    assert (results.cash, results.mark, results.dv01) == (-1_000.0, 0.0, 0.0)
    assert [leg.nominal_delta_total for leg in results.legs] == [0.0, 0.0]


# --- averages, each leg over its own index's days -------------------------------------------------
# C5 and a WTI that is also closed on 18 January: January 2027 has 20 pricing days on the first
# and 19 on the second. Both legs asian over F27's month, each day priced by its prompt
# contract, G27 to its expiry on the 27th and H27 after.

WTI_CLOSED_18 = an_index(
    "WTI", ("DOLLAR", "BBL"), (1_000.0, "BBL"), holidays=("2026-12-25", "2027-01-01", "2027-01-18")
)
ASIAN: dict[str, object] = {**CRACK, "schedule_method": "asian", "second_schedule_method": "asian"}
JANUARY: dict[str, list[object]] = {**TICKET, "contract_code": ["F27"], "spread_price": [-9.10]}


def test_each_leg_averages_its_own_days_and_a_day_one_leg_prices_is_no_slot_of_the_other() -> None:
    batch = booked(ASIAN, JANUARY, (C5, WTI_CLOSED_18))
    c5, crude = batch.encoded.legs
    assert (c5.slot_date.size, crude.slot_date.size) == (20, 19)
    assert day("2027-01-18") in c5.slot_date and day("2027-01-18") not in crude.slot_date
    # Each slot carries its own day count's share: 420 dollars a cent over 20 days, and 1,000
    # barrels over 19.
    close(c5.slot_exposure, [21.0] * 20)
    close(crude.slot_exposure, [-1_000.0 / 19] * 19)


@pytest.mark.parametrize(("crude", "payment"), [(70.00, 0.0), (69.00, 1_000.0)])
def test_the_two_averages_pay_the_issues_c5_example(crude: float, payment: float) -> None:
    # Every day live, valued 28 December: C5 averaging 145 cents and WTI averaging 70.00 pay
    # nothing at -9.10, and WTI averaging 69.00 pays 1,000.
    results = valued(
        booked(ASIAN, JANUARY, (C5, WTI_CLOSED_18)),
        ((140.0, 145.0, 145.0), (60.0, crude, crude)),
        curve_of(("2026-12-28", 1.0), (PAY, 0.95)),
        "2026-12-28",
    )
    near(results.payment_amount, [payment])
    assert [leg.nominal_delta_total for leg in results.legs] == pytest.approx([1.0, -1.0])


def history_at(ix: Index, as_of: str, settle: float, moved: Mapping[str, float]) -> MarketHistory:
    """The index's history on the day: one settle on every fixed pricing day but the days
    given, newest first as the fixings creator takes them."""
    cal = calendar(valuation_date(day(as_of), 0.5), ix)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = np.full(priced.size, settle)
    for text, price in moved.items():
        assert day(text) in priced, text
        settles[priced == day(text)] = price
    return market_history(cal, futures_fixings(priced[::-1].copy(), settles[::-1, None].copy(), ix))


def test_a_fixing_on_a_day_one_leg_alone_prices_moves_that_leg_alone() -> None:
    # Valued 20 January, the days before it fixed: C5's settle of the 18th, a day WTI is closed,
    # at 165 in place of 145 is 20 cents on one of its 20 days, a cent on its average, 420
    # dollars on its side and on the payment; WTI's side stands.
    batch = booked(ASIAN, JANUARY, (C5, WTI_CLOSED_18))
    crude = history_at(WTI_CLOSED_18, "2027-01-20", 70.00, {})
    payments: list[float] = []
    sides: list[tuple[float, float]] = []
    for settle in (145.0, 165.0):
        c5 = history_at(C5, "2027-01-20", 145.0, {"2027-01-18": settle})
        prepared = prepared_trades(batch.encoded, (c5, crude), WorkCounter())
        results = trade_results(
            prepared,
            (quoted(c5, 145.0, 145.0), quoted(crude, 70.00, 70.00)),
            WorkCounter(),
            curve_set(curve_of(("2027-01-20", 1.0), (PAY, 0.95))),
        )
        assert results.payment_amount is not None
        payments.append(float(results.payment_amount[0]))
        sides.append(
            (
                float(results.legs[0].prepared.fixed_contribution.sum()),
                float(results.legs[1].prepared.fixed_contribution.sum()),
            )
        )
    assert payments[0] == pytest.approx(0.0, abs=1e-8)
    assert payments[1] == pytest.approx(420.0, abs=1e-8)
    assert sides[1][0] - sides[0][0] == pytest.approx(420.0, abs=1e-8)
    assert sides[1][1] == sides[0][1]


# --- the collection -------------------------------------------------------------------------------


def test_the_crack_nets_with_a_position_on_crude_and_each_index_keeps_its_own_lots() -> None:
    # Beside 2,000 BBL of WTI bought at 69.00 against 70.00: payment 2,000, mark 1,900, 2 lots,
    # 1.9 of delta, -0.19 of DV01. RB stays 1 and 0.95; WTI nets to 1 and 0.95; SOFR's DV01 is
    # -0.494. Gallon lots and barrel lots are never summed.
    hist_rb, hist_wti = history_on(RB, AS_OF, {}), history_on(WTI, AS_OF, {})
    markets = (quoted(hist_rb, 2.10), quoted(hist_wti, 70.00))
    curves = curve_set(SOFR)
    crack = trade_results(
        prepared_trades(booked().encoded, (hist_rb, hist_wti), WorkCounter()),
        markets,
        WorkCounter(),
        curves,
    )
    alone: dict[str, object] = {
        k: v for k, v in PAIR_BILATERAL.items() if k != "second_schedule_method"
    }
    rows: dict[str, list[object]] = {
        "trade_id": [2],
        "trade_date": ["2026-12-15"],
        "contract_code": ["G27"],
        "quantity": [2_000],
        "fixed_price": [69.00],
    }
    bought = trades(
        (WTI,), a_ticket(rows), a_template({**alone, "quantity_unit": "BBL"}), UNITS, WorkCounter()
    )
    position = trade_results(
        prepared_trades(bought.encoded, (hist_wti,), WorkCounter()),
        markets[1:],
        WorkCounter(),
        curves,
    )
    assert position.mark == pytest.approx(1_900.0, **CLOSE)
    together = aggregate_results((crack, position), WorkCounter())
    rb, wti = together.index_groups
    assert rb.index is RB and wti.index is WTI
    assert rb.nominal_delta_total == pytest.approx(1.0, **CLOSE)
    assert rb.delta_total == pytest.approx(0.95, **CLOSE)
    assert wti.nominal_delta_total == pytest.approx(1.0, **CLOSE)
    assert wti.delta_total == pytest.approx(0.95, **CLOSE)
    (sofr,) = together.rate_groups
    assert sofr.dv01 == pytest.approx(-0.494, **CLOSE)
    table = grid(together)
    assert [cell(table, r, "index") for r in range(4)] == ["RB-WTI", "RB", "WTI", "WTI"]
    assert [cell(table, r, "reporting_lot") for r in range(4)] == ["-", "LOT", "LOT", "LOT"]
    assert [cell(table, r, "nominal_delta") for r in (1, 2, 3)] == pytest.approx([1.0, -1.0, 2.0])
    assert [cell(table, r, "delta") for r in (1, 2, 3)] == pytest.approx([0.95, -0.95, 1.9])
    assert cell(table, 0, "dv01") == pytest.approx(-0.304, **CLOSE)
    assert cell(table, 3, "dv01") == pytest.approx(-0.19, **CLOSE)
    assert [cell(table, r, "cross_gamma") for r in (1, 2, 3)] == pytest.approx(
        [-0.000095, 0.000095, -0.00019], **CLOSE
    )


# --- the first slice's pair, and order, strips and rows -------------------------------------------


def test_a_gas_spread_typed_in_its_indexes_unit_is_the_first_slices_to_the_last_bit() -> None:
    # The first slice made the spread leg from the first leg's coefficient; the spread price's
    # own coefficient is that number exactly where its unit is the first index's.
    strip: dict[str, list[object]] = {**GAS_TICKET, "contract_code": ["G27-H27"]}
    for ticket in (GAS_TICKET, strip):
        batch = booked_gas(ticket=ticket)
        assert batch.resolved.price_unit == PriceUnit("DOLLAR", "MMBTU")
        first = batch.encoded.legs[0]
        np.testing.assert_array_equal(
            batch.encoded.offset, -first.coefficient * batch.resolved.price
        )
    # And 10 cents per MMBTU is the same spread: the same 500 and the same 475.
    cents = valued_gas(
        booked_gas(
            {**GAS_SPREAD, "spread_price_currency_unit": "CENT"},
            {**GAS_TICKET, "spread_price": [10.0]},
        )
    )
    near(cents.payment_amount, [500.0])
    assert cents.mark == pytest.approx(475.0, rel=1e-12)
    assert [leg.nominal_delta_total for leg in cents.legs] == pytest.approx([4.0, -4.0])


def test_the_indexes_in_the_other_order_with_quantity_and_price_negated_read_the_same() -> None:
    forward = valued(booked())
    backward_batch = booked(
        ticket={**TICKET, "quantity": [-1_000], "spread_price": [-15.00]}, indexes=(WTI, RB)
    )
    assert backward_batch.resolved.descriptor == "WTI-RB"
    backward = valued(backward_batch, ((70.00,), (2.10,)))
    assert backward.mark == pytest.approx(forward.mark, **CLOSE)
    assert backward.dv01 == pytest.approx(forward.dv01, **CLOSE)
    # Each index keeps its lots whichever leg it stands on: RB one, WTI minus one.
    assert [leg.nominal_delta_total for leg in backward.legs] == pytest.approx([-1.0, 1.0])
    assert [leg.delta_total for leg in backward.legs] == pytest.approx([-0.95, 0.95], **CLOSE)


def test_a_spread_price_in_a_unit_neither_leg_quotes_in() -> None:
    # RB less heating oil, both in dollars a gallon, at 4.00 dollars a barrel: 88,200 less
    # 84,000 less 4,000.
    batch = booked(ticket={**TICKET, "spread_price": [4.00]}, indexes=(RB, HO))
    close(valued(batch, ((2.10,), (2.00,))).payment_amount, [200.0])


def test_a_strip_calday_and_a_zero_row_on_a_crack() -> None:
    strip = valued(
        booked(ticket={**TICKET, "contract_code": ["G27-H27"]}), ((2.10, 2.20), (70.00, 71.00))
    )
    # H27: 42,000 GAL at 2.20 is 92,400, less 71,000, less 15,000.
    close(strip.payment_amount, [3_200.0, 6_400.0])
    assert [leg.nominal_delta_total for leg in strip.legs] == pytest.approx([2.0, -2.0], **CLOSE)
    daily = valued(booked({**CRACK, "quantity_per": "calday"}))
    close(daily.payment_amount, [3_200.0 * 28])  # February's 28 days, 28,000 BBL
    assert [leg.nominal_delta_total for leg in daily.legs] == pytest.approx([28.0, -28.0])
    kept = booked(ticket={**TICKET, "quantity": [0]})
    assert [leg.quote_quantity.tolist() for leg in kept.encoded.legs] == [[0.0], [0.0]]
    zero = valued(kept)
    assert (zero.mark, zero.dv01) == (0.0, 0.0)


# --- the rules ------------------------------------------------------------------------------------

UNITS_OF_THE_PRICE = ("spread_price_currency_unit", "spread_price_quantity_unit")


def test_the_spread_prices_unit_is_required_typed_and_one_for_the_batch() -> None:
    for name in UNITS_OF_THE_PRICE:
        without = {k: v for k, v in CRACK.items() if k != name}
        assert refused(without) == (
            f"{name} is missing, expected a value in the template or a column in the ticket"
        )
    assert refused({**CRACK, "spread_price_currency_unit": "EUR"}) == (
        "spread_price_currency_unit is 'EUR', expected DOLLAR or CENT"
    )
    # Nor is the currency's own name a unit of it, since currency-and-currency-unit.md.
    assert refused({**CRACK, "spread_price_currency_unit": "USD"}) == (
        "spread_price_currency_unit is 'USD', expected DOLLAR or CENT"
    )
    # A unit of another measure, and a code is matched exactly as the tables spell it.
    for text in ("MMBTU", "bbl", "DOLLAR/BBL"):
        assert refused({**CRACK, "spread_price_quantity_unit": text}) == (
            f"spread_price_quantity_unit is {text!r}, expected a VOLUME unit, GAL, BBL, L or M3"
        )
    # One for the batch, as the route is: a ticket column every row agrees on, or refused by
    # the first row that differs; never the template and the ticket both.
    by_row = {k: v for k, v in CRACK.items() if k != "spread_price_quantity_unit"}
    two: dict[str, list[object]] = {k: [*v, *v] for k, v in TICKET.items()}
    agreed = booked(by_row, {**two, "spread_price_quantity_unit": ["BBL", "BBL"]})
    assert agreed.resolved.price_unit == PriceUnit("DOLLAR", "BBL")
    assert agreed.encoded.offset.tolist() == [-15_000.0, -15_000.0]
    assert refused(by_row, {**two, "spread_price_quantity_unit": ["BBL", "GAL"]}) == (
        "spread_price_quantity_unit row 2 is 'GAL', expected 'BBL' as at row 1; a batch has one "
        "spread_price_quantity_unit"
    )
    assert refused(ticket={**TICKET, "spread_price_quantity_unit": ["BBL"]}) == (
        "spread_price_quantity_unit is supplied by the template and by the ticket, expected by "
        "one of them"
    )


def test_two_measures_and_two_settlement_units_are_refused_by_the_second_index() -> None:
    # An energy index beside a volume one, refused as that and not as a quantity unit the
    # second index does not define.
    assert refused(indexes=(RB, A)) == (
        "index 2 'A' measures ENERGY, expected VOLUME as index 1 'RB'; a spread across two "
        "measures needs a density or a heat content, which the unit tables do not carry"
    )
    in_cents = an_index("WTI", ("DOLLAR", "BBL"), (1_000.0, "BBL"), settles="CENT")
    assert refused(indexes=(RB, in_cents)) == (
        "index 2 'WTI' settles in CENT, expected DOLLAR as index 1 'RB'; a spread is one payment "
        "in one currency unit"
    )


PJM = an_index("PJM", ("DOLLAR", "MWH"), (400.0, "MWH"), measure="ENERGY", word="MMBTU")
ERCOT = an_index("ERCOT", ("DOLLAR", "MWH"), (400.0, "MWH"), measure="ENERGY", word="MMBTU")
NBP = an_index("NBP", ("DOLLAR", "THERM"), (1_000.0, "THERM"), measure="ENERGY", word="MMBTU")


def test_electricity_against_heat_is_refused_and_two_heat_units_convert() -> None:
    assert tuple(UNITS.categories["ENERGY"].sizes) == (
        "MMBTU",
        "BTU",
        "THERM",
        "GJ",
        "MWH",
        "KWH",
    )  # every unit of energy the tables hold is of one side or the other
    assert {"MWH", "KWH"} == ELECTRICITY
    assert refused(GAS_SPREAD, GAS_TICKET, (PJM, A)) == (
        "index 2 'A' quotes per MMBTU and index 1 'PJM' per MWH, expected two units of heat or "
        "two of electricity; a spread of power against fuel is struck at a heat rate, a ratio "
        "between the legs, which is not built"
    )
    # The spread price's own unit is held to the legs' side.
    assert refused({**GAS_SPREAD, "spread_price_quantity_unit": "MWH"}, GAS_TICKET, (NTO, PAN)) == (
        "spread_price_quantity_unit is 'MWH', expected a unit of heat as the two indexes quote "
        "in, MMBTU, BTU, THERM or GJ"
    )
    assert refused(GAS_SPREAD, GAS_TICKET, (PJM, ERCOT)) == (
        "spread_price_quantity_unit is 'MMBTU', expected a unit of electricity as the two "
        "indexes quote in, MWH or KWH"
    )
    power = booked({**GAS_SPREAD, "spread_price_quantity_unit": "MWH"}, GAS_TICKET, (PJM, ERCOT))
    assert power.resolved.price_unit == PriceUnit("DOLLAR", "MWH")
    # Two units of heat are a conversion like any other: 10,000 MMBTU is 100,000 therms, at
    # 0.40 a therm 40,000, less A's 35,000, less 1,000 of spread price.
    therms = booked(GAS_SPREAD, GAS_TICKET, (NBP, A))
    assert therms.encoded.legs[0].quote_quantity.tolist() == [100_000.0]
    near(valued(therms, ((0.40,), (3.50,))).payment_amount, [4_000.0])


def test_a_quantity_unit_is_one_amount_on_both_indexes_in_the_spread_prices_unit() -> None:
    # A LOT of 42,000 GAL and a LOT of 1,000 BBL are one amount and book; of 500 BBL, two.
    half = an_index("WTI", ("DOLLAR", "BBL"), (500.0, "BBL"))
    assert refused({**CRACK, "quantity_unit": "LOT"}, {**TICKET, "quantity": [1]}, (RB, half)) == (
        "quantity_unit 'LOT' of trade 1 at row 1 is 1000.0 BBL on index 'RB' and 500.0 BBL on "
        "index 'WTI', expected one quantity per entered unit on both legs"
    )
    # A word one index does not define is refused by that index, as on any pair.
    assert refused({**CRACK, "quantity_unit": "GAL"}).startswith("quantity_unit is 'GAL', expected")


def test_the_kernel_holds_a_price_unit_exactly_on_a_float_float() -> None:
    spread_unit(True, PriceUnit("DOLLAR", "BBL"))
    spread_unit(False, None)
    with pytest.raises(ValueError) as missing:
        spread_unit(True, None)
    assert str(missing.value) == (
        "price_unit is None, expected the spread price's currency unit and quantity unit with a "
        "float_float; a spread price's unit is typed, never taken from an index"
    )
    with pytest.raises(ValueError) as extra:
        spread_unit(False, PriceUnit("DOLLAR", "BBL"))
    assert str(extra.value) == (
        "price_unit is DOLLAR per BBL, expected none with a fixed_float; its price is in the unit "
        "its indexes quote in"
    )


def test_a_spread_coefficient_past_the_largest_number_is_refused_by_its_trade() -> None:
    # 2e306 barrels is a number each leg holds, and 159 times as many litres is not: the spread
    # price's own product is judged where it is made, as each leg's is.
    brent = an_index("BRENT", ("DOLLAR", "BBL"), (1_000.0, "BBL"))
    huge: dict[str, list[object]] = {**TICKET, "quantity": [2e306], "spread_price": [0.0]}
    assert refused({**CRACK, "spread_price_quantity_unit": "L"}, huge, (WTI, brent)) == (
        "trade 1 at row 1 has inf of spread coefficient, expected a finite amount of DOLLAR per "
        "DOLLAR/L; its count times its specification's size in the spread price's unit and the "
        "currency factor outruns the largest number"
    )


# --- the crack on the sheet -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """RB and WTI on a sheet: two futures indexes over F27, G27 and H27, 1 January 2027 closed,
    RB in DOLLAR per GAL with a LOT of 42,000 GAL and WTI in DOLLAR per BBL with a LOT of 1,000 BBL,
    both defining BBL; valued 4 January 2027, G27 quoted 2.10 and 70.00, SOFR at 0.95 a year on;
    a float_float template with the spread price in DOLLAR per BBL and a row of 1,000 BBL of G27
    at 15.00."""
    headers = across(
        "name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"
    )
    holidays = SEAM["_CreateHolidayCalendar"](serial("2027-01-01"), bridge.MISSING)
    date = SEAM["_CreateValuationDate"](serial(AS_OF), 0.5)
    cells: dict[str, Any] = {"holidays": holidays}
    for key, name, unit, lot, settles, quotes in (
        ("rb", "RB", "GAL", 42000.0, (2.05, 2.04), (2.10, 2.20)),
        ("wti", "WTI", "BBL", 1000.0, (70.50, 70.40), (70.00, 71.00)),
    ):
        made = SEAM["_CreateIndex"](
            name,
            f"Crack leg {name}, a futures index",
            SEAM["_CreateFuturesSchedule"](
                down("F27", "G27", "H27"),
                down(serial("2026-12-29"), serial("2027-01-27"), serial("2027-02-24")),
                bridge.MISSING,
            ),
            SEAM["_CreateIndexConventions"]("DOLLAR", unit, "DOLLAR", "VOLUME", unit),
            SEAM["_CreateContractSpecifications"](
                headers,
                Cells.from_rows([["LOT", lot, unit, 0.0, 0.0], ["BBL", 1.0, "BBL", 0.0, 0.0]]),
            ),
            holidays,
            "LOT",
        )
        history = SEAM["_CreateMarketHistory"](
            SEAM["_CreateCalendar"](date, made),
            SEAM["_CreateFuturesFixings"](
                down(serial("2026-12-31"), serial("2026-12-30")), down(*settles), made
            ),
        )
        cells[key] = made
        cells[f"hist_{key}"] = history
        cells[f"market_{key}"] = SEAM["_CreateMarket"](
            history, SEAM["_CreatePriceVector"](name, down(*quotes))
        )
    cells["curves"] = SEAM["_CollectDiscountCurves"](
        SEAM["_CreateDiscountCurve"](
            "SOFR",
            across("date", "discount_factor"),
            Cells.from_rows([[serial(AS_OF), 1.0], [serial(PAY), 0.95]]),
        )
    )
    cells["values"] = [
        "DOLLAR",
        "BBL",
        "BBL",
        "month",
        "monthly",
        1.0,
        "lastday",
        "lastday",
        "bilateral",
        "financial",
        "ACME Trading",
        "SOFR",
        serial(PAY),
        holidays,
    ]
    cells["template"] = SEAM["_CreateTradeTemplate"](
        "float_float", across(*TEMPLATE_FIELDS), across(*cells["values"])
    )
    cells["headers"] = across("trade_id", "trade_date", "contract_code", "quantity", "spread_price")
    cells["row"] = across(1.0, serial("2026-12-15"), "G27", 1000.0, 15.00)
    return cells


def test_the_sheet_books_prepares_and_values_a_crack(sheet: dict[str, Any]) -> None:
    both = down(sheet["rb"], sheet["wti"])
    booked_ = SEAM["_CreateTrades"](both, sheet["headers"], sheet["row"], sheet["template"])
    assert re.fullmatch(rf"{PID}:trades:RB-WTI:\d+", str(booked_))
    table = read(booked_)
    assert under(table, "spread_price") == [15.0]
    assert under(table, "spread_price_currency_unit") == ["DOLLAR"]
    assert under(table, "spread_price_quantity_unit") == ["BBL"]
    assert under(table, "quote_quantity") == [42_000.0] and under(table, "offset") == [-15_000.0]
    prepared = SEAM["_PrepareTrades"](booked_, down(sheet["hist_rb"], sheet["hist_wti"]))
    assert under(read(prepared), "live_lots") == pytest.approx([1.0, -1.0], **CLOSE)
    results = SEAM["_EvaluateTrades"](
        prepared, across(sheet["market_rb"], sheet["market_wti"]), sheet["curves"]
    )
    assert re.fullmatch(rf"{PID}:trade_results:RB-WTI:\d+", str(results))
    values = spilled(SEAM["_ReportValues"](results))
    assert values[2][0] == pytest.approx(3_040.0, **CLOSE) and values[2][1] == 0.0
    risk = spilled(SEAM["_ReportRisk"](results, "all", "day"))
    assert risk[1][1:] == [
        "RB nominal_delta [LOT]",
        "RB delta [LOT]",
        "WTI nominal_delta [LOT]",
        "WTI delta [LOT]",
        "SOFR USD dv01 [DOLLAR per basis point]",
        "RB SOFR cross_gamma [LOT per basis point]",
        "WTI SOFR cross_gamma [LOT per basis point]",
    ]
    assert risk[3][1:] == pytest.approx(
        [1.0, 0.95, -1.0, -0.95, -0.304, -0.000095, 0.000095], **CLOSE
    )
    slots = read(results)
    assert under(slots, "price_unit") == ["DOLLAR/GAL", "DOLLAR/BBL"]
    assert under(slots, "floating_contribution") == pytest.approx([88_200.0, -70_000.0], **CLOSE)
    # The template reads back the unit it was given.
    shown = read(sheet["template"])
    assert under(shown, "spread_price_currency_unit") == ["DOLLAR"]
    assert under(shown, "spread_price_quantity_unit") == ["BBL"]


def test_the_sheet_refuses_a_spread_price_with_no_unit_or_a_wrong_one(
    sheet: dict[str, Any],
) -> None:
    create = SEAM["_CreateTrades"]
    both = down(sheet["rb"], sheet["wti"])

    def with_units(*units: object) -> object:
        """The sheet's template with its first two cells, the unit's, replaced, or with no
        currency unit at all."""
        fields = TEMPLATE_FIELDS if units else TEMPLATE_FIELDS[1:]
        values = [*units, *sheet["values"][2:]] if units else sheet["values"][1:]
        return SEAM["_CreateTradeTemplate"]("float_float", across(*fields), across(*values))

    assert create(both, sheet["headers"], sheet["row"], with_units()) == (
        "#ERROR _CreateTrades: ValueError: spread_price_currency_unit is missing, expected a "
        "value in the template or a column in the ticket"
    )
    assert create(both, sheet["headers"], sheet["row"], with_units("EUR", "BBL")) == (
        "#ERROR _CreateTrades: ValueError: spread_price_currency_unit is 'EUR', expected "
        "DOLLAR or CENT"
    )
    # The currency's own name is no unit of it, since currency-and-currency-unit.md: the
    # code the dollar had, refused by the same sentence.
    assert create(both, sheet["headers"], sheet["row"], with_units("USD", "BBL")) == (
        "#ERROR _CreateTrades: ValueError: spread_price_currency_unit is 'USD', expected "
        "DOLLAR or CENT"
    )
    assert create(both, sheet["headers"], sheet["row"], with_units("DOLLAR", "MMBTU")) == (
        "#ERROR _CreateTrades: ValueError: spread_price_quantity_unit is 'MMBTU', expected a "
        "VOLUME unit, GAL, BBL, L or M3"
    )
    # A fixed_float has no such field: its price is in its indexes' one unit.
    assert SEAM["_CreateTradeTemplate"](
        "fixed_float", across("route", "spread_price_currency_unit"), across("bilateral", "DOLLAR")
    ) == (
        "#ERROR _CreateTradeTemplate: fields cell (1, 2) is text 'spread_price_currency_unit', "
        f"expected a field of fixed_float: {FIELDS.format(price='fixed_price')}"
    )
