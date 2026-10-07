"""What creating a batch costs, in the library and through the seam: the work resolution and
encoding report, which of the package's functions run and how many times, and which numpy C
calls cProfile sees, at five rows over two contracts and at two thousand over twenty-four. The
pins are the creator's work rules: the schedule's codes are read once each, however many rows;
each distinct contract code of the ticket is read once, through the period grammar, and the rows
holding it cost nothing more; the lag is read once per distinct text; and nothing else runs per
row, the components made in one pass of array arithmetic. The two ledgers differ in the counts
that follow the distinct codes alone, which the test says."""

from collections.abc import Callable

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FUTURE
from goosedove.instruments.fields import FieldValues
from goosedove.trades.resolution import resolved, trades
from goosedove.trades.template import TradeTemplate, trade_template

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
SIZES = [(5, 2), (2_000, 24)]
IDS = ["five rows", "two thousand rows"]
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}

# A financial index of 25 monthly contracts from October 2026, coded as the desk codes them, each
# expiring on the last business day on or before the 25th of its month, as the kernel budgets
# have it; a payment calendar of the same holidays.
MONTHS = np.arange("2026-10", "2028-11", dtype="datetime64[M]")
LETTERS = "FGHJKMNQUVXZ"
CODES = tuple(f"{LETTERS[int(m.astype(int)) % 12]}{str(m)[2:4]}" for m in MONTHS)
HOLIDAYS = np.array(["2026-12-25", "2027-01-01", "2027-12-24"], dtype="datetime64[D]")
EXPIRIES = np.busday_offset(
    MONTHS.astype("datetime64[D]") + np.timedelta64(24, "D"), 0, roll="backward", holidays=HOLIDAYS
)
GAS = index(
    "gas",
    futures_schedule(CODES, EXPIRIES, None),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([10_000.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    holiday_calendar(HOLIDAYS),
    UNITS,
)
PAYMENT_CALENDAR = holiday_calendar(HOLIDAYS)
TEMPLATE_FIELDS: dict[str, object] = {
    "quantity_unit": "lot",
    "quantity_per": "month",
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "TEST_CLEARER",
    "payment_time_lag": "+2bd",
    "payment_holiday_calendar": PAYMENT_CALENDAR,
}


def a_template(method: str = "lastday") -> TradeTemplate:
    fields = {**TEMPLATE_FIELDS, "schedule_method": method}
    return trade_template(
        FieldValues(FUTURE, 1, tuple(fields), {name: (value,) for name, value in fields.items()})
    )


def contract_rows(rows: int, contracts: int) -> NDArray[np.intp]:
    """The schedule row of each ticket row, spread over the first contracts after the boundary."""
    return 1 + np.arange(rows, dtype=np.intp) % contracts


def a_ticket(rows: int, contracts: int) -> FieldValues:
    """That many single-month rows, as the seam hands them over: dates, codes, lots and prices."""
    on = contract_rows(rows, contracts)
    return FieldValues(
        FUTURE,
        rows,
        ("trade_date", "contract_code", "quantity", "fixed_price"),
        {
            "trade_date": np.repeat(np.datetime64("2026-09-24", "D"), rows),
            "contract_code": tuple(CODES[i] for i in on),
            "quantity": np.where(np.arange(rows) % 3 == 0, -3.0, 2.0),
            "fixed_price": 3.0 + (np.arange(rows) % 7) / 100,
        },
    )


# --- the work the two children report -----------------------------------------------------------


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_creation_reports_its_rows_its_components_and_every_schedule_code(
    rows: int, contracts: int
) -> None:
    counter = WorkCounter()
    batch = trades(GAS, a_ticket(rows, contracts), a_template(), UNITS, counter)
    assert batch.encoded.groups.size == contracts
    assert counter.freeze().as_dict() == {
        "encoded_components": rows,
        "encoded_observations": rows,
        "encoded_slots": contracts,
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
    }


# --- the resolution's ledger ----------------------------------------------------------------------
# The same functions at both sizes, each once or a few times, but for four counts that follow the
# distinct contract codes of the ticket: each is read once through the period grammar, months_of,
# period_months and _label_months, and named once for its first row, _Fields.where, which the lag
# is named for as well. The schedule's 25 codes are read once each, month_and_year, whatever the
# ticket holds. Nothing runs per row.


def resolution_ledger(distinct: int) -> dict[str, int]:
    return {
        "resolved": 1,
        "_fields": 1,
        "_the_required": 1,
        "_the_specification": 1,
        "_the_conditions": 1,
        "observed": 1,  # the method's observations, made here so that payment counts from them
        "observations": 1,
        "futures_schedule_of": 3,  # the resolution's, the observations' and then the kernel's
        "_the_schedule_months": 1,
        "month_and_year": 25,
        "_the_contracts": 1,
        "_each_distinct": 2,  # the codes, then the lags
        "months_of": distinct,
        "period_months": distinct,
        "_label_months": distinct,
        "_Fields.where": distinct + 2,  # and once for the quantity unit's name
        "business_days_of": 1,  # one distinct lag
        "_the_payment_terms": 1,
        "schedule_method_of": 1,
        "route_of": 1,
        "settlement_of": 1,
        "quantity_per_of": 1,
        "choice": 4,
        "_Fields.one_text": 5,
        "_Fields.has": 15,
        "_Fields.rows": 5,
        "_Fields.texts": 3,
        "_Fields.labels": 3,
        "_Fields.numbers": 2,
        "_Fields.dates": 1,
        "_Fields.objects": 1,
        "FieldValues.has": 6,
        "FieldValues.texts": 1,
        "FieldValues.numbers": 2,
        "FieldValues.dates": 1,
        "resolved_trades": 1,
        "_the_batch": 1,
        "_the_method": 1,
        "_the_occurrences": 1,
        "_the_components": 1,
        "whole_quantities": 1,
        "finite_prices": 1,
        "_the_payment": 1,
        "_frozen_days": 2,
        "_frozen_rows": 2,
        "_frozen_numbers": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }


# The resolution's numpy, the same at both sizes but for the two months of each distinct code: the
# contracts' arithmetic, the observations' builder, which checks the order and the weights, counts
# twice and copies and freezes three columns, the payment offset and the kernel's frozen copies;
# the quantity rule is one look, whole or not, since zero is a count, zero-quantities.md; and the
# payment days are one look against the sheet's last day, 31 December 9999, since a later day
# could reach no cell.
def resolution_numpy(contracts: int) -> dict[str, int]:
    return {
        "generic.astype": 2 * contracts,  # each distinct code's two months as counts
        "ndarray.all": 1,
        "ndarray.any": 12,
        "ndarray.argsort": 4,
        "ndarray.astype": 3,
        "ndarray.clip": 1,
        "ndarray.cumsum": 4,
        "ndarray.flatten": 3,
        "ndarray.max": 1,
        "ndarray.min": 1,
        "ndarray.nonzero": 1,
        "ndarray.ravel": 1,
        "ndarray.repeat": 1,
        "ndarray.reshape": 4,
        "ndarray.round": 1,
        "ndarray.setflags": 10,  # the kernel's frozen copies and the observations' three
        "numpy.array": 14,
        "numpy.asanyarray": 8,
        "numpy.arange": 4,
        "numpy.empty": 10,
        "numpy.fromiter": 1,
        "numpy.normalize_axis_index": 1,
        "ufunc.reduce": 15,
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_resolution_reads_each_distinct_code_once_and_nothing_per_row(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    ticket, template = a_ticket(rows, contracts), a_template()
    assert call_profile(
        lambda: resolved(GAS, ticket, template, WorkCounter())
    ) == resolution_ledger(contracts)
    assert numpy_calls(lambda: resolved(GAS, ticket, template, WorkCounter())) == resolution_numpy(
        contracts
    )


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_the_penultimate_method_adds_one_look_at_the_expiries_and_nothing_per_row(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # The pen's observations read the index's holiday calendar once and ask once whether every
    # expiry is open; the step back and the payment offset are numpy's business-day functions,
    # dispatched in C and unseen. The counts the batch reports are lastday's.
    ticket, template = a_ticket(rows, contracts), a_template("penultimate")
    counter = WorkCounter()
    terms, observations = resolved(GAS, ticket, template, counter)
    assert terms.payment is not None
    np.testing.assert_array_equal(
        observations.date, np.busday_offset(EXPIRIES[terms.contract], -1, holidays=HOLIDAYS)
    )
    np.testing.assert_array_equal(
        terms.payment.date, np.busday_offset(observations.date, 2, holidays=HOLIDAYS)
    )
    assert counter.freeze().as_dict() == {
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
    }
    assert call_profile(lambda: resolved(GAS, ticket, template, WorkCounter())) == {
        **resolution_ledger(contracts),
        "with_holiday_calendar": 1,
        "open_days": 1,
    }
    assert numpy_calls(lambda: resolved(GAS, ticket, template, WorkCounter())) == {
        **resolution_numpy(contracts),
        "ndarray.any": 13,  # whether any expiry is closed
        "ufunc.reduce": 16,
    }


# --- through the seam ---------------------------------------------------------------------------
# _CreateTrades: the four arguments alone, the two handles resolved, the ticket bound against the
# template's instrument with one look per column, then the library's two children and one
# publication; the same at five rows and at 2,500 but for the distinct-code counts above.

SERIAL = np.datetime64("1899-12-30", "D")


def serial(day: np.datetime64) -> float:
    return float((day - SERIAL).astype(np.int64))


@pytest.fixture(scope="module")
def sheet() -> dict[str, object]:
    schedule = PATH["_CreateFuturesSchedule"](
        Cells.from_rows([[code] for code in CODES]),
        Cells.from_rows([[serial(day)] for day in EXPIRIES]),
        bridge.MISSING,
    )
    holidays = PATH["_CreateHolidayCalendar"](Cells.from_rows([[serial(day)] for day in HOLIDAYS]))
    conventions = PATH["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU")
    specifications = PATH["_CreateContractSpecifications"](
        Cells.from_rows(
            [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
        ),
        Cells.from_rows([["lot", 10000.0, "MMBTU", 0.0, 0.0]]),
    )
    values = [
        holidays if name == "payment_holiday_calendar" else value
        for name, value in TEMPLATE_FIELDS.items()
    ]
    return {
        "index": PATH["_CreateIndex"]("gas", schedule, conventions, specifications, holidays),
        "template": PATH["_CreateTradeTemplate"](
            "future", Cells.from_rows([list(TEMPLATE_FIELDS)]), Cells.from_rows([values])
        ),
        "headers": Cells.from_rows([["trade_date", "contract_code", "quantity", "fixed_price"]]),
    }


def a_body(rows: int, contracts: int) -> Cells:
    on = contract_rows(rows, contracts)
    return Cells.from_rows(
        [
            [46289.0, CODES[on[i]], -3.0 if i % 3 == 0 else 2.0, 3.0 + (i % 7) / 100]
            for i in range(rows)
        ]
    )


@pytest.mark.parametrize(
    ("rows", "contracts"), [(5, 2), (2_500, 24)], ids=["five rows", "2,500 rows"]
)
def test_the_creator_binds_once_per_column_resolves_once_and_publishes_once(
    call_profile: CallProfile, sheet: dict[str, object], rows: int, contracts: int
) -> None:
    body = a_body(rows, contracts)

    def call() -> object:
        return PATH["_CreateTrades"](sheet["index"], sheet["headers"], body, sheet["template"])

    assert str(call()).split(":")[1:3] == ["trades", "gas"]
    seam = {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,
        "_text": 2,  # the two handles' texts
        "_resolve": 2,  # the index and the template, one lookup each
        "_text_row": 1,
        "_texts": 1,
        "_shape": 1,
        "_mixed": 1,
        "by_template": 1,  # the template selects the instrument
        "_bind_fields": 1,
        "_dates_of": 1,
        "_as_days": 1,
        "_not_dates": 1,
        "_texts_of": 1,
        "_numbers_of": 2,
        "MixedArray.shape": 2,
        "_one_row": 1,
        "_CreateTrades": 1,
        "trades": 1,
        "encoded": 1,
        "_the_references": 1,
        "with_holiday_calendar": 1,
        "open_days": 1,
        "contract_on": 1,
        "_the_slots": 1,
        "UnitConversions.factor": 2,
        "UnitConversions.category": 2,
        "_one_payment_day_per_group": 1,
        "_publish": 1,
    }
    expected = {**resolution_ledger(contracts), **seam, "WorkCounter.hit": 6}
    assert call_profile(call) == expected


def test_the_template_creator_reads_each_value_once_and_publishes_once(
    call_profile: CallProfile, sheet: dict[str, object]
) -> None:
    holidays = PATH["_CreateHolidayCalendar"](Cells.from_rows([[46352.0]]))
    headers = Cells.from_rows([list(TEMPLATE_FIELDS)])
    values = Cells.from_rows(
        [
            [
                holidays if name == "payment_holiday_calendar" else value
                for name, value in TEMPLATE_FIELDS.items()
            ]
        ]
    )

    def call() -> object:
        return PATH["_CreateTradeTemplate"]("future", headers, values)

    assert str(call()).split(":")[1] == "trade_template"
    assert call_profile(call) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text": 2,  # the name, and the handle cell's text
        "_text_row": 1,
        "_texts": 1,
        "_shape": 1,
        "_one_row": 1,
        "_field_row": 1,  # one row, the template's shape, through the mixed rule
        "_mixed": 1,
        "MixedArray.shape": 3,
        "by_name": 1,
        "instrument": 1,
        "_bind_fields": 1,
        "_texts_of": 7,  # seven text and code columns
        "_handles_of": 1,
        "_resolve": 1,  # the one handle cell
        "_CreateTradeTemplate": 1,
        "trade_template": 1,
        "_value": 8,  # one per field
        "FieldValues.field": 8,
        "FieldValues.field.<locals>.<genexpr>": 16,
        "FieldValues.texts": 7,
        "FieldValues.objects": 1,
        "route_of": 1,
        "settlement_of": 1,
        "schedule_method_of": 1,
        "quantity_per_of": 1,
        "choice": 4,
        "business_days_of": 1,
        "_publish": 1,
    }
