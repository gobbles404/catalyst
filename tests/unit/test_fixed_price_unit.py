"""A fixed price in a unit of its own, issue #273: two fields, fixed_price_currency_unit and
fixed_price_quantity_unit, DOLLAR and MT for dollars a tonne, each row's own and each from the
template or the ticket, on a fixed_float whose index quotes in another unit. A synthetic
premium index quoted in dollars a pound and settled in dollars, defining a pound, a tonne and a
lot of 55,116 pounds, its delta reported in tonnes; the issue's three ways of writing one trade,
priced by hand; a quantity and a price each in a unit of its own; the two fields from one
source or split between the two; the default, the index's quote unit, to the last bit; indexes
that quote in cents a pound, dollars a tonne, cents a gallon and dollars per MMBTU; the
lifecycle, a strip, a pair and a closed physical contract; and what is refused, by the field
and the row. Every expected number is the issue's or hand arithmetic here; the production code
is never asked for one."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pytest
from holiday_fixtures import a_name, closed_on, index_on
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import (
    a_template,
    a_ticket,
    key_of,
    seam_calendars,
    seam_key,
    the_calendars,
)
from test_trades import dates, day, history_on, numbers, quoted
from test_two_index import (
    AS_OF,
    CLOSE,
    PAY,
    PAYS,
    PID,
    SEAM,
    SOFR,
    A,
    B,
    across,
    cell,
    close,
    down,
    grid,
    read,
    serial,
    spilled,
    under,
)
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
MONEY, PER = "fixed_price_currency_unit", "fixed_price_quantity_unit"
# A row as a test writes it: quantity, quantity_unit, fixed_price and the price's unit, its
# currency unit and the quantity unit it is per, the last None on every row for a ticket
# without the two columns.
Unit = tuple[str, str]
Row = tuple[float, str, float, Unit | None]
A_ROW: Row = (LB_PER_MT, "LB", 0.20, ("DOLLAR", "LB"))
B_ROW: Row = (1.0, "MT", 0.20 * LB_PER_MT, ("DOLLAR", "MT"))
C_ROW: Row = (1.0, "MT", 20.0, ("CENT", "LB"))
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
    units = [unit for _, _, _, unit in rows if unit is not None]
    if units:
        columns[MONEY] = [money for money, _ in units]
        columns[PER] = [per for _, per in units]
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
    assert [terms.price_units[int(i)] for i in terms.price_unit] == [
        PriceUnit("DOLLAR", "LB"),
        PriceUnit("DOLLAR", "MT"),
        PriceUnit("CENT", "LB"),
    ]
    assert len(terms.price_units) == 3  # the pairs the rows hold: no cents a tonne among them
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
    sold_b: Row = (-1.0, "MT", 0.20 * LB_PER_MT, ("DOLLAR", "MT"))
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
    batch = booked((50.0, "MT", 1870.0, ("DOLLAR", "MT")))
    assert fixed_legs(batch) == [93_500.0]
    assert batch.resolved.price.tolist() == [1870.0]
    assert batch.encoded.legs[0].coefficient.tolist() == pytest.approx([50 * LB_PER_MT], **CLOSE)


def test_the_quantity_word_does_not_choose_the_prices_unit() -> None:
    # Tonnes priced per pound and lots priced per tonne: neither price is per the word the
    # quantity was entered in. Two lots are 110,232 pounds, 50.0004 tonnes.
    # 50 tonnes are 110,231.13 pounds, at 0.91 dollars: 100,310.33.
    tonnes_at_cents_a_pound = booked((50.0, "MT", 91.0, ("CENT", "LB")))
    assert fixed_legs(tonnes_at_cents_a_pound) == pytest.approx([50 * LB_PER_MT * 0.91], **CLOSE)
    assert fixed_legs(tonnes_at_cents_a_pound) == pytest.approx([100_310.3292941193], rel=1e-12)
    # 110,232 pounds are 50.0004 tonnes, at 1,870 dollars: 93,500.74.
    lots_at_a_tonne_price = booked((2.0, "LOT", 1870.0, ("DOLLAR", "MT")))
    assert fixed_legs(lots_at_a_tonne_price) == pytest.approx(
        [2 * 55_116 / LB_PER_MT * 1870.0], **CLOSE
    )
    assert fixed_legs(lots_at_a_tonne_price) == pytest.approx([93_500.7370228008], rel=1e-12)
    # And a tonne quantity with no unit typed is priced per pound, the index's own: the trap the
    # field removes, a tonne price read as dollars a pound.
    misread = booked((50.0, "MT", 1870.0, None))
    assert fixed_legs(misread) == pytest.approx([50 * LB_PER_MT * 1870.0], **CLOSE)


# --- the two fields, each from the template or the ticket -----------------------------------------

TONNE = {MONEY: "DOLLAR", PER: "MT"}  # dollars a tonne, as a template's two values


def test_a_unit_from_the_template_is_every_rows_and_prices_as_the_columns_do() -> None:
    rows: tuple[Row, ...] = ((50.0, "MT", 1870.0, None), (2.0, "LOT", 1900.0, None))
    by_template = booked(*rows, template={**BILATERAL, **TONNE})
    by_column = booked(*[(q, word, price, ("DOLLAR", "MT")) for q, word, price, _ in rows])
    assert by_template.resolved.price_units == (PriceUnit("DOLLAR", "MT"),)
    assert by_template.resolved.price_unit.tolist() == [0, 0]
    np.testing.assert_array_equal(by_template.encoded.offset, by_column.encoded.offset)
    assert valued(by_template).mark == valued(by_column).mark


def test_the_currency_on_the_template_and_the_quantity_unit_down_the_ticket() -> None:
    # The issue's A and B with DOLLAR once on the template and LB and MT on the rows: the batch
    # both fields typed on every row make, to the last bit.
    all_ticket = booked(A_ROW, B_ROW)
    plain = ticket((A_ROW[0], "LB", A_ROW[2], None), (B_ROW[0], "MT", B_ROW[2], None))
    split = made({**plain, PER: ["LB", "MT"]}, {**BILATERAL, MONEY: "DOLLAR"})
    assert [split.resolved.price_units[int(i)] for i in split.resolved.price_unit] == [
        PriceUnit("DOLLAR", "LB"),
        PriceUnit("DOLLAR", "MT"),
    ]
    np.testing.assert_array_equal(split.encoded.offset, all_ticket.encoded.offset)
    one, other = valued(split), valued(all_ticket)
    assert (one.mark, one.dv01) == (other.mark, other.dv01)
    close(one.payment_amount, [2 * NET])
    # And the other way round, the tonne on the template and the money down the ticket: a tonne
    # at 440.92 dollars and at 44,092 cents.
    turned = made(
        {
            **ticket((1.0, "MT", 0.20 * LB_PER_MT, None), (1.0, "MT", 20.0 * LB_PER_MT, None)),
            MONEY: ["DOLLAR", "CENT"],
        },
        {**BILATERAL, PER: "MT"},
    )
    assert fixed_legs(turned) == pytest.approx([FIXED, FIXED], **CLOSE)


@pytest.mark.parametrize("field", [MONEY, PER])
def test_a_field_from_the_template_and_the_ticket_is_refused_by_its_own_name(field: str) -> None:
    with pytest.raises(ValueError) as both:
        booked((50.0, "MT", 1870.0, ("DOLLAR", "MT")), template={**BILATERAL, field: TONNE[field]})
    assert str(both.value) == (
        f"{field} is supplied by the template and by the ticket, expected by one of them"
    )


@pytest.mark.parametrize(("held", "missing"), [(MONEY, PER), (PER, MONEY)])
def test_one_field_without_the_other_is_refused_by_the_one_to_supply(
    held: str, missing: str
) -> None:
    words = (
        f"{missing} is missing, expected a value in the template or a column in the ticket "
        f"beside {held}; a fixed price's unit is both fields, or neither for the index's quote "
        "units"
    )
    plain = ticket((50.0, "MT", 1870.0, None), (2.0, "LOT", 1900.0, None))
    # A template may hold one of the two, since a ticket may hold the other: it is made, and
    # the batch whose ticket does not is refused.
    half = {**BILATERAL, held: TONNE[held]}
    assert held in a_template(half).names
    one_column: dict[str, list[object]] = {**plain, held: [TONNE[held]] * 2}
    for columns, template in ((plain, half), (one_column, BILATERAL)):
        with pytest.raises(ValueError) as refusal:
            made(columns, template)
        assert str(refusal.value) == words
    # The same half completed by the ticket is a batch.
    whole = made({**plain, missing: [TONNE[missing]] * 2}, half)
    assert whole.resolved.price_units == (PriceUnit("DOLLAR", "MT"),)


# --- the default: the unit the index quotes in ----------------------------------------------------


def test_no_unit_typed_is_the_indexes_quote_unit_to_the_last_bit() -> None:
    rows: tuple[Row, ...] = (
        (LB_PER_MT, "LB", 0.20, None),
        (3.0, "MT", 0.91, None),
        (-2.0, "LOT", 0.905, None),
        (0.0, "MT", 0.91, None),  # a zero row, kept ready
    )
    omitted = booked(*rows)
    typed = booked(*[(q, word, price, ("DOLLAR", "LB")) for q, word, price, _ in rows])
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
        (LB_PER_MT, "LB", 0.20, ("DOLLAR", "LB")),
        (50.0, "MT", 1870.0, ("DOLLAR", "MT")),
        (2.0, "LOT", 0.905, ("DOLLAR", "LB")),
        (7.5, "MT", 0.91, ("DOLLAR", "LB")),
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
    for row in ((1.0, "LOT", 84.0, ("DOLLAR", "BBL")), (1_000.0, "BBL", 200.0, ("CENT", "GAL"))):
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
    assert fixed_legs(booked((1.0, "LOT", 30.0, ("CENT", "THERM")), index=GAS)) == pytest.approx(
        [30_000.0], **CLOSE
    )
    assert fixed_legs(booked((1.0, "LOT", 3.0, ("DOLLAR", "MMBTU")), index=GAS)) == [30_000.0]
    assert refused((1.0, "LOT", 10.0, ("DOLLAR", "MWH")), index=GAS) == (
        "fixed_price_quantity_unit of trade 1 at row 1 is 'MWH', expected a unit of heat as the "
        "index quotes in, MMBTU, BTU, THERM or GJ; a price of power against fuel is struck at a "
        "heat rate, which is not built"
    )
    # 400 MWh at 4 cents a kilowatt hour: 400,000 kWh at 0.04, 16,000 dollars.
    assert fixed_legs(booked((1.0, "LOT", 4.0, ("CENT", "KWH")), index=POWER)) == pytest.approx(
        [16_000.0], **CLOSE
    )
    assert refused((1.0, "LOT", 3.0, ("DOLLAR", "MMBTU")), index=POWER) == (
        "fixed_price_quantity_unit of trade 1 at row 1 is 'MMBTU', expected a unit of "
        "electricity as the index quotes in, MWH or KWH; a price of power against fuel is "
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
    one = booked((quantity, "MT", price, (money, per)))
    other = booked((quantity, "MT", restated, (other_money, other_per)))
    np.testing.assert_allclose(one.encoded.offset, other.encoded.offset, rtol=1e-12, atol=1e-300)
    # And the floating side never moves with the price's unit.
    np.testing.assert_array_equal(
        one.encoded.legs[0].coefficient, other.encoded.legs[0].coefficient
    )


# --- signs and zeros ------------------------------------------------------------------------------


def test_negative_and_zero_prices_and_quantities_are_booked_as_they_always_were() -> None:
    batch = booked(
        (50.0, "MT", -12.5, ("DOLLAR", "MT")),  # a negative price: the fixed leg is received
        (50.0, "MT", 0.0, ("DOLLAR", "MT")),
        (-50.0, "MT", 1870.0, ("DOLLAR", "MT")),  # sold
        (0.0, "MT", 1870.0, ("DOLLAR", "MT")),
    )
    assert batch.encoded.offset.tolist() == [625.0, -0.0, 93_500.0, -0.0]
    # A zero row is kept ready, and its unit is read like any other row's.
    assert refused((0.0, "MT", 1870.0, ("DOLLAR", "BBL"))).startswith(
        "fixed_price_quantity_unit of trade 1 at row 1 is 'BBL', expected a MASS unit"
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
        (50.0, "MT", 1870.0, ("DOLLAR", "MT")), (1.0, "LOT", 0.91, ("DOLLAR", "LB")), code="G27-H27"
    )
    assert strip.resolved.occurrence.tolist() == [0, 0, 1, 1]
    assert fixed_legs(strip) == pytest.approx(
        [93_500.0, 93_500.0, 55_116 * 0.91, 55_116 * 0.91], **CLOSE
    )
    # Per calendar day: 2 tonnes a day over February's 28 days at 1,870 a tonne.
    daily = booked(
        (2.0, "MT", 1870.0, ("DOLLAR", "MT")),
        template={**BILATERAL, "quantity_per": "calday"},
        code="G27",
    )
    assert fixed_legs(daily) == [2.0 * 28 * 1870.0]
    # A part of a month, under asian: 14 to 20 February, one component, the row's quantity.
    part = made(
        {
            **{
                k: v
                for k, v in ticket((3.0, "MT", 1870.0, ("DOLLAR", "MT"))).items()
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
        PAIR_BILATERAL,
        {**PAIR_TICKET, "fixed_price": [30.0], MONEY: ["CENT"], PER: ["THERM"]},
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
    rows: tuple[Row, ...] = (
        (50.0, "MT", 1870.0, ("DOLLAR", "MT")),
        (2.0, "LOT", 1880.0, ("DOLLAR", "MT")),
    )
    restated = [(q, word, price / LB_PER_MT, ("DOLLAR", "LB")) for q, word, price, _ in rows]
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
        (3.0, "MT", 1870.0, ("DOLLAR", "MT")),
        (-3.0, "MT", 90.0, ("CENT", "LB")),
        template=physical,
        code="F27",
    )
    assert flat.encoded.closed is not None and flat.encoded.closed.tolist() == [True]
    results = valued(flat, as_of="2027-01-04", curve=None, finals={"F27": 0.93})
    assert results.cash == pytest.approx(3 * LB_PER_MT * 0.90 - 3 * 1870.0, **CLOSE)
    assert results.mark == 0.0
    left_open = booked(
        (3.0, "MT", 1870.0, ("DOLLAR", "MT")),
        (-2.0, "MT", 90.0, ("CENT", "LB")),
        template=physical,
        code="F27",
    )
    with pytest.raises(ValueError, match="a physical position open past its expiry"):
        valued(left_open, as_of="2027-01-04", curve=None, finals={"F27": 0.93})


# --- what is refused ------------------------------------------------------------------------------

MONEY_UNITS = "DOLLAR or CENT"
MASS_UNITS = "a MASS unit, KG, LB, MT, ST, LT, G, OZT or CWT_US"


@pytest.mark.parametrize(
    ("unit", "field", "expected"),
    [
        (("USD", "MT"), MONEY, MONEY_UNITS),  # the currency's name is no unit of it
        (("dollar", "MT"), MONEY, MONEY_UNITS),
        ((" DOLLAR", "MT"), MONEY, MONEY_UNITS),
        (("DOLLAR ", "MT"), MONEY, MONEY_UNITS),
        (("MT", "DOLLAR"), MONEY, MONEY_UNITS),  # the two the wrong way round
        (("DOLLAR/MT", "MT"), MONEY, MONEY_UNITS),  # a unit with a slash is no code
        (("USD", "BBL"), MONEY, MONEY_UNITS),  # both wrong: the currency unit is read first
        (("DOLLAR", "mt"), PER, MASS_UNITS),
        (("DOLLAR", " MT"), PER, MASS_UNITS),
        (("DOLLAR", "MT "), PER, MASS_UNITS),
        (("DOLLAR", "BBL"), PER, MASS_UNITS),  # a volume under a mass index: a density
        (("DOLLAR", "MMBTU"), PER, MASS_UNITS),
        (("DOLLAR", "LOT"), PER, MASS_UNITS),  # the desk's word for a specification is no unit
        (("DOLLAR", "TONNE"), PER, MASS_UNITS),
        (("DOLLAR", "DOLLAR/MT"), PER, MASS_UNITS),
    ],
)
def test_a_code_the_tables_do_not_hold_for_the_index_is_refused_by_its_field_and_trade(
    unit: Unit, field: str, expected: str
) -> None:
    good: Row = (1.0, "MT", 1870.0, ("DOLLAR", "MT"))
    code = unit[(MONEY, PER).index(field)]
    assert refused(good, (1.0, "MT", 1870.0, unit)) == (
        f"{field} of trade 2 at row 2 is {code!r}, expected {expected}"
    )
    # A template's unit is every row's: the template is made, no table being at hand to read a
    # code by, and the batch is refused naming the first row's trade.
    by_template = {**BILATERAL, MONEY: unit[0], PER: unit[1]}
    assert (
        refused((1.0, "MT", 1870.0, None), template=by_template)
        == f"{field} of trade 1 at row 1 is {code!r}, expected {expected}"
    )


def test_the_first_row_from_the_top_with_a_bad_unit_is_the_one_named() -> None:
    good: Row = (1.0, "MT", 1870.0, ("DOLLAR", "MT"))
    # ZZ at row 2 and AA at row 3: row 2, whichever text sorts first, and whichever of the two
    # fields the row below it breaks.
    for below in (("DOLLAR", "AA"), ("AA", "MT")):
        assert refused(good, (1.0, "MT", 1.0, ("DOLLAR", "ZZ")), (1.0, "MT", 1.0, below)) == (
            f"{PER} of trade 2 at row 2 is 'ZZ', expected {MASS_UNITS}"
        )
    assert refused(good, (1.0, "MT", 1.0, ("ZZ", "MT")), (1.0, "MT", 1.0, ("DOLLAR", "AA"))) == (
        f"{MONEY} of trade 2 at row 2 is 'ZZ', expected {MONEY_UNITS}"
    )


def test_a_supplied_column_never_falls_back_to_the_default_on_a_row() -> None:
    # A column on the ticket holds a code on every row. A blank cell and an empty text never
    # reach the library: the seam refuses each for a field whose cells must hold a value, as it
    # does for any field but the three of a period.
    for name in (MONEY, PER):
        field = next(field for field in FIXED_FLOAT.fields if field.name == name)
        assert not field.may_be_unsupplied
    count = bridge.entry("CountFieldRows")
    headers = Cells.from_rows([["quantity", MONEY, PER]])
    whole: list[list[object]] = [[1.0, "DOLLAR", "MT"], [2.0, "CENT", "LB"]]
    assert count("fixed_float", headers, Cells.from_rows(whole)) == 2.0
    for column in (2, 3):
        for held, words in ((None, "blank"), ("", "empty text")):
            second = list(whole[1])
            second[column - 1] = held
            assert count("fixed_float", headers, Cells.from_rows([whole[0], second])) == (
                f"#ERROR CountFieldRows: rows cell (2, {column}) is {words}, expected text"
            )


def test_a_conversion_or_a_fixed_leg_past_the_largest_number_is_refused_by_its_trade() -> None:
    # On an index quoted per tonne, 1e306 tonnes is a quantity the floating side holds, and a
    # million times as many grams is not: the fixed price's own coefficient outruns.
    tonnes = an_index("MWT", ("DOLLAR", "MT"))
    assert refused((1e306, "MT", 1.0, ("DOLLAR", "G")), index=tonnes) == (
        "trade 1 at row 1 has inf of fixed coefficient, expected a finite amount of DOLLAR per "
        "DOLLAR/G; its count times its specification's size in the fixed price's unit and the "
        "currency factor outruns the largest number"
    )
    # And a coefficient that stands times a price too large is the fixed leg's, as before.
    assert refused((1e300, "MT", 1e10, ("DOLLAR", "MT")), index=tonnes) == (
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


# --- the readback ---------------------------------------------------------------------------------
# The sheet's example, the owner's premium: a market of 0.95 dollars a pound, and four rows on
# one contract, each its own quantity word and its own price unit.

SHEET_ROWS: tuple[Row, ...] = (
    (50.0, "MT", 1870.0, ("DOLLAR", "MT")),
    (275_578.0, "LB", 0.91, ("DOLLAR", "LB")),
    (2.0, "LOT", 1870.0, ("DOLLAR", "MT")),
    (50.0, "MT", 91.0, ("CENT", "LB")),
)
SHEET_UNITS: list[tuple[object, object]] = [
    ("DOLLAR", "MT"),
    ("DOLLAR", "LB"),
    ("DOLLAR", "MT"),
    ("CENT", "LB"),
]
# Each row's fixed leg by hand: 50 x 1,870; 275,578 x 0.91; 110,232 lb as tonnes x 1,870; and
# 50 tonnes as pounds x 0.91.
SHEET_FIXED = [93_500.0, 250_775.98, 93_500.7370228008, 100_310.3292941193]
# Against 0.95 a pound the four pay 11,219.57, 11,023.12, 11,219.66 and 4,409.25.
SHEET_PAYMENT = 37_871.60275871356


def units_of(table: list[list[object]]) -> list[tuple[object, object]]:
    """Each component's fixed price's unit as a readback shows it, under the two fields."""
    return list(zip(under(table, MONEY), under(table, PER), strict=True))


def test_the_readback_shows_each_price_as_entered_with_its_unit_in_the_last_columns() -> None:
    table = grid(booked(*SHEET_ROWS))
    # The two fields last, in the definition's order, and no column before them moved.
    assert table[0][-3:] == ["payment_holiday_key", MONEY, PER]
    assert table[1][-2:] == ["str", "str"]
    assert units_of(table) == SHEET_UNITS
    assert under(table, "fixed_price") == [1870.0, 0.91, 1870.0, 91.0]  # as entered
    assert under(table, "quantity_unit") == ["MT", "LB", "LOT", "MT"]
    assert [-float(str(each)) for each in under(table, "offset")] == pytest.approx(
        SHEET_FIXED, rel=1e-12
    )
    # The floating side is the index's own whatever the price's unit: pounds, 0.95 away from
    # dollars.
    assert under(table, "quote_quantity") == pytest.approx(
        [50 * LB_PER_MT, 275_578.0, 110_232.0, 50 * LB_PER_MT], **CLOSE
    )


def test_the_readback_says_the_indexes_unit_where_none_was_typed() -> None:
    # The price never stands without its unit: no column and no template value, and the
    # readback shows the two units the index quotes in on every row.
    table = grid(booked(*[(q, word, price, None) for q, word, price, _ in SHEET_ROWS]))
    assert table[0][-2:] == [MONEY, PER]
    assert units_of(table) == [("DOLLAR", "LB")] * 4
    cents = an_index("MWC", ("CENT", "LB"))
    assert units_of(grid(booked((1.0, "MT", 20.0, None), index=cents))) == [("CENT", "LB")]
    # A template's unit is every row's, and a strip carries its row's unit to each month.
    by_template = grid(
        booked((50.0, "MT", 1870.0, None), template={**BILATERAL, **TONNE}, code="G27-H27")
    )
    assert units_of(by_template) == [("DOLLAR", "MT")] * 2
    # So does a strip whose rows take the money from the template and the rest from the ticket.
    split = grid(
        made(
            {
                **ticket((50.0, "MT", 1870.0, None), (2.0, "LOT", 0.91, None), code="G27-H27"),
                PER: ["MT", "LB"],
            },
            {**BILATERAL, MONEY: "DOLLAR"},
        )
    )
    assert units_of(split) == [("DOLLAR", "MT")] * 2 + [("DOLLAR", "LB")] * 2
    # A physical batch has no payment key before them; the unit is still the last two columns.
    physical = {
        k: v
        for k, v in {**CLEARED, "settlement_method": "physical"}.items()
        if not k.startswith("payment_")
    }
    table = grid(booked((3.0, "MT", 1870.0, ("DOLLAR", "MT")), template=physical))
    assert table[0][-3:] == ["nearby", MONEY, PER]
    assert units_of(table) == [("DOLLAR", "MT")]


def test_a_pairs_readback_shows_its_outright_prices_unit() -> None:
    typed = grid(
        booked_pair(
            PAIR_BILATERAL,
            {**PAIR_TICKET, "fixed_price": [30.0], MONEY: ["CENT"], PER: ["THERM"]},
        )
    )
    assert cell(typed, 0, "fixed_price") == 30.0 and typed[0][-2:] == [MONEY, PER]
    assert units_of(typed) == [("CENT", "THERM")]
    assert units_of(grid(booked_pair())) == [("DOLLAR", "MMBTU")]


# --- on the sheet ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The premium on a sheet: an index quoted in dollars a pound over F27, G27 and H27, with a
    lot of 55,116 pounds, a pound and a tonne, its delta in lots; valued on 4 January 2027 with
    G27 at 0.95; a cleared template that leaves the quantity unit to each row."""
    holidays = SEAM["_CreateHolidayCalendar"](a_name(), serial("2027-01-01"))
    index = SEAM["_CreateIndex"](
        "AUP",
        "A sample aluminium premium, dollars a pound",
        SEAM["_CreateFuturesSchedule"](
            down("F27", "G27", "H27"),
            down(serial("2026-12-29"), serial("2027-01-27"), serial("2027-02-24")),
            bridge.MISSING,
        ),
        SEAM["_CreateIndexConventions"]("DOLLAR", "LB", "DOLLAR", "MASS", "LB"),
        SEAM["_CreateContractSpecifications"](
            across(
                "name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"
            ),
            Cells.from_rows(
                [
                    ["lots", 55116.0, "LB", 0.0, 0.0],
                    ["lb", 1.0, "LB", 0.0, 0.0],
                    ["mt", 1.0, "MT", 0.0, 0.0],
                ]
            ),
        ),
        seam_key(holidays),
        "lots",
        seam_calendars(),
    )
    history = SEAM["_CreateMarketHistory"](
        SEAM["_CreateCalendar"](SEAM["_CreateValuationDate"](serial(AS_OF), 0.5), index),
        SEAM["_CreateFuturesFixings"](
            down(serial("2026-12-31"), serial("2026-12-30")), down(0.93, 0.92), index
        ),
    )
    fields = (
        "quantity_per",
        "settlement_frequency",
        "nearby",
        "schedule_method",
        "route",
        "settlement_method",
        "clearing_house",
        "payment_day",
        "payment_holiday_key",
    )
    values = ("month", "monthly", 1.0, "lastday", "cleared", "financial", "CME Clearing", "+2bd")
    names = ("trade_id", "trade_date", "contract_code", "quantity", "quantity_unit", "fixed_price")
    return {
        "index": index,
        "history": history,
        "market": SEAM["_CreateMarket"](
            history, SEAM["_CreatePriceVector"]("AUP", down(0.95, 0.96))
        ),
        "fields": fields,
        "values": (*values, seam_key(holidays)),
        "template": SEAM["_CreateTradeTemplate"](
            "fixed_float", across(*fields), across(*values, seam_key(holidays))
        ),
        "names": names,
        "headers": across(*names),
        "unit_headers": across(*names, MONEY, PER),
    }


def sheet_rows(*rows: tuple[object, ...]) -> Cells:
    """Ticket rows on G27 as the sheet holds them: each row's quantity, quantity unit and fixed
    price, then whatever cells of the price's unit its ticket has columns for."""
    return Cells.from_rows(
        [[float(i + 1), serial("2026-12-15"), "G27", *row] for i, row in enumerate(rows)]
    )


SHEET_WORDS = {"MT": "mt", "LB": "lb", "LOT": "lots"}
ON_SHEET = tuple(
    (q, SHEET_WORDS[word], price, *unit)
    for (q, word, price, _), unit in zip(SHEET_ROWS, SHEET_UNITS, strict=True)
)
PARTIAL = (
    "fixed_price_quantity_unit is missing, expected a value in the template or a column in the "
    "ticket beside fixed_price_currency_unit; a fixed price's unit is both fields, or neither "
    "for the index's quote units"
)


def test_the_sheet_books_mixed_units_values_them_and_reads_them_back(
    sheet: dict[str, Any],
) -> None:
    batch = SEAM["_CreateTrades"](
        sheet["index"], sheet["unit_headers"], sheet_rows(*ON_SHEET), sheet["template"]
    )
    assert re.fullmatch(rf"{PID}:trades:AUP:\d+", str(batch))
    table = read(batch)
    assert table[0][-2:] == [MONEY, PER] and table[1][-2:] == ["str", "str"]
    assert units_of(table) == SHEET_UNITS
    assert under(table, "fixed_price") == [1870.0, 0.91, 1870.0, 91.0]
    assert [-float(str(each)) for each in under(table, "offset")] == pytest.approx(
        SHEET_FIXED, rel=1e-12
    )
    results = SEAM["_EvaluateTrades"](
        SEAM["_PrepareTrades"](batch, sheet["history"]), sheet["market"], bridge.MISSING
    )
    assert re.fullmatch(rf"{PID}:trade_results:AUP:\d+", str(results)), results
    values = spilled(SEAM["_ReportValues"](results))
    assert values[0][0] == "cleared_mark"
    assert values[2][0] == pytest.approx(SHEET_PAYMENT, rel=1e-12) and values[2][1] == 0.0
    risk = spilled(SEAM["_ReportRisk"](results, "nominal_delta", "year"))
    # 606,272.26 pounds in lots of 55,116: a shade under eleven.
    assert risk[-1][-1] == pytest.approx(10.999932182757778, rel=1e-12)


def test_the_sheet_reads_the_default_and_a_templates_unit(sheet: dict[str, Any]) -> None:
    # No column and no template value: every price in the index's unit, and the readback says so.
    rows = sheet_rows((275_578.0, "lb", 0.91))
    plain = read(SEAM["_CreateTrades"](sheet["index"], sheet["headers"], rows, sheet["template"]))
    assert units_of(plain) == [("DOLLAR", "LB")]
    assert under(plain, "offset") == [-250_775.98]
    # The template's unit, every row's.
    tonne_template = SEAM["_CreateTradeTemplate"](
        "fixed_float",
        across(*sheet["fields"], MONEY, PER),
        across(*sheet["values"], "DOLLAR", "MT"),
    )
    rows = sheet_rows((50.0, "mt", 1870.0))
    priced = read(SEAM["_CreateTrades"](sheet["index"], sheet["headers"], rows, tonne_template))
    assert units_of(priced) == [("DOLLAR", "MT")]
    assert under(priced, "offset") == [-93_500.0]
    # And never both, each field refused by its own name.
    assert SEAM["_CreateTrades"](
        sheet["index"],
        sheet["unit_headers"],
        sheet_rows((50.0, "mt", 1870.0, "DOLLAR", "MT")),
        tonne_template,
    ) == (
        "#ERROR _CreateTrades: ValueError: fixed_price_currency_unit is supplied by the template "
        "and by the ticket, expected by one of them"
    )


def test_the_sheet_takes_the_money_from_the_template_and_the_rest_from_the_ticket(
    sheet: dict[str, Any],
) -> None:
    # Dollars once, on the template, and the tonne and the pound down the ticket: the first two
    # rows of the mixed batch, to the cent.
    dollars = SEAM["_CreateTradeTemplate"](
        "fixed_float", across(*sheet["fields"], MONEY), across(*sheet["values"], "DOLLAR")
    )
    assert spilled(SEAM["util_ReadHandle"](dollars))[0][-1] == MONEY  # the half it holds
    rows = sheet_rows((50.0, "mt", 1870.0, "MT"), (275_578.0, "lb", 0.91, "LB"))
    split = read(SEAM["_CreateTrades"](sheet["index"], across(*sheet["names"], PER), rows, dollars))
    assert units_of(split) == SHEET_UNITS[:2]
    assert [-float(str(each)) for each in under(split, "offset")] == SHEET_FIXED[:2]
    # The template's half with no other half on the ticket is refused by the field to supply.
    rows = sheet_rows((50.0, "mt", 1870.0))
    assert (
        SEAM["_CreateTrades"](sheet["index"], sheet["headers"], rows, dollars)
        == f"#ERROR _CreateTrades: ValueError: {PARTIAL}"
    )


MASS_ON_SHEET = "expected a MASS unit, KG, LB, MT, ST, LT, G, OZT or CWT_US"
SHEET_REFUSALS: list[tuple[object, object, str]] = [
    (
        "USD",
        "MT",
        f"ValueError: {MONEY} of trade 2 at row 2 is 'USD', expected DOLLAR or CENT",
    ),
    (
        "DOLLAR/MT",  # a unit with a slash is no code
        "MT",
        f"ValueError: {MONEY} of trade 2 at row 2 is 'DOLLAR/MT', expected DOLLAR or CENT",
    ),
    ("DOLLAR", "BBL", f"ValueError: {PER} of trade 2 at row 2 is 'BBL', {MASS_ON_SHEET}"),
    (
        "DOLLAR",
        "lots",  # the row's own quantity word is a specification and no unit
        f"ValueError: {PER} of trade 2 at row 2 is 'lots', {MASS_ON_SHEET}",
    ),
    (None, "MT", "trade_rows cell (2, 7) is blank, expected text"),
    ("", "MT", "trade_rows cell (2, 7) is empty text, expected text"),
    ("DOLLAR", None, "trade_rows cell (2, 8) is blank, expected text"),
    ("DOLLAR", "", "trade_rows cell (2, 8) is empty text, expected text"),
    ("DOLLAR", 1870.0, "trade_rows cell (2, 8) is number 1870.0, expected text"),
]


@pytest.mark.parametrize(
    ("money", "per", "words"), SHEET_REFUSALS, ids=[repr(case[:2]) for case in SHEET_REFUSALS]
)
def test_the_sheet_refuses_a_unit_by_its_field_and_row_in_the_librarys_words_or_the_seams(
    sheet: dict[str, Any], money: object, per: object, words: str
) -> None:
    rows = sheet_rows((50.0, "mt", 1870.0, "DOLLAR", "MT"), (2.0, "lots", 1870.0, money, per))
    assert (
        SEAM["_CreateTrades"](sheet["index"], sheet["unit_headers"], rows, sheet["template"])
        == f"#ERROR _CreateTrades: {words}"
    )


def test_the_sheet_refuses_the_one_cell_field_and_a_spread_the_two(sheet: dict[str, Any]) -> None:
    # fixed_price_unit, one cell with a slash, is no field of the instrument: a template's row
    # and a ticket's column of that name are each refused as any unknown field is. A spread has
    # its own two unit fields and takes neither of a fixed price's.
    for instrument, field in (
        ("fixed_float", "fixed_price_unit"),
        ("float_float", MONEY),
        ("float_float", PER),
    ):
        refusal = str(SEAM["_CreateTradeTemplate"](instrument, across(field), across("DOLLAR")))
        assert refusal.startswith(
            f"#ERROR _CreateTradeTemplate: fields cell (1, 1) is text {field!r}, expected a "
            f"field of {instrument}: "
        )
    refusal = str(
        SEAM["_CreateTrades"](
            sheet["index"],
            across(*sheet["names"], "fixed_price_unit"),
            sheet_rows((50.0, "mt", 1870.0, "DOLLAR/MT")),
            sheet["template"],
        )
    )
    assert refusal.startswith(
        "#ERROR _CreateTrades: fields cell (1, 7) is text 'fixed_price_unit', expected a field "
        "of fixed_float: "
    )
