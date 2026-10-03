"""Static trade ingestion: one batch path, one binding pass, bounded storage and display."""

from collections.abc import Callable

import numpy as np
import pytest
from test_seam_allocation import SLACK, peak_bytes

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.trades.futures_trades import futures_trades

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
HEADERS = Cells.from_rows(
    [["trade_id", "trade_date", "contract_code", "signed_lots", "trade_price"]]
)
SPECIFICATION_HEADERS = Cells.from_rows(
    [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)


def ng_index() -> Index:
    return index(
        "Henry Hub NYMEX",
        futures_schedule(
            ("Z26", "F27"),
            np.array(["2026-11-25", "2026-12-29"], dtype="datetime64[D]"),
            None,
        ),
        index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
        contract_specifications(
            ("NYMEX NG",),
            np.array([10_000.0]),
            ("MMBTU",),
            np.array([0.0]),
            np.array([0.0]),
            UNITS,
        ),
        holiday_calendar(np.array(["2026-12-25"], dtype="datetime64[D]")),
        UNITS,
    )


def ng_handle() -> object:
    return ENTRY["_CreateIndex"](
        "Henry Hub NYMEX",
        ENTRY["_CreateFuturesSchedule"](
            Cells.from_rows([["Z26"], ["F27"]]),
            Cells.from_rows([[46351.0], [46385.0]]),
            MISSING,
        ),
        ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU"),
        ENTRY["_CreateContractSpecifications"](
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10_000.0, "MMBTU", 0.0, 0.0]]),
        ),
        ENTRY["_CreateHolidayCalendar"](Cells.from_rows([[46381.0]])),
    )


def trade_body(count: int) -> Cells:
    """Short repeated labels avoid measuring the length of identifiers instead of row work."""
    return Cells.from_rows(
        [
            ["t", 46290.0, "F27" if row % 2 else "Z26", -2.0 if row % 2 else 3.0, 3.25]
            for row in range(count)
        ]
    )


def test_one_and_many_use_one_creator_and_one_contract_binding(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    handle = ng_handle()
    profiles: list[dict[str, int]] = []
    numpy_profiles: list[dict[str, int]] = []
    for count in (1, 10_000):
        body = trade_body(count)

        def create(body: Cells = body) -> object:
            return ENTRY["_CreateFuturesTrades"](handle, "NYMEX NG", HEADERS, body)

        create()
        profile = call_profile(create)
        # Identifiers are resolved once per occurrence. The only Python calls whose
        # count grows with the rows are this text-binding generator: N yielded values
        # and one close. fromiter preallocates the array at its known final length.
        assert profile.pop("_contract_positions.<locals>.<genexpr>") == count + 1
        assert profile["_CreateFuturesTrades"] == 1
        assert profile["futures_trades"] == 1
        assert profile["_contract_positions"] == 1
        assert profile["_publish"] == 1
        profiles.append(profile)
        numpy_profiles.append(numpy_calls(create))
    assert profiles[0] == profiles[1]
    assert numpy_profiles[0] == numpy_profiles[1]
    assert numpy_profiles[0]["numpy.fromiter"] == 1
    assert numpy_profiles[0]["ndarray.setflags"] == 4


def test_reading_one_or_many_trades_does_not_repeat_binding(call_profile: CallProfile) -> None:
    index_handle = ng_handle()
    profiles: list[dict[str, int]] = []
    for count in (1, 10_000):
        handle = ENTRY["_CreateFuturesTrades"](index_handle, "NYMEX NG", HEADERS, trade_body(count))

        def read(handle: object = handle) -> object:
            return ENTRY["util_ReadHandle"](handle)

        read()
        profile = call_profile(read)
        assert profile["futures_trades_table"] == 1
        assert profile["MixedArray.table"] == 1
        assert profile["_table_column"] == 4
        assert "futures_trades" not in profile
        assert "_contract_positions" not in profile
        assert "_publish" not in profile
        profiles.append(profile)
    assert profiles[0] == profiles[1]


@pytest.mark.parametrize("count", [1, 10_000])
def test_retained_numeric_storage_is_four_columns_and_text_is_shared(count: int) -> None:
    shared = ng_index()
    ids = ("t",) * count
    codes = ("Z26",) * count
    dates = np.full(count, np.datetime64("2026-09-25", "D"))
    lots = np.ones(count)
    prices = np.full(count, 3.25)
    trades = futures_trades(shared, "NYMEX NG", ids, dates, codes, lots, prices)
    columns = (
        trades.trade_dates,
        trades.signed_lots,
        trades.trade_prices,
        trades.contract_positions,
    )
    bytes_per_row = 3 * np.dtype(np.float64).itemsize + np.dtype(np.intp).itemsize
    assert sum(column.nbytes for column in columns) == bytes_per_row * count
    assert all(column.flags.owndata and not column.flags.writeable for column in columns)
    assert trades.trade_ids is ids
    assert trades.contract_codes is codes
    assert trades.index is shared
    assert not np.shares_memory(trades.trade_dates, dates)
    assert not np.shares_memory(trades.signed_lots, lots)
    assert not np.shares_memory(trades.trade_prices, prices)


@pytest.mark.parametrize("count", [120, 10_000])
def test_ingestion_and_readback_have_linear_peak_memory(count: int) -> None:
    index_handle = ng_handle()
    body = trade_body(count)

    def create() -> object:
        return ENTRY["_CreateFuturesTrades"](index_handle, "NYMEX NG", HEADERS, body)

    # The input exists before the measured call. The allowance includes the seam's
    # text gathers/date conversion, four retained columns and validation temporaries.
    assert peak_bytes(create) <= 72 * count + 4 * SLACK
    handle = create()
    # Six output columns, two heading rows, the text gather, and the seam's checks.
    assert peak_bytes(lambda: ENTRY["util_ReadHandle"](handle)) <= 172 * count + 4 * SLACK
