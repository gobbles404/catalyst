"""What the valuation path costs through the seam: _PrepareTrades, _EvaluateTrades and the two
reports, each as the host calls it. The pins are the pipeline's rules on the sheet: preparing
resolves two handles and runs the kernel's preparation and nothing of the encoding; a tick
resolves two handles and runs the evaluation alone, one quote per live reference, nothing of the
preparation; a report resolves one handle and lays out one row, no kernel call at all. The same
functions at five rows and at two thousand, and the peaks by slot and by reference, never by
trade."""

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from test_seam_allocation import SLACK, least_peak

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
FIRST = np.datetime64("1899-12-30", "D")
SIZES = [(5, 2), (2_000, 24)]
IDS = ["five trades", "two thousand trades"]

# The budgets' index on the sheet: 25 monthly contracts from October 2026, each expiring on the
# last business day on or before the 25th, valued on 10 March 2027 with a settle of 3.00 on every
# fixed day and a quote per contract from the prompt on; the batch spread over the first 2 or 24
# contracts after the boundary, so that four or five contracts have fixed and the rest are live.
MONTHS = np.arange("2026-10", "2028-11", dtype="datetime64[M]")
LETTERS = "FGHJKMNQUVXZ"
CODES = [f"{LETTERS[int(m.astype(int)) % 12]}{str(m)[2:4]}" for m in MONTHS]
HOLIDAYS = np.array(["2026-12-25", "2027-01-01", "2027-12-24"], dtype="datetime64[D]")
EXPIRIES = np.busday_offset(
    MONTHS.astype("datetime64[D]") + np.timedelta64(24, "D"), 0, roll="backward", holidays=HOLIDAYS
)
AS_OF = np.datetime64("2027-03-10", "D")


def serial(day: np.datetime64) -> float:
    return float((day - FIRST).astype(np.int64))


def column(values: list[float]) -> Cells:
    return Cells.from_rows([[v] for v in values])


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    schedule = PATH["_CreateFuturesSchedule"](
        Cells.from_rows([[code] for code in CODES]),
        column([serial(d) for d in EXPIRIES]),
        bridge.MISSING,
    )
    holidays = PATH["_CreateHolidayCalendar"](column([serial(d) for d in HOLIDAYS]))
    conventions = PATH["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU")
    specifications = PATH["_CreateContractSpecifications"](
        Cells.from_rows(
            [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
        ),
        Cells.from_rows([["lot", 10000.0, "MMBTU", 0.0, 0.0]]),
    )
    index = PATH["_CreateIndex"](
        "gas", "Sample gas index", schedule, conventions, specifications, holidays, "lot"
    )
    fields = [
        "quantity_unit",
        "quantity_per",
        "schedule_method",
        "route",
        "settlement_method",
        "clearing_house",
        "payment_time_lag",
        "payment_holiday_calendar",
    ]
    template = PATH["_CreateTradeTemplate"](
        "future",
        Cells.from_rows([fields]),
        Cells.from_rows(
            [["lot", "month", "lastday", "cleared", "financial", "TEST", "+2bd", holidays]]
        ),
    )
    days = np.arange(EXPIRIES[0] + np.timedelta64(1, "D"), AS_OF)
    days = days[np.is_busday(days, holidays=HOLIDAYS)]
    fixings = PATH["_CreateFuturesFixings"](
        column([serial(d) for d in days[::-1]]), column([3.0] * days.size), index
    )
    calendar = PATH["_CreateCalendar"](PATH["_CreateValuationDate"](serial(AS_OF), 0.5), index)
    history = PATH["_CreateMarketHistory"](calendar, fixings)
    live = int((EXPIRIES >= AS_OF).sum())
    market = PATH["_CreateMarket"](
        history, PATH["_CreatePriceVector"]("gas", column([3.5 + i / 100 for i in range(live)]))
    )
    headers = Cells.from_rows([["trade_date", "contract_code", "quantity", "fixed_price"]])
    return {
        "index": index,
        "template": template,
        "headers": headers,
        "history": history,
        "market": market,
    }


def a_batch(sheet: dict[str, Any], rows: int, contracts: int) -> str:
    body = Cells.from_rows(
        [
            [46289.0, CODES[1 + i % contracts], 2.0 if i % 3 else -3.0, 3.0 + (i % 7) / 100]
            for i in range(rows)
        ]
    )
    return str(PATH["_CreateTrades"](sheet["index"], sheet["headers"], body, sheet["template"]))


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_preparing_resolves_two_handles_and_runs_the_kernels_preparation_alone(
    call_profile: CallProfile, sheet: dict[str, Any], rows: int, contracts: int
) -> None:
    trades = a_batch(sheet, rows, contracts)

    def prepare() -> object:
        return PATH["_PrepareTrades"](trades, sheet["history"])

    assert str(prepare()).split(":")[1:3] == ["prepared_trades", "gas"]
    assert call_profile(prepare) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,
        "_resolve": 2,
        "_PrepareTrades": 1,
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
        "_publish": 1,
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_tick_resolves_two_handles_and_runs_the_evaluation_alone(
    call_profile: CallProfile, sheet: dict[str, Any], rows: int, contracts: int
) -> None:
    prepared = PATH["_PrepareTrades"](a_batch(sheet, rows, contracts), sheet["history"])

    def tick() -> object:
        return PATH["_EvaluateTrades"](prepared, sheet["market"])

    assert str(tick()).split(":")[1:3] == ["trade_results", "gas"]
    assert call_profile(tick) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,
        "_resolve": 2,
        "_EvaluateTrades": 1,
        "trade_results": 1,
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
        "_publish": 1,
    }


def test_a_report_resolves_one_handle_and_lays_out_one_row(
    call_profile: CallProfile, sheet: dict[str, Any]
) -> None:
    prepared = PATH["_PrepareTrades"](a_batch(sheet, 5, 2), sheet["history"])
    results = PATH["_EvaluateTrades"](prepared, sheet["market"])
    live = bridge.live_handles()
    for name, numeric, dated in (
        ("_ReportValues", 3, True),
        ("_ReportRisk", 3, True),
        ("_ReportReserves", 3, False),  # three totals and a currency, no day, since #NN
    ):
        profile = call_profile(lambda name=name: PATH[name](results))
        expected = {
            "Registered.run": 1,
            "_arguments": 1,
            "_validate": 1,
            "_text": 1,
            "_resolve": 1,
            name: 1,
            "MixedArray.table": 1,
            "_table_column": numeric,  # the numbers, and the day where the report has one
            "_mixed_out": 1,
            "_bad_mixed": 1,  # the way out's check of the rectangle, finding nothing wrong
        }
        if dated:
            expected["_serials"] = 1  # the day to its serial
            expected["_unit"] = 1
        assert profile == expected, name
    assert bridge.live_handles() == live  # a report publishes nothing


# Memory on the sheet, 2,500 single-month trades over 24 contracts, 24 slots: preparing peaks at
# the kernel's arrays by slot, some thirty of them at 24 elements each, where the hundred bytes
# an array costs beside its data outweighs the data, and the handle's small objects; a tick at
# the quotes and the contributions by live reference and slot; a report at one row laid out;
# none by trade, since the batch of five rows and two slots prepares at 3,527 bytes and the one
# of 2,500 rows at 8,912. Measured 2026-10-04: preparing 8,912 bytes, a tick 1,144, the values
# report 1,967 and the risk report 1,948.
def test_the_valuation_path_allocates_by_slot_and_never_by_trade(sheet: dict[str, Any]) -> None:
    trades = a_batch(sheet, 2_500, 24)
    assert least_peak(lambda: PATH["_PrepareTrades"](trades, sheet["history"])) <= 10 * SLACK
    prepared = PATH["_PrepareTrades"](trades, sheet["history"])
    assert least_peak(lambda: PATH["_EvaluateTrades"](prepared, sheet["market"])) <= 2 * SLACK
    results = PATH["_EvaluateTrades"](prepared, sheet["market"])
    assert least_peak(lambda: PATH["_ReportValues"](results)) <= 2 * SLACK
    assert least_peak(lambda: PATH["_ReportRisk"](results)) <= 2 * SLACK
    assert least_peak(lambda: PATH["_ReportReserves"](results)) <= 2 * SLACK
