from goosedove.excel import bridge


def test_ping_is_registered() -> None:
    names = [name for name, _, _ in bridge.function_specs()]
    assert "Ping" in names


def test_call_ping_reports_version_and_location() -> None:
    result = bridge.call("Ping", [])
    assert isinstance(result, str)
    assert "goosedove" in result


def test_errors_become_cell_text() -> None:
    result = bridge.call("Ping", ["unexpected argument"])
    assert isinstance(result, str)
    assert result.startswith("#ERROR")


def test_specs_carry_name_description_and_parameters() -> None:
    specs = {name: (doc, params) for name, doc, params in bridge.function_specs()}
    assert specs["Add"] == ("Add two numbers; proves arguments cross the seam.", ["a", "b"])
    assert specs["Ping"][1] == []
