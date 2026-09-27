"""What one call through the seam costs, itemized: exact and deterministic."""

import ctypes
from collections.abc import Callable

import numpy as np
import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells

CallProfile = Callable[[Callable[[], object]], dict[str, int]]

# Each registered function's prepared path, fetched once as the host does at registration; the
# three looks in conftest.py (FirstOfNumbers, FirstOfDates, FirstOfNames) are registered
# when pytest loads it, so they are in it too.
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}


def test_accepted_scalar_call_itemized(call_profile: CallProfile) -> None:
    PATH["Add"](1.0, 2.0)
    assert call_profile(lambda: PATH["Add"](1.0, 2.0)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_number": 2,
        "Add": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_rejected_scalar_call_stops_at_the_first_failure(call_profile: CallProfile) -> None:
    assert call_profile(lambda: PATH["Add"]("x", 2.0)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_number": 1,
        "_Rejected.__init__": 1,
        "describe": 1,
    }


# A range of numbers needs no look: the host's summary settles it. Whatever a range holds, the
# seam's own functions run the same number of times.
def test_accepted_array_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(i)] for i in range(10_000)])
    PATH["SumArray"](column)
    assert call_profile(lambda: PATH["SumArray"](column)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_numbers": 1,
        "SumArray": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_accepted_column_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(i)] for i in range(10_000)])
    PATH["FirstOfNumbers"](column)
    assert call_profile(lambda: PATH["FirstOfNumbers"](column)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_accepted_date_column_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(61 + i)] for i in range(10_000)])
    PATH["FirstOfDates"](column)
    assert call_profile(lambda: PATH["FirstOfDates"](column)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_date_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_dates": 1,
        "_not_dates": 1,  # the two helpers the date rule shares with a table's column of dates
        "_as_days": 1,
        "_text_out": 1,
        "_scalar": 1,
    }


def test_accepted_text_column_call_itemized(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    names = Cells.from_rows([[f"name{i}"] for i in range(10_000)])
    PATH["FirstOfNames"](names)
    assert call_profile(lambda: PATH["FirstOfNames"](names)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_texts": 1,
        "_text_out": 1,
        "_scalar": 1,
    }
    # The host's tuple of text cells is the column itself, handed over as it is: nothing is
    # asked of numpy. Before, the tuple went into an object array and back out of one.
    assert numpy_calls(lambda: PATH["FirstOfNames"](names)) == {}


# A bad cell deep inside a range is found and named without a walk, whatever it holds.
REJECTED_DEEP = {
    "Registered.run": 1,
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
    assert call_profile(lambda: PATH["SumArray"](column)) == REJECTED_DEEP


def test_text_deep_in_a_column_is_named_without_a_walk(call_profile: CallProfile) -> None:
    rows: list[list[object]] = [[float(i)] for i in range(10_000)]
    rows[5_000][0] = "n/a"
    column = Cells.from_rows(rows)
    assert call_profile(lambda: PATH["SumArray"](column)) == REJECTED_DEEP


# --- every probe, itemized on both ledgers ------------------------------------
# The package ledger is the seam's own functions; the numpy ledger is the copies and
# reductions numpy ran for them. Inputs are built inside the test: a large parameter would
# put its repr into the test id, which pytest keeps in an environment variable that Windows
# caps at 32,767 characters.

N = 10_000


def column() -> Cells:
    return Cells.from_rows([[float(i)] for i in range(N)])


def row() -> Cells:
    return Cells.from_rows([[float(i) for i in range(N)]])


def grid() -> Cells:
    return Cells.from_rows([[float(r * 100 + c) for c in range(100)] for r in range(100)])


def test_zero_is_the_floor_of_one_call(call_profile: CallProfile) -> None:
    PATH["Zero"]()
    assert call_profile(lambda: PATH["Zero"]()) == {
        "Registered.run": 1,
        "_arguments": 1,
        "Zero": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_a_missing_argument_takes_its_default_without_a_look(call_profile: CallProfile) -> None:
    PATH["Times"](5.0, MISSING)
    assert call_profile(lambda: PATH["Times"](5.0, MISSING)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_number": 1,
        "Times": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_text_in_and_out_itemized(call_profile: CallProfile) -> None:
    PATH["EchoText"]("WTI")
    assert call_profile(lambda: PATH["EchoText"]("WTI")) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text": 1,
        "EchoText": 1,
        "_text_out": 1,
        "_scalar": 1,
    }


def test_a_boolean_in_and_out_itemized(call_profile: CallProfile) -> None:
    PATH["EchoBoolean"](True)
    assert call_profile(lambda: PATH["EchoBoolean"](True)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_boolean": 1,
        "EchoBoolean": 1,
        "_boolean_out": 1,
        "_scalar": 1,
    }


def test_a_failing_body_costs_no_look(call_profile: CallProfile) -> None:
    PATH["Fail"]()
    assert call_profile(lambda: PATH["Fail"]()) == {
        "Registered.run": 1,
        "_arguments": 1,
        "Fail": 1,
    }


def test_two_ranges_are_two_checks_and_no_look(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    a, b = column(), column()
    PATH["Dot"](a, b)
    assert call_profile(lambda: PATH["Dot"](a, b)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_column": 2,
        "_one_column": 2,
        "_shape": 2,
        "_numbers": 2,
        "Dot": 1,
        "_number_out": 1,
        "_scalar": 1,
    }
    # Two ranges of numbers: the host's summary settles both, so numpy takes no look at all.
    assert numpy_calls(lambda: PATH["Dot"](a, b)) == {}


def test_a_sum_is_one_reduction_and_no_look(numpy_calls: CallProfile) -> None:
    values = column()
    PATH["SumArray"](values)
    assert numpy_calls(lambda: PATH["SumArray"](values)) == {
        "ndarray.sum": 1,
        "ufunc.reduce": 1,
    }


# The mixed road out runs the same functions and takes the same three looks whatever the
# rectangle holds: one for a cell holding no value, one for a number that is not finite, one
# for a boolean slot that is not 0 or 1. The texts are joined and encoded once, off the ledger,
# and split per text only when the total runs past what a cell holds.
@pytest.mark.parametrize("rectangle", ["numbers", "mixed"])
def test_a_mixed_array_out_takes_three_looks_whatever_it_holds(
    rectangle: str, call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    cells = column() if rectangle == "numbers" else mixed()
    PATH["EchoMixed"](cells)
    assert call_profile(lambda: PATH["EchoMixed"](cells)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_mixed": 1,
        "EchoMixed": 1,
        "_mixed_out": 1,
        "_bad_mixed": 1,  # the cells holding no value, flagged in one array
    }
    assert numpy_calls(lambda: PATH["EchoMixed"](cells)) == {
        "ndarray.any": 3,
        "numpy.ascontiguousarray": 2,  # the kinds and the numbers, already contiguous: no copy
        "ufunc.reduce": 3,
    }


def mixed() -> Cells:
    """A trade's shape: a name, a serial, a quantity and a flag, over and over."""
    return Cells.from_rows([[f"n{i}", 46164.0 + i, float(i), i % 2 == 0] for i in range(N // 4)])


# A mixed range is the numeric call with one rule changed, and that is the whole difference:
# the summary settles the kinds, so numpy is asked for nothing on either.
def test_a_mixed_range_costs_the_numeric_call_with_one_rule_changed(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    numbers, cells = column(), mixed()
    PATH["CountArray"](numbers)
    PATH["CountMixed"](cells)
    assert call_profile(lambda: PATH["CountArray"](numbers)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_numbers": 1,
        "CountArray": 1,
        "_whole_out": 1,
        "_scalar": 1,
    }
    assert call_profile(lambda: PATH["CountMixed"](cells)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_mixed": 1,  # where the numeric call runs _numbers
        "MixedArray.shape": 1,  # and the record reads its own rows and columns
        "CountMixed": 1,
        "_whole_out": 1,
        "_scalar": 1,
    }
    assert numpy_calls(lambda: PATH["CountArray"](numbers)) == {}
    assert numpy_calls(lambda: PATH["CountMixed"](cells)) == {}


# Whatever the offending cell holds, and however it fails, the same functions run once each.
def test_a_mixed_range_names_its_first_bad_cell_the_same_way_whichever_way_it_is_bad(
    call_profile: CallProfile,
) -> None:
    rejected = {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_mixed": 1,
        "_bad_mixed": 1,
        "_first_bad": 1,
        "_cell": 1,
        "_Rejected.__init__": 1,
        "describe": 1,
    }
    blank: list[list[object]] = [[float(i)] for i in range(N)]
    blank[N // 2][0] = None
    empty: list[list[object]] = [[f"n{i}"] for i in range(N)]
    empty[N // 2][0] = ""
    for rows in (blank, empty):
        values = Cells.from_rows(rows)
        PATH["CountMixed"](values)
        assert call_profile(lambda v=values: PATH["CountMixed"](v)) == rejected


HEADERS = Cells.from_rows([["date", "product", "quantity", "cleared"]])


def trades() -> Cells:
    """A table's body at N cells: a date, a text, a number and a flag per row."""
    return Cells.from_rows([[46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(N // 4)])


# A table is the mixed call with the binding and one rule per column on top: every bridge
# function runs once, and numpy takes one look per column, one conversion per date or boolean
# column, and one gather for the column of text, whatever the number of rows.
def test_a_table_in_itemized(call_profile: CallProfile, numpy_calls: CallProfile) -> None:
    body = trades()
    PATH["SumQuantity"](HEADERS, body)
    assert call_profile(lambda: PATH["SumQuantity"](HEADERS, body)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text_row": 1,  # the header row, as any row of text
        "_one_row": 1,
        "_shape": 1,
        "_texts": 1,
        "_mixed": 1,  # the body, admitted as any mixed range
        "MixedArray.shape": 1,
        "_refine": 1,  # then bound and refined
        "_bind": 1,
        "_refine.<locals>.<lambda>": 1,  # the text places, made once on first use
        "_text_places": 1,
        "_dates_of": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_texts_of": 1,
        "_numbers_of": 1,
        "_booleans_of": 1,
        "SumQuantity": 1,
        "_number_out": 1,
        "_scalar": 1,
    }
    assert numpy_calls(lambda: PATH["SumQuantity"](HEADERS, body)) == {
        "ndarray.any": 4,  # one look per column
        "ndarray.astype": 3,  # the date column twice on its way to days, the boolean column once
        "numpy.array": 1,  # the texts as an array, for the gather
        "ndarray.cumsum": 1,  # the text cells above each row
        "ndarray.sum": 3,  # text cells per row, text cells to the left, and the probe's own sum
        "ufunc.reduce": 7,
    }


# A bad cell deep in a column is found by that column's look and named without a walk, and
# the columns after it are never looked at.
def test_a_table_rejected_on_a_cell_names_it_after_one_look_at_its_column(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    rows: list[list[object]] = [[46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(N // 4)]
    rows[N // 8][2] = "x"
    body = Cells.from_rows(rows)
    PATH["SumQuantity"](HEADERS, body)
    assert call_profile(lambda: PATH["SumQuantity"](HEADERS, body)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text_row": 1,
        "_one_row": 1,
        "_shape": 1,
        "_texts": 1,
        "_mixed": 1,
        "MixedArray.shape": 1,
        "_refine": 1,
        "_bind": 1,
        "_refine.<locals>.<lambda>": 1,
        "_text_places": 1,
        "_dates_of": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_texts_of": 1,
        "_numbers_of": 1,  # the third column fails here, and the fourth is never reached
        "_bad_cell": 1,
        "_cell": 1,
        "describe": 1,
    }
    assert numpy_calls(lambda: PATH["SumQuantity"](HEADERS, body)) == {
        "ndarray.any": 3,
        "ndarray.argmax": 1,  # the first bad cell of the column
        "ndarray.ravel": 1,  # and its text, by counting the text codes before it
        "ndarray.astype": 2,
        "numpy.array": 1,
        "ndarray.cumsum": 1,
        "ndarray.sum": 2,
        "ufunc.reduce": 5,
    }


def test_a_column_out_copies_nothing(call_profile: CallProfile, numpy_calls: CallProfile) -> None:
    values = column()
    PATH["EchoColumn"](values)
    assert call_profile(lambda: PATH["EchoColumn"](values)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,
        "EchoColumn": 1,
        "_column_out": 1,
        "_dimensions": 1,
        "_finite": 1,
    }
    # No look in, the summary settles it; one look out (all); ascontiguousarray hands back the
    # same array.
    assert numpy_calls(lambda: PATH["EchoColumn"](values)) == {
        "ndarray.all": 1,
        "ndarray.reshape": 1,
        "numpy.ascontiguousarray": 1,
        "ufunc.reduce": 1,
    }


def test_a_row_out_costs_what_a_column_out_costs(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    values = row()
    PATH["EchoRow"](values)
    assert call_profile(lambda: PATH["EchoRow"](values)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_row": 1,
        "_one_row": 1,
        "_shape": 1,
        "_numbers": 1,
        "EchoRow": 1,
        "_row_out": 1,
        "_dimensions": 1,
        "_finite": 1,
    }
    assert numpy_calls(lambda: PATH["EchoRow"](values)) == {
        "ndarray.all": 1,
        "ndarray.reshape": 1,
        "numpy.ascontiguousarray": 1,
        "ufunc.reduce": 1,
    }


def test_one_answer_per_row_itemized(call_profile: CallProfile, numpy_calls: CallProfile) -> None:
    values = grid()
    PATH["RowSums"](values)
    assert call_profile(lambda: PATH["RowSums"](values)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_numbers": 1,
        "RowSums": 1,
        "_column_out": 1,
        "_dimensions": 1,
        "_finite": 1,
    }
    assert numpy_calls(lambda: PATH["RowSums"](values)) == {
        "ndarray.sum": 1,
        "ndarray.all": 1,
        "ndarray.reshape": 1,
        "numpy.ascontiguousarray": 1,
        "ufunc.reduce": 2,
    }


def test_an_array_out_from_nothing_in_itemized(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    PATH["Grid"](5000, 2)
    assert call_profile(lambda: PATH["Grid"](5000, 2)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_whole": 2,
        "_number": 2,
        "Grid": 1,
        "_array_out": 1,
        "_dimensions": 1,
        "_finite": 1,
    }
    assert numpy_calls(lambda: PATH["Grid"](5000, 2)) == {
        "numpy.arange": 1,
        "ndarray.reshape": 1,
        "numpy.ascontiguousarray": 1,
        "ndarray.all": 1,
        "ufunc.reduce": 1,
    }


# --- handles: a creator publishes, a reader resolves, itemized --------------
# A creator is the call for its inputs with the library's builder and one publication on top;
# a reader is a text call with one lookup on top. The store is asked one question per call.

CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def curve_body(rows: int) -> Cells:
    """A curve's table: one calendar day and its factor per row, from 11 September 2026."""
    return Cells.from_rows([[46276.0 + i, 1.0 - i * 1e-5] for i in range(rows)])


def test_a_valuation_date_is_two_scalars_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    PATH["_CreateValuationDate"](46276.0, 0.5)
    assert call_profile(lambda: PATH["_CreateValuationDate"](46276.0, 0.5)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_date": 1,  # the date, through the number rule it builds on, then its own two tests
        "_number": 2,
        "_CreateValuationDate": 1,
        "valuation_date": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateValuationDate"](46276.0, 0.5)) == {}


def anchor_body(anchors: int, days: int) -> Cells:
    """Anchors spread evenly over that many days from 11 September 2026, as the sheet sends them."""
    step = days // (anchors - 1)
    return Cells.from_rows([[46276.0 + i * step, 1.0 - i * step * 1e-5] for i in range(anchors)])


# A curve: the table path, the builder's own looks on the anchors, the days between them filled,
# and one publication. The same functions run and the same looks are taken whether the anchors
# are every day of ten years or a dozen over them: the work of filling is per day, inside one
# numpy call, and no ledger counts it.
CURVE_LEDGER = {
    "Registered.run": 1,
    "_arguments": 1,
    "_validate": 2,
    "_text_row": 1,
    "_one_row": 1,
    "_shape": 1,
    "_texts": 1,
    "_mixed": 1,
    "MixedArray.shape": 1,
    "_refine": 1,
    "_bind": 1,
    "_dates_of": 1,  # no column of text, so no text places are made
    "_not_dates": 1,
    "_as_days": 1,
    "_numbers_of": 1,
    "_CreateDiscountCurve": 1,
    "discount_curve": 1,
    "interpolate_discount_factors": 1,
    "_publish": 1,
}
CURVE_NUMPY = {
    "ndarray.any": 5,  # one look per column, then finite, rising and unordered, one look each
    "ndarray.astype": 3,  # the date column on its way to days, and the gaps between anchors
    "numpy.asarray": 2,  # the anchors' days read as they are, and the interpolation's own
    "numpy.arange": 2,  # the days from the first anchor to the last, and their offsets
    "ndarray.repeat": 1,  # the anchor each day runs to, which the line is held above
    "ndarray.setflags": 2,  # frozen
    "ufunc.reduce": 5,
}


def test_a_discount_curve_is_a_table_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    body = curve_body(3_631)
    PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)
    assert call_profile(lambda: PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)) == CURVE_LEDGER
    assert numpy_calls(lambda: PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)) == CURVE_NUMPY


def test_a_curve_from_a_dozen_anchors_runs_what_a_daily_table_runs(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    body = anchor_body(12, 3_630)
    PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)
    assert call_profile(lambda: PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)) == CURVE_LEDGER
    assert numpy_calls(lambda: PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)) == CURVE_NUMPY


# The reader of any handle: the text rule and one lookup, the kind's table built a column at a
# time, dates to serials, and the mixed road out with its three looks.
def test_a_reader_is_a_text_call_one_lookup_and_a_table_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    handle = PATH["_CreateDiscountCurve"](CURVE_HEADERS, curve_body(3_631))
    PATH["util_ReadHandle"](handle)
    assert call_profile(lambda: PATH["util_ReadHandle"](handle)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve": 1,  # the handle: the text rule, then one dictionary lookup
        "_text": 1,
        "util_ReadHandle": 1,
        "discount_curve_table": 1,  # the kind's own table, reached by dispatch, not by a check
        "MixedArray.table": 1,
        "_table_column": 2,  # each array column checked before its copy: the dates, the factors
        "_unit": 1,
        "_serials": 1,
        "_mixed_out": 1,
        "_bad_mixed": 1,
    }
    assert numpy_calls(lambda: PATH["util_ReadHandle"](handle)) == {
        "numpy.empty": 2,  # the kinds, and the slots underneath numpy's full
        "numpy.asarray": 1,
        "numpy.datetime_data": 1,  # the unit of the date column
        "ndarray.any": 5,  # the serials' two checks, then the mixed road's three looks
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }


def test_a_dead_handle_is_refused_after_one_lookup(call_profile: CallProfile) -> None:
    dead = "discount_curve:9999999"
    assert call_profile(lambda: PATH["util_ReadHandle"](dead)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve": 1,
        "_text": 1,
    }


# --- the first index definition: up to three columns in, one publication out -------------


def schedule_columns(contracts: int) -> tuple[Cells, Cells, Cells, Cells]:
    """Codes and three date columns for that many monthly contracts, as the sheet sends them:
    the futures, the options and a third column a month apart, dates for the schedules of the
    other markets."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + 30 * i] for i in range(contracts)])
    options = Cells.from_rows([[46156.0 + 30 * i] for i in range(contracts)])
    publications = Cells.from_rows([[46162.0 + 30 * i] for i in range(contracts)])
    return codes, futures, options, publications


# Ten years of monthly contracts with every column: the text column handed over as it is, one
# look and two conversions per date column, the builder's two copies, and one publication.
# Twenty-six calls across fifteen functions, the accept rule once per argument.
def test_a_futures_schedule_is_three_columns_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, options, _ = schedule_columns(120)
    PATH["_CreateFuturesSchedule"](codes, futures, options)
    assert call_profile(lambda: PATH["_CreateFuturesSchedule"](codes, futures, options)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text_column": 1,
        "_date_column": 2,
        "_one_column": 3,
        "_shape": 3,
        "_texts": 1,
        "_dates": 2,
        "_not_dates": 2,
        "_as_days": 2,
        "_CreateFuturesSchedule": 1,
        "futures_schedule": 1,
        "_one_per_code": 2,  # the one rule, once per date column
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateFuturesSchedule"](codes, futures, options)) == {
        "ndarray.any": 2,  # one look per date column, for the calendar
        "ndarray.astype": 4,  # each date column on its way to days
        "numpy.array": 2,  # the two copies the schedule keeps
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 2,
    }


# The third column left out: the stored default is handed over, and nothing runs for it
# beyond the accept rule's one call.
def test_a_futures_schedule_without_options_pays_for_two_columns(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, _, _ = schedule_columns(120)
    PATH["_CreateFuturesSchedule"](codes, futures, MISSING)
    assert call_profile(lambda: PATH["_CreateFuturesSchedule"](codes, futures, MISSING)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text_column": 1,
        "_date_column": 1,
        "_one_column": 2,
        "_shape": 2,
        "_texts": 1,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_CreateFuturesSchedule": 1,
        "futures_schedule": 1,
        "_one_per_code": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateFuturesSchedule"](codes, futures, MISSING)) == {
        "ndarray.any": 1,
        "ndarray.astype": 2,
        "numpy.array": 1,
        "ndarray.setflags": 1,
        "ufunc.reduce": 1,
    }


# --- the second index definition: one column in, one publication out ------------------


def holiday_column(days: int) -> Cells:
    """That many holidays as the sheet sends them, one serial per row, a week apart."""
    return Cells.from_rows([[46023.0 + 7 * i] for i in range(days)])


# Ten years of one market's holidays: one look and two conversions for the column, the builder's
# one copy and one publication. The builder has no rule of its own, so nothing else runs.
def test_a_holiday_calendar_is_one_column_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    holidays = holiday_column(100)
    PATH["_CreateHolidayCalendar"](holidays)
    assert call_profile(lambda: PATH["_CreateHolidayCalendar"](holidays)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_date_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_CreateHolidayCalendar": 1,
        "holiday_calendar": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateHolidayCalendar"](holidays)) == {
        "ndarray.any": 1,  # one look, for the calendar
        "ndarray.astype": 2,  # the column on its way to days
        "numpy.array": 1,  # the one copy the calendar keeps
        "ndarray.setflags": 1,  # frozen
        "ufunc.reduce": 1,
    }


# --- the fifth index definition: three columns in, one publication out ---------------


def iferc_columns(contracts: int) -> tuple[Cells, Cells, Cells]:
    """Codes, the day each month's future stops trading and the day its index is published, for
    that many contract months, as the sheet sends them: the codes, the futures and the
    third date column of schedule_columns."""
    codes, last_trading, _, publications = schedule_columns(contracts)
    return codes, last_trading, publications


# Ten years of IFERC contract months: the text column handed over as it is, one look and two
# conversions per date column, the builder's two copies and one publication. Twenty-six calls
# across fifteen functions, the accept rule once per argument: the futures schedule's ledger with
# its options, column for column, the third date column here being the publication day.
def test_an_iferc_schedule_is_three_columns_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, last_trading, publications = iferc_columns(120)
    PATH["_CreateIfercSchedule"](codes, last_trading, publications)
    assert call_profile(
        lambda: PATH["_CreateIfercSchedule"](codes, last_trading, publications)
    ) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text_column": 1,
        "_date_column": 2,
        "_one_column": 3,
        "_shape": 3,
        "_texts": 1,
        "_dates": 2,
        "_not_dates": 2,
        "_as_days": 2,
        "_CreateIfercSchedule": 1,
        "iferc_schedule": 1,
        "_one_per_code": 2,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateIfercSchedule"](codes, last_trading, publications)) == {
        "ndarray.any": 2,  # one look per date column, for the calendar
        "ndarray.astype": 4,  # each date column on its way to days
        "numpy.array": 2,  # the two copies the schedule keeps
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 2,
    }


# --- the sixth index definition: three columns in, one publication out ---------------


def gas_daily_columns(contracts: int) -> tuple[Cells, Cells, Cells]:
    """Codes and the first and last day of gas of that many contract months, as the sheet sends
    them: the codes, the options and the third date column of schedule_columns, any dates
    serving a count."""
    codes, _, first, last = schedule_columns(contracts)
    return codes, first, last


# Ten years of Gas Daily contract months: the IFERC schedule's ledger to the call, three
# columns of the same kinds through the same rules and a builder of the same shape.
def test_a_gas_daily_schedule_is_three_columns_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, first, last = gas_daily_columns(120)
    PATH["_CreateGasDailySchedule"](codes, first, last)
    assert call_profile(lambda: PATH["_CreateGasDailySchedule"](codes, first, last)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text_column": 1,
        "_date_column": 2,
        "_one_column": 3,
        "_shape": 3,
        "_texts": 1,
        "_dates": 2,
        "_not_dates": 2,
        "_as_days": 2,
        "_CreateGasDailySchedule": 1,
        "gas_daily_schedule": 1,
        "_one_per_code": 2,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateGasDailySchedule"](codes, first, last)) == {
        "ndarray.any": 2,  # one look per date column, for the calendar
        "ndarray.astype": 4,  # each date column on its way to days
        "numpy.array": 2,  # the two copies the schedule keeps
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 2,
    }


# --- the third index definition: five texts in, one publication out ------------------


# Five scalars, each through the text rule, the builder and one publication: nothing is asked of
# numpy, and the builder's five rules are lookups in the unit tables by key, which the profiler
# does not see as calls.
def test_index_conventions_are_five_texts_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes = ("USD", "BBL", "USD", "volume", "BBL")
    PATH["_CreateIndexConventions"](*codes)
    assert call_profile(lambda: PATH["_CreateIndexConventions"](*codes)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 5,
        "_text": 5,
        "_CreateIndexConventions": 1,
        "index_conventions": 1,
        "measures_of": 1,  # the categories a quantity measures, read once
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateIndexConventions"](*codes)) == {}


# --- the fourth index definition: a table of contracts in, one publication out ----------


SPECIFICATION_HEADERS = Cells.from_rows(
    [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)


def specification_body(contracts: int) -> Cells:
    """That many contracts as the sheet sends them: a name, a whole lot size and two fees."""
    return Cells.from_rows(
        [[f"contract {i}", 1000.0 + i, "MMBTU", 3.0, 2.0] for i in range(contracts)]
    )


def an_index(schedule: object, holidays: object = MISSING) -> object:
    """The index handle of that schedule handle and holiday calendar handle, with the conventions
    of gas and one lot, since nothing measured here reads either."""
    return PATH["_CreateIndex"](
        "sample",
        schedule,
        PATH["_CreateIndexConventions"]("USD", "MMBTU", "USD", "energy", "MMBTU"),
        PATH["_CreateContractSpecifications"](SPECIFICATION_HEADERS, specification_body(1)),
        holidays,
    )


# A dozen words at the table path: the header row as any row of text, the body admitted as a
# mixed range and bound, then each column through its rule, the names and the lot units gathered
# and the three number columns as views, the builder's four looks, a fraction and a lot below one
# among the lot sizes and a fee below zero in each fee column, the measures read once and the one
# set of their units the lot units are looked up in, its three copies and one publication.
# Twenty-three calls across nineteen functions; the set of units is built inline and is no call.
def test_contract_specifications_are_a_table_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    body = specification_body(12)
    PATH["_CreateContractSpecifications"](SPECIFICATION_HEADERS, body)
    assert call_profile(
        lambda: PATH["_CreateContractSpecifications"](SPECIFICATION_HEADERS, body)
    ) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text_row": 1,
        "_one_row": 1,
        "_shape": 1,
        "_texts": 1,
        "_mixed": 1,
        "MixedArray.shape": 1,
        "_refine": 1,
        "_bind": 1,
        "_refine.<locals>.<lambda>": 1,  # the text places, made once on first use
        "_text_places": 1,
        "_texts_of": 2,  # the names, then the lot units
        "_numbers_of": 3,
        "_CreateContractSpecifications": 1,
        "contract_specifications": 1,
        "measures_of": 1,
        "_publish": 1,
    }
    assert numpy_calls(
        lambda: PATH["_CreateContractSpecifications"](SPECIFICATION_HEADERS, body)
    ) == {
        "ndarray.any": 9,  # one look per column, five of them, then the builder's four
        "numpy.array": 4,  # the names as an array for the gather, and the builder's three copies
        "ndarray.cumsum": 1,  # the text cells above each row
        "ndarray.sum": 3,  # text cells per row, and to the left of each of the two text columns
        "ndarray.setflags": 3,  # frozen
        "ufunc.reduce": 12,
    }


# cells_from_buffers is the real entry for a range: what the host's pinned buffers cost to own.
def host_buffers(text_cell: bool) -> tuple[int, int, str, int]:
    kinds = (ctypes.c_uint8 * N)(*([0] * (N - 1) + [1 if text_cell else 0]))
    numbers = (ctypes.c_double * N)(*[float(i) for i in range(N)])
    _keep.extend((kinds, numbers))
    seen = bridge.ONLY_NUMBERS | (bridge.ONLY_TEXT if text_cell else 0)
    return ctypes.addressof(kinds), ctypes.addressof(numbers), "x" if text_cell else "", seen


_keep: list[object] = []


@pytest.mark.parametrize("text_cell", [False, True], ids=["numbers", "one text cell"])
def test_cells_from_buffers_copies_each_buffer_once(
    text_cell: bool, call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    kinds, numbers, text, seen = host_buffers(text_cell)
    bridge.cells_from_buffers(kinds, numbers, N, 1, text, seen)
    assert call_profile(lambda: bridge.cells_from_buffers(kinds, numbers, N, 1, text, seen)) == {
        "cells_from_buffers": 1,
    }
    # Two views, two copies, and no look: the host's summary says whether there is text.
    assert numpy_calls(lambda: bridge.cells_from_buffers(kinds, numbers, N, 1, text, seen)) == {
        "numpy.frombuffer": 2,
        "ndarray.reshape": 2,
        "ndarray.copy": 2,
    }


# --- the index: text and four handles in, one publication out -------------------------------


def index_parts() -> tuple[object, object, object, object]:
    """The four handles an index takes: a futures schedule of thirteen contracts, the
    conventions of gas, a dozen contracts' specifications and a calendar of a hundred holidays."""
    codes, futures, _, _ = schedule_columns(13)
    return (
        PATH["_CreateFuturesSchedule"](codes, futures, MISSING),
        PATH["_CreateIndexConventions"]("USD", "MMBTU", "USD", "energy", "MMBTU"),
        PATH["_CreateContractSpecifications"](SPECIFICATION_HEADERS, specification_body(12)),
        PATH["_CreateHolidayCalendar"](holiday_column(100)),
    )


# Text through its rule and four handles, each through the text rule and one lookup, the
# builder's dispatch to the futures index, its holiday rule and one publication: twenty-one
# calls across ten functions, and not one numpy call, no copy and no look at the schedule,
# whatever its length. The lot-unit rule of #115 is one lookup per row of the specifications and
# calls nothing the ledger counts. An IFERC index leaves the holiday calendar out, one handle
# fewer through the text rule and the lookup, and runs the other holiday rule: nineteen calls
# across ten functions.
def test_an_index_is_text_and_four_handles_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    schedule, conventions, specifications, holidays = index_parts()
    PATH["_CreateIndex"]("Henry Hub NYMEX", schedule, conventions, specifications, holidays)
    assert call_profile(
        lambda: PATH["_CreateIndex"](
            "Henry Hub NYMEX", schedule, conventions, specifications, holidays
        )
    ) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 5,
        "_text": 5,  # the name's rule, and each handle's text rule
        "_resolve": 4,  # each handle's one lookup
        "_CreateIndex": 1,
        "index": 1,
        "futures_index": 1,
        "with_holiday_calendar": 1,
        "_publish": 1,
    }
    assert (
        numpy_calls(
            lambda: PATH["_CreateIndex"](
                "Henry Hub NYMEX", schedule, conventions, specifications, holidays
            )
        )
        == {}
    )
    months = PATH["_CreateIfercSchedule"](*iferc_columns(120))
    PATH["_CreateIndex"]("Henry Hub IFERC", months, conventions, specifications, MISSING)
    assert call_profile(
        lambda: PATH["_CreateIndex"](
            "Henry Hub IFERC", months, conventions, specifications, MISSING
        )
    ) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 5,
        "_text": 4,
        "_resolve": 3,
        "_CreateIndex": 1,
        "index": 1,
        "iferc_index": 1,
        "without_holiday_calendar": 1,
        "_publish": 1,
    }


# Reading an index back: the handle's text rule and one lookup, then one row of five cells
# through the mixed road, two lengths read off the parts and nothing else of them touched.
def test_reading_an_index_back_costs_one_row(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    schedule, conventions, specifications, holidays = index_parts()
    made = PATH["_CreateIndex"]("Henry Hub NYMEX", schedule, conventions, specifications, holidays)
    PATH["util_ReadHandle"](made)
    assert call_profile(lambda: PATH["util_ReadHandle"](made)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text": 1,
        "_resolve": 1,
        "util_ReadHandle": 1,
        "index_table": 1,
        "MixedArray.table": 1,
        "_table_column": 3,
        "_beyond_exact": 2,  # the two counts, whole numbers the sheet can hold exactly
        "_mixed_out": 1,
        "_bad_mixed": 1,
    }
    assert numpy_calls(lambda: PATH["util_ReadHandle"](made)) == {
        "numpy.array": 4,  # the three text columns gathered, and the table's texts
        "ndarray.ravel": 1,  # the texts in sheet order
        "numpy.empty": 2,  # the kinds, and the slots underneath numpy's full
        "numpy.asarray": 1,
        "ndarray.any": 5,  # the two counts' exactness looks, then the mixed road's three
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }


# --- the futures fixings: two columns and a calendar's handle in, one publication out -----------


def fixings_columns(rows: int, holidays: int) -> tuple[Cells, Cells]:
    """That many futures fixings as the sheet sends them, a column of serials and a column of
    settles, one per business day from Friday 1 May 2026 under a calendar of that many Thursdays
    a week apart, the calendar holiday_column makes."""
    epoch = np.datetime64("1899-12-30")
    closed = epoch + (46023 + 7 * np.arange(holidays)).astype("timedelta64[D]")
    days = np.busday_offset(np.datetime64("2026-05-01"), np.arange(rows), holidays=closed)
    serials = (days - epoch).astype(np.int64)
    return (
        Cells.from_rows([[float(serials[i])] for i in range(rows)]),
        Cells.from_rows([[100.0 + i % 7] for i in range(rows)]),
    )


# A year of fixings at the column path, with the index by handle: the date column through its
# look and its conversion to days, the settle column accepted on the host's summary alone, the
# handle's text rule and its one lookup, then the builder's kind check, the holiday calendar
# read off the index, its count, its three looks, the order of the dates, the days the market
# is closed and the business days without a fixing, its two copies, and one publication.
# Twenty-one calls across seventeen functions, the accept rule once per argument. The three
# business-day calls, the calendar, is_busday and busday_offset, raise no event the numpy
# fixture reads, so only their looks are in its count.
def test_futures_fixings_are_two_columns_and_an_index_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, _, _ = schedule_columns(2)
    index = an_index(
        PATH["_CreateFuturesSchedule"](codes, futures, MISSING),
        PATH["_CreateHolidayCalendar"](holiday_column(100)),
    )
    days, settles = fixings_columns(260, 100)
    PATH["_CreateFuturesFixings"](days, settles, index)
    assert call_profile(lambda: PATH["_CreateFuturesFixings"](days, settles, index)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_date_column": 1,
        "_column": 1,
        "_one_column": 2,
        "_shape": 2,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_numbers": 1,
        "_text": 1,  # the handle's text rule
        "_resolve": 1,  # and its one lookup
        "_CreateFuturesFixings": 1,
        "futures_fixings": 1,
        "with_holiday_calendar": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateFuturesFixings"](days, settles, index)) == {
        "ndarray.any": 4,  # the date column's look for the calendar, then the builder's three
        "ndarray.astype": 2,  # the date column on its way to days
        "numpy.array": 2,  # the two copies the fixings keep
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 4,
    }


# --- the calendar: a schedule of any kind in, four columns made once, one publication out --


def calendar_sources(contracts: int) -> tuple[object, object]:
    """The two handles a calendar takes: the valuation date, and the index of a schedule of that
    many monthly contracts a month apart with a calendar of a hundred holidays a week apart."""
    codes, futures, _, _ = schedule_columns(contracts)
    schedule = PATH["_CreateFuturesSchedule"](codes, futures, MISSING)
    holidays = PATH["_CreateHolidayCalendar"](holiday_column(100))
    return PATH["_CreateValuationDate"](46276.0, 0.5), an_index(schedule, holidays)


# A year of days from thirteen contracts: two handles, each the text rule and one lookup, the
# index's kind choosing the futures builder, the holiday calendar read off the index, its one
# look at the order of the expiries, its days in one arange, the prompt row of each in one
# searchsorted, the two flags, and one publication. Fifteen calls across twelve functions, the
# accept rule once per argument; is_busday and the comparison against the valuation date raise
# no event the numpy fixture reads.
def test_a_calendar_is_two_handles_in_and_four_columns_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    valuation, index = calendar_sources(13)
    PATH["_CreateCalendar"](valuation, index)
    assert call_profile(lambda: PATH["_CreateCalendar"](valuation, index)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,  # each handle's text rule
        "_resolve": 2,  # and its one lookup
        "_CreateCalendar": 1,
        "calendar": 1,
        "_futures_calendar": 1,
        "with_holiday_calendar": 1,
        "_each_code_once": 1,
        "_frozen": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateCalendar"](valuation, index)) == {
        "ndarray.any": 1,  # the builder's look at the order of the expiries
        "numpy.arange": 1,  # every day, once
        "ndarray.searchsorted": 1,  # the prompt row of every day, once
        "ndarray.setflags": 4,  # the four columns frozen
        "ufunc.reduce": 1,
    }


# Reading a calendar back rebuilds nothing: no arange, no searchsorted, no look at a holiday
# or the valuation date. The reader takes the schedule's codes once as an array and gathers
# each day's through the prompt rows, then the table checks its three array columns, the days
# to serials, and the mixed road out takes its three looks.
def test_reading_a_calendar_back_rebuilds_nothing(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made = PATH["_CreateCalendar"](*calendar_sources(13))
    PATH["util_ReadHandle"](made)
    assert call_profile(lambda: PATH["util_ReadHandle"](made)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text": 1,
        "_resolve": 1,
        "util_ReadHandle": 1,
        "calendar_table": 1,
        "MixedArray.table": 1,
        "_table_column": 3,  # the days, then the two flags; the codes are a tuple of text
        "_unit": 1,
        "_serials": 1,
        "_mixed_out": 1,
        "_bad_mixed": 1,
    }
    calls = numpy_calls(lambda: PATH["util_ReadHandle"](made))
    assert calls == {
        "numpy.array": 2,  # the schedule's codes as an array, and the table's texts gathered
        "ndarray.ravel": 1,  # the texts in sheet order
        "numpy.empty": 2,  # the kinds, and the slots underneath numpy's full
        "numpy.asarray": 1,
        "numpy.datetime_data": 1,  # the unit of the date column
        "ndarray.any": 5,  # the serials' two checks, then the mixed road's three looks
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }
    assert "numpy.arange" not in calls and "ndarray.searchsorted" not in calls


def gas_daily_month_columns(months: int) -> tuple[Cells, Cells, Cells]:
    """Codes and the first and last day of that many calendar months from January 2026, laid
    end to end, as the sheet sends them."""
    firsts = np.arange("2026-01", "2126-01", dtype="datetime64[M]")[: months + 1]
    starts = firsts[:-1].astype("datetime64[D]")
    ends = firsts[1:].astype("datetime64[D]") - np.timedelta64(1, "D")
    # Days since 1970 to the sheet's serials: 1 January 1970 is serial 25569.
    first = starts.astype(np.int64) + 25569
    last = ends.astype(np.int64) + 25569
    return (
        Cells.from_rows([[f"c{i}"] for i in range(months)]),
        Cells.from_rows([[float(first[i])] for i in range(months)]),
        Cells.from_rows([[float(last[i])] for i in range(months)]),
    )


# A year of flow days from twelve months: two handles, each the text rule and one lookup, the
# index's kind choosing the Gas Daily builder, its two looks, a
# month's last day before its first and a gap between months, its days in one arange, the month
# of each in one searchsorted, the priced flag in one empty, the fixed flag, and one publication.
# Fifteen calls across twelve functions, the accept rule once per argument.
def test_a_gas_daily_calendar_is_an_index_and_a_valuation_date_in_and_four_columns_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    valuation = PATH["_CreateValuationDate"](46276.0, 0.5)
    schedule = PATH["_CreateGasDailySchedule"](*gas_daily_month_columns(12))
    index = an_index(schedule)
    PATH["_CreateCalendar"](valuation, index)
    assert call_profile(lambda: PATH["_CreateCalendar"](valuation, index)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,
        "_resolve": 2,
        "_CreateCalendar": 1,
        "calendar": 1,
        "_gas_daily_calendar": 1,
        "_at_least_one": 1,
        "_each_code_once": 1,
        "_frozen": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateCalendar"](valuation, index)) == {
        "ndarray.any": 2,
        "numpy.arange": 1,
        "ndarray.searchsorted": 1,
        "numpy.empty": 1,  # the priced flag, true throughout
        "ndarray.setflags": 4,
        "ufunc.reduce": 2,
    }


# Ten years of IFERC months: two handles as above, the IFERC builder's one look at the order of
# the publication days, its one copy of them, the months' rows in one arange, the priced flag
# in one empty, the fixed flag, and one publication. Fifteen calls across twelve functions.
def test_an_iferc_calendar_is_an_index_and_a_valuation_date_in_and_four_columns_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    valuation = PATH["_CreateValuationDate"](46276.0, 0.5)
    schedule = PATH["_CreateIfercSchedule"](*iferc_columns(120))
    index = an_index(schedule)
    PATH["_CreateCalendar"](valuation, index)
    assert call_profile(lambda: PATH["_CreateCalendar"](valuation, index)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,
        "_resolve": 2,
        "_CreateCalendar": 1,
        "calendar": 1,
        "_iferc_calendar": 1,
        "_at_least_one": 1,
        "_each_code_once": 1,
        "_frozen": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateCalendar"](valuation, index)) == {
        "ndarray.any": 1,
        "numpy.array": 1,
        "numpy.arange": 1,
        "numpy.empty": 1,  # the priced flag, true throughout
        "ndarray.setflags": 4,
        "ufunc.reduce": 1,
    }


# --- the market history: two handles in, the calendar kept, its fixed periods priced -----------


def history_sources(contracts: int) -> tuple[object, object]:
    """The two handles a history takes: the calendar calendar_sources makes, valued on 11
    September 2026, and fixings on every business day from Friday 1 May 2026 to the day
    before, under the same hundred Thursdays, so every past business day has one."""
    valuation, index = calendar_sources(contracts)
    made = PATH["_CreateCalendar"](valuation, index)
    closed = np.datetime64("1899-12-30") + (46023 + 7 * np.arange(100)).astype("timedelta64[D]")
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=closed))
    fixings = PATH["_CreateFuturesFixings"](*fixings_columns(rows, 100), index)
    return made, fixings


# A year of days and the fixings on its fixed business days: two handles, each the text rule and
# one lookup, the builder's dispatch to the futures binder, its one comparison of the fixings'
# index with the calendar's, its two looks, a fixing on or after the valuation date and a fixed
# day without one, its rows from one subtraction over the fixings' days, the days covered in one
# zeros, the two columns frozen, and one publication. Fifteen calls across twelve functions, the
# accept rule once per argument; no arange, no searchsorted and no look at a holiday, since the
# calendar is taken as it is and nothing of it is made again, and no look for a closed day, both
# having been checked against one holiday calendar.
def test_a_market_history_is_two_handles_in_and_the_calendar_kept(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made, fixings = history_sources(13)
    PATH["_CreateMarketHistory"](made, fixings)
    assert call_profile(lambda: PATH["_CreateMarketHistory"](made, fixings)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,  # each handle's text rule
        "_resolve": 2,  # and its one lookup
        "_CreateMarketHistory": 1,
        "market_history": 1,
        "futures_history": 1,
        "_over_the_calendars_index": 1,
        "_every_fixed_day": 1,
        "_frozen": 1,
        "_publish": 1,
    }
    calls = numpy_calls(lambda: PATH["_CreateMarketHistory"](made, fixings))
    assert calls == {
        "ndarray.any": 2,  # the builder's two looks
        "ndarray.astype": 1,  # the fixings' days to rows of the calendar
        "numpy.zeros": 1,  # the rows covered
        "ndarray.setflags": 2,  # the two columns frozen
        "ufunc.reduce": 2,
    }
    assert "numpy.arange" not in calls and "ndarray.searchsorted" not in calls


def gas_daily_history_sources() -> tuple[object, object]:
    """The two handles a Gas Daily history takes: the calendar of the twelve months of 2026
    valued on 11 September, and a print on every flow day from New Year's Day to the 11th, so
    that every fixed day has one."""
    valuation = PATH["_CreateValuationDate"](46276.0, 0.5)
    schedule = PATH["_CreateGasDailySchedule"](*gas_daily_month_columns(12))
    index = an_index(schedule)
    made = PATH["_CreateCalendar"](valuation, index)
    days = 46276 - 46023 + 1  # New Year's Day 2026 is serial 46023
    fixings = PATH["_CreateGasDailyFixings"](
        Cells.from_rows([[46023.0 + i] for i in range(days)]),
        Cells.from_rows([[2.8 + (i % 30) / 100] for i in range(days)]),
        index,
    )
    return made, fixings


# A year of flow days and the prints on those that have fixed: two handles as above, the
# builder's dispatch to the Gas Daily binder, its one comparison of the fixings' index with the
# calendar's, its two looks, a print after the valuation day and a fixed day without one, its
# rows from one subtraction over the flow days, the days covered in one zeros, the two columns
# frozen, and one publication.
# Fifteen calls across twelve functions, the accept rule once per argument; no arange, no
# searchsorted and no look at a holiday.
def test_a_gas_daily_history_is_two_handles_in_and_the_calendar_kept(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made, fixings = gas_daily_history_sources()
    PATH["_CreateMarketHistory"](made, fixings)
    assert call_profile(lambda: PATH["_CreateMarketHistory"](made, fixings)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,
        "_resolve": 2,
        "_CreateMarketHistory": 1,
        "market_history": 1,
        "gas_daily_history": 1,
        "_over_the_calendars_index": 1,
        "_every_fixed_day": 1,
        "_frozen": 1,
        "_publish": 1,
    }
    calls = numpy_calls(lambda: PATH["_CreateMarketHistory"](made, fixings))
    assert calls == {
        "ndarray.any": 2,  # the builder's two looks
        "ndarray.astype": 1,  # the flow days to rows of the calendar
        "numpy.zeros": 1,  # the rows covered
        "ndarray.setflags": 2,  # the two columns frozen
        "ufunc.reduce": 2,
    }
    assert "numpy.arange" not in calls and "ndarray.searchsorted" not in calls


def iferc_history_sources() -> tuple[object, object]:
    """The two handles an IFERC history takes: the calendar of the ten years of months
    iferc_columns lays out, valued after the last month's publication day so that every month
    has fixed, and an index for each of them."""
    valuation = PATH["_CreateValuationDate"](49740.0, 0.5)
    schedule = PATH["_CreateIfercSchedule"](*iferc_columns(120))
    index = an_index(schedule)
    made = PATH["_CreateCalendar"](valuation, index)
    fixings = PATH["_CreateIfercFixings"](*iferc_fixing_columns(120), index)
    return made, fixings


# Ten years of months, every one published, and their indices: two handles as above, the
# builder's dispatch to the IFERC binder, its one comparison of the fixings' index with the
# calendar's, one pass over the codes for their rows, every code a month of the index since the
# fixings' creator refused any other, the rows of the months in one array, two looks, an index
# for a month not yet fixed and a fixed month without one, the months covered in one zeros, the
# rows put in the calendar's order by one argsort, the two columns frozen, and one publication.
# Fourteen calls across eleven functions, the accept rule once per argument; no arange and no
# searchsorted.
def test_an_iferc_history_is_two_handles_in_and_the_calendar_kept(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made, fixings = iferc_history_sources()
    PATH["_CreateMarketHistory"](made, fixings)
    assert call_profile(lambda: PATH["_CreateMarketHistory"](made, fixings)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,
        "_resolve": 2,
        "_CreateMarketHistory": 1,
        "market_history": 1,
        "iferc_history": 1,
        "_over_the_calendars_index": 1,
        "_frozen": 1,
        "_publish": 1,
    }
    calls = numpy_calls(lambda: PATH["_CreateMarketHistory"](made, fixings))
    assert calls == {
        "numpy.array": 1,  # the row of each index's month
        "ndarray.any": 2,  # the builder's two looks
        "numpy.zeros": 1,  # the months covered
        "ndarray.argsort": 1,  # the calendar's order
        "ndarray.setflags": 2,  # the two columns frozen
        "ufunc.reduce": 2,
    }
    assert "numpy.arange" not in calls and "ndarray.searchsorted" not in calls


# Reading a history back is reading its calendar back, the same calls, and then the fifth
# column written by kind through the helper the market's reader shares: the words made once, the
# wider kinds and slots, the codes paired with the words and the pairs shown, the two words
# shared by every row; no arange, no searchsorted, nothing of the calendar made again.
def test_reading_a_market_history_back_rebuilds_nothing(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made = PATH["_CreateMarketHistory"](*history_sources(13))
    PATH["util_ReadHandle"](made)
    assert call_profile(lambda: PATH["util_ReadHandle"](made)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text": 1,
        "_resolve": 1,
        "util_ReadHandle": 1,
        "market_history_table": 1,
        "_priced_column": 1,  # the fifth column, through the helper the market's reader shares
        "calendar_table": 1,  # the calendar's own table, as the calendar shows
        "MixedArray.table": 1,
        "_table_column": 3,
        "_unit": 1,
        "_serials": 1,
        "MixedArray.shape": 1,
        "_mixed_out": 1,
        "_bad_mixed": 1,
    }
    calls = numpy_calls(lambda: PATH["util_ReadHandle"](made))
    assert calls == {
        "numpy.array": 2,  # the calendar's: the codes as an array, its texts gathered
        "ndarray.ravel": 1,  # the calendar's texts in sheet order
        "numpy.empty": 7,  # the calendar's two; the words, kinds, slots, pairs and mask
        "numpy.asarray": 2,
        "numpy.datetime_data": 1,  # the unit of the date column
        "ndarray.any": 5,  # the serials' two checks, then the mixed road's three looks
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }
    assert "numpy.arange" not in calls and "ndarray.searchsorted" not in calls


# --- the market: two handles in, one number found, nothing built ---------------------------


def market_sources(contracts: int, days_apart: int) -> tuple[object, object]:
    """The two handles a market takes: the history of a calendar of that many contracts that
    many days apart from 19 May 2026, valued on 11 September 2026 with a fixing on every
    business day before it under a hundred Thursdays, and a vector with one quote per contract
    from the valuation day's prompt through the last."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + days_apart * i] for i in range(contracts)])
    valuation = PATH["_CreateValuationDate"](46276.0, 0.5)
    schedule = PATH["_CreateFuturesSchedule"](codes, futures, MISSING)
    index = an_index(schedule, PATH["_CreateHolidayCalendar"](holiday_column(100)))
    made = PATH["_CreateCalendar"](valuation, index)
    closed = np.datetime64("1899-12-30") + (46023 + 7 * np.arange(100)).astype("timedelta64[D]")
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=closed))
    fixings = PATH["_CreateFuturesFixings"](*fixings_columns(rows, 100), index)
    history = PATH["_CreateMarketHistory"](made, fixings)
    first = int(np.searchsorted(46161.0 + days_apart * np.arange(contracts), 46276.0))
    quotes = Cells.from_rows([[70.0 + i % 5] for i in range(contracts - first)])
    return history, PATH["_CreatePriceVector"]("sample", quotes)


def gas_daily_market_sources() -> tuple[object, object]:
    """The two handles a Gas Daily market takes: the history gas_daily_history_sources makes,
    the twelve months of 2026 valued on 11 September, and a vector of four quotes, the balance
    of September and the three months after it."""
    history = PATH["_CreateMarketHistory"](*gas_daily_history_sources())
    return history, PATH["_CreatePriceVector"](
        "sample", Cells.from_rows([[3.0 + i] for i in range(4)])
    )


def iferc_market_sources() -> tuple[object, object]:
    """The two handles an IFERC market takes: the calendar of the ten years of months
    iferc_columns lays out, valued on 11 September 2026 with four months published and an index
    for each, and a vector of 116 quotes, one per month still to publish."""
    valuation = PATH["_CreateValuationDate"](46276.0, 0.5)
    schedule = PATH["_CreateIfercSchedule"](*iferc_columns(120))
    index = an_index(schedule)
    made = PATH["_CreateCalendar"](valuation, index)
    fixings = PATH["_CreateIfercFixings"](*iferc_fixing_columns(4), index)
    history = PATH["_CreateMarketHistory"](made, fixings)
    return history, PATH["_CreatePriceVector"](
        "sample", Cells.from_rows([[2.0 + i] for i in range(116)])
    )


MARKET_LEDGER = {
    "Registered.run": 1,
    "_arguments": 1,
    "_validate": 2,
    "_text": 2,  # each handle's text rule
    "_resolve": 2,  # and its one lookup
    "_CreateMarket": 1,
    "market": 1,
    "_publish": 1,
}


# The hot operation: two handles, each the text rule and one lookup, the builder's two rules on
# scalars, the row of the first unfixed period read off the calendar, which counted its fixed
# flags once when it was made, its contract read there, and one publication. Eleven calls across
# eight functions, and not one numpy call: no copy, no count, no look, no mask and no array,
# whatever the calendar's length and the vector's, a year of days with nine quotes, ten years
# with one quote, or a year with 246 quotes alike.
@pytest.mark.parametrize(
    ("contracts", "days_apart"),
    [(13, 30), (2, 3600), (361, 1)],
    ids=["a year of days, nine quotes", "ten years of days, one quote", "a year, 246 quotes"],
)
def test_a_market_is_two_handles_in_and_one_number_out_whatever_the_sizes(
    contracts: int, days_apart: int, call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    history, quotes = market_sources(contracts, days_apart)
    PATH["_CreateMarket"](history, quotes)
    assert call_profile(lambda: PATH["_CreateMarket"](history, quotes)) == MARKET_LEDGER
    assert numpy_calls(lambda: PATH["_CreateMarket"](history, quotes)) == {}


# The same ledger over a Gas Daily history, a year of flow days with four quotes, and over an
# IFERC one, ten years of months with 116: the kind of the calendar is read by nothing here.
@pytest.mark.parametrize(
    "sources",
    [gas_daily_market_sources, iferc_market_sources],
    ids=["a Gas Daily market", "an IFERC market"],
)
def test_a_market_over_the_other_two_calendars_costs_the_same(
    sources: Callable[[], tuple[object, object]],
    call_profile: CallProfile,
    numpy_calls: CallProfile,
) -> None:
    history, quotes = sources()
    PATH["_CreateMarket"](history, quotes)
    assert call_profile(lambda: PATH["_CreateMarket"](history, quotes)) == MARKET_LEDGER
    assert numpy_calls(lambda: PATH["_CreateMarket"](history, quotes)) == {}


# Reading a market back is reading its calendar back, then the fifth column through the helper
# the history's reader shares: the live rows found in one flatnonzero, their prompt rows gathered
# and the quotes read through them, the fixings and the quotes written into their rows and the
# word closed shared by every other; no arange, no searchsorted, nothing of the calendar made
# again.
@pytest.mark.parametrize(
    "sources",
    [lambda: market_sources(13, 30), gas_daily_market_sources, iferc_market_sources],
    ids=["a futures market", "a Gas Daily market", "an IFERC market"],
)
def test_reading_a_market_back_rebuilds_nothing(
    sources: Callable[[], tuple[object, object]],
    call_profile: CallProfile,
    numpy_calls: CallProfile,
) -> None:
    made = PATH["_CreateMarket"](*sources())
    PATH["util_ReadHandle"](made)
    assert call_profile(lambda: PATH["util_ReadHandle"](made)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text": 1,
        "_resolve": 1,
        "util_ReadHandle": 1,
        "market_table": 1,
        "_priced_column": 1,
        "calendar_table": 1,  # the calendar's own table, as the calendar shows
        "MixedArray.table": 1,
        "_table_column": 3,
        "_unit": 1,
        "_serials": 1,
        "MixedArray.shape": 1,
        "_mixed_out": 1,
        "_bad_mixed": 1,
    }
    calls = numpy_calls(lambda: PATH["util_ReadHandle"](made))
    assert calls == {
        "numpy.array": 2,  # the calendar's: the schedule's codes as an array, its texts gathered
        "ndarray.ravel": 2,  # the calendar's texts in sheet order, and the live mask flattened
        "numpy.asanyarray": 1,  # on the way to the live rows
        "ndarray.nonzero": 1,  # the live rows
        "numpy.empty": 6,  # the calendar's two; the kinds, the slots, the pairs and their mask
        "numpy.asarray": 2,
        "numpy.datetime_data": 1,  # the unit of the date column
        "ndarray.any": 5,  # the serials' two checks, then the mixed road's three looks
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }
    assert "numpy.arange" not in calls and "ndarray.searchsorted" not in calls


# --- the Gas Daily fixings: two columns in, the days checked and both copied -----------------


def flow_day_columns(count: int) -> tuple[Cells, Cells]:
    """That many consecutive flow days from 1 September 2026 as the sheet sends them, a serial
    per row, and a price beside each."""
    return (
        Cells.from_rows([[46266.0 + i] for i in range(count)]),
        Cells.from_rows([[2.8 + (i % 30) / 100] for i in range(count)]),
    )


# A year of flow days: the date column through its look and its conversion to days, the number
# column accepted on the host's summary alone, the index by handle through its text rule and one
# lookup, the builder's kind check, its one look over the days for the day after each, its two
# copies and one publication. Twenty calls across sixteen functions, the accept rule once per
# argument; on numpy one look for the calendar and one for the days, the column's two
# conversions, the two copies and their freezes.
def test_gas_daily_fixings_are_two_columns_and_an_index_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    flow_days, prices = flow_day_columns(365)
    index = an_index(PATH["_CreateGasDailySchedule"](*gas_daily_month_columns(12)))
    PATH["_CreateGasDailyFixings"](flow_days, prices, index)
    assert call_profile(lambda: PATH["_CreateGasDailyFixings"](flow_days, prices, index)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text": 1,  # the handle's text rule
        "_resolve": 1,  # and its one lookup
        "_date_column": 1,
        "_column": 1,
        "_one_column": 2,
        "_shape": 2,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_numbers": 1,
        "_CreateGasDailyFixings": 1,
        "gas_daily_fixings": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateGasDailyFixings"](flow_days, prices, index)) == {
        "ndarray.any": 2,  # the column's look for the calendar, then the look over the days
        "ndarray.astype": 2,  # the column on its way to days
        "numpy.array": 2,  # the two copies the fixings keep
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 2,
    }


# --- the IFERC fixings: two columns in, the codes kept and the prices copied ---------------


def iferc_fixing_columns(count: int) -> tuple[Cells, Cells]:
    """That many contract months' indices as the sheet sends them: the codes of schedule_columns
    and a price beside each."""
    codes, _, _, _ = schedule_columns(count)
    return codes, Cells.from_rows([[2.0 + i / 100] for i in range(count)])


# Ten years of monthly indices: the text column handed over as it is, the number column accepted
# on the host's summary alone, the index by handle through its text rule and one lookup, the
# builder's kind check and count, its one pass over the codes against the index's months and for
# repeats, its one copy of the prices, and one publication. Eighteen calls across fourteen
# functions, the accept rule once per argument; nothing is asked of numpy but the copy and its
# freeze.
def test_iferc_fixings_are_two_columns_and_an_index_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, prices = iferc_fixing_columns(120)
    index = an_index(PATH["_CreateIfercSchedule"](*iferc_columns(120)))
    PATH["_CreateIfercFixings"](codes, prices, index)
    assert call_profile(lambda: PATH["_CreateIfercFixings"](codes, prices, index)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text": 1,  # the handle's text rule
        "_resolve": 1,  # and its one lookup
        "_text_column": 1,
        "_column": 1,
        "_one_column": 2,
        "_shape": 2,
        "_texts": 1,
        "_numbers": 1,
        "_CreateIfercFixings": 1,
        "iferc_fixings": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateIfercFixings"](codes, prices, index)) == {
        "numpy.array": 1,  # the one copy the fixings keep
        "ndarray.setflags": 1,  # frozen
    }


# --- the price vector: a name and one column of numbers in, one copy kept, one publication out --


def price_column(prices: int) -> Cells:
    """That many prices as the sheet sends them, one per row, around 74."""
    return Cells.from_rows([[74.25 + i % 7 - 3.0] for i in range(prices)])


# The name and the hot column: the name's text rule, the column accepted on the host's summary,
# no look, then the builder's one copy and its freeze, and one publication. Twelve calls across
# eleven functions, the text rule and the accept rule once each, and on numpy the copy and the
# freeze alone; nothing is sorted, checked, looked up or converted, and the name costs the
# library nothing.
def test_a_price_vector_is_a_name_and_one_column_in_and_one_copy_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    column = price_column(120)
    PATH["_CreatePriceVector"]("sample", column)
    assert call_profile(lambda: PATH["_CreatePriceVector"]("sample", column)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 1,  # the name's rule
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,  # the host's summary settles it: no look
        "_CreatePriceVector": 1,
        "price_vector": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreatePriceVector"]("sample", column)) == {
        "numpy.array": 1,  # the one copy the vector keeps
        "ndarray.setflags": 1,  # frozen
    }
