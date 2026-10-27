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


def test_the_filters_answer_is_read_as_whole_numbers_under_tradeids_and_nothing_else() -> None:
    assert ids_from_json('{"tradeIds": [105, 103, 104]}') == (105, 103, 104)
    assert ids_from_json('{"tradeIds": []}') == ()
    # Any other key is passed over, and the whitespace JSON allows.
    assert ids_from_json(
        ' {"count": 1, "tradeIds": [ 7 ], "filter": "Cleared_Futures_Today"} '
    ) == (7,)
    # The sheet's own bound on an ID, 15 digits, zero and signed values within it; a repeat is
    # read as it came, the walk's to refuse.
    assert ids_from_json('{"tradeIds": [999999999999999, 0, -999999999999999]}') == (
        999999999999999,
        0,
        -999999999999999,
    )
    assert ids_from_json('{"tradeIds": [105, 104, 104]}') == (105, 104, 104)
    item = "expected a whole number, a trade ID"
    bound = "expected a whole number of at most 15 digits"
    no_key = "expected an object holding tradeIds"
    for text, message in (
        ('{"tradeIds": [105.0]}', f"the filter's item 1 is 105.0, {item}"),
        ('{"tradeIds": [105, "104"]}', f"the filter's item 2 is text '104', {item}"),
        ('{"tradeIds": [true]}', f"the filter's item 1 is a flag, {item}"),
        ('{"tradeIds": [null]}', f"the filter's item 1 is nothing, {item}"),
        ('{"tradeIds": [[105]]}', f"the filter's item 1 is a list, {item}"),
        ('{"tradeIds": [{"id": 105}]}', f"the filter's item 1 is an object, {item}"),
        ('{"tradeIds": [1000000000000000]}', f"the filter's item 1 is 1000000000000000, {bound}"),
        (
            '{"tradeIds": [5, -1000000000000000]}',
            f"the filter's item 2 is -1000000000000000, {bound}",
        ),
        (
            '{"tradeIds": [99999999999999999999]}',
            f"the filter's item 1 is 99999999999999999999, {bound}",
        ),
        ('{"tradeIds": null}', "the filter's tradeIds is nothing, expected a list of trade IDs"),
        ('{"tradeIds": 105}', "the filter's tradeIds is 105, expected a list of trade IDs"),
        (
            '{"tradeIds": {"105": 1}}',
            "the filter's tradeIds is an object, expected a list of trade IDs",
        ),
        (
            '{"tradeIds": "105"}',
            "the filter's tradeIds is text '105', expected a list of trade IDs",
        ),
        ('{"ids": [105]}', f"the filter's answer has no tradeIds, {no_key}"),
        ('{"tradeids": [105]}', f"the filter's answer has no tradeIds, {no_key}"),
        ('{"trade_ids": [105]}', f"the filter's answer has no tradeIds, {no_key}"),
        ("{}", f"the filter's answer has no tradeIds, {no_key}"),
        ("[105, 103, 104]", f"the filter's answer is a list, {no_key}"),
        ("105", f"the filter's answer is 105, {no_key}"),
        ('"105"', f"the filter's answer is text '105', {no_key}"),
        ("null", f"the filter's answer is nothing, {no_key}"),
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
