"""The walk over the IDs a filter returned, import-cleared-futures.md: the filter's answer read at
the edge into trade IDs, a JSON list of whole numbers and nothing else; then the IDs sorted
descending and read newest first, an ID the workbook already holds stopping the walk there, every
ID before it to be fetched in that order and every ID after it left unseen, the issue's deliberate
early stop. Array code over the IDs: one sort, one uniqueness check, one membership test, and no
per-ID loop; the fetching that follows is one request at a time by the issue's rule, so the IDs
to fetch come back as plain numbers in the order to ask for them."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import WorkCounter

IDS_RETURNED: Final = "ids_returned"  # the filter's IDs, each looked at once
IDS_TO_FETCH: Final = "ids_to_fetch"  # the IDs the walk hands on, newest first


@dataclass(frozen=True, slots=True)
class Walk:
    """What one walk decided: the IDs to fetch, newest first, each one the filter returned and
    the workbook does not hold; and the ID the walk stopped at, the newest one the workbook
    holds, or None when it reached the end of the list."""

    to_fetch: tuple[int, ...]
    stopped_at: int | None


def ids_from_json(text: str) -> tuple[int, ...]:
    """The filter's answer as trade IDs: a JSON list of whole numbers, in the order the API gave
    them, each read for its type at this edge and nothing coerced: a fraction, text, a flag, a
    nested value or an answer that is no list is refused naming the item and what arrived, as a
    cell is refused at the seam. Which IDs are new is the walk's question, not this reader's."""
    try:
        loaded: object = json.loads(text)
    except json.JSONDecodeError as refusal:
        raise ValueError(f"the filter's answer is not JSON: {refusal}") from None
    if not isinstance(loaded, list):
        raise ValueError(
            f"the filter's answer is {_described(loaded)}, expected a list of trade IDs"
        )
    items = cast(list[object], loaded)
    ids: list[int] = []
    for k, item in enumerate(items):
        # A JSON number without a fraction is an int, and a flag is a bool, which Python counts as
        # an int: the type is read exactly, the one place the API's answer is checked.
        if type(item) is not int:
            raise ValueError(
                f"the filter's item {k + 1} is {_described(item)}, expected a whole number, a "
                "trade ID"
            )
        ids.append(item)
    return tuple(ids)


def _described(value: object) -> str:
    """A JSON value named in a refusal: text in quotes, a flag, nothing, or a number, list or
    object as it is."""
    match value:
        case bool():
            return "a flag"
        case None:
            return "nothing"
        case str():
            return f"text {value!r}"
        case list():
            return "a list"
        case dict():
            return "an object"
        case _:
            return repr(value)


def walk(
    returned: Sequence[int], imported: Sequence[int] | NDArray[np.int64], counter: WorkCounter
) -> Walk:
    """The walk: the returned IDs sorted descending, a repeated ID refused by name since the
    filter names each trade once; then read newest first until the first ID the workbook holds,
    which stops the walk, every ID before it to fetch in that order and every ID after it
    unseen. One sort over the IDs, one look for a repeat, one membership test against the
    workbook's IDs and one search for the first held one; the imported IDs are what the host
    read off the participating tables, whole numbers, in any order and however many. Work: the
    IDs returned and the IDs to fetch."""
    counter.hit(IDS_RETURNED, len(returned))
    ordered = np.sort(np.asarray(returned, dtype=np.int64))[::-1]
    repeated = ordered[1:] == ordered[:-1]
    if repeated.any():
        twice = int(ordered[int(repeated.argmax())])
        raise ValueError(f"the filter returned {twice} more than once, expected each trade ID once")
    held = np.isin(ordered, np.asarray(imported, dtype=np.int64))
    stop = int(held.argmax()) if held.any() else ordered.size
    counter.hit(IDS_TO_FETCH, stop)
    to_fetch: list[int] = ordered[:stop].tolist()  # plain numbers, one request each, in order
    return Walk(tuple(to_fetch), int(ordered[stop]) if stop < ordered.size else None)
