"""The walk over the IDs a filter returned, import-cleared-futures.md: the issue's table by hand,
the edges, the reader of the filter's answer and its refusals, the counts, and the property every
walk keeps. docs/engineering-tickets/import-cleared-futures.md is the page."""

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from goosedove.importer.walk import Walk, ids_from_json, walk
from goosedove.instrumentation.work_counts import WorkCounter


def walked(returned: list[int], imported: list[int]) -> Walk:
    return walk(returned, imported, WorkCounter())


def refused(message: str, returned: list[int], imported: list[int]) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        walked(returned, imported)


def test_the_issues_table_by_hand() -> None:
    # 105, 104 and 103 returned in no particular order with 104 already in the workbook: 105 is
    # fetched, 104 stops the walk, 103 is not looked at.
    assert walked([103, 105, 104], [104, 90]) == Walk((105,), 104)
    # None held: every ID fetched, newest first.
    assert walked([103, 105, 104], []) == Walk((105, 104, 103), None)
    assert walked([103, 105, 104], [1, 2]) == Walk((105, 104, 103), None)
    # The newest held: nothing fetched, the walk stopped at once.
    assert walked([103, 105, 104], [105]) == Walk((), 105)
    # An empty answer: nothing to fetch and no stop.
    assert walked([], [104]) == Walk((), None)
    # A held ID older than every returned one changes nothing.
    assert walked([107, 106], [100]) == Walk((107, 106), None)
    # The workbook's IDs in any order and with repeats among them, as many tables give them.
    assert walked([108, 107, 106, 105], [105, 107, 107, 3]) == Walk((108,), 107)


def test_a_repeated_id_is_refused_by_name() -> None:
    refused(
        "the filter returned 104 more than once, expected each trade ID once", [105, 104, 104], []
    )
    refused(
        "the filter returned 105 more than once, expected each trade ID once", [105, 105], [105]
    )


def test_the_walk_reports_its_work() -> None:
    counter = WorkCounter()
    walk([103, 105, 104, 102], [103], counter)
    assert counter.freeze().as_dict() == {"ids_returned": 4, "ids_to_fetch": 2}
    counter = WorkCounter()
    walk([], [], counter)
    assert counter.freeze().as_dict() == {"ids_returned": 0, "ids_to_fetch": 0}


def test_the_filters_answer_is_read_as_whole_numbers_and_nothing_else() -> None:
    assert ids_from_json("[105, 103, 104]") == (105, 103, 104)
    assert ids_from_json("[]") == ()
    assert ids_from_json(" [ 7 ] ") == (7,)
    for text, message in (
        ("[105.0]", "the filter's item 1 is 105.0, expected a whole number, a trade ID"),
        ('[105, "104"]', "the filter's item 2 is text '104', expected a whole number, a trade ID"),
        ("[true]", "the filter's item 1 is a flag, expected a whole number, a trade ID"),
        ("[null]", "the filter's item 1 is nothing, expected a whole number, a trade ID"),
        ("[[105]]", "the filter's item 1 is a list, expected a whole number, a trade ID"),
        ('[{"id": 105}]', "the filter's item 1 is an object, expected a whole number, a trade ID"),
        ('{"ids": [105]}', "the filter's answer is an object, expected a list of trade IDs"),
        ("105", "the filter's answer is 105, expected a list of trade IDs"),
        ('"105"', "the filter's answer is text '105', expected a list of trade IDs"),
    ):
        with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
            ids_from_json(text)
    with pytest.raises(ValueError, match=r"^the filter's answer is not JSON: "):
        ids_from_json("not json")


@settings(max_examples=100, deadline=None, derandomize=True)
@given(
    returned=st.lists(st.integers(min_value=0, max_value=10**15), unique=True),
    imported=st.lists(st.integers(min_value=0, max_value=10**15)),
)
def test_every_walk_fetches_the_descending_prefix_before_the_first_held_id(
    returned: list[int], imported: list[int]
) -> None:
    result = walked(returned, imported)
    ordered = sorted(returned, reverse=True)
    held = set(imported)
    first_held = next((trade_id for trade_id in ordered if trade_id in held), None)
    expected = ordered if first_held is None else ordered[: ordered.index(first_held)]
    assert result.to_fetch == tuple(expected)
    assert result.stopped_at == first_held
    assert not held.intersection(result.to_fetch)
    assert list(result.to_fetch) == sorted(result.to_fetch, reverse=True)
