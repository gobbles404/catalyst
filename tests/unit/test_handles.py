"""Handles: the store, the text, and the two rules that publish and resolve, pinned exactly."""

import re
from typing import cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle, Table, TextRow, excel_function
from goosedove.excel.probes import probe


class Curve:
    """A kind of the test's own; any class the library defines could stand here."""

    def __init__(self, level: float) -> None:
        self.level = level


class Other:
    """A second kind, so a handle of one kind can be handed where the other is expected."""


class Steeper(Curve):
    """A subclass: not the declared kind, so a creator returning one fails."""


_returns: dict[str, object] = {}
_seen: dict[str, object] = {}


@probe
def MakeCurve(level: float) -> Handle[Curve]:
    return Curve(level)


@probe
def MakeOther() -> Handle[Other]:
    return Other()


@probe
def MakeWhatever() -> Handle[Curve]:
    return cast(Curve, _returns["value"])


@probe
def FailToMake() -> Handle[Curve]:
    raise ValueError("as asked")


@probe
def ReadCurve(curve: Handle[Curve]) -> float:
    _seen["curve"] = curve
    return curve.level


TEXT = re.compile(r"(curve|other):([0-9a-f]{6}):([0-9]{6})")


def parts(text: object) -> tuple[str, str, int]:
    """The three parts of a handle's text, or a failed assertion naming what came instead."""
    assert isinstance(text, str)
    match = TEXT.fullmatch(text)
    assert match, text
    return match.group(1), match.group(2), int(match.group(3))


# --- the way out: publishing ------------------------------------------------


def read(text: str) -> object:
    """The object the seam hands a consumer for this handle."""
    assert bridge.call("ReadCurve", [text]) == bridge.call("ReadCurve", [text])
    return _seen["curve"]


def test_a_creator_publishes_text_of_three_parts() -> None:
    tag, session, number = parts(bridge.call("MakeCurve", [1.0]))
    tag_again, session_again, number_again = parts(bridge.call("MakeCurve", [1.0]))
    assert (tag, tag_again) == ("curve", "curve")
    assert session == session_again  # one session id for the life of this Python
    assert (number, number_again) == (number, number + 1)


def test_the_number_runs_across_kinds_and_never_repeats() -> None:
    _, _, first = parts(bridge.call("MakeCurve", [1.0]))
    _, _, second = parts(bridge.call("MakeOther", []))
    _, _, third = parts(bridge.call("MakeCurve", [1.0]))
    assert (second, third) == (first + 1, first + 2)


def test_equal_calls_give_distinct_objects_and_distinct_text() -> None:
    a = cast(str, bridge.call("MakeCurve", [1.0]))
    b = cast(str, bridge.call("MakeCurve", [1.0]))
    assert a != b
    assert read(a) is not read(b)


# The number moves only when an object is stored, so an unmoved number is an empty publication.
def test_a_failing_creator_publishes_nothing_and_moves_no_number() -> None:
    _, _, before = parts(bridge.call("MakeCurve", [1.0]))
    assert bridge.call("FailToMake", []) == "#ERROR FailToMake: ValueError: as asked"
    _, _, after = parts(bridge.call("MakeCurve", [1.0]))
    assert after == before + 1


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ([1.0], "#ERROR MakeWhatever: returned a Python list, expected curve"),
        (None, "#ERROR MakeWhatever: returned nothing, expected curve"),
        (1.0, "#ERROR MakeWhatever: returned number 1.0, expected curve"),
        (
            "curve:000000:000001",
            "#ERROR MakeWhatever: returned text 'curve:000000:000001', expected curve",
        ),
        (Steeper(1.0), "#ERROR MakeWhatever: returned a Python Steeper, expected curve"),
    ],
)
def test_a_creator_returning_the_wrong_thing_fails_and_publishes_nothing(
    value: object, text: str
) -> None:
    _, _, before = parts(bridge.call("MakeCurve", [1.0]))
    _returns["value"] = value
    assert bridge.call("MakeWhatever", []) == text
    _, _, after = parts(bridge.call("MakeCurve", [1.0]))
    assert after == before + 1


# --- the way in: resolving --------------------------------------------------


def test_a_handle_resolves_to_the_same_object_every_time() -> None:
    text = cast(str, bridge.call("MakeCurve", [2.5]))
    assert bridge.call("ReadCurve", [text]) == 2.5
    first = _seen["curve"]
    assert bridge.call("ReadCurve", [text]) == 2.5
    assert _seen["curve"] is first
    assert isinstance(first, Curve)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (3.0, "#ERROR ReadCurve: curve is number 3.0, expected curve handle"),
        (True, "#ERROR ReadCurve: curve is boolean TRUE, expected curve handle"),
        (None, "#ERROR ReadCurve: curve is blank, expected curve handle"),
        (MISSING, "#ERROR ReadCurve: curve is missing, expected curve handle"),
        ("", "#ERROR ReadCurve: curve is empty text, expected curve handle"),
        (Cells.from_rows([["x"]]), "#ERROR ReadCurve: curve is 1x1 array, expected curve handle"),
        (
            "curve:000000:000001",
            "#ERROR ReadCurve: curve is text 'curve:000000:000001' naming no live object, "
            "expected curve handle",
        ),
        (
            "#ERROR MakeCurve: ValueError: it's bad",
            "#ERROR ReadCurve: curve is the creator's failure, expected curve handle: "
            "#ERROR MakeCurve: ValueError: it's bad",
        ),
    ],
)
def test_rejected(value: object, text: str) -> None:
    assert bridge.call("ReadCurve", [value]) == text


# A consumer may refer to a cell that is itself a consumer of a failed creator. Each relay used
# to quote the whole text before it, so the quoting compounded and Excel cut the creator's own
# words after a dozen relays. Every relay now carries the creator's failure whole, and a chain
# of any length shows one text.
def test_a_chain_of_relays_shows_the_creators_failure_once() -> None:
    root = "#ERROR MakeCurve: ValueError: it's bad"
    first = bridge.call("ReadCurve", [root])
    assert first == (
        f"#ERROR ReadCurve: curve is the creator's failure, expected curve handle: {root}"
    )
    text = first
    for _ in range(20):
        text = bridge.call("ReadCurve", [text])
        assert text == first


def test_a_handle_of_another_kind_is_named_and_refused() -> None:
    other = cast(str, bridge.call("MakeOther", []))
    assert bridge.call("ReadCurve", [other]) == (
        f"#ERROR ReadCurve: curve is other handle {other!r}, expected curve handle"
    )


# --- the declaration itself is checked at registration ----------------------


A_CURVE = Curve(1.0)


def test_a_handle_parameter_takes_no_default() -> None:
    def ReadWithDefault(curve: Handle[Curve] = A_CURVE) -> float:
        return curve.level

    with pytest.raises(TypeError, match="ReadWithDefault: curve declares a handle, which takes no"):
        excel_function(ReadWithDefault)


def test_a_handle_around_one_of_the_seams_own_types_refuses_to_register() -> None:
    def Boxed() -> Handle[float]:
        return 1.0

    def Read(x: Handle[str]) -> str:
        return x

    with pytest.raises(TypeError, match=r"Boxed declares Handle\[float\] as its result"):
        excel_function(Boxed)
    with pytest.raises(TypeError, match=r"Read: x declares Handle\[str\], which the seam cannot"):
        excel_function(Read)


def test_a_handle_around_a_table_or_its_schema_refuses_to_register() -> None:
    class Rows(Table):
        name: TextRow

    def Keep() -> Handle[Rows]:
        raise AssertionError("never called")

    def Bare() -> Handle[Table]:
        raise AssertionError("never called")

    with pytest.raises(TypeError, match=r"Keep declares Handle\["):
        excel_function(Keep)
    with pytest.raises(TypeError, match=r"Bare declares Handle\["):
        excel_function(Bare)
