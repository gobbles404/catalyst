"""Handles: the store, the text, and the two rules that publish and resolve, pinned exactly."""

import os
import re
from typing import cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle, Handles, Table, TextRow, excel_function
from goosedove.excel.probes import probe

PID = os.getpid()  # leads every handle this Python publishes


class Curve:
    """A kind of the test's own; any class the library defines could stand here."""

    def __init__(self, level: float) -> None:
        self.level = level


class Other:
    """A second kind, so a handle of one kind can be handed where the other is expected."""


class Steeper(Curve):
    """A subclass: not the declared kind, so a creator returning one fails."""


class Holder:
    """An object holding a curve by its own reference, as a market holds its vector."""

    def __init__(self, curve: Curve) -> None:
        self.curve = curve


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
def HoldCurve(curve: Handle[Curve]) -> Handle[Holder]:
    return Holder(curve)


@probe
def HeldLevel(holder: Handle[Holder]) -> float:
    return holder.curve.level


TEXT = re.compile(r"([0-9]+):(curve|other):([0-9]+)")


def parts(text: object) -> tuple[str, int]:
    """The tag and the count of a handle's text, after the process ID, which is this process's
    own, or a failed assertion naming what came instead. A kind of the test's own carries no
    index's name."""
    assert isinstance(text, str)
    match = TEXT.fullmatch(text)
    assert match, text
    assert int(match.group(1)) == PID, text
    return match.group(2), int(match.group(3))


# --- the way out: publishing ------------------------------------------------


def read(text: str) -> object:
    """The object the seam hands a consumer for this handle."""
    assert bridge.call("ReadCurve", [text]) == bridge.call("ReadCurve", [text])
    return _seen["curve"]


def test_a_creator_publishes_its_tag_and_the_count() -> None:
    tag, count = parts(bridge.call("MakeCurve", [1.0]))
    tag_again, count_again = parts(bridge.call("MakeCurve", [1.0]))
    assert (tag, tag_again) == ("curve", "curve")
    assert count_again == count + 1


def test_the_count_runs_across_kinds_and_never_repeats() -> None:
    _, first = parts(bridge.call("MakeCurve", [1.0]))
    _, second = parts(bridge.call("MakeOther", []))
    _, third = parts(bridge.call("MakeCurve", [1.0]))
    assert (second, third) == (first + 1, first + 2)


# The process ID leads every text: the one this Python runs inside, read once, the same for
# every kind and every publication, so two Excels running at once never publish one text for
# two objects.
def test_the_process_id_leads_every_text_and_is_this_processs_own() -> None:
    curve = cast(str, bridge.call("MakeCurve", [1.0]))
    other = cast(str, bridge.call("MakeOther", []))
    assert curve.startswith(f"{os.getpid()}:curve:")
    assert other.startswith(f"{os.getpid()}:other:")


# The whole text is the key, so a live text under another process's ID, or with none, names
# nothing: what a handle from a second Excel, or one saved before the process ID led the text,
# meets here.
def test_a_text_under_another_process_id_or_none_names_nothing() -> None:
    text = cast(str, bridge.call("MakeCurve", [1.0]))
    tag, count = parts(text)
    assert bridge.call("ReadCurve", [text]) == 1.0
    for foreign in (f"{PID + 1}:{tag}:{count}", f"{tag}:{count}"):
        assert bridge.call("ReadCurve", [foreign]) == (
            f"#ERROR ReadCurve: curve is text {foreign!r} naming no live object, "
            "expected curve handle"
        )


def test_equal_calls_give_distinct_objects_and_distinct_text() -> None:
    a = cast(str, bridge.call("MakeCurve", [1.0]))
    b = cast(str, bridge.call("MakeCurve", [1.0]))
    assert a != b
    assert read(a) is not read(b)


# The count moves only when an object is stored, so an unmoved count is an empty publication.
def test_a_failing_creator_publishes_nothing_and_moves_no_count() -> None:
    _, before = parts(bridge.call("MakeCurve", [1.0]))
    assert bridge.call("FailToMake", []) == "#ERROR FailToMake: ValueError: as asked"
    _, after = parts(bridge.call("MakeCurve", [1.0]))
    assert after == before + 1


# Reading a handle publishes nothing and moves no count.
def test_reading_a_handle_moves_no_count() -> None:
    text = cast(str, bridge.call("MakeCurve", [1.0]))
    _, before = parts(text)
    assert bridge.call("ReadCurve", [text]) == 1.0
    assert bridge.call("ReadCurve", [text]) == 1.0
    _, after = parts(bridge.call("MakeCurve", [1.0]))
    assert after == before + 1


# The whole text is the key: a count edited to one not yet published, or to a live one under
# another tag, names nothing.
def test_an_edited_count_names_nothing() -> None:
    tag, count = parts(bridge.call("MakeCurve", [1.0]))
    _, live = parts(bridge.call("MakeOther", []))
    for edited in (f"{PID}:{tag}:{count + 9_000_000}", f"{PID}:{tag}:{live}"):
        assert bridge.call("ReadCurve", [edited]) == (
            f"#ERROR ReadCurve: curve is text {edited!r} naming no live object, "
            "expected curve handle"
        )


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ([1.0], "#ERROR MakeWhatever: returned a Python list, expected curve"),
        (None, "#ERROR MakeWhatever: returned nothing, expected curve"),
        (1.0, "#ERROR MakeWhatever: returned number 1.0, expected curve"),
        (
            "curve:9999999",
            "#ERROR MakeWhatever: returned text 'curve:9999999', expected curve",
        ),
        (Steeper(1.0), "#ERROR MakeWhatever: returned a Python Steeper, expected curve"),
    ],
)
def test_a_creator_returning_the_wrong_thing_fails_and_publishes_nothing(
    value: object, text: str
) -> None:
    _, before = parts(bridge.call("MakeCurve", [1.0]))
    _returns["value"] = value
    assert bridge.call("MakeWhatever", []) == text
    _, after = parts(bridge.call("MakeCurve", [1.0]))
    assert after == before + 1


# --- the observed path: the creator's flag, the combined result, release ----------------


# The seam tells the host which functions create a handle, read off the declared result alone,
# so the host observes those calls and no other.
def test_the_specs_say_which_functions_create_a_handle() -> None:
    publishes = {name: flag for name, _, _, _, flag in bridge.function_specs()}
    assert publishes["MakeCurve"] and publishes["MakeOther"] and publishes["HoldCurve"]
    assert publishes["_CreateValuationDate"] and publishes["_CreatePriceVector"]
    assert not publishes["ReadCurve"] and not publishes["Add"] and not publishes["util_ReadHandle"]


# The observed path's result is the cell's value and whether this call published, told by the
# count having moved and never by the text: a creator's success says yes, its failure says no,
# and a consumer's value says no.
def test_a_creators_publisher_says_whether_it_published() -> None:
    text, owned = bridge.publish("MakeCurve", [2.5])
    assert owned and isinstance(text, str) and text.startswith(f"{PID}:curve:")
    assert bridge.publish("FailToMake", []) == ("#ERROR FailToMake: ValueError: as asked", False)
    _returns["value"] = 1.0
    assert bridge.publish("MakeWhatever", []) == (
        "#ERROR MakeWhatever: returned number 1.0, expected curve",
        False,
    )
    assert bridge.publish("ReadCurve", [text]) == (2.5, False)


# Release takes one entry out of the store, by its whole text, and nothing else: the text then
# names nothing, releasing it again or releasing a text never published does nothing, the count
# does not move, and a curve a live holder keeps by its own reference lives on through it.
def test_release_takes_one_entry_and_leaves_what_others_hold() -> None:
    curve = cast(str, bridge.call("MakeCurve", [2.5]))
    holder = cast(str, bridge.call("HoldCurve", [curve]))
    _, before = parts(bridge.call("MakeCurve", [1.0]))
    live, _ = bridge.live_handles()
    assert bridge.release(curve) is True
    assert bridge.live_handles()[0] == live - 1
    assert bridge.call("ReadCurve", [curve]) == (
        f"#ERROR ReadCurve: curve is text {curve!r} naming no live object, expected curve handle"
    )
    assert bridge.release(curve) is False
    assert bridge.release("curve:9999999") is False
    assert bridge.call("HeldLevel", [holder]) == 2.5
    _, after = parts(bridge.call("MakeCurve", [1.0]))
    assert after == before + 1
    assert bridge.release(holder) is True


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
            "curve:9999999",
            "#ERROR ReadCurve: curve is text 'curve:9999999' naming no live object, "
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


# --- a handle that may be left out, with nothing in its place --------------------


# The form of an argument that may be left out takes a handle: None is the argument's absence,
# not a default the store would have to hold, so the handle is declared as if required and
# resolves as one when given.
@probe
def MaybeCurve(curve: Handle[Curve] | None = None) -> str:
    return "nothing" if curve is None else repr(curve.level)


@probe
def MaybeAny(handle: Handle[object] | None = None) -> str:
    return "nothing" if handle is None else type(handle).__name__


def test_a_handle_left_out_hands_the_function_nothing() -> None:
    assert bridge.call("MaybeCurve", [MISSING]) == "nothing"
    assert bridge.call("MaybeAny", [MISSING]) == "nothing"


def test_a_handle_given_resolves_as_a_required_one_does() -> None:
    curve = cast(str, bridge.call("MakeCurve", [2.5]))
    assert bridge.call("MaybeCurve", [curve]) == "2.5"
    assert bridge.call("MaybeAny", [curve]) == "Curve"
    other = cast(str, bridge.call("MakeOther", []))
    assert bridge.call("MaybeAny", [other]) == "Other"


# Blank and left out are different facts, and a handle's faults keep decision 35's order.
def test_a_handle_that_may_be_left_out_still_fails_in_the_handles_words() -> None:
    assert (
        bridge.call("MaybeCurve", [None])
        == "#ERROR MaybeCurve: curve is blank, expected curve handle"
    )
    assert (
        bridge.call("MaybeCurve", [3.0])
        == "#ERROR MaybeCurve: curve is number 3.0, expected curve handle"
    )
    assert bridge.call("MaybeCurve", ["curve:9999999"]) == (
        "#ERROR MaybeCurve: curve is text 'curve:9999999' naming no live object, "
        "expected curve handle"
    )
    other = cast(str, bridge.call("MakeOther", []))
    assert bridge.call("MaybeCurve", [other]) == (
        f"#ERROR MaybeCurve: curve is other handle {other!r}, expected curve handle"
    )
    assert bridge.call("MaybeCurve", ["#ERROR FailToMake: ValueError: no"]) == (
        "#ERROR MaybeCurve: curve is the creator's failure, expected curve handle: "
        "#ERROR FailToMake: ValueError: no"
    )
    assert bridge.call("MaybeAny", [None]) == "#ERROR MaybeAny: handle is blank, expected a handle"


# The form takes None as its default and nothing else, for a handle as for any type; a real
# default on a handle is still refused, above.
def test_the_form_around_a_handle_takes_none_and_nothing_else() -> None:
    def Undefaulted(curve: Handle[Curve] | None) -> float:
        return 0.0

    def Defaulted(curve: Handle[Curve] | None = A_CURVE) -> float:
        return 0.0

    with pytest.raises(
        TypeError, match=r"Undefaulted: curve declares .* and no default, expected None"
    ):
        excel_function(Undefaulted)
    with pytest.raises(
        TypeError, match=r"Defaulted: curve declares .* and defaults to .*, expected None"
    ):
        excel_function(Defaulted)


# Excel sees the name in brackets and nothing after the help, as for any argument left out.
def test_a_handle_that_may_be_left_out_is_shown_in_brackets() -> None:
    specs = {name: arguments for name, _, arguments, _, _ in bridge.function_specs()}
    assert specs["MaybeCurve"] == [("[curve]", "")]
    assert specs["ReadCurve"] == [("curve", "")]


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
            "curve:9999999",
            "#ERROR ReadAny: handle is text 'curve:9999999' naming no live object, "
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


# --- a vector of handles, decision 44, and a handle of one of two kinds, decision 45 -------


class Third:
    """A third kind, so a handle of neither declared kind can be handed where one of two is
    expected."""


@probe
def MakeThird() -> Handle[Third]:
    return Third()


@probe
def CollectCurves(curves: Handles[Curve]) -> str:
    """Probe: the levels of a cell, a row or a column of curve handles, in sheet order."""
    return ", ".join(repr(curve.level) for curve in curves)


@probe
def ReadEither(handle: Handle[Curve] | Handle[Other]) -> str:
    """Probe: the class of a curve or an other, whichever the handle stands for."""
    return type(handle).__name__


def test_a_vector_of_handles_hands_the_objects_in_sheet_order_every_cell_counted() -> None:
    one = cast(str, bridge.call("MakeCurve", [1.0]))
    two = cast(str, bridge.call("MakeCurve", [2.0]))
    assert bridge.call("CollectCurves", [one]) == "1.0"
    assert bridge.call("CollectCurves", [Cells.from_rows([[one]])]) == "1.0"
    assert bridge.call("CollectCurves", [Cells.from_rows([[one, two]])]) == "1.0, 2.0"
    assert bridge.call("CollectCurves", [Cells.from_rows([[two], [one], [two]])]) == "2.0, 1.0, 2.0"


def test_a_vector_of_handles_refuses_the_shape_first_and_then_each_cell_at_its_place() -> None:
    one = cast(str, bridge.call("MakeCurve", [1.0]))
    other = cast(str, bridge.call("MakeOther", []))
    failed = cast(str, bridge.call("FailToMake", []))
    assert bridge.call("CollectCurves", [Cells.from_rows([[one, one], [one, None]])]) == (
        "#ERROR CollectCurves: curves is 2x2 array, expected one cell, one row or one column of "
        "curve handles"
    )
    assert bridge.call("CollectCurves", [Cells.from_rows([[one], [None]])]) == (
        "#ERROR CollectCurves: curves cell (2, 1) is blank, expected curve handle"
    )
    assert bridge.call("CollectCurves", [Cells.from_rows([[one, 3.0]])]) == (
        "#ERROR CollectCurves: curves cell (1, 2) is number 3.0, expected curve handle"
    )
    assert bridge.call("CollectCurves", [Cells.from_rows([[one], [True]])]) == (
        "#ERROR CollectCurves: curves cell (2, 1) is boolean TRUE, expected curve handle"
    )
    assert bridge.call("CollectCurves", [Cells.from_rows([[one], [""]])]) == (
        "#ERROR CollectCurves: curves cell (2, 1) is empty text, expected curve handle"
    )
    assert bridge.call("CollectCurves", [Cells.from_rows([[one], ["x"]])]) == (
        "#ERROR CollectCurves: curves cell (2, 1) is text 'x' naming no live object, expected "
        "curve handle"
    )
    assert bridge.call("CollectCurves", [Cells.from_rows([[one, other]])]) == (
        f"#ERROR CollectCurves: curves cell (1, 2) is other handle {other!r}, expected curve handle"
    )
    assert bridge.call("CollectCurves", [Cells.from_rows([[failed], [one]])]) == (
        "#ERROR CollectCurves: curves cell (1, 1) is the creator's failure, expected curve handle: "
        f"{failed}"
    )
    assert bridge.call("CollectCurves", [MISSING]) == (
        "#ERROR CollectCurves: curves is missing, expected curve handles in a cell, a row or a "
        "column"
    )
    assert bridge.call("CollectCurves", [None]) == (
        "#ERROR CollectCurves: curves is blank, expected curve handles in a cell, a row or a column"
    )
    assert bridge.call("CollectCurves", [2.0]) == (
        "#ERROR CollectCurves: curves is number 2.0, expected curve handles in a cell, a row or a "
        "column"
    )


def test_a_vector_of_handles_names_one_kind_and_takes_no_default() -> None:
    def CollectAny(handles: Handles[object]) -> str:
        return ""

    with pytest.raises(TypeError, match=r"CollectAny: handles declares .*, which the seam cannot"):
        probe(CollectAny)

    def CollectTables(handles: Handles[Table]) -> str:
        return ""

    with pytest.raises(
        TypeError, match=r"CollectTables: handles declares .*, which the seam cannot"
    ):
        probe(CollectTables)

    def CollectWithDefault(handles: Handles[Curve] = ()) -> str:
        return ""

    with pytest.raises(
        TypeError, match=r"CollectWithDefault: handles declares a handle, which takes"
    ):
        probe(CollectWithDefault)


def test_a_handle_of_one_of_two_kinds_resolves_either_and_names_both_when_refusing() -> None:
    curve = cast(str, bridge.call("MakeCurve", [1.0]))
    other = cast(str, bridge.call("MakeOther", []))
    third = cast(str, bridge.call("MakeThird", []))
    assert bridge.call("ReadEither", [curve]) == "Curve"
    assert bridge.call("ReadEither", [other]) == "Other"
    assert bridge.call("ReadEither", [third]) == (
        f"#ERROR ReadEither: handle is third handle {third!r}, expected curve or other handle"
    )
    assert bridge.call("ReadEither", ["x"]) == (
        "#ERROR ReadEither: handle is text 'x' naming no live object, expected curve or other "
        "handle"
    )
    assert bridge.call("ReadEither", [None]) == (
        "#ERROR ReadEither: handle is blank, expected curve or other handle"
    )
    assert bridge.call("ReadEither", [2.0]) == (
        "#ERROR ReadEither: handle is number 2.0, expected curve or other handle"
    )


def test_a_handle_of_one_of_two_kinds_names_both_kinds_and_takes_no_default() -> None:
    def ReadAnyOfTwo(handle: Handle[Curve] | Handle[object]) -> str:
        return ""

    with pytest.raises(TypeError, match=r"ReadAnyOfTwo: handle declares .*, which the seam cannot"):
        probe(ReadAnyOfTwo)

    def ReadHandleOrText(handle: Handle[Curve] | str) -> str:
        return ""

    with pytest.raises(
        TypeError, match=r"ReadHandleOrText: handle declares .*, which the seam cannot"
    ):
        probe(ReadHandleOrText)

    def ReadEitherWithDefault(handle: Handle[Curve] | Handle[Other] = A_CURVE) -> str:
        return ""

    with pytest.raises(
        TypeError, match=r"ReadEitherWithDefault: handle declares a handle, which takes"
    ):
        probe(ReadEitherWithDefault)
