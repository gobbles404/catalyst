"""A fixed price in a unit of its own, issue #273: fixed_price_unit, one text such as
`DOLLAR/MT`, each row's own, on a fixed_float whose index quotes in another unit. A synthetic
premium index quoted in dollars a pound and settled in dollars, defining a pound, a tonne and a
lot of 55,116 pounds, its delta reported in tonnes; the issue's three ways of writing one trade,
priced by hand; a quantity and a price each in a unit of its own; the default, the index's quote
unit, to the last bit; indexes that quote in cents a pound, dollars a tonne, cents a gallon and
dollars per MMBTU; the lifecycle, a strip, a pair and a closed physical contract; and what is
refused, by the field and the row. Every expected number is the issue's or hand arithmetic
here; the production code is never asked for one."""

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pytest
from holiday_fixtures import closed_on, index_on
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import a_template, a_ticket, key_of, the_calendars
from test_trades import dates, day, history_on, numbers, quoted
from test_two_index import AS_OF, CLOSE, PAY, PAYS, SOFR, A, B, close
from test_two_index import BILATERAL as PAIR_BILATERAL
from test_two_index import TICKET as PAIR_TICKET
from test_two_index import booked as booked_pair
from test_two_index import valued as valued_pair

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.globals.discount_curve import DiscountCurve, bump_discount_curve
from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.trades.encoding import encoded
from catalyst.trades.evaluation import trade_results
from catalyst.trades.observations import observed
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.results import TradeResults
from catalyst.trades.terms import PriceUnit, ResolvedTrades, resolved_trades

# --- the indexes ----------------------------------------------------------------------------------
# Futures indexes over X26 to J27, F27 expiring 29 December 2026 and G27 27 January 2027,
# Christmas and New Year's Day closed. On the valuation day, 4 January 2027, G27 is the first
# live contract.

CODES = ("X26", "Z26", "F27", "G27", "H27", "J27")
EXPIRIES = ("2026-10-28", "2026-11-25", "2026-12-29", "2027-01-27", "2027-02-24", "2027-03-29")
Spec = tuple[str, float, str]
# A pound, a tonne and the exchange's lot, 55,116 pounds, which is 25 tonnes and a little.
MASS_SPECS: tuple[Spec, ...] = (("LB", 1.0, "LB"), ("MT", 1.0, "MT"), ("LOT", 55_116.0, "LB"))
# The pounds in a tonne, exactly as the unit tables define the two: 2204.62262...
LB_PER_MT = 1000 / 0.45359237


def an_index(
    name: str,
    quote: tuple[str, str],
    specs: tuple[Spec, ...] = MASS_SPECS,
    *,
    measure: str = "MASS",
    reports: str = "MT",
    fees: tuple[float, float] = (0.0, 0.0),
) -> Index:
    """A futures index quoted in that currency unit per that quantity unit and settled in
    dollars, with those specifications; the two fees are per unit of a specification's lot."""
    sizes = numbers(*(size for _, size, _ in specs))
    return index_on(
        name,
        f"Index {name}",
        futures_schedule(CODES, dates(*EXPIRIES), None),
        index_conventions(quote[0], quote[1], "DOLLAR", measure, quote[1], UNITS),
        contract_specifications(
            tuple(word for word, _, _ in specs),
            sizes,
            tuple(unit for _, _, unit in specs),
            sizes * fees[0],
            sizes * fees[1],
            UNITS,
        ),
        closed_on(dates("2026-12-25", "2027-01-01")),
        reports,
        UNITS,
    )


MWP = an_index("MWP", ("DOLLAR", "LB"))  # the issue's index: dollars a pound
BILATERAL: dict[str, object] = {
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "lastday",
    "settlement_method": "financial",
    "payment_holiday_key": key_of(PAYS),
    "route": "bilateral",
    "counterparty": "ACME Trading",
    "discount_curve_key": "SOFR",
    "payment_day": day(PAY),  # a year after the valuation day, a factor of 0.95
}
CLEARED: dict[str, object] = {
    **{k: v for k, v in BILATERAL.items() if k not in ("counterparty", "discount_curve_key")},
    "route": "cleared",
    "clearing_house": "CME Clearing",
}
# A row as a test writes it: quantity, quantity_unit, fixed_price and fixed_price_unit, the
# last None on every row for a ticket without the column.
Row = tuple[float, str, float, str | None]
A_ROW: Row = (LB_PER_MT, "LB", 0.20, "DOLLAR/LB")
B_ROW: Row = (1.0, "MT", 0.20 * LB_PER_MT, "DOLLAR/MT")
C_ROW: Row = (1.0, "MT", 20.0, "CENT/LB")
# The issue's table, each of the three alone: one tonne bought at 20 cents a pound, the market
# at 25, one payment a year on at a factor of 0.95.
FIXED = 440.9245243697552
FLOATING = 551.155655462194
NET = 110.2311310924388
MARK = 104.7195745378168
DV01 = -0.0104719574537817


def ticket(*rows: Row, code: str = "G27", **more: list[object]) -> dict[str, list[object]]:
    columns: dict[str, list[object]] = {
        "trade_id": [float(i + 1) for i in range(len(rows))],
        "trade_date": ["2026-12-15"] * len(rows),
        "contract_code": [code] * len(rows),
        "quantity": [quantity for quantity, _, _, _ in rows],
        "quantity_unit": [word for _, word, _, _ in rows],
        "fixed_price": [price for _, _, price, _ in rows],
    }
    units = [unit for _, _, _, unit in rows]
    if any(unit is not None for unit in units):
        columns["fixed_price_unit"] = list(units)
    return {**columns, **more}


def booked(
    *rows: Row,
    index: Index = MWP,
    template: Mapping[str, object] = BILATERAL,
    code: str = "G27",
    **more: list[object],
) -> Trades:
    return made(ticket(*rows, code=code, **more), template, (index,))


def made(
    columns: Mapping[str, list[object]],
    template: Mapping[str, object] = BILATERAL,
    indexes: Sequence[Index] = (MWP,),
) -> Trades:
    return trades(
        indexes, a_ticket(columns), a_template(template), UNITS, WorkCounter(), the_calendars()
    )


def refused(*rows: Row, index: Index = MWP, template: Mapping[str, object] = BILATERAL) -> str:
    with pytest.raises(ValueError) as refusal:
        booked(*rows, index=index, template=template)
    return str(refusal.value)


def valued(
    batch: Trades,
    *quotes: float,
    as_of: str = AS_OF,
    curve: DiscountCurve | None = SOFR,
    finals: Mapping[str, float] | None = None,
) -> TradeResults:
    """The batch prepared and valued on the day: its index's history, a settle of 3.00 on every
    fixed day but the finals given, and its market quoted from its first live contract on."""
    history = history_on(batch.resolved.legs[0].index, as_of, dict(finals or {}))
    prepared = prepared_trades(batch.encoded, (history,), WorkCounter())
    market = quoted(history, *(quotes or (0.25,)))
    return trade_results(
        prepared, (market,), WorkCounter(), None if curve is None else curve_set(curve)
    )


def fixed_legs(batch: Trades) -> list[float]:
    """Each component's fixed leg as an amount paid: the offset, without its sign."""
    return (-batch.encoded.offset).tolist()


# --- the issue's worked example -------------------------------------------------------------------


@pytest.mark.parametrize("row", [A_ROW, B_ROW, C_ROW], ids=["A", "B", "C"])
def test_the_issue_table_is_one_trade_written_three_ways(row: Row) -> None:
    batch = booked(row)
    assert fixed_legs(batch) == pytest.approx([FIXED], **CLOSE)
    (leg,) = batch.encoded.legs
    assert leg.quote_quantity.tolist() == pytest.approx([LB_PER_MT], **CLOSE)  # pounds, the index's
    assert leg.coefficient.tolist() == pytest.approx([LB_PER_MT], **CLOSE)
    results = valued(batch)
    (floating,) = results.legs
    close(floating.dated_live_contribution, [FLOATING])
    close(results.payment_amount, [NET])
    close(results.payment_factor, [0.95])
    assert results.mark == pytest.approx(MARK, **CLOSE)
    assert results.dv01 == pytest.approx(DV01, **CLOSE)
    assert results.cash == 0.0
    assert floating.nominal_delta_total == pytest.approx(1.0, **CLOSE)  # one tonne, the lot
    assert floating.delta_total == pytest.approx(0.95, **CLOSE)
    assert floating.cross_gamma_total == pytest.approx(-0.000095, **CLOSE)


def test_the_three_ways_in_one_batch_are_three_times_one_trade() -> None:
    batch = booked(A_ROW, B_ROW, C_ROW)
    terms = batch.resolved
    # The batch's distinct units, and each row's place among them.
    assert [terms.price_units[int(i)].code for i in terms.price_unit] == [
        "DOLLAR/LB",
        "DOLLAR/MT",
        "CENT/LB",
    ]
    assert terms.price.tolist() == [0.20, 0.20 * LB_PER_MT, 20.0]  # as entered, never restated
    assert fixed_legs(batch) == pytest.approx([FIXED] * 3, **CLOSE)
    results = valued(batch)
    close(results.payment_amount, [3 * NET])  # one payment group: one day, one curve
    assert results.mark == pytest.approx(3 * MARK, **CLOSE)
    assert results.dv01 == pytest.approx(3 * DV01, **CLOSE)
    (floating,) = results.legs
    assert floating.nominal_delta_total == pytest.approx(3.0, **CLOSE)
    assert floating.delta_total == pytest.approx(2.85, **CLOSE)
    assert floating.cross_gamma_total == pytest.approx(-0.000285, **CLOSE)


def test_two_of_them_double_and_one_against_another_sold_cancels() -> None:
    both = valued(booked(A_ROW, B_ROW))
    close(both.payment_amount, [2 * NET])
    assert both.mark == pytest.approx(2 * MARK, **CLOSE)
    sold_b: Row = (-1.0, "MT", 0.20 * LB_PER_MT, "DOLLAR/MT")
    flat = valued(booked(A_ROW, sold_b))
    (floating,) = flat.legs
    # The same trade bought in pounds and sold in tonnes: nothing left, to the roundoff of the
    # tables' one factor on amounts of a few hundred dollars.
    assert flat.payment_amount is not None
    assert abs(float(flat.payment_amount[0])) < 1e-10
    assert abs(flat.mark) < 1e-10 and abs(flat.dv01) < 1e-14
    assert abs(floating.nominal_delta_total) < 1e-12
    assert abs(floating.delta_total) < 1e-12


def test_the_cleared_trade_has_the_same_payment_and_mark_undiscounted() -> None:
    for row in (A_ROW, B_ROW, C_ROW):
        results = valued(booked(row, template=CLEARED), curve=None)
        assert results.mark == pytest.approx(NET, **CLOSE)
        assert results.dv01 == 0.0
        assert results.legs[0].nominal_delta_total == pytest.approx(1.0, **CLOSE)


# --- a quantity and a price, each in its own unit -------------------------------------------------


def test_a_tonne_trade_at_a_tonne_price_is_exact() -> None:
    # 50 tonnes at 1,870 dollars a tonne is 93,500 dollars and not a cent of roundoff, on an
    # index that quotes per pound: the price is never restated in pounds.
    batch = booked((50.0, "MT", 1870.0, "DOLLAR/MT"))
    assert fixed_legs(batch) == [93_500.0]
    assert batch.resolved.price.tolist() == [1870.0]
    assert batch.encoded.legs[0].coefficient.tolist() == pytest.approx([50 * LB_PER_MT], **CLOSE)


def test_the_quantity_word_does_not_choose_the_prices_unit() -> None:
    # Tonnes priced per pound and lots priced per tonne: neither price is per the word the
    # quantity was entered in. Two lots are 110,232 pounds, 50.0004 tonnes.
    # 50 tonnes are 110,231.13 pounds, at 0.91 dollars: 100,310.33.
    tonnes_at_cents_a_pound = booked((50.0, "MT", 91.0, "CENT/LB"))
    assert fixed_legs(tonnes_at_cents_a_pound) == pytest.approx([50 * LB_PER_MT * 0.91], **CLOSE)
    assert fixed_legs(tonnes_at_cents_a_pound) == pytest.approx([100_310.3292941193], rel=1e-12)
    # 110,232 pounds are 50.0004 tonnes, at 1,870 dollars: 93,500.74.
    lots_at_a_tonne_price = booked((2.0, "LOT", 1870.0, "DOLLAR/MT"))
    assert fixed_legs(lots_at_a_tonne_price) == pytest.approx(
        [2 * 55_116 / LB_PER_MT * 1870.0], **CLOSE
    )
    assert fixed_legs(lots_at_a_tonne_price) == pytest.approx([93_500.7370228008], rel=1e-12)
    # And a tonne quantity with no unit typed is priced per pound, the index's own: the trap the
    # field removes, a tonne price read as dollars a pound.
    misread = booked((50.0, "MT", 1870.0, None))
    assert fixed_legs(misread) == pytest.approx([50 * LB_PER_MT * 1870.0], **CLOSE)


def test_a_unit_from_the_template_is_every_rows_and_prices_as_the_column_does() -> None:
    rows: tuple[Row, ...] = ((50.0, "MT", 1870.0, None), (2.0, "LOT", 1900.0, None))
    by_template = booked(*rows, template={**BILATERAL, "fixed_price_unit": "DOLLAR/MT"})
    by_column = booked(*[(q, word, price, "DOLLAR/MT") for q, word, price, _ in rows])
    assert by_template.resolved.price_units == (PriceUnit("DOLLAR", "MT"),)
    assert by_template.resolved.price_unit.tolist() == [0, 0]
    np.testing.assert_array_equal(by_template.encoded.offset, by_column.encoded.offset)
    assert valued(by_template).mark == valued(by_column).mark
    with pytest.raises(ValueError) as both:
        booked(
            (50.0, "MT", 1870.0, "DOLLAR/MT"),
            template={**BILATERAL, "fixed_price_unit": "DOLLAR/MT"},
        )
    assert str(both.value) == (
        "fixed_price_unit is supplied by the template and by the ticket, expected by one of them"
    )


# --- the default: the unit the index quotes in ----------------------------------------------------


def test_no_unit_typed_is_the_indexes_quote_unit_to_the_last_bit() -> None:
    rows: tuple[Row, ...] = (
        (LB_PER_MT, "LB", 0.20, None),
        (3.0, "MT", 0.91, None),
        (-2.0, "LOT", 0.905, None),
        (0.0, "MT", 0.91, None),  # a zero row, kept ready
    )
    omitted = booked(*rows)
    typed = booked(*[(q, word, price, "DOLLAR/LB") for q, word, price, _ in rows])
    # The omitted unit is resolved into the same record a typed one makes.
    assert (
        omitted.resolved.price_units == typed.resolved.price_units == (PriceUnit("DOLLAR", "LB"),)
    )
    np.testing.assert_array_equal(omitted.resolved.price_unit, typed.resolved.price_unit)
    np.testing.assert_array_equal(omitted.encoded.offset, typed.encoded.offset)
    # And the fixed leg is the first leg's coefficient times the price, as it always was.
    (leg,) = omitted.encoded.legs
    np.testing.assert_array_equal(omitted.encoded.offset, -leg.coefficient * omitted.resolved.price)
    one, other = valued(omitted), valued(typed)
    assert (one.mark, one.dv01) == (other.mark, other.dv01)
    assert omitted.encoded.offset[3] == 0.0


def test_a_row_in_the_indexes_unit_beside_another_takes_the_first_legs_coefficient() -> None:
    # A mixed batch makes every row's coefficient in its own unit, and the rows typed in the
    # index's unit come out as the first leg's coefficient to the last bit.
    batch = booked(
        (LB_PER_MT, "LB", 0.20, "DOLLAR/LB"),
        (50.0, "MT", 1870.0, "DOLLAR/MT"),
        (2.0, "LOT", 0.905, "DOLLAR/LB"),
        (7.5, "MT", 0.91, "DOLLAR/LB"),
    )
    (leg,) = batch.encoded.legs
    own = [0, 2, 3]
    np.testing.assert_array_equal(
        batch.encoded.offset[own], (-leg.coefficient * batch.resolved.price)[own]
    )
    assert batch.encoded.offset[1] == -93_500.0


# --- indexes that quote in other units ------------------------------------------------------------


def test_the_conversion_runs_both_ways_whatever_the_index_quotes_in() -> None:
    # One tonne at 20 cents a pound, 440.92 dollars, on an index quoted in cents a pound and on
    # one quoted in dollars a tonne: the fixed leg is the same amount of dollars however the
    # index quotes and however the price is written, and the floating side is the index's own.
    cents = an_index("MWC", ("CENT", "LB"))
    tonnes = an_index("MWT", ("DOLLAR", "MT"))
    for index, quote, coefficient in (
        (cents, 25.0, LB_PER_MT * 0.01),  # dollars per cent a pound
        (tonnes, 0.25 * LB_PER_MT, 1.0),  # dollars per dollar a tonne
    ):
        for _, _, price, unit in (A_ROW, B_ROW, C_ROW):
            batch = booked((1.0, "MT", price, unit), index=index)
            assert fixed_legs(batch) == pytest.approx([FIXED], **CLOSE), (index.name, unit)
            assert batch.encoded.legs[0].coefficient.tolist() == pytest.approx(
                [coefficient], **CLOSE
            )
            results = valued(batch, quote)
            close(results.payment_amount, [NET])
            assert results.mark == pytest.approx(MARK, **CLOSE)
            assert results.legs[0].nominal_delta_total == pytest.approx(1.0, **CLOSE)


def test_a_gallon_index_takes_a_price_per_barrel() -> None:
    # No metal in it: an index in cents a gallon, a lot of 42,000 gallons, a deal struck in
    # dollars a barrel. One lot is 1,000 barrels; at 84 dollars a barrel the fixed leg is
    # 84,000, and against 210 cents a gallon, 88,200, the payment is 4,200. Read as cents a
    # gallon the 84 would have been 35,280.
    gallons = an_index(
        "RB",
        ("CENT", "GAL"),
        (("LOT", 42_000.0, "GAL"), ("BBL", 1.0, "BBL")),
        measure="VOLUME",
        reports="LOT",
    )
    for row in ((1.0, "LOT", 84.0, "DOLLAR/BBL"), (1_000.0, "BBL", 200.0, "CENT/GAL")):
        batch = booked(row, index=gallons)
        assert fixed_legs(batch) == pytest.approx([84_000.0], **CLOSE)
        results = valued(batch, 210.0)
        close(results.legs[0].dated_live_contribution, [88_200.0])
        close(results.payment_amount, [4_200.0])
    assert fixed_legs(booked((1.0, "LOT", 84.0, None), index=gallons)) == pytest.approx(
        [35_280.0], **CLOSE
    )


GAS = an_index(
    "GAS",
    ("DOLLAR", "MMBTU"),
    (("LOT", 10_000.0, "MMBTU"), ("MMBTU", 1.0, "MMBTU")),
    measure="ENERGY",
    reports="LOT",
)
POWER = an_index(
    "PWR",
    ("DOLLAR", "MWH"),
    (("LOT", 400.0, "MWH"), ("MWH", 1.0, "MWH")),
    measure="ENERGY",
    reports="LOT",
)


def test_heat_is_priced_in_a_unit_of_heat_and_power_in_one_of_electricity() -> None:
    # 10,000 MMBTU at 30 cents a therm is 100,000 therms at 0.30: 30,000 dollars, as 3.00 a
    # MMBTU is. A megawatt hour is 3.412 MMBTU as energy, but a price of gas per megawatt hour
    # is struck at a heat rate, which is no unit conversion: refused, both ways.
    assert fixed_legs(booked((1.0, "LOT", 30.0, "CENT/THERM"), index=GAS)) == pytest.approx(
        [30_000.0], **CLOSE
    )
    assert fixed_legs(booked((1.0, "LOT", 3.0, "DOLLAR/MMBTU"), index=GAS)) == [30_000.0]
    assert refused((1.0, "LOT", 10.0, "DOLLAR/MWH"), index=GAS) == (
        "fixed_price_unit of trade 1 at row 1 is 'DOLLAR/MWH', expected a unit of heat after "
        "the /, as the index quotes in, MMBTU, BTU, THERM or GJ; a price of power against fuel "
        "is struck at a heat rate, which is not built"
    )
    # 400 MWh at 4 cents a kilowatt hour: 400,000 kWh at 0.04, 16,000 dollars.
    assert fixed_legs(booked((1.0, "LOT", 4.0, "CENT/KWH"), index=POWER)) == pytest.approx(
        [16_000.0], **CLOSE
    )
    assert refused((1.0, "LOT", 3.0, "DOLLAR/MMBTU"), index=POWER) == (
        "fixed_price_unit of trade 1 at row 1 is 'DOLLAR/MMBTU', expected a unit of electricity "
        "after the /, as the index quotes in, MWH or KWH; a price of power against fuel is "
        "struck at a heat rate, which is not built"
    )


@settings(max_examples=60, deadline=None)
@given(
    st.sampled_from(sorted(UNITS.categories["MASS"].sizes)),
    st.sampled_from(sorted(UNITS.categories["MASS"].sizes)),
    st.sampled_from(["DOLLAR", "CENT"]),
    st.sampled_from(["DOLLAR", "CENT"]),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
)
def test_a_price_restated_by_hand_in_another_unit_is_the_same_fixed_leg(
    per: str, other_per: str, money: str, other_money: str, quantity: float, price: float
) -> None:
    # For any two mass units and any two currency units: the price times the tables' factors
    # between the units, typed in the second unit, books the fixed leg the first unit books.
    restated = (
        price * UNITS.factor("USD", money, other_money) / UNITS.factor("MASS", per, other_per)
    )
    one = booked((quantity, "MT", price, f"{money}/{per}"))
    other = booked((quantity, "MT", restated, f"{other_money}/{other_per}"))
    np.testing.assert_allclose(one.encoded.offset, other.encoded.offset, rtol=1e-12, atol=1e-300)
    # And the floating side never moves with the price's unit.
    np.testing.assert_array_equal(
        one.encoded.legs[0].coefficient, other.encoded.legs[0].coefficient
    )


# --- signs and zeros ------------------------------------------------------------------------------


def test_negative_and_zero_prices_and_quantities_are_booked_as_they_always_were() -> None:
    batch = booked(
        (50.0, "MT", -12.5, "DOLLAR/MT"),  # a negative price: the fixed leg is received
        (50.0, "MT", 0.0, "DOLLAR/MT"),
        (-50.0, "MT", 1870.0, "DOLLAR/MT"),  # sold
        (0.0, "MT", 1870.0, "DOLLAR/MT"),
    )
    assert batch.encoded.offset.tolist() == [625.0, -0.0, 93_500.0, -0.0]
    # A zero row is kept ready, and its unit is read like any other row's.
    assert refused((0.0, "MT", 1870.0, "DOLLAR/BBL")).startswith(
        "fixed_price_unit of trade 1 at row 1 is 'DOLLAR/BBL', expected a MASS unit"
    )


# --- the lifecycle --------------------------------------------------------------------------------


# Paid five business days after the last observation: G27 under lastday is observed on its
# expiry, 27 January, and pays 3 February; under asian it is February's pricing days, the last
# the 26th, and pays 5 March.
STATES = [
    ("lastday", "2027-01-04", False),  # live
    ("lastday", "2027-02-01", False),  # fixed, not yet paid
    ("lastday", "2027-02-10", True),  # paid: cash
    ("asian", "2027-01-04", False),  # live
    ("asian", "2027-02-10", False),  # a part of the month fixed
    ("asian", "2027-03-02", False),  # every day fixed, not yet paid
    ("asian", "2027-03-10", True),  # paid: cash
]


@pytest.mark.parametrize(("method", "as_of", "paid"), STATES)
def test_every_state_values_the_same_whichever_way_the_price_was_written(
    method: str, as_of: str, paid: bool
) -> None:
    template = {**BILATERAL, "schedule_method": method, "payment_day": "+5bd"}
    curve = curve_of((as_of, 1.0), ("2028-01-04", 0.95))
    # A quote for each contract still live on the day, G27, H27 and J27 in January: February's
    # days are priced by H27 to its expiry on the 24th and by J27 after it.
    quotes = (0.25, 0.26, 0.27)[sum(as_of > expiry for expiry in EXPIRIES[3:]) :]
    valuations: list[tuple[float, float, float]] = []
    for row in ((LB_PER_MT, "LB", 0.20, None), B_ROW, C_ROW):
        batch = booked(row, template=template)
        results = valued(batch, *quotes, as_of=as_of, curve=curve, finals={"G27": 0.26})
        valuations.append((results.mark, results.cash, results.dv01))
    (mark, cash, dv01), *others = valuations
    assert (cash != 0.0) == paid and (mark != 0.0) != paid
    for other_mark, other_cash, other_dv01 in others:
        assert other_mark == pytest.approx(mark, rel=1e-12, abs=1e-9)
        assert other_cash == pytest.approx(cash, rel=1e-12, abs=1e-9)
        assert other_dv01 == pytest.approx(dv01, rel=1e-12, abs=1e-12)


def test_a_price_tick_moves_the_floating_side_alone_and_a_rate_tick_the_discounting_alone() -> None:
    batch = booked(B_ROW)
    before = batch.encoded.offset.copy()
    low, high = valued(batch, 0.25), valued(batch, 0.30)
    assert low.payment_amount is not None and high.payment_amount is not None
    # Five cents a pound on a tonne: 110.23 dollars more, the fixed leg where it was.
    assert float(high.payment_amount[0] - low.payment_amount[0]) == pytest.approx(
        0.05 * LB_PER_MT, **CLOSE
    )
    np.testing.assert_array_equal(batch.encoded.offset, before)
    bumped = valued(batch, 0.25, curve=bump_discount_curve(SOFR, 1.0, WorkCounter()))
    close(bumped.payment_amount, [NET])  # the payment stands; its factor and the mark move
    assert bumped.mark != low.mark
    assert bumped.mark - low.mark == pytest.approx(DV01, rel=1e-3)


# --- strips, days, a pair and a closed physical contract ------------------------------------------


def test_a_strip_carries_its_rows_unit_to_every_month() -> None:
    strip = booked(
        (50.0, "MT", 1870.0, "DOLLAR/MT"), (1.0, "LOT", 0.91, "DOLLAR/LB"), code="G27-H27"
    )
    assert strip.resolved.occurrence.tolist() == [0, 0, 1, 1]
    assert fixed_legs(strip) == pytest.approx(
        [93_500.0, 93_500.0, 55_116 * 0.91, 55_116 * 0.91], **CLOSE
    )
    # Per calendar day: 2 tonnes a day over February's 28 days at 1,870 a tonne.
    daily = booked(
        (2.0, "MT", 1870.0, "DOLLAR/MT"),
        template={**BILATERAL, "quantity_per": "calday"},
        code="G27",
    )
    assert fixed_legs(daily) == [2.0 * 28 * 1870.0]
    # A part of a month, under asian: 14 to 20 February, one component, the row's quantity.
    part = made(
        {
            **{
                k: v
                for k, v in ticket((3.0, "MT", 1870.0, "DOLLAR/MT")).items()
                if k != "contract_code"
            },
            "start_date": ["2027-02-14"],
            "end_date": ["2027-02-20"],
        },
        {**BILATERAL, "schedule_method": "asian"},
    )
    assert fixed_legs(part) == [3.0 * 1870.0]


def test_a_pairs_one_outright_price_takes_a_unit_too() -> None:
    # two-index-one-price.md's pair, A plus B, 10,000 MMBTU at an outright of 3.00 a MMBTU:
    # typed as 30 cents a therm it is the same 30,000 dollars, the payment 1,000 and the mark 950.
    typed = booked_pair(
        PAIR_BILATERAL, {**PAIR_TICKET, "fixed_price": [30.0], "fixed_price_unit": ["CENT/THERM"]}
    )
    assert [leg.index for leg in typed.resolved.legs] == [A, B]
    close(typed.encoded.offset, [-30_000.0])
    results = valued_pair(typed)
    close(results.payment_amount, [1_000.0])
    assert results.mark == pytest.approx(950.0, **CLOSE)
    assert [leg.nominal_delta_total for leg in results.legs] == pytest.approx([1.0, 4.0], **CLOSE)


def test_the_fees_follow_the_quantity_and_never_the_prices_unit() -> None:
    # A cent of brokerage and half a cent of clearing per unit of each specification's lot, a
    # cent a tonne on the tonne row and 551.16 a lot: the reserves are the quantities' and stand
    # whatever unit the prices are in.
    index = an_index("FEE", ("DOLLAR", "LB"), fees=(0.01, 0.005))
    rows: tuple[Row, ...] = ((50.0, "MT", 1870.0, "DOLLAR/MT"), (2.0, "LOT", 1880.0, "DOLLAR/MT"))
    restated = [(q, word, price / LB_PER_MT, "DOLLAR/LB") for q, word, price, _ in rows]
    omitted = [(q, word, price / LB_PER_MT, None) for q, word, price, _ in rows]
    reserves = [
        made(ticket(*each, broker=["ION", "ION"]), CLEARED, (index,)).encoded.reserves
        for each in (rows, restated, omitted)
    ]
    assert reserves[0] == reserves[1] == reserves[2]
    # 50 tonnes at the tonne row's rate and two lots at the lot row's, by hand.
    assert reserves[0].brokerage == pytest.approx(50 * 0.01 + 2 * 55_116 * 0.01, **CLOSE)
    assert reserves[0].clearing == pytest.approx(50 * 0.005 + 2 * 55_116 * 0.005, **CLOSE)


def test_a_closed_physical_contract_is_cash_at_its_converted_fixed_legs() -> None:
    # Three tonnes bought at 1,870 dollars a tonne and sold at 90 cents a pound on F27, cleared
    # and physical, flat: past the expiry the contract is cash, the two fixed legs netted,
    # 3 x 2204.62 x 0.90 less 3 x 1,870. A count left open is still a delivery, refused.
    physical = {
        k: v
        for k, v in {**CLEARED, "settlement_method": "physical"}.items()
        if not k.startswith("payment_")
    }
    flat = booked(
        (3.0, "MT", 1870.0, "DOLLAR/MT"),
        (-3.0, "MT", 90.0, "CENT/LB"),
        template=physical,
        code="F27",
    )
    assert flat.encoded.closed is not None and flat.encoded.closed.tolist() == [True]
    results = valued(flat, as_of="2027-01-04", curve=None, finals={"F27": 0.93})
    assert results.cash == pytest.approx(3 * LB_PER_MT * 0.90 - 3 * 1870.0, **CLOSE)
    assert results.mark == 0.0
    left_open = booked(
        (3.0, "MT", 1870.0, "DOLLAR/MT"),
        (-2.0, "MT", 90.0, "CENT/LB"),
        template=physical,
        code="F27",
    )
    with pytest.raises(ValueError, match="a physical position open past its expiry"):
        valued(left_open, as_of="2027-01-04", curve=None, finals={"F27": 0.93})


# --- what is refused ------------------------------------------------------------------------------

NO_FORM = "expected a currency unit and a quantity unit joined by one /, such as DOLLAR/MT"


@pytest.mark.parametrize(
    "text",
    ["DOLLAR", "DOLLAR/", "/MT", "/", "DOLLAR/MT/LB", "DOLLAR//MT", "DOLLAR-MT", "DOLLAR MT"],
)
def test_a_unit_that_is_not_two_codes_and_one_slash_is_refused_by_its_field_and_row(
    text: str,
) -> None:
    good: Row = (1.0, "MT", 1870.0, "DOLLAR/MT")
    assert (
        refused(good, (1.0, "MT", 1870.0, text)) == f"fixed_price_unit row 2 is {text!r}, {NO_FORM}"
    )
    # In a template the form is read when the template is made, by the field alone.
    with pytest.raises(ValueError) as refusal:
        a_template({**BILATERAL, "fixed_price_unit": text})
    assert str(refusal.value) == f"fixed_price_unit is {text!r}, {NO_FORM}"


MASS_UNITS = "a MASS unit, KG, LB, MT, ST, LT, G, OZT or CWT_US, after the /"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("USD/MT", "DOLLAR or CENT before the /"),  # the currency's name is no unit of it
        ("dollar/MT", "DOLLAR or CENT before the /"),
        (" DOLLAR/MT", "DOLLAR or CENT before the /"),
        ("DOLLAR /MT", "DOLLAR or CENT before the /"),
        ("MT/DOLLAR", "DOLLAR or CENT before the /"),
        ("DOLLAR/mt", MASS_UNITS),
        ("DOLLAR/ MT", MASS_UNITS),
        ("DOLLAR/MT ", MASS_UNITS),
        ("DOLLAR/BBL", MASS_UNITS),  # a volume under a mass index: a density, which is not here
        ("DOLLAR/MMBTU", MASS_UNITS),
        ("DOLLAR/LOT", MASS_UNITS),  # the desk's word for a specification is no unit
        ("DOLLAR/TONNE", MASS_UNITS),
    ],
)
def test_a_code_the_tables_do_not_hold_for_the_index_is_refused_by_its_trade(
    text: str, expected: str
) -> None:
    good: Row = (1.0, "MT", 1870.0, "DOLLAR/MT")
    assert refused(good, (1.0, "MT", 1870.0, text)) == (
        f"fixed_price_unit of trade 2 at row 2 is {text!r}, expected {expected}"
    )
    # The template's one unit is every row's, and the first row's trade names it.
    assert (
        refused((1.0, "MT", 1870.0, None), template={**BILATERAL, "fixed_price_unit": text})
        == f"fixed_price_unit of trade 1 at row 1 is {text!r}, expected {expected}"
    )


def test_the_first_row_from_the_top_with_a_bad_unit_is_the_one_named() -> None:
    good: Row = (1.0, "MT", 1870.0, "DOLLAR/MT")
    # "DOLLAR/ZZ" at row 2 and "DOLLAR/AA" at row 3: row 2, whichever text sorts first.
    assert refused(good, (1.0, "MT", 1.0, "DOLLAR/ZZ"), (1.0, "MT", 1.0, "DOLLAR/AA")) == (
        f"fixed_price_unit of trade 2 at row 2 is 'DOLLAR/ZZ', expected {MASS_UNITS}"
    )
    assert refused(good, (1.0, "MT", 1.0, "ZZ-MT"), (1.0, "MT", 1.0, "AA-MT")) == (
        f"fixed_price_unit row 2 is 'ZZ-MT', {NO_FORM}"
    )


def test_a_supplied_column_never_falls_back_to_the_default_on_a_row() -> None:
    # A column on the ticket holds a unit on every row. A blank cell and an empty text never
    # reach the library: the seam refuses each for a field whose cells must hold a value, as it
    # does for any field but the three of a period.
    field = next(field for field in FIXED_FLOAT.fields if field.name == "fixed_price_unit")
    assert not field.may_be_unsupplied
    count = bridge.entry("CountFieldRows")
    headers = Cells.from_rows([["quantity", "fixed_price_unit"]])
    assert (
        count("fixed_float", headers, Cells.from_rows([[1.0, "DOLLAR/MT"], [2.0, "CENT/LB"]]))
        == 2.0
    )
    for cell, words in ((None, "blank"), ("", "empty text")):
        body = Cells.from_rows([[1.0, "DOLLAR/MT"], [2.0, cell]])
        assert count("fixed_float", headers, body) == (
            f"#ERROR CountFieldRows: rows cell (2, 2) is {words}, expected text"
        )


def test_a_conversion_or_a_fixed_leg_past_the_largest_number_is_refused_by_its_trade() -> None:
    # On an index quoted per tonne, 1e306 tonnes is a quantity the floating side holds, and a
    # million times as many grams is not: the fixed price's own coefficient outruns.
    tonnes = an_index("MWT", ("DOLLAR", "MT"))
    assert refused((1e306, "MT", 1.0, "DOLLAR/G"), index=tonnes) == (
        "trade 1 at row 1 has inf of fixed coefficient, expected a finite amount of DOLLAR per "
        "DOLLAR/G; its count times its specification's size in the fixed price's unit and the "
        "currency factor outruns the largest number"
    )
    # And a coefficient that stands times a price too large is the fixed leg's, as before.
    assert refused((1e300, "MT", 1e10, "DOLLAR/MT"), index=tonnes) == (
        "trade 1 at row 1 has -inf of fixed leg, expected a finite amount of DOLLAR; its "
        "coefficient times its fixed price outruns the largest number"
    )


# --- the kernel's rules over the units, for a caller in Python ------------------------------------


def _kernel(**units: Any) -> ResolvedTrades:
    """The terms of one row booked on MWP, made by the kernel with the units given."""
    terms = booked((1.0, "MT", 1870.0, None), (2.0, "MT", 1880.0, None)).resolved
    (leg,) = terms.legs
    return resolved_trades(
        terms.instrument,
        leg.index,
        leg.specification,
        terms.route,
        terms.settlement,
        leg.schedule_method,
        terms.quantity_per,
        terms.settlement_frequency,
        terms.nearby,
        terms.trade_ids,
        terms.clearing_house,
        terms.broker,
        terms.trade_dates,
        terms.occurrence,
        leg.contract,
        terms.quantity,
        terms.start_date,
        terms.end_date,
        terms.price,
        terms.payment,
        counterparty=terms.counterparty,
        discount_curve_key=terms.discount_curve_key,
        payment_holiday_key=terms.payment_holiday_key,
        **units,
    )


def places(*values: int) -> NDArray[np.intp]:
    return np.array(values, dtype=np.intp)


def test_the_kernel_resolves_the_default_and_holds_each_rows_place_in_range() -> None:
    tonne, pound = PriceUnit("DOLLAR", "MT"), PriceUnit("DOLLAR", "LB")
    default = _kernel()
    assert default.price_units == (pound,) and default.price_unit.tolist() == [0, 0]
    assert not default.price_unit.flags.writeable
    # One unit without places is every row's; places choose among several.
    assert _kernel(price_units=(tonne,)).price_unit.tolist() == [0, 0]
    mixed = _kernel(price_units=(tonne, pound), price_unit=places(1, 0))
    assert [mixed.price_units[i] for i in mixed.price_unit] == [pound, tonne]
    for units, message in (
        (
            {"price_units": (tonne, pound)},
            "price_unit is None with 2 price units, expected each occurrence's position among them",
        ),
        (
            {"price_units": (tonne, pound), "price_unit": places(0, 2)},
            "price_unit row 2 is 2, expected a price unit, its position among price_units, 0 to 1",
        ),
        (
            {"price_units": (tonne, pound), "price_unit": places(0)},
            "price_unit has 1 rows, expected 2, one per occurrence",
        ),
    ):
        with pytest.raises(ValueError) as refusal:
            _kernel(**units)
        assert str(refusal.value) == message
    # A unit no row is priced in is read for nothing: the batch prices in tonnes alone.
    spare = _kernel(price_units=(tonne, PriceUnit("EUR", "BBL")), price_unit=places(0, 0))
    made_of = encoded(spare, (_observed(spare),), UNITS, WorkCounter())
    assert (-made_of.offset).tolist() == [1870.0, 3760.0]


def _observed(terms: ResolvedTrades) -> Any:
    (leg,) = terms.legs
    return observed(
        leg.schedule_method[terms.occurrence],
        leg.index,
        leg.contract,
        terms.start_date,
        terms.end_date,
        terms.named,
    )
