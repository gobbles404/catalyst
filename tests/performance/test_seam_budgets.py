"""What one scalar call through the seam costs, itemized: exact and deterministic."""

from collections.abc import Callable

from goosedove.excel import bridge

CallProfile = Callable[[Callable[[], object]], dict[str, int]]


def test_accepted_scalar_call_itemized(call_profile: CallProfile) -> None:
    bridge.call("Add", [1.0, 2.0])
    assert call_profile(lambda: bridge.call("Add", [1.0, 2.0])) == {
        "call": 1,
        "_arguments": 1,
        "_guard": 2,
        "_number": 2,
        "Add": 1,
    }


def test_rejected_scalar_call_stops_at_the_first_failure(call_profile: CallProfile) -> None:
    assert call_profile(lambda: bridge.call("Add", ["x", 2.0])) == {
        "call": 1,
        "_arguments": 1,
        "_guard": 1,
        "_number": 1,
        "describe": 1,
    }
