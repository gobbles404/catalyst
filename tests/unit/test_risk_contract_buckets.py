"""Risk by pricing contract month, risk-contract-month-bucketing.md: the ticket's hand examples
through the seam. The month and year views of the deltas follow the contract supplying the price,
not the day it is observed on; the day view and the DV01's payment axis stand as they were. The
calendars are synthetic, weekdays only and closed on nothing before 2030, so the arithmetic owes
nothing to any exchange's holidays."""

from typing import cast

import pytest
from test_trade_valuation import (
    ENTRY,
    a_history,
    a_market,
    an_index,
    risk_head,
    row,
    rows,
    serial,
    spilled,
    unit_curve,
)

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

NO_HOLIDAYS = ["2030-01-01"]
AS_OF = "2026-10-14"
HEADERS = ("trade_id", "trade_date", "contract_code", "quantity", "fixed_price")
FIELDS = (
    "quantity_unit",
    "quantity_per",
    "schedule_method",
    "route",
    "settlement_method",
    "clearing_house",
    "payment_time_lag",
    "payment_holiday_calendar",
)
# An NG-like index, one lot a unit: V26 the boundary, X26 observing 28 October, Z26 25 November and
# F27 29 December, each its month's last trading day under lastday.
NG_CONTRACTS = [
    ("V26", "2026-09-28"),
    ("X26", "2026-10-28"),
    ("Z26", "2026-11-25"),
    ("F27", "2026-12-29"),
]
# An ethane-like index whose contracts expire on their own month's last weekday: V26 prices every
# October day through the 30th.
ETHANE_CONTRACTS = [("U26", "2026-09-30"), ("V26", "2026-10-30"), ("X26", "2026-11-30")]


def an_ng() -> tuple[str, str]:
    return an_index("NG2", NG_CONTRACTS, NO_HOLIDAYS, [("LOT", 1.0)])


def an_ethane() -> tuple[str, str]:
    return an_index("ETH2", ETHANE_CONTRACTS, NO_HOLIDAYS, [("LOT", 1.0)])


def a_template(
    calendar: str,
    method: str = "lastday",
    route: str = "cleared",
    lag: str | None = "+2bd",
    counterparty: str | None = None,
) -> str:
    fields: list[str] = list(FIELDS)
    values: list[object] = [
        "LOT",
        "month",
        method,
        route,
        "financial",
        "Prototype Clearing",
        lag,
        calendar,
    ]
    if lag is None:
        k = fields.index("payment_time_lag")
        del fields[k], values[k]
    if route == "bilateral":  # a bilateral row faces a counterparty and names no clearing house
        k = fields.index("clearing_house")
        del fields[k], values[k]
        fields.insert(4, "counterparty")
        values.insert(4, counterparty)
    return str(ENTRY["_CreateTradeTemplate"]("fixed_float", row(*fields), row(*values)))


def booked(
    index: str, template: str, lines: list[list[object]], headers: tuple[str, ...] = HEADERS
) -> str:
    made = ENTRY["_CreateTrades"](index, row(*headers), rows(*lines), template)
    assert not str(made).startswith("#ERROR"), made
    return str(made)


def valued_on(trades: str, history: str, market: str, curve: object = bridge.MISSING) -> str:
    """The batch prepared against that history and valued on that market, the objects shared by
    every batch that is to collect with it."""
    results = ENTRY["_EvaluateTrades"](ENTRY["_PrepareTrades"](trades, history), market, curve)
    assert not str(results).startswith("#ERROR"), results
    return str(results)


def evaluated(
    trades: str,
    index: str,
    name: str,
    first: str,
    as_of: str,
    quotes: tuple[float, ...],
    curve: object = bridge.MISSING,
) -> str:
    history = a_history(index, first, as_of, NO_HOLIDAYS, {})
    return valued_on(trades, history, a_market(history, name, *quotes), curve)


def stacked(*handles: str) -> Cells:
    """A column of handles, as the sheet sends a range of cells to the collector."""
    return Cells.from_rows([[handle] for handle in handles])


def report(results: str, risk: str, bucket: str) -> list[list[object]]:
    return spilled(ENTRY["_ReportRisk"](results, risk, bucket))


def dated(results: str, risk: str, bucket: str) -> list[list[object]]:
    """The dated rows of a report, each the period's serial and the values."""
    return report(results, risk, bucket)[4:]


# --- NG futures and the current month
# -----------------------------------------------------------------


def test_november_ng_risk_stands_in_november_though_its_contract_observes_in_october() -> None:
    # +10 lots of X26 observing 28 October and +5 of Z26 observing 25 November, both live on
    # 14 October 2026: by day 10 on the 28th and 5 on the 25th; by month, since the contracts' own
    # months decide, 10 in November and 5 in December under an October row of zero, the
    # valuation month the spill starts at; by year 15 in 2026; the Total 15 on every view. Once
    # X26's observation fixes, its November row is kept at zero.
    index, calendar = an_ng()
    template = a_template(calendar)
    trades = booked(
        index,
        template,
        [
            [1.0, serial("2026-10-01"), "X26", 10.0, 3.0],
            [2.0, serial("2026-10-01"), "Z26", 5.0, 3.0],
        ],
    )
    results = evaluated(trades, index, "NG2", "2026-09-29", AS_OF, (3.2, 3.3, 3.4))
    assert report(results, "nominal_delta", "month") == [
        *risk_head(AS_OF, "NG2 nominal_delta [LOT]"),
        ["Total", 15.0],
        [serial("2026-10-01"), 0.0],
        [serial("2026-11-01"), 10.0],
        [serial("2026-12-01"), 5.0],
    ]
    assert dated(results, "delta", "month") == dated(results, "nominal_delta", "month")
    assert dated(results, "nominal_delta", "day") == [
        [serial("2026-10-28"), 10.0],
        [serial("2026-11-25"), 5.0],
    ]
    assert dated(results, "nominal_delta", "year") == [[serial("2026-01-01"), 15.0]]
    # Grouping the day rows by their calendar month gives October 10 and November 5, which the
    # month view no longer reproduces; every view keeps the saved Total.
    for bucket in ("day", "month", "year"):
        table = report(results, "all", bucket)
        assert table[3] == ["Total", 15.0, 15.0, 0.0, 0.0]
        assert sum(cast(float, line[1]) for line in table[4:]) == 15.0
    fixed = evaluated(trades, index, "NG2", "2026-09-29", "2026-10-29", (3.3, 3.4))
    assert report(fixed, "nominal_delta", "month")[3:] == [
        ["Total", 5.0],
        [serial("2026-10-01"), 0.0],
        [serial("2026-11-01"), 0.0],
        [serial("2026-12-01"), 5.0],
    ]
    assert dated(fixed, "nominal_delta", "day") == [
        [serial("2026-10-28"), 0.0],
        [serial("2026-11-25"), 5.0],
    ]


# --- the October ethane asian
# -------------------------------------------------------------------------


def test_an_october_ethane_asian_stands_in_october_when_v26_supplies_its_price() -> None:
    # +22 lots for October, a lot a weekday over its 22 weekdays, every day priced by V26, which
    # expires on the 30th: on 14 October nine days have fixed and thirteen are live, so the month
    # view is October 13 and the Total 13; no November row appears for the payment in November.
    index, calendar = an_ethane()
    trades = booked(
        index, a_template(calendar, method="asian"), [[3.0, serial("2026-10-01"), "V26", 22.0, 3.0]]
    )
    results = evaluated(trades, index, "ETH2", "2026-10-01", AS_OF, (3.1, 3.2))
    assert report(results, "nominal_delta", "month")[3:] == [
        ["Total", 13.0],
        [serial("2026-10-01"), 13.0],
    ]
    days = dated(results, "nominal_delta", "day")
    assert len(days) == 22 and sum(cast(float, line[1]) for line in days) == 13.0
    assert [line[1] for line in days] == [0.0] * 9 + [1.0] * 13
    assert dated(results, "nominal_delta", "year") == [[serial("2026-01-01"), 13.0]]


# --- the October NG asian across a roll
# -----------------------------------------------------------------


def test_an_october_ng_asian_splits_between_the_contracts_pricing_its_days() -> None:
    # The same 22-weekday window booked as V26 on the NG-like index, where X26 prices through
    # 28 October and Z26 from the 29th: on 14 October eleven live days reference X26 and two Z26,
    # so the month view is November 11 and December 2 under an October row of zero, the Total 13,
    # the booked code's October holding nothing. On 29 October, every X26 day fixed, November is
    # zero and December still 2.
    index, calendar = an_ng()
    trades = booked(
        index, a_template(calendar, method="asian"), [[4.0, serial("2026-10-01"), "V26", 22.0, 3.0]]
    )
    results = evaluated(trades, index, "NG2", "2026-09-29", AS_OF, (3.2, 3.3, 3.4))
    assert report(results, "nominal_delta", "month")[3:] == [
        ["Total", 13.0],
        [serial("2026-10-01"), 0.0],
        [serial("2026-11-01"), 11.0],
        [serial("2026-12-01"), 2.0],
    ]
    assert dated(results, "nominal_delta", "year") == [[serial("2026-01-01"), 13.0]]
    rolled = evaluated(trades, index, "NG2", "2026-09-29", "2026-10-29", (3.3, 3.4))
    assert report(rolled, "nominal_delta", "month")[3:] == [
        ["Total", 2.0],
        [serial("2026-10-01"), 0.0],
        [serial("2026-11-01"), 0.0],
        [serial("2026-12-01"), 2.0],
    ]


# --- a December observation referencing F27
# ---------------------------------------------------------------


def test_a_december_observation_of_f27_reports_in_january_2027_and_in_2027() -> None:
    # One lot of F27 under lastday observes 29 December 2026: the day view keeps that day, the
    # month view shows January 2027 under three zero months from October, and the year view 2027
    # under a zero 2026, the contract's year and not the observation's.
    index, calendar = an_ng()
    trades = booked(index, a_template(calendar), [[5.0, serial("2026-10-01"), "F27", 1.0, 3.0]])
    results = evaluated(trades, index, "NG2", "2026-09-29", AS_OF, (3.2, 3.3, 3.4))
    assert dated(results, "nominal_delta", "day") == [[serial("2026-12-29"), 1.0]]
    assert dated(results, "nominal_delta", "month") == [
        [serial("2026-10-01"), 0.0],
        [serial("2026-11-01"), 0.0],
        [serial("2026-12-01"), 0.0],
        [serial("2027-01-01"), 1.0],
    ]
    assert dated(results, "nominal_delta", "year") == [
        [serial("2026-01-01"), 0.0],
        [serial("2027-01-01"), 1.0],
    ]


# --- discounting and collection
# -----------------------------------------------------------------------------


def test_discounting_and_collection_keep_the_contract_month_and_the_payment_month_apart() -> None:
    # Cleared +10 and bilateral +10 of X26, the bilateral paying two business days after the 28th,
    # on 30 October, at a factor of 0.95: collected, November's nominal delta is 20 and its delta
    # 19.5, the DV01 on the payment's month, October; at 0.90 the delta is 19, the nominal 20 and
    # no date moves. Two bilateral groups on X26 at different factors keep both before the sum.
    index, calendar = an_ng()
    cleared = booked(index, a_template(calendar), [[1.0, serial("2026-10-01"), "X26", 10.0, 3.0]])
    bilateral_template = a_template(calendar, route="bilateral", counterparty="ACME Trading")
    bilateral = booked(index, bilateral_template, [[2.0, serial("2026-10-01"), "X26", 10.0, 3.0]])
    history = a_history(index, "2026-09-29", AS_OF, NO_HOLIDAYS, {})
    market = a_market(history, "NG2", 3.2, 3.3, 3.4)
    cleared_results = valued_on(cleared, history, market)
    for factor, delta in ((0.95, 19.5), (0.90, 19.0)):
        curve = unit_curve((AS_OF, 1.0), ("2026-10-30", factor))
        bilateral_results = valued_on(bilateral, history, market, curve)
        collection = str(ENTRY["_AggregateResults"](stacked(cleared_results, bilateral_results)))
        assert report(collection, "nominal_delta", "month")[3:] == [
            ["Total", 20.0],
            [serial("2026-10-01"), 0.0],
            [serial("2026-11-01"), 20.0],
        ]
        assert report(collection, "delta", "month")[3:] == [
            ["Total", pytest.approx(delta)],
            [serial("2026-10-01"), 0.0],
            [serial("2026-11-01"), pytest.approx(delta)],
        ]
        everything = report(collection, "all", "month")
        # Since #197 the cross-gamma of the two pairs, the cleared one nothing and the bilateral
        # one its 10 lots at the factor times sixteen days over 365 per basis point, on the
        # contract's November as the delta is and not on the payment's October.
        cross = -0.0001 * 16 / 365 * (delta - 10.0)
        assert everything[1] == [
            "period",
            "NG2 nominal_delta [LOT]",
            "NG2 delta [LOT]",
            "SOFR USD dv01 [USD per basis point]",
            "NG2 cleared cross_gamma [LOT per basis point]",
            "NG2 SOFR cross_gamma [LOT per basis point]",
        ]
        dv01 = cast(float, everything[3][3])
        assert dv01 != 0.0
        assert everything[4:] == [
            [serial("2026-10-01"), 0.0, 0.0, pytest.approx(dv01), 0.0, 0.0],
            [serial("2026-11-01"), 20.0, pytest.approx(delta), 0.0, 0.0, pytest.approx(cross)],
        ]
        assert dated(collection, "dv01", "month") == [[serial("2026-10-01"), pytest.approx(dv01)]]
    two_groups = booked(
        index,
        a_template(calendar, route="bilateral", lag=None, counterparty="ACME Trading"),
        [
            [6.0, serial("2026-10-01"), "X26", 10.0, 3.0, "+2bd"],
            [7.0, serial("2026-10-01"), "X26", 10.0, 3.0, "+5bd"],
        ],
        (*HEADERS, "payment_time_lag"),
    )
    curve = unit_curve((AS_OF, 1.0), ("2026-10-30", 0.95), ("2026-11-04", 0.90))
    results = valued_on(two_groups, history, market, curve)
    table = report(results, "all", "month")
    dv01 = cast(float, table[3][3])
    assert table[3][:3] == ["Total", 20.0, pytest.approx(18.5)] and dv01 != 0.0
    # The deltas on the contract's November; the DV01 on the two payment months, October and
    # November, each group's own, summing to the Total.
    assert [line[0] for line in table[4:]] == [serial("2026-10-01"), serial("2026-11-01")]
    assert [line[1] for line in table[4:]] == [0.0, 20.0]
    assert [line[2] for line in table[4:]] == [0.0, pytest.approx(18.5)]
    assert all(cast(float, line[3]) != 0.0 for line in table[4:])
    assert sum(cast(float, line[3]) for line in table[4:]) == pytest.approx(dv01)
    by_day = dated(results, "dv01", "day")
    assert [line[0] for line in by_day] == [serial("2026-10-30"), serial("2026-11-04")]
    assert all(cast(float, line[1]) != 0.0 for line in by_day)


def test_ng_and_ethane_collect_under_their_own_columns_on_one_month_axis() -> None:
    # The NG example and the ethane asian on 14 October, collected: one month axis, October,
    # November
    # and December, with October ethane under its column and November and December NG under theirs;
    # the sources reordered or repeated change the columns' order or double a column and nothing
    # else.
    ng, ng_calendar = an_ng()
    ethane, ethane_calendar = an_ethane()
    ng_results = evaluated(
        booked(
            ng,
            a_template(ng_calendar),
            [
                [1.0, serial("2026-10-01"), "X26", 10.0, 3.0],
                [2.0, serial("2026-10-01"), "Z26", 5.0, 3.0],
            ],
        ),
        ng,
        "NG2",
        "2026-09-29",
        AS_OF,
        (3.2, 3.3, 3.4),
    )
    ethane_results = evaluated(
        booked(
            ethane,
            a_template(ethane_calendar, method="asian"),
            [[3.0, serial("2026-10-01"), "V26", 22.0, 3.0]],
        ),
        ethane,
        "ETH2",
        "2026-10-01",
        AS_OF,
        (3.1, 3.2),
    )
    collection = str(ENTRY["_AggregateResults"](stacked(ng_results, ethane_results)))
    assert report(collection, "nominal_delta", "month")[1:] == [
        ["period", "NG2 nominal_delta [LOT]", "ETH2 nominal_delta [LOT]"],
        ["str | datetime64[D]", "float64", "float64"],
        ["Total", 15.0, 13.0],
        [serial("2026-10-01"), 0.0, 13.0],
        [serial("2026-11-01"), 10.0, 0.0],
        [serial("2026-12-01"), 5.0, 0.0],
    ]
    reordered = str(ENTRY["_AggregateResults"](stacked(ethane_results, ng_results, ng_results)))
    assert report(reordered, "nominal_delta", "month")[1:] == [
        ["period", "ETH2 nominal_delta [LOT]", "NG2 nominal_delta [LOT]"],
        ["str | datetime64[D]", "float64", "float64"],
        ["Total", 13.0, 30.0],
        [serial("2026-10-01"), 13.0, 0.0],
        [serial("2026-11-01"), 0.0, 20.0],
        [serial("2026-12-01"), 0.0, 10.0],
    ]
    assert dated(collection, "nominal_delta", "year") == [[serial("2026-01-01"), 15.0, 13.0]]


# --- the display start and the refusal of older risk ------------------------------------------


def test_the_period_spill_starts_at_the_valuation_month_and_refuses_older_live_risk() -> None:
    # On an index whose U26 keeps trading to 15 October 2026, three lots of U26 are live on
    # 14 October in a contract month before the valuation month: the day view shows them on the
    # 15th, the year view in 2026, and the month view is refused in words naming the index, the
    # month, the lots and the valuation day rather than shown from October with September gone;
    # a report of all three is refused the same way. Once U26 has fixed, on the 16th, the month
    # view starts at October with zero and shows no September row, and the refusal is gone. A
    # contract year before the valuation year is refused by the year view the same way.
    index, calendar = an_index(
        "NG3",
        [("Q26", "2026-08-27"), ("U26", "2026-10-15"), ("X26", "2026-10-28")],
        NO_HOLIDAYS,
        [("LOT", 1.0)],
    )
    trades = booked(index, a_template(calendar), [[8.0, serial("2026-10-01"), "U26", 3.0, 3.0]])
    results = evaluated(trades, index, "NG3", "2026-08-28", AS_OF, (3.2, 3.3))
    assert dated(results, "nominal_delta", "day") == [[serial("2026-10-15"), 3.0]]
    assert dated(results, "nominal_delta", "year") == [[serial("2026-01-01"), 3.0]]
    refused = (
        "#ERROR _ReportRisk: ValueError: the nominal delta of index 'NG3' in the contract "
        "month from 2026-09-01 is 3.0 lots of LOT (1 MMBTU), before the report's first month, "
        "2026-10-01, the month of as_of 2026-10-14; the day view shows where it stands"
    )
    assert ENTRY["_ReportRisk"](results, "nominal_delta", "month") == refused
    assert ENTRY["_ReportRisk"](results, "all", "month") == refused
    assert ENTRY["_ReportRisk"](results, "delta", "month") == refused.replace(
        "nominal delta", "delta"
    )
    fixed = evaluated(trades, index, "NG3", "2026-08-28", "2026-10-16", (3.3,))
    assert report(fixed, "nominal_delta", "month")[3:] == [
        ["Total", 0.0],
        [serial("2026-10-01"), 0.0],
    ]
    # A collection of the refused result is refused the same way, its index named.
    collection = str(ENTRY["_AggregateResults"](stacked(results)))
    assert ENTRY["_ReportRisk"](collection, "nominal_delta", "month") == refused
    assert dated(collection, "nominal_delta", "day") == [[serial("2026-10-15"), 3.0]]
    # The year: Z26, a December 2026 contract, still trading on 5 January 2027, its expiry the 11th.
    index, calendar = an_index(
        "NG4",
        [("X26", "2026-10-28"), ("Z26", "2027-01-11"), ("F27", "2027-01-27")],
        NO_HOLIDAYS,
        [("LOT", 1.0)],
    )
    trades = booked(index, a_template(calendar), [[9.0, serial("2026-11-02"), "Z26", 2.0, 3.0]])
    results = evaluated(trades, index, "NG4", "2026-10-29", "2027-01-05", (3.2, 3.3))
    assert ENTRY["_ReportRisk"](results, "nominal_delta", "month") == (
        "#ERROR _ReportRisk: ValueError: the nominal delta of index 'NG4' in the contract "
        "month from 2026-12-01 is 2.0 lots of LOT (1 MMBTU), before the report's first month, "
        "2027-01-01, the month of as_of 2027-01-05; the day view shows where it stands"
    )
    assert ENTRY["_ReportRisk"](results, "nominal_delta", "year") == (
        "#ERROR _ReportRisk: ValueError: the nominal delta of index 'NG4' in the contract "
        "year from 2026-01-01 is 2.0 lots of LOT (1 MMBTU), before the report's first year, "
        "2027-01-01, the year of as_of 2027-01-05; the day view shows where it stands"
    )
    assert dated(results, "nominal_delta", "day") == [[serial("2027-01-11"), 2.0]]


def test_an_all_fixed_result_shows_the_valuation_period_alone_and_a_later_payment_extends_all() -> (
    None
):
    # Every contract fixed: the month view is the valuation month at zero and nothing else; a
    # bilateral result whose payment falls later extends all three through the payment month
    # while the delta alone stops at the last contract month.
    index, calendar = an_ng()
    trades = booked(index, a_template(calendar), [[1.0, serial("2026-10-01"), "X26", 10.0, 3.0]])
    fixed = evaluated(trades, index, "NG2", "2026-09-29", "2026-12-01", (3.4,))
    assert report(fixed, "nominal_delta", "month")[3:] == [
        ["Total", 0.0],
        [serial("2026-12-01"), 0.0],
    ]
    assert report(fixed, "nominal_delta", "year")[3:] == [
        ["Total", 0.0],
        [serial("2026-01-01"), 0.0],
    ]
    bilateral = booked(
        index,
        a_template(calendar, route="bilateral", lag="+15bd", counterparty="ACME Trading"),
        [[2.0, serial("2026-10-01"), "X26", 10.0, 3.0]],
    )
    history = a_history(index, "2026-09-29", AS_OF, NO_HOLIDAYS, {})
    market = a_market(history, "NG2", 3.2, 3.3, 3.4)
    curve = unit_curve((AS_OF, 1.0), ("2026-11-18", 0.95))
    results = valued_on(bilateral, history, market, curve)
    assert [line[0] for line in dated(results, "delta", "month")] == [
        serial("2026-10-01"),
        serial("2026-11-01"),
    ]
    assert [line[0] for line in dated(results, "dv01", "month")] == [
        serial("2026-10-01"),
        serial("2026-11-01"),
    ]
    assert [line[0] for line in dated(results, "all", "month")] == [
        serial("2026-10-01"),
        serial("2026-11-01"),
    ]
