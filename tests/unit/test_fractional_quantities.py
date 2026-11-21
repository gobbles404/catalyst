"""A financially settled trade takes a fractional quantity, fractional-quantities.md: the
ticket's worked example by hand, a bilateral crude swap of a lot and a half, from the template and
from a ticket row, at 1.5 and at -0.25; a fraction under each quantity basis on each shape that
books it, a fixed_float on one index and on two and a float_float; a cleared row; the reserves; a
physical row whole as it always was and a number that is not finite refused under either
settlement; the rule waiting for the ticket's settlement method where the template gives the
quantity alone; and a fraction through the seam. Every expected number is hand arithmetic here;
the production code is never asked for an expected answer.
docs/library/trades/create-trades.md is the page."""

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import (
    NG,
    NG_TEMPLATE,
    NG_TICKET,
    a_template,
    an_index,
    created,
    key_of,
    refused,
)
from test_float_float import BILATERAL as SPREAD
from test_float_float import TICKET as SPREAD_TICKET
from test_float_float import booked as booked_spread
from test_float_float import refused as refused_spread
from test_float_float import valued as valued_spread
from test_onetime_average import CL, TMA_TEMPLATE, TMA_TICKET, deltas, valued_on
from test_trades import day, history_on, quoted
from test_two_index import BILATERAL as PAIR
from test_two_index import (
    CLOSE,
    SEAM,
    across,
    cell,
    close,
    down,
    futures,
    grid,
    read,
    serial,
    spilled,
    the_sheet,
    under,
)
from test_two_index import TICKET as PAIR_TICKET
from test_two_index import booked as booked_pair
from test_two_index import refused as refused_pair
from test_two_index import valued as valued_pair

from catalyst.globals.discount_curve import DiscountCurve
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades
from catalyst.trades.results import TradeResults

# --- the worked example --------------------------------------------------------------------------
# OIL: a futures index quoted in dollars a barrel, its one specification a LOT of 1,000 BBL, the
# lot reported; G27 expiring 20 January 2027, so on 4 January its one lastday observation is live.
# The market quotes G27 at 70.00. A bilateral swap bought at 68.00 pays once, on 4 January 2028,
# 365 days on, a year under ACT/365F, where SOFR's factor is 0.95.

AS_OF, PAY = "2027-01-04", "2028-01-04"
SOFR = curve_of((AS_OF, 1.0), (PAY, 0.95))
OIL = an_index(
    "OIL",
    (("Z26", "2026-11-20"), ("F27", "2026-12-21"), ("G27", "2027-01-20"), ("H27", "2027-02-22")),
    ("2027-01-01",),
    (("LOT", 1_000.0, "BBL"),),
    ("VOLUME", "BBL"),
)
SWAP: dict[str, object] = {
    "quantity_unit": "LOT",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "lastday",
    "route": "bilateral",
    "settlement_method": "financial",
    "counterparty": "ACME Trading",
    "discount_curve_key": "SOFR",
    "payment_day": day(PAY),
    "payment_calendar_key": key_of(OIL.holiday_calendar),
}
CLEARED: dict[str, object] = {
    **{k: v for k, v in SWAP.items() if k not in ("counterparty", "discount_curve_key")},
    "route": "cleared",
    "clearing_house": "ICE Clear Europe",
}
ROW: dict[str, list[object]] = {
    "trade_id": [1],
    "trade_date": ["2026-12-15"],
    "contract_code": ["G27"],
    "quantity": [1.5],
    "fixed_price": [68.0],
}
NO_QUANTITY: dict[str, list[object]] = {k: v for k, v in ROW.items() if k != "quantity"}


def swap(quantity: float, template: Mapping[str, object] = SWAP) -> Trades:
    """The example's row at that quantity, the quantity in the ticket."""
    batch, _ = created(OIL, {**ROW, "quantity": [quantity]}, template)
    return batch


def valued(batch: Trades, curve: DiscountCurve | None = SOFR) -> TradeResults:
    """A batch on OIL prepared and valued on the example's day, G27 quoted 70.00 and H27 70.50,
    against SOFR, or against no curve where the batch is cleared."""
    history = history_on(OIL, AS_OF, {})
    prepared = prepared_trades(batch.encoded, (history,), WorkCounter())
    return trade_results(
        prepared,
        (quoted(history, 70.0, 70.5),),
        WorkCounter(),
        None if curve is None else curve_set(curve),
    )


def the_measures(results: TradeResults) -> tuple[float, float, float, float, float, float]:
    """The ticket's table: the net undiscounted amount, the NPV, the nominal and the discounted
    delta in lots, the curve's DV01 and the index's cross gamma against the curve."""
    assert results.payment_amount is not None
    (leg,) = results.legs
    return (
        float(results.payment_amount[0]),
        results.mark,
        leg.nominal_delta_total,
        leg.delta_total,
        results.dv01,
        leg.cross_gamma_total,
    )


# 1.5 lots of 1,000 BBL at 70.00 against 68.00: 1,500 x 2.00 = 3,000, at 0.95 an NPV of 2,850; the
# lots 1.5 and, discounted, 1.425; the DV01 one year x 2,850 x 0.0001 = 0.285, falling as rates
# rise; the cross gamma the discounted lots x one year x 0.0001 = 0.0001425, falling too.
AT_ONE_AND_A_HALF = (3_000.0, 2_850.0, 1.5, 1.425, -0.285, -0.0001425)
# The same row sold a quarter of a lot: each figure times -0.25 / 1.5, a sixth with the sign turned.
AT_A_QUARTER_SOLD = (-500.0, -475.0, -0.25, -0.2375, 0.0475, 0.00002375)


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [(1.5, AT_ONE_AND_A_HALF), (-0.25, AT_A_QUARTER_SOLD)],
    ids=["bought 1.5", "sold 0.25"],
)
def test_the_worked_example_by_hand_from_a_ticket_row_and_from_the_template(
    quantity: float, expected: tuple[float, ...]
) -> None:
    from_the_ticket = swap(quantity)
    from_the_template, _ = created(OIL, NO_QUANTITY, {**SWAP, "quantity": quantity})
    for batch in (from_the_ticket, from_the_template):
        assert the_measures(valued(batch)) == pytest.approx(expected, **CLOSE)
        # The quantity as entered, in the terms, in the encoding's exposure and on the readback.
        np.testing.assert_array_equal(batch.resolved.quantity, [quantity])
        close(batch.encoded.legs[0].slot_exposure, [quantity * 1_000.0])  # barrels
        assert cell(grid(batch), 0, "quantity") == quantity
    # Each figure is the quantity times the same trade at a quantity of one.
    one = the_measures(valued(swap(1.0)))
    assert one == pytest.approx((2_000.0, 1_900.0, 1.0, 0.95, -0.19, -0.000095), **CLOSE)
    assert expected == pytest.approx([quantity * figure for figure in one], **CLOSE)


def test_a_fraction_on_a_cleared_financial_row_books_and_values() -> None:
    # The example's row cleared: no curve, no rate risk, the mark the undiscounted 3,000 and the
    # delta the nominal lot and a half.
    batch = swap(1.5, CLEARED)
    results = valued(batch, None)
    (leg,) = results.legs
    assert (results.mark, results.dv01) == (3_000.0, 0.0)
    assert (leg.nominal_delta_total, leg.delta_total, leg.cross_gamma_total) == (1.5, 1.5, 0.0)
    assert results.payment_amount is None and results.curves == ()
    assert cell(grid(batch), 0, "quantity") == 1.5


@settings(max_examples=60, deadline=None)
@given(st.floats(min_value=-1e9, max_value=1e9, allow_nan=False))
def test_any_finite_quantity_is_kept_as_entered_and_scales_every_figure(quantity: float) -> None:
    # The general rule: nothing rounds, snaps or truncates a quantity, and a financial quantity
    # only ever multiplies, so the row at any quantity is that quantity times the row at one.
    batch = swap(quantity)
    np.testing.assert_array_equal(batch.resolved.quantity, [quantity])
    assert cell(grid(batch), 0, "quantity") == quantity
    figures = the_measures(valued(batch))
    at_one = (2_000.0, 1_900.0, 1.0, 0.95, -0.19, -0.000095)
    assert figures == pytest.approx([quantity * figure for figure in at_one], rel=1e-12, abs=1e-9)


def test_fractions_that_do_not_net_exactly_book_and_value_with_no_rule_for_the_residue() -> None:
    # 0.1 + 0.2 - 0.3 is not zero in binary, and nothing asks whether a financial position is
    # closed: three rows on one contract and one payment day are one group, each row as entered,
    # the group worth the residue's few thousandths of a billionth of a lot. A zero row beside
    # fractions is kept and adds nothing, as before.
    ticket: dict[str, list[object]] = {
        "trade_id": [1, 2, 3],
        "trade_date": ["2026-12-15"] * 3,
        "contract_code": ["G27"] * 3,
        "quantity": [0.1, 0.2, -0.3],
        "fixed_price": [68.0] * 3,
    }
    batch, _ = created(OIL, ticket, SWAP)
    assert under(grid(batch), "quantity") == [0.1, 0.2, -0.3]
    results = valued(batch)
    assert results.mark == pytest.approx(0.0, abs=1e-9)
    kept, _ = created(OIL, {**ticket, "quantity": [1.5, 0.0, -0.25]}, SWAP)
    assert under(grid(kept), "quantity") == [1.5, 0.0, -0.25]
    # 1.25 lots net: 1,250 BBL x 2.00 = 2,500, at 0.95 an NPV of 2,375.
    worth = valued(kept)
    close(worth.payment_amount, [2_500.0])
    assert worth.mark == pytest.approx(2_375.0, **CLOSE)
    assert worth.legs[0].nominal_delta_total == pytest.approx(1.25, **CLOSE)


# --- each quantity basis, on each shape that books it --------------------------------------------


def test_a_fraction_per_calendar_day_is_the_fraction_times_the_months_days() -> None:
    # 1.5 lots a day over February 2027, G27's month of 28 days: 42 lots, 42,000 BBL x 2.00 =
    # 84,000, at 0.95 an NPV of 79,800; DV01 7.98 and cross gamma 0.00399, both falling.
    batch = swap(1.5, {**SWAP, "quantity_per": "calday"})
    assert the_measures(valued(batch)) == pytest.approx(
        (84_000.0, 79_800.0, 42.0, 39.9, -7.98, -0.00399), **CLOSE
    )
    assert cell(grid(batch), 0, "quantity") == 1.5  # as entered, a day's worth


def test_a_fraction_for_a_whole_period_is_spread_over_its_pricing_days() -> None:
    # The WTI trade month of onetime-averaging.md at 1,000.5 barrels for the period, a barrel the
    # specification: with N26 at 70 and Q26 at 72 the average projects 70.2727 against 71, so
    # the mark is 1,000.5 x -8/11 = -727.64, and the barrels fall 19/22 to N26 and 3/22 to Q26.
    batch, _ = created(CL, {**TMA_TICKET, "quantity": [1_000.5]}, TMA_TEMPLATE)
    results = valued_on(batch, "2026-05-20", 70.0, 70.0, 72.0, 74.0)
    assert results.mark == pytest.approx(1_000.5 * -8 / 11, **CLOSE)
    assert deltas(results) == pytest.approx(
        {"N26": 1_000.5 * 19 / 22, "Q26": 1_000.5 * 3 / 22}, **CLOSE
    )
    np.testing.assert_allclose(batch.encoded.legs[0].slot_exposure, np.full(22, 1_000.5 / 22))
    assert cell(grid(batch), 0, "quantity") == 1_000.5


@pytest.mark.parametrize(
    ("per", "quantity", "payment", "lots_a", "lots_b"),
    [
        # 12,345.5 MMBTU at the outright 3.00 against 3.50 and -0.40, 3.10 together: 1,234.55;
        # 1.23455 of A's 10,000 MMBTU lots and 4.9382 of B's 2,500.
        ("month", 12_345.5, 1_234.55, 1.23455, 4.9382),
        # 100.5 MMBTU a day over February's 28 days, 2,814 MMBTU: 281.40; 0.2814 and 1.1256 lots.
        ("calday", 100.5, 281.40, 0.2814, 1.1256),
    ],
)
def test_a_fraction_on_two_indexes_at_one_price(
    per: str, quantity: float, payment: float, lots_a: float, lots_b: float
) -> None:
    batch = booked_pair({**PAIR, "quantity_per": per}, {**PAIR_TICKET, "quantity": [quantity]})
    results = valued_pair(batch)
    a, b = results.legs
    close(results.payment_amount, [payment])
    assert results.mark == pytest.approx(payment * 0.95, **CLOSE)
    assert results.dv01 == pytest.approx(-payment * 0.95 * 0.0001, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == pytest.approx(
        (lots_a, lots_b), **CLOSE
    )
    assert (a.delta_total, b.delta_total) == pytest.approx((lots_a * 0.95, lots_b * 0.95), **CLOSE)
    assert cell(grid(batch), 0, "quantity") == quantity


@pytest.mark.parametrize(
    ("per", "quantity", "payment", "lots"),
    [
        # 12,345.5 MMBTU of NTO at -0.25 less PAN at -0.40, 0.15 apart, against a spread price
        # of 0.10: 0.05 x 12,345.5 = 617.275; 4.9382 lots of 2,500 MMBTU received and as many paid.
        ("month", 12_345.5, 617.275, 4.9382),
        # 100.5 MMBTU a day over February's 28 days, 2,814 MMBTU: 140.70; 1.1256 lots a side.
        ("calday", 100.5, 140.70, 1.1256),
    ],
)
def test_a_fraction_on_a_float_float_spread(
    per: str, quantity: float, payment: float, lots: float
) -> None:
    batch = booked_spread(
        {**SPREAD, "quantity_per": per}, {**SPREAD_TICKET, "quantity": [quantity]}
    )
    results = valued_spread(batch)
    nto, pan = results.legs
    close(results.payment_amount, [payment])
    assert results.mark == pytest.approx(payment * 0.95, **CLOSE)
    assert (nto.nominal_delta_total, pan.nominal_delta_total) == pytest.approx(
        (lots, -lots), **CLOSE
    )
    assert cell(grid(batch), 0, "quantity") == quantity


def test_a_period_on_a_pair_is_unbuilt_as_before_whatever_the_quantity() -> None:
    # A whole period is one futures index's average, onetime-averaging.md: on two indexes it is
    # refused by name for a fraction as for a whole number, the quantity changing nothing.
    onetime = {"quantity_per": "period", "settlement_frequency": "onetime"}
    assert refused_pair({**PAIR, **onetime}, {**PAIR_TICKET, "quantity": [0.5]}) == (
        "settlement_frequency of trade 1 at row 1 is 'onetime', expected 'monthly' with two "
        "indexes; a onetime period on a pair is not built"
    )
    fraction = refused_spread({**SPREAD, **onetime}, {**SPREAD_TICKET, "quantity": [0.5]})
    whole = refused_spread({**SPREAD, **onetime}, SPREAD_TICKET)
    assert fraction == whole and "'onetime', expected 'monthly'" in fraction


# --- the reserves --------------------------------------------------------------------------------


def test_the_fees_follow_the_size_of_the_quantity_and_the_entered_reserves_do_not() -> None:
    # FEES charges a cent of brokerage and half a cent of clearing per MMBTU, 100 and 50 a LOT
    # of 10,000 MMBTU. A cleared, brokered row: 150 and 75 at a lot and a half, 25 and 12.50 at a
    # quarter sold, the size and not the sign, nothing at zero; the marketing reserve of 15 and
    # the CVA reserve of -40 are the row's own amounts at every quantity.
    fees = futures("FEES", 10_000.0, 0.01, 0.005)
    template: dict[str, object] = {
        **{
            k: v
            for k, v in PAIR.items()
            if k not in ("second_schedule_method", "counterparty", "discount_curve_key")
        },
        "route": "cleared",
        "clearing_house": "ICE Clear Europe",
        "broker": "ICAP",
        "quantity_unit": "LOT",
    }
    for quantity, brokerage, clearing in (
        (1.0, 100.0, 50.0),
        (1.5, 150.0, 75.0),
        (-0.25, 25.0, 12.5),
        (0.0, 0.0, 0.0),
    ):
        ticket: dict[str, list[object]] = {
            **PAIR_TICKET,
            "quantity": [quantity],
            "marketing_reserve": [15.0],
            "cva_reserve": [-40.0],
        }
        reserves = booked_pair(template, ticket, (fees,)).encoded.reserves
        assert (reserves.brokerage, reserves.clearing) == pytest.approx(
            (brokerage, clearing), **CLOSE
        ), quantity
        assert (reserves.marketing, reserves.cva) == (15.0, -40.0), quantity


# --- the rule by settlement ----------------------------------------------------------------------


def test_a_physical_row_is_whole_as_it_always_was_and_a_financial_one_takes_the_fraction() -> None:
    fraction: dict[str, list[object]] = {**NG_TICKET, "quantity": [10, 2.5, 7, -12, 10]}
    assert refused(NG, fraction, NG_TEMPLATE) == (
        "quantity of trade 1002 at row 2 is 2.5, expected a whole number"
    )
    whole, _ = created(NG, NG_TICKET, NG_TEMPLATE)
    np.testing.assert_array_equal(whole.resolved.quantity, [10.0, -4.0, 7.0, -12.0, 10.0])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_number_that_is_not_finite_is_refused_under_either_settlement(bad: float) -> None:
    # Each in its settlement's words, named by its trade and row: a physical row's as before.
    assert refused(NG, {**NG_TICKET, "quantity": [10, bad, 7, -12, 10]}, NG_TEMPLATE) == (
        f"quantity of trade 1002 at row 2 is {bad!r}, expected a whole number"
    )
    assert refused(OIL, {**ROW, "quantity": [bad]}, SWAP) == (
        f"quantity of trade 1 at row 1 is {bad!r}, expected a finite quantity"
    )
    with pytest.raises(
        ValueError, match=r"^quantity is (nan|inf|-inf), expected a finite quantity$"
    ):
        a_template({**SWAP, "quantity": bad})


def test_the_rule_waits_for_the_tickets_settlement_method_where_the_template_has_none() -> None:
    # The quantity in the template and the settlement method in the ticket: the template is made,
    # holding the fraction, and the batch applies the rule once it knows the method, naming the
    # trade. Financial books the example; physical refuses the fraction in today's words.
    waiting = {**{k: v for k, v in SWAP.items() if k != "settlement_method"}, "quantity": 1.5}
    assert a_template(waiting).defaults["quantity"] == 1.5
    batch, _ = created(OIL, {**NO_QUANTITY, "settlement_method": ["financial"]}, waiting)
    assert the_measures(valued(batch)) == pytest.approx(AT_ONE_AND_A_HALF, **CLOSE)
    physical = {
        **{k: v for k, v in NG_TEMPLATE.items() if k != "settlement_method"},
        "quantity": 1.5,
    }
    rest: dict[str, list[object]] = {k: v for k, v in NG_TICKET.items() if k != "quantity"}
    assert a_template(physical).defaults["quantity"] == 1.5
    assert refused(NG, {**rest, "settlement_method": ["physical"] * 5}, physical) == (
        "quantity of trade 1001 at row 1 is 1.5, expected a whole number"
    )
    # Where the template holds both, a physical template refuses the fraction when it is made.
    with pytest.raises(ValueError, match=r"^quantity is 1\.5, expected a whole number$"):
        a_template({**NG_TEMPLATE, "quantity": 1.5})


def test_trade_ids_nearbys_and_lot_sizes_stay_whole_numbers() -> None:
    # A fraction is a quantity's alone: an identifier, a position among the contracts and the
    # size of a lot are whole numbers still.
    assert refused(OIL, {**ROW, "trade_id": [1.5]}, SWAP) == (
        "trade_id row 1 is 1.5, expected a whole number of at most 15 digits"
    )
    with pytest.raises(ValueError, match=r"^nearby is 1\.5, expected a whole number of 1 or more"):
        a_template({**SWAP, "nearby": 1.5})
    with pytest.raises(ValueError, match=r"^lot_size row 1 is 1000\.5, expected a whole number$"):
        an_index("HALF", lots=(("LOT", 1_000.5, "BBL"),), measure=("VOLUME", "BBL"))


# --- through the seam ----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The pair test's sheet, made once: A and B, each defining the NYMEX NG lot of 10,000 MMBTU,
    valued 4 January 2027 with SOFR at 0.95 a year on, and its bilateral financial template."""
    return the_sheet()


@pytest.mark.parametrize(("quantity", "mark"), [(1.5, 1_425.0), (-0.25, -237.5)])
def test_the_sheet_books_prepares_values_and_reads_back_a_fraction(
    sheet: dict[str, Any], quantity: float, mark: float
) -> None:
    # One lot of the pair at the outright 3.00 against 3.10 marks 950, the pair test's hand
    # table: a lot and a half 1,425, a quarter sold -237.50, the lots of each leg the quantity.
    trades = SEAM["_CreateTrades"](
        down(sheet["a"], sheet["b"]),
        sheet["headers"],
        across(1.0, serial("2026-12-15"), "G27", quantity, 3.00),
        sheet["template"],
    )
    assert under(read(trades), "quantity") == [quantity]
    prepared = SEAM["_PrepareTrades"](trades, down(sheet["hist_a"], sheet["hist_b"]))
    assert under(read(prepared), "live_lots") == pytest.approx([quantity, quantity], **CLOSE)
    results = SEAM["_EvaluateTrades"](
        prepared, across(sheet["market_a"], sheet["market_b"]), sheet["curves"]
    )
    assert under(read(results), "contract_nominal_delta") == pytest.approx(
        [quantity, quantity], **CLOSE
    )
    values = spilled(SEAM["_ReportValues"](results))
    assert values[2][0] == pytest.approx(mark, **CLOSE)
    risk = spilled(SEAM["_ReportRisk"](results, "nominal_delta", "day"))
    assert risk[3][0] == "Total" and risk[3][1:] == pytest.approx([quantity, quantity], **CLOSE)


def test_the_sheet_refuses_a_fraction_on_a_physical_row_in_the_words_it_always_gave(
    sheet: dict[str, Any],
) -> None:
    terms: dict[str, object] = {
        "settlement_method": "physical",
        "quantity_unit": "NYMEX NG",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "nearby": 1.0,
        "schedule_method": "lastday",
        "route": "cleared",
        "clearing_house": "CME Clearing",
    }
    physical = SEAM["_CreateTradeTemplate"]("fixed_float", across(*terms), across(*terms.values()))
    create = SEAM["_CreateTrades"]
    row = across(1.0, serial("2026-12-15"), "G27", 1.5, 3.00)
    assert create(sheet["a"], sheet["headers"], row, physical) == (
        "#ERROR _CreateTrades: ValueError: quantity of trade 1 at row 1 is 1.5, expected a whole "
        "number"
    )
    whole = across(1.0, serial("2026-12-15"), "G27", 2.0, 3.00)
    assert under(read(create(sheet["a"], sheet["headers"], whole, physical)), "quantity") == [2.0]
    # The template itself, holding both fields, refuses the fraction when it is made.
    assert SEAM["_CreateTradeTemplate"](
        "fixed_float",
        across("settlement_method", "quantity"),
        across("physical", 1.5),
    ) == ("#ERROR _CreateTradeTemplate: ValueError: quantity is 1.5, expected a whole number")
