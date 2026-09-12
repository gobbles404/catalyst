import ctypes

import numpy as np
import pytest

from goosedove.excel import bridge


def test_ping_is_registered() -> None:
    names = [name for name, _, _, _ in bridge.function_specs()]
    assert "Ping" in names


def test_call_ping_reports_version_and_location() -> None:
    result = bridge.call("Ping", [])
    assert isinstance(result, str)
    assert "goosedove" in result


def test_specs_carry_name_description_parameters_and_hidden() -> None:
    specs = {name: (doc, params, hidden) for name, doc, params, hidden in bridge.function_specs()}
    assert specs["Add"] == (
        "Probe: a number in and a number out; the reference for the cost of one call.",
        ["a", "b"],
        True,
    )
    assert specs["Ping"] == ("Confirm which goosedove Excel is running.", [], False)


_kept: dict[str, bridge.MixedArray] = {}


@bridge.excel_function
def KeepMixed(values: bridge.MixedArray) -> float:
    """Keep what arrived, so a test can hold it while later calls reuse the host's buffers."""
    _kept["values"] = values
    return 1.0


def test_a_mixed_range_hands_over_the_storage_the_transport_owns() -> None:
    # No copy: the record's three fields are the objects the range already held. NumberArray and
    # TextColumn do the same; this says it of a record rather than of a bare array.
    arrived = bridge.Cells.from_rows([["a", 1.0], [True, 2.0]])
    bridge.call("KeepMixed", [arrived])
    record = _kept["values"]
    assert record.kinds is arrived.kinds
    assert record.numeric_slots is arrived.numbers
    assert record.texts is arrived.texts
    assert record.shape == arrived.kinds.shape


def test_a_kept_mixed_range_survives_the_host_refilling_and_growing_its_buffers() -> None:
    # Python owns its copy of the buffers, so a record a function kept is still what it was
    # after the host writes the next range over the same memory and then grows it for a larger.
    kinds = (ctypes.c_uint8 * 2)(1, 0)
    numbers = (ctypes.c_double * 2)(float("nan"), 7.0)
    arrived = bridge.cells_from_buffers(
        ctypes.addressof(kinds), ctypes.addressof(numbers), 1, 2, "keep", 0b11
    )
    bridge.call("KeepMixed", [arrived])
    record = _kept["values"]
    column = record.numeric_slots[:, 1]  # a view, which retains the whole buffer

    kinds[0], kinds[1] = 3, 3  # the host refills the same buffers for the next range
    numbers[0], numbers[1] = 99.0, 99.0
    bigger = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)  # and grows them for a larger one
    wider = (ctypes.c_uint8 * 4)(0, 0, 0, 0)
    bridge.call(
        "SumArray",
        [
            bridge.cells_from_buffers(
                ctypes.addressof(wider), ctypes.addressof(bigger), 2, 2, "", 0b1
            )
        ],
    )

    assert record.shape == (1, 2)
    assert record.kinds.tolist() == [[1, 0]]
    assert record.texts == ("keep",)
    assert column.tolist() == [7.0]


def test_every_probe_is_hidden_and_ping_is_not() -> None:
    hidden = {name for name, _, _, hidden in bridge.function_specs() if hidden}
    assert hidden >= {
        "Zero",
        "Add",
        "Times",
        "EchoText",
        "EchoBoolean",
        "SumArray",
        "CountArray",
        "CountMixed",
        "Dot",
        "EchoColumn",
        "EchoRow",
        "RowSums",
        "Grid",
        "Fail",
    }
    assert "Ping" not in hidden


def test_add_crosses_the_seam() -> None:
    assert bridge.call("Add", [1.5, 2.0]) == 3.5


# What the host sends for a 2x2 range holding 1.5, "n/a", a blank, and TRUE.
def test_cells_from_buffers_copies_the_host_buffers() -> None:
    kinds = (ctypes.c_uint8 * 4)(0, 1, 3, 2)
    numbers = (ctypes.c_double * 4)(1.5, float("nan"), float("nan"), 1.0)
    cells = bridge.cells_from_buffers(
        ctypes.addressof(kinds), ctypes.addressof(numbers), 2, 2, "n/a", 0b1111
    )
    kinds[0] = 9
    numbers[0] = 99.0
    assert cells.kinds.tolist() == [[0, 1], [3, 2]]
    assert cells.numbers[0, 0] == 1.5
    assert np.isnan(cells.numbers[0, 1])
    assert cells.texts == ("n/a",)
    assert cells.seen == 0b1111


def test_cells_from_buffers_splits_the_joined_text_even_when_a_cell_is_empty() -> None:
    kinds = (ctypes.c_uint8 * 2)(1, 1)
    numbers = (ctypes.c_double * 2)(float("nan"), float("nan"))
    cells = bridge.cells_from_buffers(
        ctypes.addressof(kinds), ctypes.addressof(numbers), 1, 2, "x\0", bridge.ONLY_TEXT
    )
    assert cells.texts == ("x", "")


def test_cells_from_buffers_with_no_text_has_no_texts() -> None:
    kinds = (ctypes.c_uint8 * 1)(0)
    numbers = (ctypes.c_double * 1)(2.0)
    cells = bridge.cells_from_buffers(
        ctypes.addressof(kinds), ctypes.addressof(numbers), 1, 1, "", bridge.ONLY_NUMBERS
    )
    assert cells.texts == ()


# The host's summary is one bit per kind that occurred; from_rows computes the same one.
def test_from_rows_sees_the_kinds_the_host_would_see() -> None:
    assert bridge.Cells.from_rows([[1.0, 2.0]]).seen == bridge.ONLY_NUMBERS
    assert bridge.Cells.from_rows([["a"], ["b"]]).seen == bridge.ONLY_TEXT
    assert bridge.Cells.from_rows([[1.0, "x", None, True, bridge.MISSING]]).seen == 0b11111


def test_from_rows_refuses_a_range_with_no_cells() -> None:
    with pytest.raises(ValueError):
        bridge.Cells.from_rows([[]])
    with pytest.raises(ValueError):
        bridge.Cells.from_rows([])


# A bad cell is still named by its kind code when the summary says the range is not all numbers.
def test_the_summary_decides_and_the_kinds_name_the_cell() -> None:
    assert bridge.call("SumArray", [bridge.Cells.from_rows([[1.0, 2.0], [3.0, 4.0]])]) == 10.0
    assert (
        bridge.call("SumArray", [bridge.Cells.from_rows([[1.0, 2.0], [3.0, "x"]])])
        == "#ERROR SumArray: values cell (2, 2) is text 'x', expected number"
    )
    assert (
        bridge.call("SumArray", [bridge.Cells.from_rows([[1.0, True]])])
        == "#ERROR SumArray: values cell (1, 2) is boolean TRUE, expected number"
    )


def test_entry_is_the_prepared_path_the_host_holds() -> None:
    add = bridge.entry("Add")
    assert add(1.0, 2.0) == 3.0
    assert add(1.0, True) == "#ERROR Add: b is boolean TRUE, expected number"
    assert add(1.0) == "#ERROR Add: expected 2 arguments, got 1"
    assert bridge.entry("Fail")() == "#ERROR Fail: ValueError: as asked"


def test_entry_of_an_unregistered_name_fails_at_registration_not_at_the_call() -> None:
    with pytest.raises(KeyError):
        bridge.entry("NoSuchFunction")


def test_call_by_name_is_the_same_path() -> None:
    assert bridge.call("Add", [1.0, 2.0]) == bridge.entry("Add")(1.0, 2.0)
