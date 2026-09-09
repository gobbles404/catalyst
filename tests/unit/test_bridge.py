import ctypes

import numpy as np

from goosedove.excel import bridge


def test_ping_is_registered() -> None:
    names = [name for name, _, _ in bridge.function_specs()]
    assert "Ping" in names


def test_call_ping_reports_version_and_location() -> None:
    result = bridge.call("Ping", [])
    assert isinstance(result, str)
    assert "goosedove" in result


def test_specs_carry_name_description_and_parameters() -> None:
    specs = {name: (doc, params) for name, doc, params in bridge.function_specs()}
    assert specs["Add"] == ("Add two numbers; proves arguments cross the seam.", ["a", "b"])
    assert specs["Ping"][1] == []


def test_add_crosses_the_seam() -> None:
    assert bridge.call("Add", [1.5, 2.0]) == 3.5


# What the host sends for a 2x2 range holding 1.5, "n/a", a blank, and TRUE.
def test_cells_block_copies_the_host_buffers() -> None:
    kinds = (ctypes.c_uint8 * 4)(0, 1, 3, 2)
    numbers = (ctypes.c_double * 4)(1.5, float("nan"), float("nan"), 1.0)
    cells = bridge.cells_block(ctypes.addressof(kinds), ctypes.addressof(numbers), 2, 2, "n/a")
    kinds[0] = 9
    numbers[0] = 99.0
    assert cells.kinds.tolist() == [[0, 1], [3, 2]]
    assert cells.numbers[0, 0] == 1.5
    assert np.isnan(cells.numbers[0, 1])
    assert cells.texts == ("n/a",)


def test_cells_block_splits_the_joined_text_even_when_a_cell_is_empty() -> None:
    kinds = (ctypes.c_uint8 * 2)(1, 1)
    numbers = (ctypes.c_double * 2)(float("nan"), float("nan"))
    cells = bridge.cells_block(ctypes.addressof(kinds), ctypes.addressof(numbers), 1, 2, "x\0")
    assert cells.texts == ("x", "")


def test_cells_block_with_no_text_has_no_texts() -> None:
    kinds = (ctypes.c_uint8 * 1)(0)
    numbers = (ctypes.c_double * 1)(2.0)
    cells = bridge.cells_block(ctypes.addressof(kinds), ctypes.addressof(numbers), 1, 1, "")
    assert cells.texts == ()
