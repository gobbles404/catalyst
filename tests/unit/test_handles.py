"""Handles: the store, the text, and the two rules that publish and resolve, pinned exactly."""

import re
from typing import cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import (
    MISSING,
    Cells,
    Handle,
    Table,
    TextRow,
    excel_function,
    register,
)
from goosedove.excel.probes import probe


class Curve:
    """A kind of the test's own; any class the library defines could stand here."""

    def __init__(self, level: float) -> None:
        self.level = level


class Other:
    """A second kind, so a handle of one kind can be handed where the other is expected."""


class Steeper(Curve):
    """A subclass: not the declared kind, so a creator returning one fails."""


class Third:
    """A third kind, refused where one of two is expected."""


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


@probe
def MakeThird() -> Handle[Third]:
    return Third()


@probe
def ReadEither(item: Handle[Curve | Other]) -> str:
    _seen["either"] = item
    return type(item).__name__


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


# --- a handle of any kind ----------------------------------------------------


@probe
def ReadAny(handle: Handle[object]) -> str:
    """Names the class of whatever object a handle stands for."""
    _seen["any"] = handle
    return type(handle).__name__


def test_a_handle_of_any_kind_resolves_whatever_the_key_finds() -> None:
    curve = cast(str, bridge.call("MakeCurve", [1.0]))
    other = cast(str, bridge.call("MakeOther", []))
    assert bridge.call("ReadAny", [curve]) == "Curve"
    assert _seen["any"] is read(curve)
    assert bridge.call("ReadAny", [other]) == "Other"


# Decision 35's order and words, with no kind to name.
@pytest.mark.parametrize(
    ("value", "text"),
    [
        (3.0, "#ERROR ReadAny: handle is number 3.0, expected a handle"),
        (None, "#ERROR ReadAny: handle is blank, expected a handle"),
        (MISSING, "#ERROR ReadAny: handle is missing, expected a handle"),
        ("", "#ERROR ReadAny: handle is empty text, expected a handle"),
        (Cells.from_rows([["x"]]), "#ERROR ReadAny: handle is 1x1 array, expected a handle"),
        (
            "curve:000000:000001",
            "#ERROR ReadAny: handle is text 'curve:000000:000001' naming no live object, "
            "expected a handle",
        ),
        (
            "#ERROR MakeCurve: ValueError: it's bad",
            "#ERROR ReadAny: handle is the creator's failure, expected a handle: "
            "#ERROR MakeCurve: ValueError: it's bad",
        ),
    ],
)
def test_a_handle_of_any_kind_keeps_every_other_failure(value: object, text: str) -> None:
    assert bridge.call("ReadAny", [value]) == text


# A creator names what it makes: any kind is a parameter's declaration only, and a bare Handle
# names nothing at all.
def test_a_creator_of_any_kind_and_a_bare_handle_refuse_to_register() -> None:
    def MakeAny() -> Handle[object]:
        raise AssertionError("never called")

    def ReadBare(handle: object) -> float:
        return 1.0

    ReadBare.__annotations__["handle"] = Handle
    with pytest.raises(
        TypeError, match=r"MakeAny declares Handle\[object\] as its result; a creator names what"
    ):
        excel_function(MakeAny)
    with pytest.raises(TypeError, match="ReadBare: handle declares Handle, which the seam cannot"):
        excel_function(ReadBare)


# --- a handle of one of several kinds ------------------------------------------------


# A parameter declared Handle[Curve | Other] takes a curve's handle or another's and receives
# the object either stands for, the same object a single-kind parameter receives.
def test_a_handle_of_either_declared_kind_resolves_to_its_object() -> None:
    curve, other = bridge.call("MakeCurve", [1.5]), bridge.call("MakeOther", [])
    assert bridge.call("ReadEither", [curve]) == "Curve"
    bridge.call("ReadCurve", [curve])
    assert _seen["either"] is _seen["curve"]
    assert bridge.call("ReadEither", [other]) == "Other"


def test_a_handle_of_a_third_kind_is_refused_naming_both_kinds() -> None:
    third = bridge.call("MakeThird", [])
    assert bridge.call("ReadEither", [third]) == (
        f"#ERROR ReadEither: item is third handle {third!r}, expected curve or other handle"
    )


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (3.0, "#ERROR ReadEither: item is number 3.0, expected curve or other handle"),
        (None, "#ERROR ReadEither: item is blank, expected curve or other handle"),
        (MISSING, "#ERROR ReadEither: item is missing, expected curve or other handle"),
        ("", "#ERROR ReadEither: item is empty text, expected curve or other handle"),
        (
            "curve:000000:000001",
            "#ERROR ReadEither: item is text 'curve:000000:000001' naming no live object, "
            "expected curve or other handle",
        ),
        (
            "#ERROR MakeCurve: ValueError: x",
            "#ERROR ReadEither: item is the creator's failure, expected curve or other handle: "
            "#ERROR MakeCurve: ValueError: x",
        ),
    ],
    ids=["a number", "a blank", "missing", "empty text", "a dead handle", "a relayed failure"],
)
def test_a_handle_of_either_kind_keeps_every_other_failure(value: object, text: str) -> None:
    assert bridge.call("ReadEither", [value]) == text


# The kinds of a union are each a class the library defines: one of the seam's own, or object
# beside another kind, refuses to register as an unknown annotation does; and a creator names
# the one kind it makes, so a union as a result refuses to register too.
def test_a_handle_of_several_kinds_registers_around_library_classes_as_a_parameter() -> None:
    def Mixed(x: Handle[Curve | float]) -> float:
        return 1.0

    def AnyToo(x: Handle[Curve | object]) -> float:
        return 1.0

    def MakeEither() -> Handle[Curve | Other]:
        return Curve(1.0)

    with pytest.raises(TypeError, match=r"Mixed: x declares .*, which the seam"):
        register(Mixed, hidden=True)
    with pytest.raises(TypeError, match=r"AnyToo: x declares .*, which the seam"):
        register(AnyToo, hidden=True)
    with pytest.raises(
        TypeError,
        match="MakeEither declares a handle of several kinds as its result; "
        "a creator names the one kind it makes",
    ):
        register(MakeEither, hidden=True)
