"""A float_float swap on two indexes at one spread price, float-float-spread.md: the first
index's price less the second's against one agreed spread_price, the second leg signed once at
creation. Two synthetic IFERC indexes named NTO and PAN, each with a 2,500 MMBTU reporting lot,
carry the ticket's hand table; the pair test's A, a futures index, and B, an IFERC one, carry
the lifecycle, where the legs fix on different days. Every expected number is the ticket's or
hand arithmetic here; the production code is never asked for an expected answer."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

import numpy as np
import pytest
from test_aggregate_risk import same_view
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import a_template, a_ticket
from test_trades import dates, day, quoted, waha_history
from test_two_index import (
    AS_OF,
    CLOSE,
    PAY,
    PID,
    SEAM,
    SOFR,
    A,
    B,
    across,
    cell,
    close,
    down,
    futures,
    grid,
    iferc,
    on,
    read,
    serial,
    spilled,
    the_sheet,
    under,
)
from test_two_index import BILATERAL as PAIR_BILATERAL
from test_two_index import CLEARED as PAIR_CLEARED
from test_two_index import LIFECYCLE as PAIR_LIFECYCLE
from test_two_index import booked as booked_pair
from test_two_index import valued as valued_on_a_and_b

from catalyst.excel import bridge
from catalyst.globals.discount_curve import DiscountCurve, bump_discount_curve
from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.index import Index
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT, FLOAT_FLOAT
from catalyst.market.market import Market
from catalyst.market.market_history import MarketHistory
from catalyst.trades.aggregation import aggregate_results
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.results import TradeResults
from catalyst.trades.risk_report import Bucket, Risk

# --- the spread -----------------------------------------------------------------------------------
# NTO and PAN: two IFERC indexes over Z26 to J27, G27 publishing 1 February 2027, each with a
# LOT of 2,500 MMBTU reported and one MMBTU per entered unit. Valued 4 January 2027, G27 quoted
# -0.25 on NTO and -0.40 on PAN, one payment a year on at a SOFR factor of 0.95.

# Every float_float types its spread price's unit, float-float-units.md: dollars per MMBTU here,
# the unit both indexes quote in, on the pair test's three templates.
UNIT: dict[str, object] = {
    "spread_price_currency_unit": "USD",
    "spread_price_quantity_unit": "MMBTU",
}
BILATERAL: dict[str, object] = {**PAIR_BILATERAL, **UNIT}
CLEARED: dict[str, object] = {**PAIR_CLEARED, **UNIT}
LIFECYCLE: dict[str, object] = {**PAIR_LIFECYCLE, **UNIT}

NTO = iferc("NTO", 2_500.0)
PAN = iferc("PAN", 2_500.0)
TICKET: dict[str, list[object]] = {
    "trade_id": [1],
    "trade_date": ["2026-12-15"],
    "contract_code": ["G27"],
    "quantity": [10_000],
    "spread_price": [0.10],  # the one price of the deal, against NTO less PAN
}
ONE_INDEX = {k: v for k, v in PAIR_BILATERAL.items() if k != "second_schedule_method"}
QUOTES_NTO, QUOTES_PAN = (-0.23, -0.25, -0.27), (-0.38, -0.40, -0.42)  # from F27 on


def booked(
    template: Mapping[str, object] = BILATERAL,
    ticket: Mapping[str, list[object]] = TICKET,
    indexes: Sequence[Index] = (NTO, PAN),
) -> Trades:
    return trades(
        indexes,
        a_ticket(ticket, FLOAT_FLOAT),
        a_template(template, FLOAT_FLOAT),
        UNITS,
        WorkCounter(),
    )


def refused(
    template: Mapping[str, object] = BILATERAL,
    ticket: Mapping[str, list[object]] = TICKET,
    indexes: Sequence[Index] = (NTO, PAN),
) -> str:
    with pytest.raises(ValueError) as refusal:
        booked(template, ticket, indexes)
    return str(refusal.value)


def the_markets(
    quotes_nto: tuple[float, ...] = QUOTES_NTO, quotes_pan: tuple[float, ...] = QUOTES_PAN
) -> tuple[tuple[MarketHistory, MarketHistory], tuple[Market, Market]]:
    """NTO's and PAN's histories on the hand table's day, December's index behind each, and
    their markets, quoted from F27 on."""
    nto = waha_history(AS_OF, {"Z26": -0.20}, NTO)
    pan = waha_history(AS_OF, {"Z26": -0.35}, PAN)
    return (nto, pan), (quoted(nto, *quotes_nto), quoted(pan, *quotes_pan))


def valued(
    batch: Trades,
    curve: DiscountCurve = SOFR,
    quotes_nto: tuple[float, ...] = QUOTES_NTO,
    quotes_pan: tuple[float, ...] = QUOTES_PAN,
) -> TradeResults:
    """A batch on NTO and PAN, either order, or on one of them, prepared and valued on the
    hand table's day; the histories and the markets find their legs by identity."""
    histories, markets = the_markets(quotes_nto, quotes_pan)
    indexes = [leg.index for leg in batch.resolved.legs]
    mine = [k for k, ix in enumerate((NTO, PAN)) if any(ix is each for each in indexes)]
    prepared = prepared_trades(batch.encoded, [histories[k] for k in mine], WorkCounter())
    return trade_results(prepared, [markets[k] for k in mine], WorkCounter(), curve_set(curve))


def leg_on(results: TradeResults, ix: Index) -> Any:
    """The results' leg on that index, wherever it stands among the legs."""
    (leg,) = [leg for leg in results.legs if leg.prepared.encoded.leg.index is ix]
    return leg


def alone(ix: Index, quantity: float, fixed_price: float) -> Trades:
    """A fixed_float on one of the two indexes, the hand table's row at its own fixed price."""
    rows: dict[str, list[object]] = {
        "trade_id": [1],
        "trade_date": ["2026-12-15"],
        "contract_code": ["G27"],
        "quantity": [quantity],
        "fixed_price": [fixed_price],
    }
    return trades((ix,), a_ticket(rows), a_template(ONE_INDEX), UNITS, WorkCounter())


def number(value: object) -> float:
    return cast(float, value)


# --- the hand-priced acceptance table ------------------------------------------------------------


def test_the_hand_table_a_bought_spread_both_legs_live() -> None:
    # 10,000 MMBTU of NTO less PAN at a spread price of 0.10, the indexes at -0.25 and -0.40,
    # 0.15 apart, one payment a year on at 0.95: payment 500, mark 475, DV01 -0.0475; nominal
    # deltas 4 lots of NTO and -4 of PAN, deltas 3.8 and -3.8, cross-gammas -0.00038 and
    # 0.00038; no leg has a value.
    batch = booked()
    terms = batch.resolved
    assert terms.instrument is FLOAT_FLOAT and terms.descriptor == "NTO-PAN"
    assert [leg.index for leg in terms.legs] == [NTO, PAN]
    assert [leg.subtracted for leg in terms.legs] == [False, True]
    close(terms.price, [0.10])
    first, second = batch.encoded.legs
    # The second leg's sign, taken once at creation: its quantities and coefficients negated.
    close(first.quote_quantity, [10_000.0])
    close(second.quote_quantity, [-10_000.0])
    close(first.coefficient, [10_000.0])
    close(second.coefficient, [-10_000.0])
    close(first.slot_exposure, [10_000.0])
    close(second.slot_exposure, [-10_000.0])
    close(batch.encoded.offset, [-1_000.0])  # the spread leg: -10,000 MMBTU at 0.10, once
    close(batch.encoded.offset_of_group, [-1_000.0])
    results = valued(batch)
    nto, pan = results.legs
    assert (nto.prepared.encoded.leg.index, pan.prepared.encoded.leg.index) == (NTO, PAN)
    close(results.payment_amount, [500.0])
    close(results.payment_factor, [0.95])
    assert results.mark == pytest.approx(475.0, **CLOSE)
    assert results.dv01 == pytest.approx(-0.0475, **CLOSE)
    close(results.npv_by_group, [475.0])
    close(results.dv01_by_group, [-0.0475])
    close(nto.dated_live_contribution, [-2_500.0])  # received: 10,000 at -0.25
    close(pan.dated_live_contribution, [4_000.0])  # paid: -10,000 at -0.40
    assert nto.nominal_delta_total == pytest.approx(4.0, **CLOSE)
    assert pan.nominal_delta_total == pytest.approx(-4.0, **CLOSE)
    assert nto.delta_total == pytest.approx(3.8, **CLOSE)
    assert pan.delta_total == pytest.approx(-3.8, **CLOSE)
    assert nto.cross_gamma_total == pytest.approx(-0.00038, **CLOSE)
    assert pan.cross_gamma_total == pytest.approx(0.00038, **CLOSE)
    for name in ("mark", "cash", "dv01", "payment_amount", "npv_by_group", "dv01_by_group"):
        assert not hasattr(nto, name) and not hasattr(pan, name), name
    (rate,) = results.rate_contributions
    assert rate.curve is SOFR and rate.dv01 == pytest.approx(-0.0475, **CLOSE)
    assert results.cash == 0.0


def test_the_three_contributions_reconcile_from_the_readback_and_no_leg_keeps_one() -> None:
    # The ticket's -2,375, 3,800 and -950: each leg's floating contribution and the spread leg,
    # read back undiscounted, times the payment's factor, summing to the mark. A test's
    # arithmetic over the readback, the records keeping no leg's value since #242.
    batch = booked()
    table = grid(valued(batch))
    factor = number(cell(table, 0, "payment_factor"))
    sides = [number(cell(table, r, "floating_contribution")) * factor for r in (0, 1)]
    spread_leg = number(cell(grid(batch), 0, "offset")) * factor
    assert sides == pytest.approx([-2_375.0, 3_800.0], **CLOSE)
    assert spread_leg == pytest.approx(-950.0, **CLOSE)
    assert sum(sides) + spread_leg == pytest.approx(475.0, **CLOSE)
    assert cell(table, 0, "group_npv") == pytest.approx(475.0, **CLOSE)
    for name in ("leg_amount", "leg_npv", "leg_group_dv01", "leg_mark", "leg_cash", "leg_dv01"):
        assert name not in table[0], name


@pytest.mark.parametrize(
    ("spread_price", "payment", "mark", "dv01"),
    [(0.0, 1_500.0, 1_425.0, -0.1425), (-0.10, 2_500.0, 2_375.0, -0.2375)],
    ids=["zero", "negative"],
)
def test_moving_the_spread_price_moves_the_value_and_the_rate_risk_and_not_the_deltas(
    spread_price: float, payment: float, mark: float, dv01: float
) -> None:
    results = valued(booked(ticket={**TICKET, "spread_price": [spread_price]}))
    nto, pan = results.legs
    close(results.payment_amount, [payment])
    assert results.mark == pytest.approx(mark, **CLOSE)
    assert results.dv01 == pytest.approx(dv01, **CLOSE)
    assert (nto.nominal_delta_total, pan.nominal_delta_total) == (4.0, -4.0)
    assert (nto.delta_total, pan.delta_total) == pytest.approx((3.8, -3.8), **CLOSE)
    assert nto.cross_gamma_total == pytest.approx(-0.00038, **CLOSE)
    assert pan.cross_gamma_total == pytest.approx(0.00038, **CLOSE)


def test_a_sold_spread_reverses_cash_value_and_every_risk() -> None:
    sold = valued(booked(ticket={**TICKET, "quantity": [-10_000]}))
    nto, pan = sold.legs
    close(sold.payment_amount, [-500.0])
    assert sold.mark == pytest.approx(-475.0, **CLOSE)
    assert sold.dv01 == pytest.approx(0.0475, **CLOSE)
    assert (nto.nominal_delta_total, pan.nominal_delta_total) == (-4.0, 4.0)
    assert (nto.delta_total, pan.delta_total) == pytest.approx((-3.8, 3.8), **CLOSE)
    assert nto.cross_gamma_total == pytest.approx(0.00038, **CLOSE)
    assert pan.cross_gamma_total == pytest.approx(-0.00038, **CLOSE)


def test_a_zero_quantity_is_a_row_kept_with_nothing_on_it() -> None:
    kept = booked(ticket={**TICKET, "quantity": [0]})
    assert [leg.quote_quantity.tolist() for leg in kept.encoded.legs] == [[0.0], [0.0]]
    zero = valued(kept)
    assert zero.mark == 0.0 and zero.dv01 == 0.0
    assert [leg.nominal_delta_total for leg in zero.legs] == [0.0, 0.0]


def test_the_analytic_rate_risk_matches_a_bumped_curve() -> None:
    batch = booked()
    up = valued(batch, bump_discount_curve(SOFR, 1.0, WorkCounter()))
    down_ = valued(batch, bump_discount_curve(SOFR, -1.0, WorkCounter()))
    results = valued(batch)
    assert (up.mark - down_.mark) / 2 == pytest.approx(results.dv01, rel=1e-6)
    for before, after, leg in zip(up.legs, down_.legs, results.legs, strict=True):
        assert (before.delta_total - after.delta_total) / 2 == pytest.approx(
            leg.cross_gamma_total, rel=1e-6
        )


# --- the lifecycle, the legs fixing on different days ---------------------------------------------
# A less B, 10,000 MMBTU at a spread price of 3.80: A observes F27 on 29 December 2026 at 3.55, B
# publishes 4 January 2027 at -0.35, and +2bd from the later pays 6 January.

F27: dict[str, list[object]] = {**TICKET, "contract_code": ["F27"], "spread_price": [3.80]}


def a_less_b(ticket: Mapping[str, list[object]] = F27) -> Trades:
    return booked(LIFECYCLE, ticket, (A, B))


def test_the_lifecycle_both_live_on_28_december() -> None:
    results = valued_on_a_and_b(
        a_less_b(),
        "2026-12-28",
        finals_a={},
        quotes_a=(3.50, 3.60, 3.70),
        quotes_b=(-0.40, -0.42, -0.44),
        curve=on("2026-12-28", 0.99),
    )
    a, b = results.legs
    close(results.payment_amount, [1_000.0])  # 3.50 less -0.40 is 3.90, less the spread 3.80
    assert results.mark == pytest.approx(1_000.0 * 0.99, **CLOSE)
    assert results.dv01 == pytest.approx(-0.0001 * (9 / 365) * 1_000.0 * 0.99, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (1.0, -4.0)


def test_the_lifecycle_a_fixed_and_b_live_on_30_december() -> None:
    results = valued_on_a_and_b(
        a_less_b(),
        "2026-12-30",
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.40, -0.42, -0.44),
        curve=on("2026-12-30", 0.995),
    )
    a, b = results.legs
    close(results.payment_amount, [1_500.0])  # 3.55 less -0.40 is 3.95
    close(a.prepared.fixed_contribution, [35_500.0])  # received, fixed at 3.55
    close(b.dated_live_contribution, [4_000.0])  # paid, live at -0.40
    assert results.mark == pytest.approx(1_500.0 * 0.995, **CLOSE)
    assert results.dv01 == pytest.approx(-0.0001 * (7 / 365) * 1_500.0 * 0.995, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (0.0, -4.0)
    assert a.cross_gamma_total == 0.0 and b.cross_gamma_total > 0.0
    # B's quote moved down a nickel raises the payment, B being paid; only B's side moves.
    moved = valued_on_a_and_b(
        a_less_b(),
        "2026-12-30",
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.45, -0.42, -0.44),
        curve=on("2026-12-30", 0.995),
    )
    close(moved.payment_amount, [2_000.0])  # 3.55 less -0.45 is 4.00
    close(moved.legs[0].prepared.fixed_contribution, [35_500.0])
    close(moved.legs[1].dated_live_contribution, [4_500.0])


def test_the_lifecycle_both_fixed_on_5_january_and_a_fixing_corrected() -> None:
    fixed = {"Z26": -0.30, "F27": -0.35}
    results = valued_on_a_and_b(
        a_less_b(),
        "2027-01-05",
        indices_b=fixed,
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.42, -0.44),
        curve=on("2027-01-05", 0.9999),
    )
    a, b = results.legs
    # B published at -0.35, above its last quote: the payment falls from 1,500 to 1,000, where a
    # fixed_float pair's would rise.
    close(results.payment_amount, [1_000.0])  # 3.55 less -0.35 is 3.90
    close(a.prepared.fixed_contribution, [35_500.0])
    close(b.prepared.fixed_contribution, [3_500.0])
    assert results.mark == pytest.approx(1_000.0 * 0.9999, **CLOSE)
    assert results.dv01 == pytest.approx(-0.0001 * (1 / 365) * 1_000.0 * 0.9999, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (0.0, 0.0)
    assert results.cash == 0.0
    corrected = valued_on_a_and_b(
        a_less_b(),
        "2027-01-05",
        finals_a={"F27": 3.60},
        indices_b=fixed,
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.42, -0.44),
        curve=on("2027-01-05", 0.9999),
    )
    close(corrected.payment_amount, [1_500.0])  # 3.60 less -0.35 is 3.95
    close(corrected.legs[0].prepared.fixed_contribution, [36_000.0])
    close(corrected.legs[1].prepared.fixed_contribution, [3_500.0])


def test_the_lifecycle_paid_on_6_january_is_one_cash_amount() -> None:
    results = valued_on_a_and_b(
        a_less_b(),
        "2027-01-06",
        indices_b={"Z26": -0.30, "F27": -0.35},
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.42, -0.44),
        curve=curve_of(("2027-01-06", 1.0), ("2027-06-30", 0.98)),
    )
    assert (results.mark, results.dv01) == (0.0, 0.0)
    assert results.cash == pytest.approx(1_000.0, **CLOSE)
    assert [leg.nominal_delta_total for leg in results.legs] == [0.0, 0.0]
    assert results.prepared.is_settled.tolist() == [True]


def test_a_dollar_survives_two_prices_that_cancel_at_the_sixteenth_digit() -> None:
    # The ordinary case of a spread, two prices far larger than their difference: one MMBTU,
    # both indexes at ten thousand trillion and a spread price of -1. A plain sum that met the
    # spread leg first would round the dollar away; the payment is its signed terms summed with
    # compensation, so it reads one dollar with both legs live, with A fixed, with both fixed
    # and, paid, as cash.
    extreme: dict[str, list[object]] = {**F27, "quantity": [1], "spread_price": [-1.0]}
    big = (1e16, 1e16, 1e16)
    live = valued_on_a_and_b(
        a_less_b(extreme),
        "2026-12-28",
        finals_a={},
        quotes_a=big,
        quotes_b=big,
        curve=on("2026-12-28", 0.99),
    )
    close(live.payment_amount, [1.0])
    assert live.mark == pytest.approx(0.99, **CLOSE)
    a_fixed = valued_on_a_and_b(
        a_less_b(extreme),
        "2026-12-30",
        finals_a={"F27": 1e16},
        quotes_a=big,
        quotes_b=big,
        curve=on("2026-12-30", 0.995),
    )
    close(a_fixed.payment_amount, [1.0])
    both = {"Z26": -0.30, "F27": 1e16}
    both_fixed = valued_on_a_and_b(
        a_less_b(extreme),
        "2027-01-05",
        finals_a={"F27": 1e16},
        indices_b=both,
        quotes_a=big,
        quotes_b=big,
        curve=on("2027-01-05", 0.9999),
    )
    close(both_fixed.payment_amount, [1.0])
    assert both_fixed.prepared.set_unsettled == (1e16, -1e16)  # each leg's, kept apart
    paid = valued_on_a_and_b(
        a_less_b(extreme),
        "2027-01-06",
        finals_a={"F27": 1e16},
        indices_b=both,
        quotes_a=big,
        quotes_b=big,
        curve=curve_of(("2027-01-06", 1.0), ("2027-06-30", 0.98)),
    )
    assert (paid.cash, paid.mark) == (1.0, 0.0)


# --- order, strips and rows -----------------------------------------------------------------------


def test_the_indexes_in_the_other_order_with_quantity_and_price_negated_read_the_same() -> None:
    forward = valued(booked())
    backward_batch = booked(
        ticket={**TICKET, "quantity": [-10_000], "spread_price": [-0.10]}, indexes=(PAN, NTO)
    )
    assert backward_batch.resolved.descriptor == "PAN-NTO"
    assert [leg.subtracted for leg in backward_batch.resolved.legs] == [False, True]
    backward = valued(backward_batch)
    assert backward.mark == pytest.approx(forward.mark, **CLOSE)
    assert backward.dv01 == pytest.approx(forward.dv01, **CLOSE)
    for ix in (NTO, PAN):
        mine, theirs = leg_on(backward, ix), leg_on(forward, ix)
        assert mine.nominal_delta_total == pytest.approx(theirs.nominal_delta_total, **CLOSE)
        assert mine.delta_total == pytest.approx(theirs.delta_total, **CLOSE)
        assert mine.cross_gamma_total == pytest.approx(theirs.cross_gamma_total, **CLOSE)


def test_a_strip_pays_one_net_amount_a_month_and_calday_counts_each_months_days() -> None:
    strip = valued(booked(ticket={**TICKET, "contract_code": ["G27-H27"]}))
    # G27: -0.25 less -0.40; H27: -0.27 less -0.42; each 0.15 apart, 0.05 over the spread price.
    close(strip.payment_amount, [500.0, 500.0])
    assert strip.mark == pytest.approx(950.0, **CLOSE)
    assert [leg.nominal_delta_total for leg in strip.legs] == pytest.approx([8.0, -8.0], **CLOSE)
    daily = valued(booked({**BILATERAL, "quantity_per": "calday"}))
    # February's 28 days: 280,000 MMBTU, 0.05 over the spread price.
    close(daily.payment_amount, [14_000.0])
    assert daily.legs[1].nominal_delta_total == pytest.approx(-112.0, **CLOSE)


def test_a_batch_equals_its_singleton_rows_and_a_duplicate_counts_twice() -> None:
    rows: dict[str, list[object]] = {
        "trade_id": [1, 2],
        "trade_date": ["2026-12-15", "2026-12-16"],
        "contract_code": ["G27", "H27"],
        "quantity": [10_000, -5_000],
        "spread_price": [0.10, 0.12],
    }
    both = valued(booked(ticket=rows))
    first = valued(booked(ticket={k: [v[0]] for k, v in rows.items()}))
    second = valued(booked(ticket={k: [v[1]] for k, v in rows.items()}))
    assert both.mark == pytest.approx(first.mark + second.mark, **CLOSE)
    assert both.dv01 == pytest.approx(first.dv01 + second.dv01, **CLOSE)
    for k in range(2):
        assert both.legs[k].nominal_delta_total == pytest.approx(
            first.legs[k].nominal_delta_total + second.legs[k].nominal_delta_total, **CLOSE
        )
    twice = valued(booked(ticket={k: [v[0], v[0]] for k, v in rows.items()}))
    assert twice.mark == pytest.approx(2 * first.mark, **CLOSE)
    assert twice.legs[1].nominal_delta_total == pytest.approx(-8.0, **CLOSE)


def test_the_reserves_are_the_rows_own_and_no_fee_is_charged() -> None:
    plain = booked()
    reserves = plain.encoded.reserves
    assert (reserves.brokerage, reserves.clearing, reserves.marketing, reserves.cva) == (
        0.0,
        0.0,
        0.0,
        0.0,
    )
    entered = booked(ticket={**TICKET, "marketing_reserve": [15.0], "cva_reserve": [-40.0]})
    assert (entered.encoded.reserves.marketing, entered.encoded.reserves.cva) == (15.0, -40.0)
    assert valued(entered).mark == valued(plain).mark  # a reserve enters no number
    # None in any case is no broker, as on a fixed_float.
    for word in ("none", "None", "NONE"):
        assert booked({**BILATERAL, "broker": word}).encoded.reserves.brokerage == 0.0


# --- the reports and the collection ---------------------------------------------------------------


def test_a_spreads_report_reads_as_the_collection_of_its_legs() -> None:
    # Every risk by every bucket: the spread's report and the collection of two fixed_floats
    # booked apart, NTO bought at -0.20 and PAN sold at -0.30, one split of the spread price of
    # 0.10, have the same labels, dates, Totals and columns: two commodity groups and one DV01
    # column, never a joint-index column.
    spread = valued(booked())
    legs = aggregate_results(
        (valued(alone(NTO, 10_000, -0.20)), valued(alone(PAN, -10_000, -0.30))), WorkCounter()
    )
    for risk in Risk:
        for bucket in Bucket:
            same_view(spread.report(risk, bucket), legs.report(risk, bucket))
    everything = spread.report(Risk.ALL, Bucket.DAY)
    assert everything.labels[:5] == (
        "NTO nominal_delta [LOT]",
        "NTO delta [LOT]",
        "PAN nominal_delta [LOT]",
        "PAN delta [LOT]",
        "SOFR USD dv01 [USD per basis point]",
    )
    assert len(everything.labels) == 7
    assert everything.totals[:5] == pytest.approx([4.0, 3.8, -4.0, -3.8, -0.0475], **CLOSE)


def spread_beside(quantity: float) -> tuple[TradeResults, TradeResults]:
    """The hand table's spread beside a fixed_float on NTO alone at -0.30, on one history, one
    market and one curve of NTO, as a collection takes them."""
    histories, markets = the_markets()
    curves = curve_set(SOFR)
    spread = trade_results(
        prepared_trades(booked().encoded, histories, WorkCounter()), markets, WorkCounter(), curves
    )
    position = trade_results(
        prepared_trades(alone(NTO, quantity, -0.30).encoded, histories[:1], WorkCounter()),
        markets[:1],
        WorkCounter(),
        curves,
    )
    return spread, position


def test_the_spread_nets_with_an_ordinary_position_on_each_index_and_on_the_curve() -> None:
    # Beside 5,000 MMBTU of NTO bought at -0.30 against -0.25: payment 250, mark 237.5, 2 lots
    # nominal, 1.9 of delta and -0.02375 of DV01. NTO totals 6 and 5.7, PAN stays -4 and -3.8,
    # SOFR's DV01 is -0.07125; nothing is counted twice and no joint index is made.
    spread, position = spread_beside(5_000)
    assert position.mark == pytest.approx(237.5, **CLOSE)
    together = aggregate_results((spread, position), WorkCounter())
    nto, pan = together.index_groups
    assert nto.index is NTO and pan.index is PAN
    assert nto.occurrences.tolist() == [0, 1] and pan.occurrences.tolist() == [0]
    assert nto.nominal_delta_total == pytest.approx(6.0, **CLOSE)
    assert nto.delta_total == pytest.approx(5.7, **CLOSE)
    assert pan.nominal_delta_total == pytest.approx(-4.0, **CLOSE)
    assert pan.delta_total == pytest.approx(-3.8, **CLOSE)
    (sofr,) = together.rate_groups
    assert sofr.curve is SOFR and sofr.dv01 == pytest.approx(-0.07125, **CLOSE)
    assert [(c.index.name, c.word) for c in together.cross_groups] == [
        ("NTO", "SOFR"),
        ("PAN", "SOFR"),
    ]
    assert together.cross_groups[0].cross_gamma_total == pytest.approx(-0.00057, **CLOSE)
    assert together.cross_groups[1].cross_gamma_total == pytest.approx(0.00038, **CLOSE)
    # The membership readback: the spread's own row, named by its descriptor, carries its DV01,
    # and a row per leg its index's commodity risk; the position keeps its one row.
    table = grid(together)
    assert len(table) == 6
    assert [cell(table, r, "position") for r in range(4)] == [1.0, 1.0, 1.0, 2.0]
    assert [cell(table, r, "index") for r in range(4)] == ["NTO-PAN", "NTO", "PAN", "NTO"]
    assert [cell(table, r, "reporting_lot") for r in range(4)] == ["-", "LOT", "LOT", "LOT"]
    assert cell(table, 0, "nominal_delta") == "-" and cell(table, 0, "delta") == "-"
    assert [cell(table, r, "nominal_delta") for r in (1, 2, 3)] == pytest.approx([4.0, -4.0, 2.0])
    assert [cell(table, r, "delta") for r in (1, 2, 3)] == pytest.approx([3.8, -3.8, 1.9])
    assert cell(table, 0, "dv01") == pytest.approx(-0.0475, **CLOSE)
    assert cell(table, 1, "dv01") == "-" and cell(table, 2, "dv01") == "-"
    assert cell(table, 3, "dv01") == pytest.approx(-0.02375, **CLOSE)
    assert cell(table, 0, "cross_gamma") == "-"
    assert [cell(table, r, "cross_gamma") for r in (1, 2, 3)] == pytest.approx(
        [-0.00038, 0.00038, -0.00019], **CLOSE
    )


def test_a_sold_position_of_the_spreads_size_leaves_the_first_index_flat() -> None:
    spread, sold = spread_beside(-10_000)
    nto, pan = aggregate_results((spread, sold), WorkCounter()).index_groups
    assert nto.nominal_delta_total == pytest.approx(0.0, abs=1e-12)
    assert nto.delta_total == pytest.approx(0.0, abs=1e-12)
    assert pan.nominal_delta_total == pytest.approx(-4.0, **CLOSE)


def test_a_repeated_spread_counts_twice_in_a_collection() -> None:
    spread = valued(booked())
    nto, pan = (twice := aggregate_results((spread, spread), WorkCounter())).index_groups
    assert nto.occurrences.tolist() == [0, 1] and pan.occurrences.tolist() == [0, 1]
    assert nto.nominal_delta_total == pytest.approx(8.0, **CLOSE)
    assert pan.nominal_delta_total == pytest.approx(-8.0, **CLOSE)
    assert twice.rate_groups[0].dv01 == pytest.approx(-0.095, **CLOSE)


# --- the readbacks --------------------------------------------------------------------------------


def test_the_created_spread_reads_back_its_price_under_its_own_name() -> None:
    table = grid(booked())
    headings = table[0]
    assert "fixed_price" not in headings
    pair = grid(booked_pair())[0]  # a fixed_float pair's headings: the same places
    at = headings.index("spread_price")
    assert at == pair.index("fixed_price")
    # Its unit follows it, as typed, float-float-units.md, and no other column moves.
    units = ["spread_price_currency_unit", "spread_price_quantity_unit"]
    assert headings[at + 1 : at + 3] == units
    assert [h for h in headings if h not in ("spread_price", *units)] == [
        h for h in pair if h != "fixed_price"
    ]
    assert cell(table, 0, "spread_price") == 0.10
    assert [cell(table, 0, unit) for unit in units] == ["USD", "MMBTU"]
    assert cell(table, 0, "offset") == pytest.approx(-1_000.0, **CLOSE)  # the spread leg
    assert cell(table, 0, "second_schedule_method") == "lastday"
    assert cell(table, 0, "quote_quantity") == 10_000.0  # the first leg's, the batch's own


def test_the_prepared_and_valued_spread_read_back_the_second_leg_with_its_sign() -> None:
    batch = booked()
    histories, markets = the_markets()
    prepared = prepared_trades(batch.encoded, histories, WorkCounter())
    slots = grid(prepared)
    assert [row[:2] for row in slots[2:]] == [[1.0, "NTO"], [2.0, "PAN"]]
    assert cell(slots, 0, "live_lots") == pytest.approx(4.0, **CLOSE)
    assert cell(slots, 1, "live_lots") == pytest.approx(-4.0, **CLOSE)
    table = grid(trade_results(prepared, markets, WorkCounter(), curve_set(SOFR)))
    assert len(table) == 4 and [row[:2] for row in table[2:]] == [[1.0, "NTO"], [2.0, "PAN"]]
    assert cell(table, 0, "payment_amount") == pytest.approx(500.0, **CLOSE)
    assert cell(table, 1, "payment_amount") == "-"
    assert cell(table, 0, "group_dv01") == pytest.approx(-0.0475, **CLOSE)
    assert cell(table, 0, "observation_coefficient") == 10_000.0
    assert cell(table, 1, "observation_coefficient") == -10_000.0
    assert cell(table, 0, "observation_price") == -0.25
    assert cell(table, 1, "observation_price") == -0.40
    assert cell(table, 0, "floating_contribution") == pytest.approx(-2_500.0, **CLOSE)
    assert cell(table, 1, "floating_contribution") == pytest.approx(4_000.0, **CLOSE)
    assert cell(table, 0, "contract_cross_gamma") == pytest.approx(-0.00038, **CLOSE)
    assert cell(table, 1, "contract_cross_gamma") == pytest.approx(0.00038, **CLOSE)
    assert cell(table, 0, "brokerage_reserve") == 0.0


# --- the rules of a float_float -------------------------------------------------------------------


def test_a_spread_is_on_two_indexes_bilateral_and_names_no_broker() -> None:
    assert refused(indexes=(NTO,)) == (
        "indexes are 1, expected two with a float_float; a spread is the first index's price "
        "less the second's"
    )
    assert refused(indexes=(NTO, PAN, NTO)) == (
        "indexes are 3, expected one or two; a batch is on one index or, since "
        "two-index-fixed-float.md, on a pair"
    )
    # A cleared spread is refused as that, before a clearing house is asked for.
    assert refused(CLEARED) == (
        "route is 'cleared', expected 'bilateral' on a float_float; a cleared spread is not built"
    )
    assert refused({**BILATERAL, "broker": "ICAP"}) == (
        "broker of trade 1 at row 1 is 'ICAP', expected none on a float_float; a brokered spread "
        "is not built"
    )
    two: dict[str, list[object]] = {k: [*v, *v] for k, v in TICKET.items()}
    two["trade_id"], two["broker"] = [1, 2], ["none", "TP"]
    assert refused(ticket=two) == (
        "broker of trade 2 at row 2 is 'TP', expected none on a float_float; a brokered spread is "
        "not built"
    )
    assert refused({**BILATERAL, "clearing_house": "ICE Clear Europe"}) == (
        "clearing_house is 'ICE Clear Europe', expected none unless route = cleared"
    )


def test_the_spread_price_and_the_second_method_are_always_required_and_the_price_finite() -> None:
    assert refused(ticket={k: v for k, v in TICKET.items() if k != "spread_price"}) == (
        "spread_price is missing, expected a value in the template or a column in the ticket"
    )
    without = {k: v for k, v in BILATERAL.items() if k != "second_schedule_method"}
    assert refused(without) == (
        "second_schedule_method is missing, expected a value in the template or a column in the "
        "ticket"
    )
    assert refused(ticket={**TICKET, "spread_price": [float("inf")]}) == (
        "spread_price of trade 1 at row 1 is inf, expected a finite price"
    )
    with pytest.raises(ValueError, match=r"^spread_price is nan, expected a finite price$"):
        a_template({**BILATERAL, "spread_price": float("nan")}, FLOAT_FLOAT)
    # The price may be supplied by the template, one spread for every row.
    shared = booked(
        {**BILATERAL, "spread_price": 0.10},
        {k: v for k, v in TICKET.items() if k != "spread_price"},
    )
    close(shared.resolved.price, [0.10])
    # Neither instrument defines the other's price.
    assert "fixed_price" not in {field.name for field in FLOAT_FLOAT.fields}
    assert "spread_price" not in {field.name for field in FIXED_FLOAT.fields}


def test_the_pairs_rules_stand_in_their_words() -> None:
    assert refused(indexes=(NTO, NTO)) == (
        "index 2 is index 1, 'NTO', again, expected two distinct indexes; a pair of one index is "
        "outside this version"
    )
    assert refused(indexes=(NTO, futures("NTO", 2_500.0, 0.0, 0.0))) == (
        "index 2 is another index named 'NTO', the name of index 1, expected one index for one name"
    )
    physical = {
        k: v for k, v in BILATERAL.items() if k not in ("payment_day", "payment_holiday_calendar")
    } | {"settlement_method": "physical"}
    assert refused(physical, indexes=(A, B)) == (
        "settlement_method is 'physical', expected 'financial' with two indexes; a two-index "
        "physical settlement is outside this version"
    )
    window: dict[str, list[object]] = {k: v for k, v in TICKET.items() if k != "contract_code"}
    window["start_date"], window["end_date"] = ["2027-01-15"], ["2027-02-14"]
    onetime = {
        **BILATERAL,
        "schedule_method": "asian",
        "settlement_frequency": "onetime",
        "quantity_per": "period",
    }
    assert refused(onetime, window, (A, B)) == (
        "settlement_frequency of trade 1 at row 1 is 'onetime', expected 'monthly' with two "
        "indexes; a onetime period on a pair is not built"
    )
    assert refused({**BILATERAL, "schedule_method": "asian", "nearby": 2.0}, indexes=(A, B)) == (
        "nearby of trade 1 at row 1 is 2, expected 1 with two indexes; a later nearby on a pair "
        "is not built"
    )
    assert refused({**BILATERAL, "quantity_unit": "LOT"}, indexes=(A, B)) == (
        "quantity_unit 'LOT' of trade 1 at row 1 is 10000.0 MMBTU on index 'A' and 2500.0 MMBTU "
        "on index 'B', expected one quantity per entered unit on both legs"
    )


def test_a_fixed_float_pair_on_the_same_indexes_is_as_it_was() -> None:
    # The same two indexes and the same row under a fixed_float: the sum against the price, the
    # second leg received, its handle joined by a plus.
    rows: dict[str, list[object]] = {k: v for k, v in TICKET.items() if k != "spread_price"}
    rows["fixed_price"] = [-0.75]
    pair = trades((NTO, PAN), a_ticket(rows), a_template(PAIR_BILATERAL), UNITS, WorkCounter())
    assert pair.resolved.descriptor == "NTO+PAN"
    assert [leg.subtracted for leg in pair.resolved.legs] == [False, False]
    results = valued(pair)
    close(results.payment_amount, [1_000.0])  # -0.25 and -0.40 are -0.65, less -0.75
    assert [leg.nominal_delta_total for leg in results.legs] == [4.0, 4.0]


# --- the spread on the sheet ----------------------------------------------------------------------

FIELDS = (
    "trade_id, trade_date, contract_code, start_date, end_date, schedule_method, route, "
    "settlement_method, clearing_house, counterparty, discount_curve_key, broker, quantity, "
    "quantity_unit, quantity_per, {price}, second_schedule_method, payment_day, "
    "payment_holiday_calendar, marketing_reserve, cva_reserve, settlement_frequency, nearby"
)
SPREAD_FIELDS = FIELDS.format(
    price="spread_price, spread_price_currency_unit, spread_price_quantity_unit"
)
TEMPLATE_FIELDS = (
    "spread_price_currency_unit",
    "spread_price_quantity_unit",
    "quantity_unit",
    "quantity_per",
    "settlement_frequency",
    "nearby",
    "schedule_method",
    "second_schedule_method",
    "route",
    "settlement_method",
    "counterparty",
    "discount_curve_key",
    "payment_day",
    "payment_holiday_calendar",
)


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The pair test's sheet, A a futures index and B an IFERC one, both defining the NYMEX NG
    lot of 10,000 MMBTU, G27 quoted 3.50 and -0.40 on 4 January 2027, with a float_float
    template and the row of one lot of A less B at a spread price of 3.80."""
    cells = the_sheet()
    cells["template"] = SEAM["_CreateTradeTemplate"](
        "float_float",
        across(*TEMPLATE_FIELDS),
        across(
            "USD",
            "MMBTU",
            "NYMEX NG",
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
            cells["holidays"],
        ),
    )
    cells["headers"] = across("trade_id", "trade_date", "contract_code", "quantity", "spread_price")
    cells["row"] = across(1.0, serial("2026-12-15"), "G27", 1.0, 3.80)
    return cells


def test_the_sheet_books_prepares_and_values_a_spread(sheet: dict[str, Any]) -> None:
    booked_ = SEAM["_CreateTrades"](
        down(sheet["a"], sheet["b"]), sheet["headers"], sheet["row"], sheet["template"]
    )
    assert re.fullmatch(rf"{PID}:trades:A-B:\d+", str(booked_))
    table = read(booked_)
    assert under(table, "spread_price") == [3.8] and "fixed_price" not in table[0]
    assert under(table, "offset") == pytest.approx([-38_000.0], **CLOSE)
    prepared = SEAM["_PrepareTrades"](booked_, down(sheet["hist_b"], sheet["hist_a"]))
    assert re.fullmatch(rf"{PID}:prepared_trades:A-B:\d+", str(prepared))
    assert under(read(prepared), "live_lots") == pytest.approx([1.0, -1.0], **CLOSE)
    results = SEAM["_EvaluateTrades"](
        prepared, across(sheet["market_a"], sheet["market_b"]), sheet["curves"]
    )
    assert re.fullmatch(rf"{PID}:trade_results:A-B:\d+", str(results))
    values = spilled(SEAM["_ReportValues"](results))
    assert values[0][0] == "bilateral_mark"
    # 3.50 less -0.40 is 3.90, a dime over the spread price: 1,000 at 0.95.
    assert values[2][0] == pytest.approx(950.0, **CLOSE) and values[2][1] == 0.0
    risk = spilled(SEAM["_ReportRisk"](results, "all", "day"))
    assert risk[1][1:] == [
        "A nominal_delta [NYMEX NG]",
        "A delta [NYMEX NG]",
        "B nominal_delta [NYMEX NG]",
        "B delta [NYMEX NG]",
        "SOFR USD dv01 [USD per basis point]",
        "A SOFR cross_gamma [NYMEX NG per basis point]",
        "B SOFR cross_gamma [NYMEX NG per basis point]",
    ]
    assert risk[3][1:] == pytest.approx(
        [1.0, 0.95, -1.0, -0.95, -0.095, -0.000095, 0.000095], **CLOSE
    )
    slots = read(results)
    assert under(slots, "index") == ["A", "B"]
    assert under(slots, "floating_contribution") == pytest.approx([35_000.0, 4_000.0], **CLOSE)
    # The other order is the other spread: B less A, the handle saying so.
    assert re.fullmatch(
        rf"{PID}:trades:B-A:\d+",
        str(
            SEAM["_CreateTrades"](
                across(sheet["b"], sheet["a"]), sheet["headers"], sheet["row"], sheet["template"]
            )
        ),
    )


def test_the_sheet_refuses_what_a_spread_does_not_book(sheet: dict[str, Any]) -> None:
    create = SEAM["_CreateTrades"]
    both = down(sheet["a"], sheet["b"])
    # Each instrument refuses the other's price at the header, as any unknown field.
    fixed = across("trade_id", "trade_date", "contract_code", "quantity", "fixed_price")
    assert create(both, fixed, sheet["row"], sheet["template"]) == (
        "#ERROR _CreateTrades: fields cell (1, 5) is text 'fixed_price', expected a field of "
        f"float_float: {SPREAD_FIELDS}"
    )
    assert create(both, sheet["headers"], sheet["row"], the_sheet()["template"]) == (
        "#ERROR _CreateTrades: fields cell (1, 5) is text 'spread_price', expected a field of "
        f"fixed_float: {FIELDS.format(price='fixed_price')}"
    )
    assert SEAM["_CreateTradeTemplate"](
        "float_float", across("route", "fixed_price"), across("bilateral", 3.0)
    ) == (
        "#ERROR _CreateTradeTemplate: fields cell (1, 2) is text 'fixed_price', expected a field "
        f"of float_float: {SPREAD_FIELDS}"
    )
    assert create(sheet["a"], sheet["headers"], sheet["row"], sheet["template"]) == (
        "#ERROR _CreateTrades: ValueError: indexes are 1, expected two with a float_float; a "
        "spread is the first index's price less the second's"
    )
    brokered = across(
        "trade_id", "trade_date", "contract_code", "quantity", "spread_price", "broker"
    )
    row = across(7.0, serial("2026-12-15"), "G27", 1.0, 3.80, "ICAP")
    assert create(both, brokered, row, sheet["template"]) == (
        "#ERROR _CreateTrades: ValueError: broker of trade 7 at row 1 is 'ICAP', expected none on "
        "a float_float; a brokered spread is not built"
    )
    # No quote prices a spread: its template is refused as a cashflow's is.
    assert bridge.entry("_CreateQuoteTemplate")(
        "float_float", across("route"), across("bilateral")
    ) == (
        "#ERROR _CreateQuoteTemplate: ValueError: instrument is 'float_float', expected one a "
        "quote prices: 'fixed_float'"
    )
    # A row of nothing books a spread leg of nothing and is kept, ready for a deal.
    kept = create(
        both,
        sheet["headers"],
        across(1.0, serial("2026-12-15"), "G27", 0.0, 3.80),
        sheet["template"],
    )
    assert under(read(kept), "offset") == [0.0]


def test_the_dates_helper_is_the_pair_tests() -> None:
    # The lifecycle's payment day, two business days after the later observation, B's
    # publication on 4 January 2027.
    terms = a_less_b().resolved
    assert terms.payment is not None
    np.testing.assert_array_equal(terms.payment.date, dates("2027-01-06"))
    assert day("2027-01-06") == terms.payment.date[0]
