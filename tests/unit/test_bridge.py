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


def test_numeric_block_copies_the_host_buffer() -> None:
    buffer = (ctypes.c_double * 6)(1.0, 2.0, 3.0, 4.0, 5.0, float("nan"))
    block = bridge.numeric_block(ctypes.addressof(buffer), 2, 3)
    buffer[0] = 99.0
    assert block[0, 0] == 1.0
    assert np.isnan(block[1, 2])
    assert block.shape == (2, 3)
