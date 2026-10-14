"""The valuation path on the sheet: _PrepareTrades, _EvaluateTrades, _ReportValues and
_ReportRisk over the kernel, through the seam. The NG example and its toy lifecycle valued cell to
cell, the two reports' spills pinned, the handles' texts, the readers' spills of the dated
contents, a tick making new results over the same preparation while the old results stand, and
each refusal in the seam's order and then the library's. docs/library/trades/prepare-trades.md,
evaluate-trades.md, report-values.md and report-risk.md are the pages."""

import os
import re
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
FIRST = np.datetime64("1899-12-30", "D")


def serial(text: str) -> float:
    return float((np.datetime64(text, "D") - FIRST).astype(np.int64))


def row(*cells: object) -> Cells:
    return Cells.from_rows([list(cells)])


def rows(*lines: list[Any]) -> Cells:
    return Cells.from_rows(list(lines))


def column(values: NDArray[Any] | list[float]) -> Cells:
    return Cells.from_rows([[float(v)] for v in values])


def spilled(result: object) -> list[list[object]]:
    kinds, slots, text = cast(tuple[NDArray[np.uint8], NDArray[np.float64], str], result)
    texts = iter(text.split("\0"))
    return [
        [
            next(texts) if kinds[r, c] == bridge.TEXT_CODE else slots[r, c]
            for c in range(kinds.shape[1])
        ]
        for r in range(kinds.shape[0])
    ]


NG_TEMPLATE = {
    "contract_specification": "NYMEX NG",
    "quantity_unit": "LOT",
    "quantity_per": "month",
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "physical",
    "clearing_house": "CME Clearing",
}
NG_HEADERS = ("trade_id", "trade_date", "contract_code", "quantity", "fixed_price")
NG_ROWS: list[list[object]] = [
    ["NG-001", serial("2026-09-24"), "Z26", 10.0, 3.1],
    ["NG-002", serial("2026-09-24"), "z26", -4.0, 3.15],
    ["NG-003", serial("2026-09-25"), "F27", 7.0, 3.4],
    ["NG-004", serial("2026-09-25"), "F27", -12.0, 3.35],
    ["NG-001", serial("2026-09-24"), "Z26", 10.0, 3.1],
]


def an_index(
    name: str, contracts: list[tuple[str, str]], holidays: list[str], lot: tuple[str, float]
) -> tuple[str, str]:
    """An index of those contracts and holidays through the seam, and its holiday calendar."""
    schedule = ENTRY["_CreateFuturesSchedule"](
        rows(*[[code] for code, _ in contracts]),
        column([serial(expiry) for _, expiry in contracts]),
        bridge.MISSING,
    )
    calendar = ENTRY["_CreateHolidayCalendar"](column([serial(day) for day in holidays]))
    conventions = ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU")
    specifications = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        row(lot[0], lot[1], "MMBTU", 0.0, 0.0),
    )
    return str(ENTRY["_CreateIndex"](name, schedule, conventions, specifications, calendar)), str(
        calendar
    )


def a_history(
    index: str, first: str, as_of: str, holidays: list[str], settles: dict[str, float]
) -> str:
    """The index's history valued on that day: 3.00 on every business day from the calendar's first
    day to the day before, the settles given standing on their days, newest first as the fixings
    creator takes them."""
    days = np.arange(np.datetime64(first, "D"), np.datetime64(as_of, "D"))
    days = days[np.is_busday(days, holidays=np.array(holidays, dtype="datetime64[D]"))]
    prices = np.full(days.size, 3.0)
    for text, price in settles.items():
        prices[days == np.datetime64(text, "D")] = price
    fixings = ENTRY["_CreateFuturesFixings"](
        column([serial(str(d)) for d in days[::-1]]), column(prices[::-1]), index
    )
    calendar = ENTRY["_CreateCalendar"](ENTRY["_CreateValuationDate"](serial(as_of), 0.5), index)
    return str(ENTRY["_CreateMarketHistory"](calendar, fixings))


def a_market(history: str, name: str, *quotes: float) -> str:
    return str(
        ENTRY["_CreateMarket"](history, ENTRY["_CreatePriceVector"](name, column(list(quotes))))
    )


@pytest.fixture(scope="module")
def ng() -> dict[str, Any]:
    """The NG example on the sheet: the index, the template, the five rows as a batch, the
    history valued on 24 November 2026 with a settle of 3.00 on every fixed day, and the market
    quoting Z26 at 3.20 and F27 at 3.50."""
    holidays = ["2026-11-26", "2026-12-25"]
    index, _ = an_index(
        "Henry Hub NYMEX",
        [("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29")],
        holidays,
        ("NYMEX NG", 10_000.0),
    )
    template = ENTRY["_CreateTradeTemplate"](
        "future", row(*NG_TEMPLATE), row(*NG_TEMPLATE.values())
    )
    trades = ENTRY["_CreateTrades"](index, row(*NG_HEADERS), rows(*NG_ROWS), template)
    history = a_history(index, "2026-10-29", "2026-11-24", holidays, {})
    market = a_market(history, "Henry Hub NYMEX", 3.20, 3.50)
    prepared = ENTRY["_PrepareTrades"](trades, history)
    results = ENTRY["_EvaluateTrades"](prepared, market)
    return {
        "index": index,
        "template": template,
        "trades": trades,
        "history": history,
        "market": market,
        "prepared": prepared,
        "results": results,
    }


# --- the NG example valued cell to cell -----------------------------------------------------


def test_the_handles_are_named_for_the_index(ng: dict[str, Any]) -> None:
    pid = os.getpid()
    assert re.fullmatch(rf"{pid}:prepared_trades:Henry Hub NYMEX:\d+", str(ng["prepared"]))
    assert re.fullmatch(rf"{pid}:trade_results:Henry Hub NYMEX:\d+", str(ng["results"]))


def test_the_values_report_spills_the_mark_and_the_cash_under_the_routes_labels(
    ng: dict[str, Any],
) -> None:
    assert spilled(ENTRY["_ReportValues"](ng["results"])) == [
        ["cleared_mark", "cleared_cash", "currency", "as_of"],
        ["float64", "float64", "str", "datetime64[D]"],
        [7_000.0, 0.0, "USD", serial("2026-11-24")],
    ]


def test_the_risk_report_spills_the_total_delta_and_the_dv01_with_their_units(
    ng: dict[str, Any],
) -> None:
    assert spilled(ENTRY["_ReportRisk"](ng["results"])) == [
        ["delta_total", "delta_unit", "dv01", "dv01_unit", "as_of"],
        ["float64", "str", "float64", "str", "datetime64[D]"],
        [110_000.0, "USD per USD/MMBTU", 0.0, "USD per basis point", serial("2026-11-24")],
    ]


def test_the_readers_spill_the_dated_contents_one_row_per_slot(ng: dict[str, Any]) -> None:
    assert spilled(ENTRY["util_ReadHandle"](ng["prepared"])) == [
        ["contract_code", "observation_date", "is_fixed", "is_settled", "live_exposure"],
        ["str", "datetime64[D]", "bool", "bool", "float64"],
        ["Z26", serial("2026-11-25"), False, False, 160_000.0],
        ["F27", serial("2026-12-29"), False, False, -50_000.0],
    ]
    table = spilled(ENTRY["util_ReadHandle"](ng["results"]))
    assert table[:2] == [
        [
            "contract_code",
            "observation_date",
            "is_fixed",
            "live_exposure",
            "live_contribution",
            "contract_delta",
        ],
        ["str", "datetime64[D]", "bool", "float64", "float64", "float64"],
    ]
    assert table[2][:4] == ["Z26", serial("2026-11-25"), False, 160_000.0]
    assert table[2][4] == pytest.approx(512_000.0) and table[2][5] == 160_000.0
    assert table[3][4] == pytest.approx(-175_000.0) and table[3][5] == -50_000.0


def test_a_tick_makes_new_results_over_the_same_preparation_and_the_old_stand(
    ng: dict[str, Any],
) -> None:
    ticked = a_market(ng["history"], "Henry Hub NYMEX", 3.21, 3.50)
    later = ENTRY["_EvaluateTrades"](ng["prepared"], ticked)
    assert later != ng["results"]
    assert spilled(ENTRY["_ReportValues"](later))[2][0] == pytest.approx(8_600.0)
    assert spilled(ENTRY["_ReportValues"](ng["results"]))[2][0] == 7_000.0  # unmoved
    assert spilled(ENTRY["_ReportRisk"](later))[2][0] == 110_000.0  # delta, no tick changes it


def test_one_trade_takes_the_same_path_as_five(ng: dict[str, Any]) -> None:
    one = ENTRY["_CreateTrades"](ng["index"], row(*NG_HEADERS), rows(NG_ROWS[3]), ng["template"])
    prepared = ENTRY["_PrepareTrades"](one, ng["history"])
    results = ENTRY["_EvaluateTrades"](prepared, ng["market"])
    values = spilled(ENTRY["_ReportValues"](results))
    assert values[2][:2] == [pytest.approx(-18_000.0), 0.0]
    assert spilled(ENTRY["_ReportRisk"](results))[2][0] == -120_000.0


# --- the toy lifecycle on the sheet: the seven states of the example page ---------------------

TOY_HOLIDAYS = ["2026-11-26", "2026-12-25", "2027-01-01"]


@pytest.fixture(scope="module")
def toy() -> dict[str, Any]:
    """The toy of the example page on the sheet: TOY_GAS with G27 after F27, the payment calendar
    closed on 26 November, 25 December and New Year's Day, the financial template paying two
    business days after each expiry, and the five NG rows as a batch."""
    index, calendar = an_index(
        "TOY_GAS",
        [
            ("X26", "2026-10-28"),
            ("Z26", "2026-11-25"),
            ("F27", "2026-12-29"),
            ("G27", "2027-01-27"),
        ],
        TOY_HOLIDAYS,
        ("TOY", 10_000.0),
    )
    fields = {
        **NG_TEMPLATE,
        "contract_specification": "TOY",
        "settlement_method": "financial",
        "clearing_house": "TEST_CLEARER",
        "payment_time_lag": "+2bd",
        "payment_holiday_calendar": calendar,
    }
    template = ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*fields.values()))
    trades = ENTRY["_CreateTrades"](index, row(*NG_HEADERS), rows(*NG_ROWS), template)
    return {"index": index, "template": template, "trades": trades}


def toy_state(
    toy: dict[str, Any], as_of: str, settles: dict[str, float], quotes: tuple[float, ...]
) -> tuple[str, str]:
    """One state of the lifecycle: the history valued on that day with those settles standing on
    their days, the market quoting from the prompt on, the batch prepared and evaluated; the
    prepared and the results handles."""
    history = a_history(toy["index"], "2026-10-29", as_of, TOY_HOLIDAYS, settles)
    market = a_market(history, "TOY_GAS", *quotes)
    prepared = ENTRY["_PrepareTrades"](toy["trades"], history)
    return str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


def valued(results: str) -> tuple[float, float, float]:
    """The mark, the cash and the total delta a results handle reports."""
    values = spilled(ENTRY["_ReportValues"](results))[2]
    risk = spilled(ENTRY["_ReportRisk"](results))[2]
    return cast(float, values[0]), cast(float, values[1]), cast(float, risk[0])


Z26_FIRST = {"2026-11-25": 3.22}
Z26 = {"2026-11-25": 3.23}
BOTH = {"2026-11-25": 3.23, "2026-12-29": 3.45}


@pytest.mark.parametrize(
    ("as_of", "settles", "quotes", "mark", "cash", "delta"),
    [
        ("2026-11-24", {}, (3.20, 3.50, 3.60), 7_000, 0, 110_000),
        ("2026-11-24", {}, (3.21, 3.50, 3.60), 8_600, 0, 110_000),
        ("2026-11-26", Z26_FIRST, (3.50, 3.60), 10_200, 0, -50_000),
        ("2026-11-26", Z26, (3.50, 3.60), 11_800, 0, -50_000),
        ("2026-11-30", Z26, (3.50, 3.60), -11_000, 22_800, -50_000),
        ("2026-12-30", BOTH, (3.60,), -8_500, 22_800, 0),
        ("2026-12-31", BOTH, (3.60,), 0, 14_300, 0),
    ],
    ids=[
        "24 Nov, initial",
        "24 Nov, a tick",
        "26 Nov, Z26 fixed at 3.22",
        "26 Nov, corrected to 3.23",
        "30 Nov, Z26 paid",
        "30 Dec, both fixed, F27 unpaid",
        "31 Dec, both paid",
    ],
)
def test_the_toys_seven_states_value_on_the_sheet_as_the_page_says(
    toy: dict[str, Any],
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
) -> None:
    _, results = toy_state(toy, as_of, settles, quotes)
    got = valued(results)
    assert got[0] == pytest.approx(mark) and got[1] == pytest.approx(cash)
    assert got[2] == pytest.approx(delta)
    assert got[0] + got[1] == pytest.approx(mark + cash)  # the page's total P&L column
    assert spilled(ENTRY["_ReportValues"](results))[2][3] == serial(as_of)


def test_the_tick_reuses_the_initial_states_preparation(toy: dict[str, Any]) -> None:
    history = a_history(toy["index"], "2026-10-29", "2026-11-24", TOY_HOLIDAYS, {})
    prepared = ENTRY["_PrepareTrades"](toy["trades"], history)
    initial = ENTRY["_EvaluateTrades"](prepared, a_market(history, "TOY_GAS", 3.20, 3.50, 3.60))
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "TOY_GAS", 3.21, 3.50, 3.60))
    assert valued(str(initial))[0] == pytest.approx(7_000)
    assert valued(str(ticked))[0] == pytest.approx(8_600)
    assert valued(str(initial))[0] == pytest.approx(7_000)  # the old results stand


def test_the_paid_contract_reads_back_fixed_and_settled_with_no_live_exposure(
    toy: dict[str, Any],
) -> None:
    prepared, results = toy_state(toy, "2026-11-30", Z26, (3.50, 3.60))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert slots[2] == ["Z26", serial("2026-11-25"), True, True, 0.0]
    assert slots[3] == ["F27", serial("2026-12-29"), False, False, -50_000.0]
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[2] == ["Z26", serial("2026-11-25"), True, 0.0, 0.0, 0.0]
    assert table[3][:4] == ["F27", serial("2026-12-29"), False, -50_000.0]
    assert table[3][4] == pytest.approx(-175_000.0) and table[3][5] == -50_000.0


def test_a_fully_fixed_batch_inside_a_live_market_reads_no_quote_and_reports_its_cash(
    toy: dict[str, Any],
) -> None:
    prepared, results = toy_state(toy, "2026-12-31", BOTH, (3.60,))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert [line[2:5] for line in slots[2:]] == [[True, True, 0.0], [True, True, 0.0]]
    assert spilled(ENTRY["util_ReadHandle"](results))[2:] == [
        ["Z26", serial("2026-11-25"), True, 0.0, 0.0, 0.0],
        ["F27", serial("2026-12-29"), True, 0.0, 0.0, 0.0],
    ]
    assert valued(results) == (pytest.approx(0.0), pytest.approx(14_300), 0.0)


def test_a_missing_final_price_fails_the_history_before_any_trade_is_prepared(
    toy: dict[str, Any],
) -> None:
    # The settle on Z26's expiry day is a fixing like any other: a series that skips it is a
    # series like any other to the fixings creator, and the history valued after that day refuses
    # it, so no forecast ever stands in for a final price.
    days = np.arange(np.datetime64("2026-10-29", "D"), np.datetime64("2026-11-26", "D"))
    days = days[np.is_busday(days, holidays=np.array(TOY_HOLIDAYS, dtype="datetime64[D]"))]
    without = days[days != np.datetime64("2026-11-25", "D")]
    fixings = ENTRY["_CreateFuturesFixings"](
        column([serial(str(d)) for d in without[::-1]]), column([3.0] * without.size), toy["index"]
    )
    calendar = ENTRY["_CreateCalendar"](
        ENTRY["_CreateValuationDate"](serial("2026-11-26"), 0.5), toy["index"]
    )
    assert ENTRY["_CreateMarketHistory"](calendar, fixings) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2026-11-25, "
        "expected a fixing for every fixed day in calendar"
    )


# --- what is refused, in the seam's order and then the library's ------------------------------


def test_the_refusals_come_in_the_seams_order_then_the_librarys(ng: dict[str, Any]) -> None:
    prepare, evaluate = ENTRY["_PrepareTrades"], ENTRY["_EvaluateTrades"]
    assert (
        prepare(None, ng["history"])
        == "#ERROR _PrepareTrades: trades is blank, expected trades handle"
    )
    assert prepare("x:trades:9", ng["history"]) == (
        "#ERROR _PrepareTrades: trades is text 'x:trades:9' naming no live object, "
        "expected trades handle"
    )
    assert prepare(ng["trades"], ng["market"]) == (
        f"#ERROR _PrepareTrades: history is market handle {ng['market']!r}, "
        "expected market history handle"
    )
    assert evaluate(ng["prepared"], bridge.MISSING) == (
        "#ERROR _EvaluateTrades: market is missing, expected market handle"
    )
    assert evaluate(ng["trades"], ng["market"]) == (
        f"#ERROR _EvaluateTrades: prepared is trades handle {ng['trades']!r}, "
        "expected prepared trades handle"
    )
    assert ENTRY["_ReportValues"](ng["prepared"]) == (
        f"#ERROR _ReportValues: results is prepared trades handle {ng['prepared']!r}, "
        "expected trade results handle"
    )
    assert ENTRY["_ReportRisk"](None) == (
        "#ERROR _ReportRisk: results is blank, expected trade results handle"
    )
    # Then the library: another index's history, the same facts and name; a market over another
    # history; a physical contract past its expiry; a bilateral route.
    twin, _ = an_index(
        "Henry Hub NYMEX",
        [("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29")],
        ["2026-11-26", "2026-12-25"],
        ("NYMEX NG", 10_000.0),
    )
    other = a_history(twin, "2026-10-29", "2026-11-24", ["2026-11-26", "2026-12-25"], {})
    assert prepare(ng["trades"], other) == (
        "#ERROR _PrepareTrades: ValueError: history is over another index, 'Henry Hub NYMEX', "
        "expected the trades', 'Henry Hub NYMEX'"
    )
    assert evaluate(ng["prepared"], a_market(other, "Henry Hub NYMEX", 3.2, 3.5)) == (
        "#ERROR _EvaluateTrades: ValueError: market is over another history of index "
        "'Henry Hub NYMEX', expected the one the trades were prepared against"
    )
    expired = a_history(ng["index"], "2026-10-29", "2026-11-26", ["2026-11-26", "2026-12-25"], {})
    assert prepare(ng["trades"], expired) == (
        "#ERROR _PrepareTrades: ValueError: trade 'NG-001' at row 1 on Z26 expired 2026-11-25, "
        "before valuation date 2026-11-26; a physical future after its expiry is not supported"
    )
    bilateral = ENTRY["_CreateTradeTemplate"](
        "future",
        row(
            "contract_specification",
            "quantity_unit",
            "quantity_per",
            "schedule_method",
            "route",
            "settlement_method",
        ),
        row("NYMEX NG", "LOT", "month", "lastday", "bilateral", "physical"),
    )
    trades = ENTRY["_CreateTrades"](ng["index"], row(*NG_HEADERS), rows(*NG_ROWS), bilateral)
    assert evaluate(prepare(trades, ng["history"]), ng["market"]) == (
        "#ERROR _EvaluateTrades: ValueError: route is bilateral, expected cleared; bilateral "
        "valuation needs discount factors and a DV01 convention, not built yet"
    )
