"""What one call through the seam costs, itemized: exact and deterministic."""

from collections.abc import Callable

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells, Column, DateColumn, TextColumn, excel_function

CallProfile = Callable[[Callable[[], object]], dict[str, int]]


# The column, date, and text looks have no probe, because the host cannot tell those ranges
# from any other; these three exist only to count the Python side of each look. Defined
# here, outside the package, they are not themselves counted.
@excel_function
def FirstOfNumbers(values: Column) -> float:
    return float(values[0])


@excel_function
def FirstOfDates(dates: DateColumn) -> str:
    return str(dates[0])


@excel_function
def FirstOfNames(names: TextColumn) -> str:
    return names[0]


def test_accepted_scalar_call_itemized(call_profile: CallProfile) -> None:
    bridge.call("Add", [1.0, 2.0])
    assert call_profile(lambda: bridge.call("Add", [1.0, 2.0])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 2,
        "_number": 2,
        "Add": 1,
    }


def test_rejected_scalar_call_stops_at_the_first_failure(call_profile: CallProfile) -> None:
    assert call_profile(lambda: bridge.call("Add", ["x", 2.0])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_number": 1,
        "_Rejected.__init__": 1,
        "describe": 1,
    }


# Every range is one vectorized look, however many cells it holds and whatever they hold.
def test_accepted_array_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(i)] for i in range(10_000)])
    bridge.call("SumArray", [column])
    assert call_profile(lambda: bridge.call("SumArray", [column])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_numbers": 1,
        "SumArray": 1,
    }


def test_accepted_column_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(i)] for i in range(10_000)])
    bridge.call("FirstOfNumbers", [column])
    assert call_profile(lambda: bridge.call("FirstOfNumbers", [column])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,
    }


def test_accepted_date_column_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(61 + i)] for i in range(10_000)])
    bridge.call("FirstOfDates", [column])
    assert call_profile(lambda: bridge.call("FirstOfDates", [column])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_date_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_dates": 1,
    }


def test_accepted_text_column_call_itemized(call_profile: CallProfile) -> None:
    names = Cells.from_rows([[f"name{i}"] for i in range(10_000)])
    bridge.call("FirstOfNames", [names])
    assert call_profile(lambda: bridge.call("FirstOfNames", [names])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_texts": 1,
    }


# A bad cell deep inside a range is found and named without a walk, whatever it holds.
REJECTED_DEEP = {
    "call": 1,
    "_arguments": 1,
    "_validate": 1,
    "_numbers": 1,
    "_first_bad": 1,
    "_cell": 1,
    "_Rejected.__init__": 1,
    "describe": 1,
}


def test_blank_deep_in_a_column_is_named_without_a_walk(call_profile: CallProfile) -> None:
    rows: list[list[object]] = [[float(i)] for i in range(10_000)]
    rows[5_000][0] = None
    column = Cells.from_rows(rows)
    assert call_profile(lambda: bridge.call("SumArray", [column])) == REJECTED_DEEP


def test_text_deep_in_a_column_is_named_without_a_walk(call_profile: CallProfile) -> None:
    rows: list[list[object]] = [[float(i)] for i in range(10_000)]
    rows[5_000][0] = "n/a"
    column = Cells.from_rows(rows)
    assert call_profile(lambda: bridge.call("SumArray", [column])) == REJECTED_DEEP
