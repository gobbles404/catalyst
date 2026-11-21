"""Aggregate evaluated risk in Excel, aggregate-risk-excel-integration.md: `_AggregateResults`
over a cell, a row or a column of results handles, and `_ReportRisk` over the collection's handle
as over a result's, through the seam. The ticket's four sources on one-unit HNG and WTI indexes,
valued on 4 January 2027: HNG observing that day at 80 against 70, WTI on the 5th at 55 against 50,
the bilateral sources paying on 4 January 2028 on one USD curve of 0.95, every number priced by
hand.
docs/library/trades/aggregate-results.md is the page."""

import os
import re
from typing import Any, cast

import pytest
from test_trade_valuation import (
    A_YEAR_OUT,
    CLEARED_DV01,
    CURVE_DV01,
    ENTRY,
    TWO_YEARS_OUT,
    UNIT_AS_OF,
    UNIT_FIELDS,
    UNIT_HEADERS,
    UNIT_HOLIDAYS,
    a_history,
    a_market,
    an_index,
    column,
    curves_of,
    risk_head,
    row,
    rows,
    serial,
    spilled,
    templated,
    unit_curve,
)

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells

AS_OF = UNIT_AS_OF
JAN_27, JAN_28 = "2027-01-01", "2028-01-01"
HNG_NOMINAL, HNG_DELTA = "HNG nominal_delta [LOT]", "HNG delta [LOT]"
WTI_NOMINAL, WTI_DELTA = "WTI nominal_delta [LOT]", "WTI delta [LOT]"
HNG_CROSS = "HNG SOFR cross_gamma [LOT per basis point]"
HNG_CLEARED_CROSS = "HNG cleared cross_gamma [LOT per basis point]"
WTI_CROSS = "WTI SOFR cross_gamma [LOT per basis point]"
WTI_CLEARED_CROSS = "WTI cleared cross_gamma [LOT per basis point]"
PER_BP = "lots of LOT (1 BBL) per basis point"
READBACK_HEADERS = [
    "position",
    "index",
    "reporting_lot",
    "route",
    "curve",
    "currency",
    "nominal_delta",
    "delta",
    "dv01",
    "as_of",
    "cross_gamma",
    "cross_gamma_unit",
    "currency_unit",  # last, since currency-and-currency-unit.md
]
READBACK_TYPES = [
    "int64",
    "str",
    "str",
    "str",
    "str",
    "str",
    "float64",
    "float64",
    "float64",
    "datetime64[D]",
    "float64",
    "str",
    "str",
]


def one_unit_index(name: str, expiry: str) -> str:
    index, _ = an_index(
        name,
        [("Z26", "2026-12-31"), ("F27", expiry), ("F29", "2029-01-05")],
        UNIT_HOLIDAYS,
        [("LOT", 1.0)],
        ("VOLUME", "BBL"),
    )
    return index


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The ticket's sheet: B2 HNG cleared +10, B3 HNG bilateral +10, B4 WTI cleared +2 and B5 WTI
    bilateral +4, each index's two sources on one history and one market; the bilateral two on
    one curve of 0.95 a year out; the templates, headers, histories and markets kept for the
    moves."""
    hng = one_unit_index("HNG", "2027-01-04")
    wti = one_unit_index("WTI", "2027-01-05")
    payments = str(ENTRY["_CreateHolidayCalendar"](column([serial("2030-01-01")])))
    bilateral = str(
        templated(
            [*UNIT_FIELDS],
            [
                "LOT",
                "month",
                "lastday",
                "bilateral",
                "financial",
                "ACME Trading",
                "SOFR",
                payments,
                0.0,
            ],
        )
    )
    cleared = str(
        templated(
            [*UNIT_FIELDS[:5], "clearing_house", *UNIT_FIELDS[7:]],
            [
                "LOT",
                "month",
                "lastday",
                "cleared",
                "financial",
                "Prototype Clearing",
                payments,
                0.0,
            ],
        )
    )
    hng_history = a_history(hng, "2027-01-01", AS_OF, UNIT_HOLIDAYS, {})
    wti_history = a_history(wti, "2027-01-01", AS_OF, UNIT_HOLIDAYS, {})
    curve = unit_curve((AS_OF, 1.0), (A_YEAR_OUT, 0.95), (TWO_YEARS_OUT, 0.90))
    state = {
        "hng": hng,
        "wti": wti,
        "bilateral": bilateral,
        "cleared": cleared,
        "headers": row(*UNIT_HEADERS),
        "hng_history": hng_history,
        "hng_market": a_market(hng_history, "HNG", 80.0, 50.0),
        "wti_history": wti_history,
        "wti_market": a_market(wti_history, "WTI", 55.0, 50.0),
        "curve": curve,
    }
    state["b2"] = valued(state, "hng", 1001, 10.0, 70.0, "+261bd", "cleared", bridge.MISSING)
    state["b3"] = valued(state, "hng", 1002, 10.0, 70.0, "+261bd", "bilateral", curve)
    state["b4"] = valued(state, "wti", 1003, 2.0, 50.0, "+260bd", "cleared", bridge.MISSING)
    state["b5"] = valued(state, "wti", 1004, 4.0, 50.0, "+260bd", "bilateral", curve)
    return state


def valued(
    state: dict[str, Any],
    which: str,
    trade_id: int,
    lots: float,
    fixed: float,
    lag: str,
    template: str,
    curve: object,
    market: str | None = None,
    history: str | None = None,
) -> str:
    """One F27 trade of the index, booked on the valuation day, prepared against the index's
    history and valued against its market, or the market given."""
    trades = ENTRY["_CreateTrades"](
        state[which],
        state["headers"],
        rows([float(trade_id), serial(AS_OF), "F27", lots, fixed, lag]),
        state[template],
    )
    prepared = ENTRY["_PrepareTrades"](trades, history or state[f"{which}_history"])
    return str(
        ENTRY["_EvaluateTrades"](prepared, market or state[f"{which}_market"], curves_of(curve))
    )


def stacked(values: list[object]) -> Cells:
    """A column of cells, as the host sends one."""
    return Cells.from_rows([[value] for value in values])


def beside(*values: object) -> Cells:
    """A row of cells, as the host sends one."""
    return Cells.from_rows([list(values)])


def collected(*handles: object) -> str:
    return str(ENTRY["_AggregateResults"](stacked(list(handles))))


def report(results: object, risk: str, bucket: str) -> list[list[object]]:
    return spilled(ENTRY["_ReportRisk"](results, risk, bucket))


def test_the_sources_value_as_the_ticket_says(sheet: dict[str, Any]) -> None:
    for key, nominal, delta, dv01, cross in (
        ("b2", 10.0, 10.0, 0.0, 0.0),
        ("b3", 10.0, 9.5, -0.0095, -0.00095),
        ("b4", 2.0, 2.0, 0.0, 0.0),
        ("b5", 4.0, 3.8, -0.0019, -0.00038),
    ):
        total = report(sheet[key], "all", "year")[3]
        assert total[0] == "Total"
        assert total[1:] == [
            pytest.approx(nominal),
            pytest.approx(delta),
            pytest.approx(dv01),
            pytest.approx(cross),
        ]


def test_two_hng_sources_collect_into_one_handle_the_reader_takes(sheet: dict[str, Any]) -> None:
    # B2:B3 as a column: one handle of the new kind, no index name in it; all three by month under
    # the HNG labels and SOFR, the Total 20, 19.5 and -0.0095 over January 2027's lots and
    # January 2028's DV01, the eleven months between at zero since #186, the spill running from
    # the valuation month to the last payment month.
    agg = collected(sheet["b2"], sheet["b3"])
    assert re.fullmatch(rf"{os.getpid()}:aggregate_results:\d+", agg)
    between = [serial(f"2027-{m:02d}-01") for m in range(2, 13)]
    assert report(agg, "all", "month") == [
        *risk_head(AS_OF, HNG_NOMINAL, HNG_DELTA, CURVE_DV01, HNG_CLEARED_CROSS, HNG_CROSS),
        ["Total", 20.0, pytest.approx(19.5), pytest.approx(-0.0095), 0.0, pytest.approx(-0.00095)],
        [serial(JAN_27), 20.0, pytest.approx(19.5), 0.0, 0.0, pytest.approx(-0.00095)],
        *[[m, 0.0, 0.0, 0.0, 0.0, 0.0] for m in between],
        [serial(JAN_28), 0.0, 0.0, pytest.approx(-0.0095), 0.0, 0.0],
    ]
    assert report(agg, "delta", "day") == [
        *risk_head(AS_OF, HNG_DELTA),
        ["Total", pytest.approx(19.5)],
        [serial(AS_OF), pytest.approx(19.5)],
    ]
    assert report(agg, "dv01", "day")[3:] == [
        ["Total", pytest.approx(-0.0095)],
        [serial(A_YEAR_OUT), pytest.approx(-0.0095)],
    ]


def test_the_four_sources_spill_the_tickets_table(sheet: dict[str, Any]) -> None:
    # B2:B5: HNG's pair of columns, WTI's pair and the one curve's DV01; by month the lots in
    # January 2027 and the rate risk in January 2028 with the months between at zero, by day HNG
    # on the 4th, WTI on the 5th and the rate on 4 January 2028; a delta report stops at the
    # contract month and a DV01 report runs from the valuation month to the payment month.
    agg = collected(*(sheet[k] for k in ("b2", "b3", "b4", "b5")))
    between = [serial(f"2027-{m:02d}-01") for m in range(2, 13)]
    crosses = [0.0, pytest.approx(-0.00095), 0.0, pytest.approx(-0.00038)]  # since #197
    assert report(agg, "all", "month") == [
        *risk_head(
            AS_OF,
            HNG_NOMINAL,
            HNG_DELTA,
            WTI_NOMINAL,
            WTI_DELTA,
            CURVE_DV01,
            HNG_CLEARED_CROSS,
            HNG_CROSS,
            WTI_CLEARED_CROSS,
            WTI_CROSS,
        ),
        [
            "Total",
            20.0,
            pytest.approx(19.5),
            6.0,
            pytest.approx(5.8),
            pytest.approx(-0.0114),
            *crosses,
        ],
        [serial(JAN_27), 20.0, pytest.approx(19.5), 6.0, pytest.approx(5.8), 0.0, *crosses],
        *[[m, *[0.0] * 9] for m in between],
        [serial(JAN_28), 0.0, 0.0, 0.0, 0.0, pytest.approx(-0.0114), *[0.0] * 4],
    ]
    by_day = report(agg, "all", "day")
    assert [line[0] for line in by_day[4:]] == [
        serial(AS_OF),
        serial("2027-01-05"),
        serial(A_YEAR_OUT),
    ]
    assert by_day[4][1:] == [20.0, pytest.approx(19.5), 0.0, 0.0, 0.0, 0.0, crosses[1], 0.0, 0.0]
    assert by_day[5][1:] == [0.0, 0.0, 6.0, pytest.approx(5.8), 0.0, 0.0, 0.0, 0.0, crosses[3]]
    assert by_day[6][1:] == [0.0, 0.0, 0.0, 0.0, pytest.approx(-0.0114), *[0.0] * 4]
    assert [line[0] for line in report(agg, "nominal_delta", "day")[4:]] == [
        serial(AS_OF),
        serial("2027-01-05"),
    ]
    assert report(agg, "dv01", "month")[3:] == [
        ["Total", pytest.approx(-0.0114)],
        [serial(JAN_27), 0.0],
        *[[m, 0.0] for m in between],
        [serial(JAN_28), pytest.approx(-0.0114)],
    ]
    for risk, bucket in (
        ("nominal_delta", "day"),
        ("delta", "month"),
        ("dv01", "year"),
        ("all", "year"),
    ):
        view = report(agg, risk, bucket)
        for j in range(1, len(view[1])):
            assert sum(cast(float, line[j]) for line in view[4:]) == pytest.approx(view[3][j])


def test_a_row_a_cell_and_a_repeat_collect_as_the_ticket_says(sheet: dict[str, Any]) -> None:
    # A row of the four is the column's collection to the cell; one cell is the one source's own
    # report through the collector, every selection and bucket; a repeat counts again, HNG cleared,
    # bilateral and cleared again 30, 29.5 and -0.0095.
    b2, b3, b4, b5 = (sheet[k] for k in ("b2", "b3", "b4", "b5"))
    as_row = str(ENTRY["_AggregateResults"](beside(b2, b3, b4, b5)))
    assert report(as_row, "all", "day") == report(collected(b2, b3, b4, b5), "all", "day")
    alone = str(ENTRY["_AggregateResults"](b3))
    boxed = str(ENTRY["_AggregateResults"](Cells.from_rows([[b3]])))
    assert re.fullmatch(rf"{os.getpid()}:aggregate_results:\d+", alone) and alone != boxed
    for risk in ("nominal_delta", "delta", "dv01", "all"):
        for bucket in ("day", "month", "year"):
            assert report(alone, risk, bucket) == report(b3, risk, bucket), (risk, bucket)
            assert report(boxed, risk, bucket) == report(b3, risk, bucket), (risk, bucket)
    thrice = collected(b2, b3, b2)
    assert report(thrice, "all", "year")[3] == [
        "Total",
        30.0,
        pytest.approx(29.5),
        pytest.approx(-0.0095),
        0.0,
        pytest.approx(-0.00095),
    ]


def test_the_readback_lists_the_membership_in_the_order_given(sheet: dict[str, Any]) -> None:
    # One row per occurrence: its position, index, lot, route, the collection's curve number or a
    # dash, currency, its own three saved numbers and the day; a repeat a row again; no handle text.
    b2, b3, b4, b5 = (sheet[k] for k in ("b2", "b3", "b4", "b5"))
    table = spilled(ENTRY["util_ReadHandle"](collected(b2, b3, b4, b5)))
    assert table[:2] == [READBACK_HEADERS, READBACK_TYPES]
    assert table[2:] == [
        [
            1.0,
            "HNG",
            "LOT",
            "cleared",
            "-",
            "USD",
            10.0,
            10.0,
            0.0,
            serial(AS_OF),
            0.0,
            PER_BP,
            "USD",
        ],
        [
            2.0,
            "HNG",
            "LOT",
            "bilateral",
            "SOFR",
            "USD",
            10.0,
            pytest.approx(9.5),
            pytest.approx(-0.0095),
            serial(AS_OF),
            pytest.approx(-0.00095),
            PER_BP,
            "USD",
        ],
        [
            3.0,
            "WTI",
            "LOT",
            "cleared",
            "-",
            "USD",
            2.0,
            2.0,
            0.0,
            serial(AS_OF),
            0.0,
            PER_BP,
            "USD",
        ],
        [
            4.0,
            "WTI",
            "LOT",
            "bilateral",
            "SOFR",
            "USD",
            4.0,
            pytest.approx(3.8),
            pytest.approx(-0.0019),
            serial(AS_OF),
            pytest.approx(-0.00038),
            PER_BP,
            "USD",
        ],
    ]
    repeated = spilled(ENTRY["util_ReadHandle"](collected(b2, b3, b2)))
    assert [line[0] for line in repeated[2:]] == [1.0, 2.0, 3.0]
    assert repeated[4][1:] == repeated[2][1:]
    assert not any(
        isinstance(cell, str) and ":trade_results:" in cell for line in repeated for cell in line
    )


def test_a_collection_with_no_curve_reports_a_dv01_of_nothing(sheet: dict[str, Any]) -> None:
    agg = collected(sheet["b2"], sheet["b4"])
    assert report(agg, "dv01", "day") == [*risk_head(AS_OF, CLEARED_DV01), ["Total", 0.0]]
    everything = report(agg, "all", "day")
    assert everything[1] == [
        "period",
        HNG_NOMINAL,
        HNG_DELTA,
        WTI_NOMINAL,
        WTI_DELTA,
        CLEARED_DV01,
        HNG_CLEARED_CROSS,
        WTI_CLEARED_CROSS,
    ]
    assert [line[5] for line in everything[3:]] == [0.0, 0.0, 0.0]


def test_a_quote_or_a_curve_moved_through_the_cells_flows_into_the_collection(
    sheet: dict[str, Any],
) -> None:
    # HNG at 81, B2 and B3 valued again over the new vector with B4 and B5 as they were: the lots
    # stand and the DV01 in all is -0.01235; the curve at 0.96 with B3 and B5 valued again: HNG's
    # delta 19.6, WTI's 5.84, the DV01 -0.01152.
    hot = a_market(sheet["hng_history"], "HNG", 81.0, 50.0)
    b2_hot = valued(sheet, "hng", 1001, 10.0, 70.0, "+261bd", "cleared", bridge.MISSING, hot)
    b3_hot = valued(sheet, "hng", 1002, 10.0, 70.0, "+261bd", "bilateral", sheet["curve"], hot)
    total = report(collected(b2_hot, b3_hot, sheet["b4"], sheet["b5"]), "all", "year")[3]
    assert total[1:] == [
        20.0,
        pytest.approx(19.5),
        6.0,
        pytest.approx(5.8),
        pytest.approx(-0.01235),
        0.0,
        pytest.approx(-0.00095),
        0.0,
        pytest.approx(-0.00038),
    ]
    steeper = unit_curve((AS_OF, 1.0), (A_YEAR_OUT, 0.96), (TWO_YEARS_OUT, 0.90))
    b3_other = valued(sheet, "hng", 1002, 10.0, 70.0, "+261bd", "bilateral", steeper)
    b5_other = valued(sheet, "wti", 1004, 4.0, 50.0, "+260bd", "bilateral", steeper)
    total = report(collected(sheet["b2"], b3_other, sheet["b4"], b5_other), "all", "year")[3]
    assert total[1:] == [
        20.0,
        pytest.approx(19.6),
        6.0,
        pytest.approx(5.84),
        pytest.approx(-0.01152),
        0.0,
        pytest.approx(-0.00096),
        0.0,
        pytest.approx(-0.000384),
    ]


def test_opposite_positions_keep_their_residual_in_every_order(sheet: dict[str, Any]) -> None:
    # Ten thousand trillion lots bought, one lot bought and ten thousand trillion sold, quoted at
    # the fixed price so that nothing values past the largest number: one lot in all and on the
    # day, whichever order the cells come in.
    at_eighty = {
        key: valued(sheet, "hng", 1000 + k, lots, 80.0, "+261bd", "cleared", bridge.MISSING)
        for k, (key, lots) in enumerate((("bought", 1e16), ("one", 1.0), ("sold", -1e16)), start=1)
    }
    for order in (("bought", "one", "sold"), ("bought", "sold", "one"), ("sold", "one", "bought")):
        view = report(collected(*(at_eighty[k] for k in order)), "nominal_delta", "day")
        assert view[3:] == [["Total", 1.0], [serial(AS_OF), 1.0]], order


def test_a_failed_source_shows_the_creators_failure_once_through_the_collection(
    sheet: dict[str, Any],
) -> None:
    """The ticket's chain: a failed evaluation in a cell fails the collection behind the cell's
    name with the creator's text whole, and the report, the readback and a second collection over
    the failed collection's cell each show that text once behind one wrapper of their own, the
    relay rule reading through the cell's name; nothing published."""
    failed = str(
        ENTRY["_EvaluateTrades"](
            ENTRY["_PrepareTrades"](
                ENTRY["_CreateTrades"](
                    sheet["hng"],
                    sheet["headers"],
                    rows([1010.0, serial(AS_OF), "F27", 1.0, 70.0, "+261bd"]),
                    sheet["bilateral"],
                ),
                sheet["hng_history"],
            ),
            sheet["hng_market"],
            bridge.MISSING,
        )
    )
    assert failed.startswith("#ERROR _EvaluateTrades: ValueError: discount_curve_set is missing")
    live = bridge.live_handles()
    collection = str(ENTRY["_AggregateResults"](stacked([sheet["b2"], failed])))
    assert collection == (
        "#ERROR _AggregateResults: result_handles cell (2, 1) is the creator's failure, expected "
        f"trade results or cashflow results handle: {failed}"
    )
    assert ENTRY["_ReportRisk"](collection, "all", "day") == (
        "#ERROR _ReportRisk: results is the creator's failure, expected trade results or "
        f"aggregate results or cashflow results handle: {failed}"
    )
    assert ENTRY["util_ReadHandle"](collection) == (
        f"#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: {failed}"
    )
    assert ENTRY["_AggregateResults"](beside(collection, sheet["b2"])) == (
        "#ERROR _AggregateResults: result_handles cell (1, 1) is the creator's failure, expected "
        f"trade results or cashflow results handle: {failed}"
    )
    assert bridge.live_handles() == live


def test_the_collector_refuses_its_inputs_at_their_cells_and_publishes_nothing(
    sheet: dict[str, Any],
) -> None:
    # The seam's refusals: the shape first, then each cell at its own place in sheet order, a blank,
    # a number, an empty text, text naming nothing, a handle of another kind, a collection among
    # the inputs, a creator's failure carried whole; the argument left out or blank. Then the
    # library's, in the seam's words: another valuation day, another history object of the same
    # index, a distinct index of the same name. Nothing is published by a failure.
    b2, b3 = sheet["b2"], sheet["b3"]
    collect = ENTRY["_AggregateResults"]
    nested = collected(b2)
    failed = str(
        ENTRY["_EvaluateTrades"](
            ENTRY["_PrepareTrades"](
                ENTRY["_CreateTrades"](
                    sheet["hng"],
                    sheet["headers"],
                    rows([1009.0, serial(AS_OF), "F27", 1.0, 70.0, "+261bd"]),
                    sheet["bilateral"],
                ),
                sheet["hng_history"],
            ),
            sheet["hng_market"],
            bridge.MISSING,
        )
    )
    assert failed.startswith("#ERROR _EvaluateTrades: ValueError: discount_curve_set is missing")
    later = a_history(sheet["hng"], "2027-01-01", "2027-01-05", UNIT_HOLIDAYS, {"2027-01-04": 82.0})
    on_later = valued(
        sheet,
        "hng",
        1002,
        10.0,
        70.0,
        "+261bd",
        "bilateral",
        unit_curve(("2027-01-05", 1.0), (A_YEAR_OUT, 0.95)),
        a_market(later, "HNG", 50.0),
        later,
    )
    equal_history = a_history(sheet["hng"], "2027-01-01", AS_OF, UNIT_HOLIDAYS, {})
    on_equal = valued(
        sheet,
        "hng",
        1001,
        10.0,
        70.0,
        "+261bd",
        "cleared",
        bridge.MISSING,
        a_market(equal_history, "HNG", 80.0, 50.0),
        equal_history,
    )
    twin = one_unit_index("HNG", "2027-01-04")
    twin_history = a_history(twin, "2027-01-01", AS_OF, UNIT_HOLIDAYS, {})
    on_twin = str(
        ENTRY["_EvaluateTrades"](
            ENTRY["_PrepareTrades"](
                ENTRY["_CreateTrades"](
                    twin,
                    sheet["headers"],
                    rows([1001.0, serial(AS_OF), "F27", 10.0, 70.0, "+261bd"]),
                    sheet["cleared"],
                ),
                twin_history,
            ),
            a_market(twin_history, "HNG", 80.0, 50.0),
            bridge.MISSING,
        )
    )
    live = bridge.live_handles()
    assert collect(Cells.from_rows([[b2, b3], [b3, b2]])) == (
        "#ERROR _AggregateResults: result_handles is 2x2 array, expected one cell, one row or one "
        "column of trade results or cashflow results handles"
    )
    assert collect(stacked([b2, None])) == (
        "#ERROR _AggregateResults: result_handles cell (2, 1) is blank, expected trade results "
        "or cashflow results handle"
    )
    assert collect(beside(b2, 3.0)) == (
        "#ERROR _AggregateResults: result_handles cell (1, 2) is number 3.0, expected trade "
        "results or cashflow results handle"
    )
    assert collect(stacked([b2, ""])) == (
        "#ERROR _AggregateResults: result_handles cell (2, 1) is empty text, expected trade "
        "results or cashflow results handle"
    )
    assert collect(stacked([b2, "x"])) == (
        "#ERROR _AggregateResults: result_handles cell (2, 1) is text 'x' naming no live object, "
        "expected trade results or cashflow results handle"
    )
    assert collect(stacked([b2, sheet["hng"]])) == (
        f"#ERROR _AggregateResults: result_handles cell (2, 1) is index handle {sheet['hng']!r}, "
        "expected trade results or cashflow results handle"
    )
    assert collect(stacked([nested, b3])) == (
        f"#ERROR _AggregateResults: result_handles cell (1, 1) is aggregate results handle "
        f"{nested!r}, expected trade results or cashflow results handle"
    )
    assert collect(stacked([failed, b2])) == (
        "#ERROR _AggregateResults: result_handles cell (1, 1) is the creator's failure, expected "
        f"trade results or cashflow results handle: {failed}"
    )
    assert collect(bridge.MISSING) == (
        "#ERROR _AggregateResults: result_handles is missing, expected trade results or cashflow "
        "results handles in a cell, a row or a column"
    )
    assert collect(None) == (
        "#ERROR _AggregateResults: result_handles is blank, expected trade results or cashflow "
        "results handles in a cell, a row or a column"
    )
    assert collect(sheet["hng"]) == (
        f"#ERROR _AggregateResults: result_handles is index handle {sheet['hng']!r}, expected "
        "trade results or cashflow results handle"
    )
    assert collect(stacked([b2, on_later])) == (
        "#ERROR _AggregateResults: ValueError: results 2 is valued on 2027-01-05, expected "
        "2027-01-04, the valuation day of results 1"
    )
    assert collect(stacked([b2, on_equal])) == (
        "#ERROR _AggregateResults: ValueError: results 2 is on index 'HNG' over another history "
        "than results 1, expected one history for one index"
    )
    assert collect(stacked([b2, on_twin])) == (
        "#ERROR _AggregateResults: ValueError: results 2 is on another index named 'HNG' than "
        "results 1, expected one index for one name"
    )
    assert bridge.live_handles() == live  # nothing published by a failure


def test_the_reader_takes_either_kind_and_the_other_reports_take_one(sheet: dict[str, Any]) -> None:
    agg = collected(sheet["b2"], sheet["b3"])
    assert ENTRY["_ReportRisk"](sheet["hng"], "all", "day") == (
        f"#ERROR _ReportRisk: results is index handle {sheet['hng']!r}, expected trade results or "
        "aggregate results or cashflow results handle"
    )
    assert ENTRY["_ReportRisk"](None, "all", "day") == (
        "#ERROR _ReportRisk: results is blank, expected trade results or aggregate results or "
        "cashflow results handle"
    )
    assert ENTRY["_ReportValues"](agg) == (
        f"#ERROR _ReportValues: results is aggregate results handle {agg!r}, expected trade "
        "results or cashflow results handle"
    )
    assert ENTRY["_ReportReserves"](agg) == (
        f"#ERROR _ReportReserves: results is aggregate results handle {agg!r}, expected trade "
        "results handle"
    )
    assert ENTRY["_ReportRisk"](agg, "gamma", "day") == (
        "#ERROR _ReportRisk: ValueError: risk is 'gamma', expected nominal_delta, delta, dv01, "
        "cross_gamma or all"
    )


# --- trades and cashflows in one collection, named-curves-slice-2.md -----------------------------

SOFR_USD = "SOFR USD dv01 [USD per basis point]"
FFOIS_USD = "FFOIS USD dv01 [USD per basis point]"
HNG_NOMINAL_LOT = "HNG nominal_delta [LOT]"
HNG_DELTA_LOT = "HNG delta [LOT]"
CASHFLOWS_ALONE = (
    "#ERROR _ReportRisk: ValueError: risk is 'delta', expected dv01 or all for a collection of "
    "cashflows alone, which has no commodity risk"
)


def cashflow_batch(key: str) -> str:
    """The cashflow ticket's batch as a handle: 10,000 receivable a year out, 10,000 payable two
    years out and 250 paid the day before the valuation day, in USD, every row on the curve of
    that name since cashflow-curve-keys.md."""
    template = ENTRY["_CreateTradeTemplate"](
        "cashflow", row("currency", "discount_curve_key"), row("USD", key)
    )
    return str(
        ENTRY["_CreateCashflows"](
            row("trade_id", "trade_date", "amount", "payment_day"),
            rows(
                [1.0, serial(AS_OF), 10_000.0, serial(A_YEAR_OUT)],
                [2.0, serial(AS_OF), -10_000.0, serial(TWO_YEARS_OUT)],
                [3.0, serial(AS_OF), 250.0, serial(AS_OF) - 1],
            ),
            template,
        )
    )


def cashflows_on(curve: str) -> str:
    """That batch keyed on the curve given, by the name its handle shows, and valued on the
    valuation day over a collection of that one curve: 0.85 of DV01 on the ticket's curve,
    -0.95 a year out and +1.80 two years out."""
    date = ENTRY["_CreateValuationDate"](serial(AS_OF), 0.5)
    batch = cashflow_batch(curve.split(":")[2])
    return str(ENTRY["_EvaluateCashflows"](batch, date, ENTRY["_CollectDiscountCurves"](curve)))


def test_a_trade_and_a_cashflow_collect_and_the_cashflow_moves_its_curves_dv01_alone(
    sheet: dict[str, Any],
) -> None:
    b3 = sheet["b3"]
    cashflow = cashflows_on(sheet["curve"])
    assert report(cashflow, "dv01", "year")[3] == ["Total", pytest.approx(0.85)]
    both = collected(b3, cashflow)
    table = report(both, "all", "year")
    assert table[:3] == risk_head(AS_OF, HNG_NOMINAL_LOT, HNG_DELTA_LOT, SOFR_USD, HNG_CROSS)
    assert table[3:] == [
        ["Total", 10.0, pytest.approx(9.5), pytest.approx(0.8405), pytest.approx(-0.00095)],
        [serial("2027-01-01"), 10.0, pytest.approx(9.5), 0.0, pytest.approx(-0.00095)],
        [serial("2028-01-01"), 0.0, 0.0, pytest.approx(-0.9595), 0.0],
        [serial("2029-01-01"), 0.0, 0.0, pytest.approx(1.8), 0.0],
    ]
    # The lots and the cross-gamma are the trade's alone, in every view.
    for risk in ("nominal_delta", "delta", "cross_gamma"):
        for bucket in ("day", "month", "year"):
            assert report(both, risk, bucket) == report(b3, risk, bucket), (risk, bucket)


def test_a_cashflow_on_another_curve_is_a_column_of_its_own_and_cashflows_alone_collect(
    sheet: dict[str, Any],
) -> None:
    b3 = sheet["b3"]
    ffois = unit_curve((AS_OF, 1.0), (A_YEAR_OUT, 0.96), (TWO_YEARS_OUT, 0.92), name="FFOIS")
    on_sofr, on_ffois = cashflows_on(sheet["curve"]), cashflows_on(ffois)
    three = collected(b3, on_sofr, on_ffois)
    table = report(three, "dv01", "year")
    assert table[:3] == risk_head(AS_OF, SOFR_USD, FFOIS_USD)
    assert table[3:] == [
        ["Total", pytest.approx(0.8405), pytest.approx(0.88)],
        [serial("2027-01-01"), 0.0, 0.0],
        [serial("2028-01-01"), pytest.approx(-0.9595), pytest.approx(-0.96)],
        [serial("2029-01-01"), pytest.approx(1.8), pytest.approx(1.84)],
    ]
    # Cashflows alone: the result's own report under dv01 and all, twice doubled, and the
    # commodity selectors refused in the cashflow result's words.
    alone = collected(on_sofr)
    for risk in ("dv01", "all"):
        for bucket in ("day", "month", "year"):
            assert report(alone, risk, bucket) == report(on_sofr, risk, bucket), (risk, bucket)
    assert report(collected(on_sofr, on_sofr), "dv01", "year")[3] == ["Total", pytest.approx(1.7)]
    assert ENTRY["_ReportRisk"](alone, "delta", "day") == CASHFLOWS_ALONE
    # The readback: a cashflow row shows cashflow under the route, its curve's word, its currency,
    # its DV01 and the day, and a dash where a batch of cashflows has no number.
    table = spilled(ENTRY["util_ReadHandle"](three))
    assert table[:2] == [READBACK_HEADERS, READBACK_TYPES]
    assert table[2][1:5] == ["HNG", "LOT", "bilateral", "SOFR"]
    assert table[3] == [
        2.0,
        "-",
        "-",
        "cashflow",
        "SOFR",
        "USD",
        "-",
        "-",
        pytest.approx(0.85),
        serial(AS_OF),
        "-",
        "-",
        "USD",  # the unit of its currency, a cashflow's whole dollars
    ]
    assert table[4] == [
        3.0,
        "-",
        "-",
        "cashflow",
        "FFOIS",
        "USD",
        "-",
        "-",
        pytest.approx(0.88),
        serial(AS_OF),
        "-",
        "-",
        "USD",
    ]


def test_two_snapshots_of_one_name_are_both_qualified_in_a_collection(
    sheet: dict[str, Any],
) -> None:
    b3 = sheet["b3"]
    second = unit_curve((AS_OF, 1.0), (A_YEAR_OUT, 0.96), (TWO_YEARS_OUT, 0.92))  # SOFR again
    b3_second = valued(sheet, "hng", 1002, 10.0, 70.0, "+261bd", "bilateral", second)
    ffois = unit_curve((AS_OF, 1.0), (A_YEAR_OUT, 0.96), (TWO_YEARS_OUT, 0.92), name="FFOIS")
    four = collected(b3, cashflows_on(sheet["curve"]), cashflows_on(ffois), b3_second)
    table = report(four, "dv01", "year")
    assert table[1] == [
        "period",
        "SOFR (curve_1) USD dv01 [USD per basis point]",
        FFOIS_USD,
        "SOFR (curve_2) USD dv01 [USD per basis point]",
    ]
    assert table[3] == ["Total", pytest.approx(0.8405), pytest.approx(0.88), pytest.approx(-0.0096)]
    table = report(four, "cross_gamma", "year")
    assert table[1] == [
        "period",
        "HNG SOFR (curve_1) cross_gamma [LOT per basis point]",
        "HNG SOFR (curve_2) cross_gamma [LOT per basis point]",
    ]
    assert table[3] == ["Total", pytest.approx(-0.00095), pytest.approx(-0.00096)]
    readback = spilled(ENTRY["util_ReadHandle"](four))
    assert [line[4] for line in readback[2:]] == [
        "SOFR (curve_1)",
        "SOFR (curve_1)",
        "FFOIS",
        "SOFR (curve_2)",
    ]
    # A single result on one curve names it bare, whatever a collection shows beside it.
    assert report(b3_second, "dv01", "year")[1] == ["period", SOFR_USD]


def test_a_handle_of_another_kind_among_results_is_refused_naming_both_kinds(
    sheet: dict[str, Any],
) -> None:
    b3 = sheet["b3"]
    batch = cashflow_batch("SOFR")
    live = bridge.live_handles()
    assert collected(b3, batch) == (
        f"#ERROR _AggregateResults: result_handles cell (2, 1) is cashflows handle {batch!r}, "
        "expected trade results or cashflow results handle"
    )
    assert bridge.live_handles() == live


# --- the currency and the unit of it, currency-and-currency-unit.md ------------------------------

SOFR_CENT = "SOFR USD dv01 [CENT per basis point]"


def cent_settled_index(name: str, expiry: str) -> str:
    """one_unit_index's twin through the seam, quoted in dollars a barrel as it is and settled
    in cents: a barrel a lot, F27 expiring on the day given."""
    schedule = ENTRY["_CreateFuturesSchedule"](
        rows(["Z26"], ["F27"], ["F29"]),
        column([serial("2026-12-31"), serial(expiry), serial("2029-01-05")]),
        bridge.MISSING,
    )
    calendar = ENTRY["_CreateHolidayCalendar"](column([serial(day) for day in UNIT_HOLIDAYS]))
    conventions = ENTRY["_CreateIndexConventions"]("USD", "BBL", "CENT", "VOLUME", "BBL")
    specifications = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        rows(["LOT", 1.0, "BBL", 0.0, 0.0]),
    )
    return str(
        ENTRY["_CreateIndex"](
            name, f"{name} index", schedule, conventions, specifications, calendar, "LOT"
        )
    )


def test_a_cent_settled_batch_is_a_column_of_its_own_beside_the_dollar_column(
    sheet: dict[str, Any],
) -> None:
    # B3's trade again on an index settled in cents: ten lots at 80 against 70, a hundred
    # dollars and so ten thousand cents a year out at 0.95, 9,500 cents of mark and -0.95 of
    # DV01 where B3 has 95 dollars and -0.0095. Its currency is USD as B3's is; the unit says
    # cents, on both reports, in the heading's brackets and in the readback's last column.
    hngc = cent_settled_index("HNGC", "2027-01-04")
    history = a_history(hngc, "2027-01-01", AS_OF, UNIT_HOLIDAYS, {})
    state = {
        **sheet,
        "hngc": hngc,
        "hngc_history": history,
        "hngc_market": a_market(history, "HNGC", 80.0, 50.0),
    }
    in_cents = valued(state, "hngc", 1005, 10.0, 70.0, "+261bd", "bilateral", sheet["curve"])
    assert spilled(ENTRY["_ReportValues"](in_cents))[2] == [
        pytest.approx(9_500.0),
        0.0,
        "USD",
        serial(AS_OF),
        "CENT",
    ]
    assert spilled(ENTRY["_ReportReserves"](in_cents))[2] == [0.0, 0.0, 0.0, 0.0, "USD", "CENT"]
    assert report(in_cents, "dv01", "year")[1] == ["period", SOFR_CENT]
    own = spilled(ENTRY["util_ReadHandle"](in_cents))
    assert own[0][-1] == "currency_unit" and own[2][-1] == "CENT"
    assert own[2][own[0].index("currency")] == "USD"
    # Collected with B3 and a cashflow on the same curve: the trade settled in dollars and the
    # cashflow, whole dollars both, share the one column they shared, 0.85 - 0.0095; the
    # cents stand beside it under the same curve and currency, told apart by the unit, and are
    # added to nothing.
    cashflow = cashflows_on(sheet["curve"])
    together = collected(sheet["b3"], cashflow, in_cents)
    table = report(together, "dv01", "year")
    assert table[1] == ["period", SOFR_USD, SOFR_CENT]
    assert table[3] == ["Total", pytest.approx(0.8405), pytest.approx(-0.95)]
    members = spilled(ENTRY["util_ReadHandle"](together))
    assert [line[3:6] for line in members[2:]] == [
        ["bilateral", "SOFR", "USD"],
        ["cashflow", "SOFR", "USD"],
        ["bilateral", "SOFR", "USD"],
    ]
    assert [line[-1] for line in members[2:]] == ["USD", "USD", "CENT"]
    assert [line[8] for line in members[2:]] == [
        pytest.approx(-0.0095),
        pytest.approx(0.85),
        pytest.approx(-0.95),
    ]
    # In the other order the columns follow first appearance and hold the same numbers.
    turned = report(collected(in_cents, cashflow, sheet["b3"]), "dv01", "year")
    assert turned[1] == ["period", SOFR_CENT, SOFR_USD]
    assert turned[3] == ["Total", pytest.approx(-0.95), pytest.approx(0.8405)]
