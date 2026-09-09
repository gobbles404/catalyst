"""What one call through the seam costs, itemized: exact and deterministic."""

from collections.abc import Callable

import numpy as np

from goosedove.excel import bridge

CallProfile = Callable[[Callable[[], object]], dict[str, int]]


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


# A numeric range is one vectorized check, however many cells it holds.
def test_accepted_column_call_itemized(call_profile: CallProfile) -> None:
    column = np.arange(10_000.0).reshape(-1, 1)
    bridge.call("SumColumn", [column])
    assert call_profile(lambda: bridge.call("SumColumn", [column])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,
        "SumColumn": 1,
    }


# So is a column of dates.
def test_accepted_date_column_call_itemized(call_profile: CallProfile) -> None:
    column = np.arange(61.0, 10_061.0).reshape(-1, 1)
    bridge.call("FirstDate", [column])
    assert call_profile(lambda: bridge.call("FirstDate", [column])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_date_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_dates": 1,
        "_dates_of": 1,
        "FirstDate": 1,
    }


# A blank deep inside a numeric range is found and named without a walk.
def test_rejected_numeric_block_names_the_cell_without_a_walk(call_profile: CallProfile) -> None:
    column = np.arange(10_000.0).reshape(-1, 1)
    column[5_000, 0] = np.nan
    assert call_profile(lambda: bridge.call("SumColumn", [column])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,
        "_first_bad": 1,
        "_cell_of": 1,
        "_Rejected.__init__": 1,
        "describe": 1,
    }


# A range with a text cell arrives cell by cell and has already failed; the walk
# stops at the first bad cell.
def test_rejected_range_call_walks_to_the_first_bad_cell(call_profile: CallProfile) -> None:
    rows = [[1.0, "n/a"], [3.0, 4.0]]
    assert call_profile(lambda: bridge.call("SumArray", [rows])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_numbers": 1,
        "_cells": 1,
        "_number": 2,
        "_Rejected.__init__": 2,
        "describe": 1,
    }


# Text is the one range that arrives cell by cell on success, so its cost is per cell.
def test_accepted_text_column_call_itemized(call_profile: CallProfile) -> None:
    names = [[f"name{i}"] for i in range(10_000)]
    bridge.call("JoinColumn", [names])
    assert call_profile(lambda: bridge.call("JoinColumn", [names])) == {
        "call": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_texts": 1,
        "_cells": 1,
        "_text": 10_000,
        "JoinColumn": 1,
    }
