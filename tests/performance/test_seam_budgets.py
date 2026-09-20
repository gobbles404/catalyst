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
    dead = "discount_curve:000000:000001"
    assert call_profile(lambda: PATH["util_ReadHandle"](dead)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve": 1,
        "_text": 1,
    }


# --- the first index definition: up to four columns in, one publication out --------------


def schedule_columns(contracts: int) -> tuple[Cells, Cells, Cells, Cells]:
    """Codes and three date columns for that many monthly contracts, as the sheet sends them:
    the futures, the options and the publication dates."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + 30 * i] for i in range(contracts)])
    options = Cells.from_rows([[46156.0 + 30 * i] for i in range(contracts)])
    publications = Cells.from_rows([[46162.0 + 30 * i] for i in range(contracts)])
    return codes, futures, options, publications


# Ten years of monthly contracts with every column: the text column handed over as it is, one
# look and two conversions per date column, the builder's three copies, and one publication.
# Thirty-four calls across fifteen functions, the accept rule once per argument.
def test_an_expiry_schedule_is_four_columns_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, options, publications = schedule_columns(120)
    PATH["_CreateExpirySchedule"](codes, futures, options, publications)
    assert call_profile(
        lambda: PATH["_CreateExpirySchedule"](codes, futures, options, publications)
    ) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,
        "_text_column": 1,
        "_date_column": 3,
        "_one_column": 4,
        "_shape": 4,
        "_texts": 1,
        "_dates": 3,
        "_not_dates": 3,
        "_as_days": 3,
        "_CreateExpirySchedule": 1,
        "expiry_schedule": 1,
        "_one_per_code": 3,  # the one rule, once per date column
        "_publish": 1,
    }
    assert numpy_calls(
        lambda: PATH["_CreateExpirySchedule"](codes, futures, options, publications)
    ) == {
        "ndarray.any": 3,  # one look per date column, for the calendar
        "ndarray.astype": 6,  # each date column on its way to days
        "numpy.array": 3,  # the three copies the schedule keeps
        "ndarray.setflags": 3,  # frozen
        "ufunc.reduce": 3,
    }


# The publication dates with the options left out: three columns' cost, the same as with the
# options and without the publication dates, since a column left out costs nothing.
def test_an_expiry_schedule_with_publication_dates_alone_pays_for_three_columns(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, _, publications = schedule_columns(120)
    PATH["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    assert call_profile(
        lambda: PATH["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    ) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,
        "_text_column": 1,
        "_date_column": 2,
        "_one_column": 3,
        "_shape": 3,
        "_texts": 1,
        "_dates": 2,
        "_not_dates": 2,
        "_as_days": 2,
        "_CreateExpirySchedule": 1,
        "expiry_schedule": 1,
        "_one_per_code": 2,
        "_publish": 1,
    }
    assert numpy_calls(
        lambda: PATH["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    ) == {
        "ndarray.any": 2,
        "ndarray.astype": 4,
        "numpy.array": 2,
        "ndarray.setflags": 2,
        "ufunc.reduce": 2,
    }


# The third and fourth columns left out: the stored defaults are handed over, and nothing runs
# for them beyond the accept rule's one call each.
def test_an_expiry_schedule_without_options_or_publication_dates_pays_for_two_columns(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, _, _ = schedule_columns(120)
    PATH["_CreateExpirySchedule"](codes, futures, MISSING, MISSING)
    assert call_profile(
        lambda: PATH["_CreateExpirySchedule"](codes, futures, MISSING, MISSING)
    ) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,
        "_text_column": 1,
        "_date_column": 1,
        "_one_column": 2,
        "_shape": 2,
        "_texts": 1,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_CreateExpirySchedule": 1,
        "expiry_schedule": 1,
        "_one_per_code": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateExpirySchedule"](codes, futures, MISSING, MISSING)) == {
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


# --- the third index definition: five texts in, one publication out ------------------


# Five scalars, each through the text rule, the builder and one publication: nothing is asked of
# numpy, and the builder has no rule of its own to run.
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
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateIndexConventions"](*codes)) == {}


# --- the fourth index definition: a table of contracts in, one publication out ----------


SPECIFICATION_HEADERS = Cells.from_rows(
    [["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)


def specification_body(contracts: int) -> Cells:
    """That many contracts as the sheet sends them: a name, a whole lot size and two fees."""
    return Cells.from_rows([[f"contract {i}", 1000.0 + i, 3.0, 2.0] for i in range(contracts)])


# A dozen contracts at the table path: the header row as any row of text, the body admitted as
# a mixed range and bound, then each column through its rule, the names gathered and the three
# number columns as views, the builder's look at the lot sizes for a fraction, its three copies
# and one publication. Twenty-one calls across eighteen functions.
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
        "_texts_of": 1,
        "_numbers_of": 3,
        "_CreateContractSpecifications": 1,
        "contract_specifications": 1,
        "_publish": 1,
    }
    assert numpy_calls(
        lambda: PATH["_CreateContractSpecifications"](SPECIFICATION_HEADERS, body)
    ) == {
        "ndarray.any": 5,  # one look per column, then the builder's, for a lot size with a fraction
        "numpy.array": 4,  # the names as an array for the gather, and the builder's three copies
        "ndarray.cumsum": 1,  # the text cells above each row
        "ndarray.sum": 2,  # text cells per row, and to the left
        "ndarray.setflags": 3,  # frozen
        "ufunc.reduce": 7,
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


# --- the daily fixings: a table and a calendar's handle in, one publication out ---------------


FIXINGS_HEADERS = Cells.from_rows([["date", "settle"]])


def fixings_body(rows: int, holidays: int) -> Cells:
    """That many daily fixings as the sheet sends them, a serial and a settle per row, one per
    business day from Friday 1 May 2026 under a calendar of that many Thursdays a week apart,
    the calendar holiday_column makes."""
    epoch = np.datetime64("1899-12-30")
    closed = epoch + (46023 + 7 * np.arange(holidays)).astype("timedelta64[D]")
    days = np.busday_offset(np.datetime64("2026-05-01"), np.arange(rows), holidays=closed)
    serials = (days - epoch).astype(np.int64)
    return Cells.from_rows([[float(serials[i]), 100.0 + i % 7] for i in range(rows)])


# A year of fixings at the table path, with the market's calendar by handle: the header row as
# any row of text, the body admitted as a mixed range and bound, one look per column, the date
# column converted to days, the handle's text rule and its one lookup, then the builder's three
# looks, the order of the dates, the days the market is closed and the business days without a
# fixing, its two copies, and one publication. Twenty-two calls across twenty functions, the
# accept rule once per argument; before the calendar, nineteen across eighteen. The three
# business-day calls, the calendar, is_busday and busday_offset, raise no event the numpy
# fixture reads, so only their looks are in its count.
def test_daily_fixings_are_a_table_and_a_calendar_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    calendar = PATH["_CreateHolidayCalendar"](holiday_column(100))
    body = fixings_body(260, 100)
    PATH["_CreateDailyFixings"](FIXINGS_HEADERS, body, calendar)
    assert call_profile(lambda: PATH["_CreateDailyFixings"](FIXINGS_HEADERS, body, calendar)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
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
        "_text": 1,  # the handle's text rule
        "_resolve": 1,  # and its one lookup
        "_CreateDailyFixings": 1,
        "daily_fixings": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateDailyFixings"](FIXINGS_HEADERS, body, calendar)) == {
        "ndarray.any": 5,  # one look per column, then the builder's: order, days closed, gaps
        "ndarray.astype": 2,  # the date column on its way to days
        "numpy.array": 2,  # the two copies the fixings keep
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 5,
    }


# --- the calendar: three handles in, four columns made once, one publication out ------------


def calendar_sources(contracts: int) -> tuple[object, str, object, object]:
    """What a calendar takes: the valuation date's handle, the mode, daily, a schedule of that
    many monthly contracts a month apart, and a calendar of a hundred holidays a week apart."""
    codes, futures, _, _ = schedule_columns(contracts)
    return (
        PATH["_CreateValuationDate"](46276.0, 0.5),
        "daily",
        PATH["_CreateExpirySchedule"](codes, futures, MISSING, MISSING),
        PATH["_CreateHolidayCalendar"](holiday_column(100)),
    )


# A year of days from thirteen contracts: three handles, each the text rule and one lookup, and
# the mode, the text rule alone, the builder's look at the mode and its one look at the order of
# the expiries, its days in one arange, the prompt row of each in one searchsorted, the two
# flags, and one publication. Sixteen calls across eight functions, the accept rule once per
# argument, from fourteen before the mode, which adds its check and its text rule; is_busday
# and the comparison against the valuation date raise no event the numpy fixture reads, and nor
# does the mode, held as an enum.
def test_a_calendar_is_three_handles_in_and_four_columns_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    valuation, mode, schedule, holidays = calendar_sources(13)
    PATH["_CreateCalendar"](valuation, mode, schedule, holidays)
    assert call_profile(lambda: PATH["_CreateCalendar"](valuation, mode, schedule, holidays)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,
        "_text": 4,  # each handle's text rule, and the mode's
        "_resolve": 3,  # each handle's one lookup
        "_CreateCalendar": 1,
        "calendar": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateCalendar"](valuation, mode, schedule, holidays)) == {
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


# --- the market history: two handles in, the calendar kept, its past business days priced ------


def history_sources(contracts: int) -> tuple[object, object]:
    """The two handles a history takes: the calendar calendar_sources makes, valued on 11
    September 2026, and fixings on every business day from Friday 1 May 2026 to the day
    before, under the same hundred Thursdays, so every past business day has one."""
    valuation, mode, schedule, holidays = calendar_sources(contracts)
    made = PATH["_CreateCalendar"](valuation, mode, schedule, holidays)
    closed = np.datetime64("1899-12-30") + (46023 + 7 * np.arange(100)).astype("timedelta64[D]")
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=closed))
    fixings = PATH["_CreateDailyFixings"](FIXINGS_HEADERS, fixings_body(rows, 100), holidays)
    return made, fixings


# A year of days and the fixings on its past business days: two handles, each the text rule and
# one lookup, the fixings' among two kinds, the builder's match on the calendar's mode and the
# fixings' kind, then the daily rules' three looks, a fixing on or after the valuation date, a
# fixing on a day the calendar closes and a past business day without one, its rows from one
# subtraction over the fixings' days, the days covered in one zeros, and one publication.
# Twelve calls across nine functions since #88, the daily rules a function of their own, from
# eleven across eight, the accept rule once per argument; no arange, no searchsorted and no
# look at a holiday, since the calendar is taken as it is and nothing of it is made again.
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
        "_resolve": 2,  # and its one lookup, the fixings' against two kinds
        "_CreateMarketHistory": 1,
        "market_history": 1,
        "_daily_history": 1,  # the daily rules, chosen by the calendar's mode
        "_publish": 1,
    }
    calls = numpy_calls(lambda: PATH["_CreateMarketHistory"](made, fixings))
    assert calls == {
        "ndarray.any": 3,  # the builder's three looks
        "ndarray.astype": 1,  # the fixings' days to rows of the calendar
        "numpy.zeros": 1,  # the rows covered
        "ndarray.setflags": 2,  # the two columns frozen
        "ufunc.reduce": 3,
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
    schedule = PATH["_CreateExpirySchedule"](codes, futures, MISSING, MISSING)
    holidays = PATH["_CreateHolidayCalendar"](holiday_column(100))
    made = PATH["_CreateCalendar"](valuation, "daily", schedule, holidays)
    closed = np.datetime64("1899-12-30") + (46023 + 7 * np.arange(100)).astype("timedelta64[D]")
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=closed))
    fixings = PATH["_CreateDailyFixings"](FIXINGS_HEADERS, fixings_body(rows, 100), holidays)
    history = PATH["_CreateMarketHistory"](made, fixings)
    first = int(np.searchsorted(46161.0 + days_apart * np.arange(contracts), 46276.0))
    quotes = Cells.from_rows([[70.0 + i % 5] for i in range(contracts - first)])
    return history, PATH["_CreatePriceVector"](quotes)


# The hot operation: two handles, each the text rule and one lookup, the builder's two rules on
# scalars, the valuation day's row from one subtraction and its prompt row read there, and one
# publication. Eleven calls across eight functions, and not one numpy call: no copy, no look,
# no mask and no array, whatever the calendar's length and the vector's, a year of days with
# nine quotes, ten years with one quote, or a year with 246 quotes alike.
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
    assert call_profile(lambda: PATH["_CreateMarket"](history, quotes)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,  # each handle's text rule
        "_resolve": 2,  # and its one lookup
        "_CreateMarket": 1,
        "market": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateMarket"](history, quotes)) == {}


# Reading a market back is reading its calendar back, then the fifth column through the helper
# the history's reader shares: the live rows found in one flatnonzero, their prompt rows gathered
# and the quotes read through them, the fixings and the quotes written into their rows and the
# word closed shared by every other; no arange, no searchsorted, nothing of the calendar made
# again.
def test_reading_a_market_back_rebuilds_nothing(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made = PATH["_CreateMarket"](*market_sources(13, 30))
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


# --- the monthly history and market: the expired contracts priced, the rest quoted -------------


def monthly_sources(contracts: int) -> tuple[object, object]:
    """The two handles a monthly history takes: a monthly calendar over the schedule of
    schedule_columns with its publication dates, the day after each expiry, under the same
    hundred Thursdays, valued on 11 September 2026, and fixings for the contracts expired by
    then, the anchor's left out, so every expired contract has one and no other does."""
    codes, futures, _, publications = schedule_columns(contracts)
    schedule = PATH["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    valuation = PATH["_CreateValuationDate"](46276.0, 0.5)
    holidays = PATH["_CreateHolidayCalendar"](holiday_column(100))
    made = PATH["_CreateCalendar"](valuation, "monthly", schedule, holidays)
    expired = int(np.searchsorted(46161.0 + 30 * np.arange(contracts), 46276.0))
    dates = Cells.from_rows([[46162.0 + 30 * i] for i in range(1, expired)])
    prices = Cells.from_rows([[2.0 + i / 100] for i in range(1, expired)])
    return made, PATH["_CreateMonthlyFixings"](dates, prices, schedule)


def monthly_market_sources(contracts: int) -> tuple[object, object]:
    """The two handles a monthly market takes: the history monthly_sources makes and a vector
    with one quote per contract from the valuation day's prompt through the last."""
    history = PATH["_CreateMarketHistory"](*monthly_sources(contracts))
    first = int(np.searchsorted(46161.0 + 30 * np.arange(contracts), 46276.0))
    quotes = Cells.from_rows([[3.0 + i % 5 / 10] for i in range(contracts - first)])
    return history, PATH["_CreatePriceVector"](quotes)


# A year of days over thirteen contracts, four expired, and the three fixings they need: two
# handles, each the text rule and one lookup, the builder's match on the mode and the kind,
# then the monthly rules and the assignment in a function of their own, and one publication.
# Twelve calls across nine functions, the daily history's count. On numpy: one look at the
# schedule's publication dates for their order, no sort and no copy; the expired contracts
# found in one searchsorted over the expiries; the live contracts' dates and then the expired
# ones' searched in the supplied dates, one searchsorted each, the two looks with their
# reductions; the fixed rows found in one searchsorted over the prompts and listed in one
# arange; the prices gathered once through the prompts, a gather raising no event the numpy
# fixture reads; the two columns frozen. No sort, no copy and no look at a day, a holiday or a
# flag, since the days of the expired contracts are the calendar's first rows and the calendar
# is taken as it is.
def test_a_monthly_history_is_two_handles_in_and_the_expired_contracts_priced(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made, fixings = monthly_sources(13)
    PATH["_CreateMarketHistory"](made, fixings)
    assert call_profile(lambda: PATH["_CreateMarketHistory"](made, fixings)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,  # each handle's text rule
        "_resolve": 2,  # and its one lookup, the fixings' against two kinds
        "_CreateMarketHistory": 1,
        "market_history": 1,
        "_monthly_history": 1,  # the monthly rules, chosen by the calendar's mode
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateMarketHistory"](made, fixings)) == {
        "ndarray.any": 2,  # the publication dates' order, then a live contract's fixing
        "ndarray.all": 1,  # every expired contract's fixing found
        "ndarray.searchsorted": 4,  # the expired contracts, the live dates, the wanted, the rows
        "numpy.arange": 1,  # the fixed rows, the calendar's first
        "ndarray.setflags": 2,  # the two columns frozen
        "ufunc.reduce": 3,
    }


# Reading a monthly history back is reading its calendar back and then the fifth column through
# the helper the daily history's reader shares, one empty fewer than the daily's: there is no
# words array to make, since every day without a fixing shows the one word; no arange, no
# searchsorted, nothing of the calendar made again.
def test_reading_a_monthly_history_back_rebuilds_nothing(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made = PATH["_CreateMarketHistory"](*monthly_sources(13))
    PATH["util_ReadHandle"](made)
    assert call_profile(lambda: PATH["util_ReadHandle"](made)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text": 1,
        "_resolve": 1,
        "util_ReadHandle": 1,
        "market_history_table": 1,
        "_priced_column": 1,
        "calendar_table": 1,
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
        "numpy.empty": 6,  # the calendar's two; the kinds, slots, pairs and mask, no words
        "numpy.asarray": 2,
        "numpy.datetime_data": 1,  # the unit of the date column
        "ndarray.any": 5,  # the serials' two checks, then the mixed road's three looks
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }
    assert "numpy.arange" not in calls and "ndarray.searchsorted" not in calls


# A monthly market is the daily one's call: two handles, the builder's two rules on scalars,
# one number and one publication, eleven calls across eight functions and no numpy call; the
# mode is read when the handle is, not here.
def test_a_monthly_market_is_two_handles_in_and_one_number_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    history, quotes = monthly_market_sources(13)
    PATH["_CreateMarket"](history, quotes)
    assert call_profile(lambda: PATH["_CreateMarket"](history, quotes)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,
        "_resolve": 2,
        "_CreateMarket": 1,
        "market": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateMarket"](history, quotes)) == {}


# Reading a monthly market back is reading its calendar back, then the fifth column through the
# helper: the live rows, every day of a contract not yet expired, found in one flatnonzero over
# the prompts, their quotes read through them, the fixings and the quotes written into their
# rows and no word left, the same calls as the daily market's reading; no arange, no
# searchsorted, nothing of the calendar made again.
def test_reading_a_monthly_market_back_rebuilds_nothing(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    made = PATH["_CreateMarket"](*monthly_market_sources(13))
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
        "calendar_table": 1,
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
        "numpy.array": 2,
        "ndarray.ravel": 2,  # the calendar's texts in sheet order, and the live mask flattened
        "numpy.asanyarray": 1,  # on the way to the live rows
        "ndarray.nonzero": 1,  # the live rows
        "numpy.empty": 6,
        "numpy.asarray": 2,
        "numpy.datetime_data": 1,
        "ndarray.any": 5,
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }
    assert "numpy.arange" not in calls and "ndarray.searchsorted" not in calls


# --- the monthly fixings: two columns and a schedule's handle in, the dates kept ------------


def published_columns(count: int) -> tuple[Cells, Cells]:
    """That many monthly publications as the sheet sends them, the publication dates of the
    schedule schedule_columns makes, a serial per row, and a price beside each."""
    _, _, _, publications = schedule_columns(count)
    return publications, Cells.from_rows([[2.0 + i / 100] for i in range(count)])


# Ten years of monthly publications, with the index's schedule by handle: the date column
# through its look and its conversion to days, the number column accepted on the host's summary
# alone, the handle's text rule and its one lookup, then the builder's three looks, the order of
# the dates, the dates the schedule does not publish on and the publications without a fixing,
# its sorted copy of the schedule's dates and its one search over the column, its two copies,
# and one publication. Twenty calls across sixteen functions; before the schedule, seventeen
# across fourteen. On numpy the sorted copy is np.unique's flatten, sort and two asanyarray,
# then one searchsorted, four looks with their reductions, and the two copies frozen.
def test_monthly_fixings_are_two_columns_and_a_schedule_in_and_the_dates_kept(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, _, publications = schedule_columns(120)
    schedule = PATH["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    dates, prices = published_columns(120)
    PATH["_CreateMonthlyFixings"](dates, prices, schedule)
    assert call_profile(lambda: PATH["_CreateMonthlyFixings"](dates, prices, schedule)) == {
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
        "_CreateMonthlyFixings": 1,
        "monthly_fixings": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateMonthlyFixings"](dates, prices, schedule)) == {
        "ndarray.any": 4,  # the column's look for the calendar, then the order, absent, skipped
        "ndarray.astype": 2,  # the column on its way to days
        "ndarray.flatten": 1,  # np.unique's copy of the schedule's dates
        "numpy.asanyarray": 2,  # and its reads of them
        "ndarray.sort": 1,  # sorted once
        "ndarray.searchsorted": 1,  # each date's place among the publications
        "numpy.array": 2,  # the two copies the fixings keep
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 4,
    }


# --- the price vector: one column of numbers in, one copy kept, one publication out -----------


def price_column(prices: int) -> Cells:
    """That many prices as the sheet sends them, one per row, around 74."""
    return Cells.from_rows([[74.25 + i % 7 - 3.0] for i in range(prices)])


# The hot column: accepted on the host's summary, no look, then the builder's one copy and its
# freeze, and one publication. Ten calls across ten functions, the accept rule once, and on
# numpy the copy and the freeze alone; nothing is sorted, checked or converted.
def test_a_price_vector_is_one_column_in_and_one_copy_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    column = price_column(120)
    PATH["_CreatePriceVector"](column)
    assert call_profile(lambda: PATH["_CreatePriceVector"](column)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,  # the host's summary settles it: no look
        "_CreatePriceVector": 1,
        "price_vector": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreatePriceVector"](column)) == {
        "numpy.array": 1,  # the one copy the vector keeps
        "ndarray.setflags": 1,  # frozen
    }
