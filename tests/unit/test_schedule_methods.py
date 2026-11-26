"""The four schedule methods and the five facts the stages share about them, pinned as a table
over the method codes, repeated and interleaved; and the catalog's choices agree with the enum.
The stages' own checks, with their refusals and their order, are pinned where they live."""

import numpy as np

from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.trades.schedule_methods import (
    METHOD_NAMES,
    METHODS,
    ScheduleMethod,
    counts_back_from_expiry,
    permits_physical_settlement,
    requires_booked_reference,
    requires_whole_month,
    supported_on_published,
)

LASTDAY, PENULTIMATE, LAST3DAY, ASIAN = range(4)


def test_the_positions_and_names_stand() -> None:
    assert [m.value for m in METHODS] == ["lastday", "penultimate", "last3day", "asian"]
    assert list(METHOD_NAMES) == ["lastday", "penultimate", "last3day", "asian"]
    assert METHOD_NAMES.dtype == object and not METHOD_NAMES.flags.writeable
    assert METHODS.index(ScheduleMethod.ASIAN) == ASIAN


def test_the_five_facts_for_the_four_methods() -> None:
    codes = np.array(
        [LASTDAY, PENULTIMATE, LAST3DAY, ASIAN, ASIAN, LASTDAY, LAST3DAY], dtype=np.intp
    )
    facts = {
        "supported on published": (supported_on_published, [1, 0, 0, 1, 1, 1, 0]),
        "permits physical settlement": (permits_physical_settlement, [1, 0, 0, 0, 0, 1, 0]),
        "requires the whole month": (requires_whole_month, [1, 1, 1, 0, 0, 1, 1]),
        "counts back from the expiry": (counts_back_from_expiry, [0, 1, 1, 0, 0, 0, 1]),
        "requires the booked reference": (requires_booked_reference, [1, 1, 1, 0, 0, 1, 1]),
    }
    for name, (rule, expected) in facts.items():
        mask = rule(codes)
        assert mask.dtype == np.bool_ and mask.shape == codes.shape, name
        assert mask.tolist() == [bool(e) for e in expected], name


def test_the_catalog_offers_the_enum_s_methods() -> None:
    field = next(f for f in FIXED_FLOAT.fields if f.name == "schedule_method")
    offered = {choice.strip() for choice in field.options.split(",")}
    assert offered == {m.value for m in ScheduleMethod}
