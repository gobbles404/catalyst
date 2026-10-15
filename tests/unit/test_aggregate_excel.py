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
    risk_head,
    row,
    rows,
    serial,
    spilled,
    unit_curve,
)

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

AS_OF = UNIT_AS_OF
JAN_27, JAN_28 = "2027-01-01", "2028-01-01"
HNG_NOMINAL, HNG_DELTA = "HNG nominal_delta [LOT]", "HNG delta [LOT]"
WTI_NOMINAL, WTI_DELTA = "WTI nominal_delta [LOT]", "WTI delta [LOT]"
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
        ENTRY["_CreateTradeTemplate"](
            "fixed_float",
            row(*UNIT_FIELDS),
            row("LOT", "month", "lastday", "bilateral", "financial", "ACME Trading", payments, 0.0),
        )
    )
    cleared = str(
        ENTRY["_CreateTradeTemplate"](
            "fixed_float",
            row(*UNIT_FIELDS[:5], "clearing_house", *UNIT_FIELDS[6:]),
            row(
                "LOT",
                "month",
                "lastday",
                "cleared",
                "financial",
                "Prototype Clearing",
                payments,
                0.0,
            ),
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
    return str(ENTRY["_EvaluateTrades"](prepared, market or state[f"{which}_market"], curve))


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
    for key, nominal, delta, dv01 in (
        ("b2", 10.0, 10.0, 0.0),
        ("b3", 10.0, 9.5, -0.0095),
        ("b4", 2.0, 2.0, 0.0),
        ("b5", 4.0, 3.8, -0.0019),
    ):
        total = report(sheet[key], "all", "year")[3]
        assert total[0] == "Total"
        assert total[1:] == [pytest.approx(nominal), pytest.approx(delta), pytest.approx(dv01)]


def test_two_hng_sources_collect_into_one_handle_the_reader_takes(sheet: dict[str, Any]) -> None:
    # B2:B3 as a column: one handle of the new kind, no index name in it; all three by month under
    # the HNG labels and curve_1, the Total 20, 19.5 and -0.0095 over January 2027's lots and
    # January 2028's DV01, the eleven months between at zero since #186, the spill running from
    # the valuation month to the last payment month.
    agg = collected(sheet["b2"], sheet["b3"])
    assert re.fullmatch(rf"{os.getpid()}:aggregate_results:\d+", agg)
    between = [serial(f"2027-{m:02d}-01") for m in range(2, 13)]
    assert report(agg, "all", "month") == [
        *risk_head(AS_OF, HNG_NOMINAL, HNG_DELTA, CURVE_DV01),
        ["Total", 20.0, pytest.approx(19.5), pytest.approx(-0.0095)],
        [serial(JAN_27), 20.0, pytest.approx(19.5), 0.0],
        *[[m, 0.0, 0.0, 0.0] for m in between],
        [serial(JAN_28), 0.0, 0.0, pytest.approx(-0.0095)],
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
    assert report(agg, "all", "month") == [
        *risk_head(AS_OF, HNG_NOMINAL, HNG_DELTA, WTI_NOMINAL, WTI_DELTA, CURVE_DV01),
        ["Total", 20.0, pytest.approx(19.5), 6.0, pytest.approx(5.8), pytest.approx(-0.0114)],
        [serial(JAN_27), 20.0, pytest.approx(19.5), 6.0, pytest.approx(5.8), 0.0],
        *[[m, 0.0, 0.0, 0.0, 0.0, 0.0] for m in between],
        [serial(JAN_28), 0.0, 0.0, 0.0, 0.0, pytest.approx(-0.0114)],
    ]
    by_day = report(agg, "all", "day")
    assert [line[0] for line in by_day[4:]] == [
        serial(AS_OF),
        serial("2027-01-05"),
        serial(A_YEAR_OUT),
    ]
    assert by_day[4][1:] == [20.0, pytest.approx(19.5), 0.0, 0.0, 0.0]
    assert by_day[5][1:] == [0.0, 0.0, 6.0, pytest.approx(5.8), 0.0]
    assert by_day[6][1:] == [0.0, 0.0, 0.0, 0.0, pytest.approx(-0.0114)]
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
    ]


def test_the_readback_lists_the_membership_in_the_order_given(sheet: dict[str, Any]) -> None:
    # One row per occurrence: its position, index, lot, route, the collection's curve number or a
    # dash, currency, its own three saved numbers and the day; a repeat a row again; no handle text.
    b2, b3, b4, b5 = (sheet[k] for k in ("b2", "b3", "b4", "b5"))
    table = spilled(ENTRY["util_ReadHandle"](collected(b2, b3, b4, b5)))
    assert table[:2] == [READBACK_HEADERS, READBACK_TYPES]
    assert table[2:] == [
        [1.0, "HNG", "LOT", "cleared", "-", "USD", 10.0, 10.0, 0.0, serial(AS_OF)],
        [
            2.0,
            "HNG",
            "LOT",
            "bilateral",
            "curve_1",
            "USD",
            10.0,
            pytest.approx(9.5),
            pytest.approx(-0.0095),
            serial(AS_OF),
        ],
        [3.0, "WTI", "LOT", "cleared", "-", "USD", 2.0, 2.0, 0.0, serial(AS_OF)],
        [
            4.0,
            "WTI",
            "LOT",
            "bilateral",
            "curve_1",
            "USD",
            4.0,
            pytest.approx(3.8),
            pytest.approx(-0.0019),
            serial(AS_OF),
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
    assert everything[1] == ["period", HNG_NOMINAL, HNG_DELTA, WTI_NOMINAL, WTI_DELTA, CLEARED_DV01]
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
    assert failed.startswith("#ERROR _EvaluateTrades: ValueError: discount_curve is missing")
    live = bridge.live_handles()
    collection = str(ENTRY["_AggregateResults"](stacked([sheet["b2"], failed])))
    assert collection == (
        "#ERROR _AggregateResults: result_handles cell (2, 1) is the creator's failure, expected "
        f"trade results handle: {failed}"
    )
    assert ENTRY["_ReportRisk"](collection, "all", "day") == (
        "#ERROR _ReportRisk: results is the creator's failure, expected trade results or "
        f"aggregate results handle: {failed}"
    )
    assert ENTRY["util_ReadHandle"](collection) == (
        f"#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: {failed}"
    )
    assert ENTRY["_AggregateResults"](beside(collection, sheet["b2"])) == (
        "#ERROR _AggregateResults: result_handles cell (1, 1) is the creator's failure, expected "
        f"trade results handle: {failed}"
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
    assert failed.startswith("#ERROR _EvaluateTrades: ValueError: discount_curve is missing")
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
        "column of trade results handles"
    )
    assert collect(stacked([b2, None])) == (
        "#ERROR _AggregateResults: result_handles cell (2, 1) is blank, expected trade results "
        "handle"
    )
    assert collect(beside(b2, 3.0)) == (
        "#ERROR _AggregateResults: result_handles cell (1, 2) is number 3.0, expected trade "
        "results handle"
    )
    assert collect(stacked([b2, ""])) == (
        "#ERROR _AggregateResults: result_handles cell (2, 1) is empty text, expected trade "
        "results handle"
    )
    assert collect(stacked([b2, "x"])) == (
        "#ERROR _AggregateResults: result_handles cell (2, 1) is text 'x' naming no live object, "
        "expected trade results handle"
    )
    assert collect(stacked([b2, sheet["hng"]])) == (
        f"#ERROR _AggregateResults: result_handles cell (2, 1) is index handle {sheet['hng']!r}, "
        "expected trade results handle"
    )
    assert collect(stacked([nested, b3])) == (
        f"#ERROR _AggregateResults: result_handles cell (1, 1) is aggregate results handle "
        f"{nested!r}, expected trade results handle"
    )
    assert collect(stacked([failed, b2])) == (
        "#ERROR _AggregateResults: result_handles cell (1, 1) is the creator's failure, expected "
        f"trade results handle: {failed}"
    )
    assert collect(bridge.MISSING) == (
        "#ERROR _AggregateResults: result_handles is missing, expected trade results handles in a "
        "cell, a row or a column"
    )
    assert collect(None) == (
        "#ERROR _AggregateResults: result_handles is blank, expected trade results handles in a "
        "cell, a row or a column"
    )
    assert collect(sheet["hng"]) == (
        f"#ERROR _AggregateResults: result_handles is index handle {sheet['hng']!r}, expected "
        "trade results handle"
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
        "aggregate results handle"
    )
    assert ENTRY["_ReportRisk"](None, "all", "day") == (
        "#ERROR _ReportRisk: results is blank, expected trade results or aggregate results handle"
    )
    assert ENTRY["_ReportValues"](agg) == (
        f"#ERROR _ReportValues: results is aggregate results handle {agg!r}, expected trade "
        "results handle"
    )
    assert ENTRY["_ReportReserves"](agg) == (
        f"#ERROR _ReportReserves: results is aggregate results handle {agg!r}, expected trade "
        "results handle"
    )
    assert ENTRY["_ReportRisk"](agg, "gamma", "day") == (
        "#ERROR _ReportRisk: ValueError: risk is 'gamma', expected nominal_delta, delta, dv01 or "
        "all"
    )
