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


def test_every_probe_is_hidden_and_ping_is_not() -> None:
    hidden = {name for name, _, _, hidden in bridge.function_specs() if hidden}
    assert hidden >= {
        "Zero",
        "Add",
        "Times",
        "EchoText",
        "EchoBoolean",
        "SumArray",
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
def test_cells_block_copies_the_host_buffers() -> None:
    kinds = (ctypes.c_uint8 * 4)(0, 1, 3, 2)
    numbers = (ctypes.c_double * 4)(1.5, float("nan"), float("nan"), 1.0)
    cells = bridge.cells_from_buffers(
        ctypes.addressof(kinds), ctypes.addressof(numbers), 2, 2, "n/a"
    )
    kinds[0] = 9
    numbers[0] = 99.0
    assert cells.kinds.tolist() == [[0, 1], [3, 2]]
    assert cells.numbers[0, 0] == 1.5
    assert np.isnan(cells.numbers[0, 1])
    assert cells.texts == ("n/a",)


def test_cells_block_splits_the_joined_text_even_when_a_cell_is_empty() -> None:
    kinds = (ctypes.c_uint8 * 2)(1, 1)
    numbers = (ctypes.c_double * 2)(float("nan"), float("nan"))
    cells = bridge.cells_from_buffers(
        ctypes.addressof(kinds), ctypes.addressof(numbers), 1, 2, "x\0"
    )
    assert cells.texts == ("x", "")


def test_cells_block_with_no_text_has_no_texts() -> None:
    kinds = (ctypes.c_uint8 * 1)(0)
    numbers = (ctypes.c_double * 1)(2.0)
    cells = bridge.cells_from_buffers(ctypes.addressof(kinds), ctypes.addressof(numbers), 1, 1, "")
    assert cells.texts == ()


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
