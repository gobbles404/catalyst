"""Properties of work-count snapshots."""

from hypothesis import given
from hypothesis import strategies as st

from catalyst.instrumentation.work_counts import KERNEL, WorkCounter


@given(before=st.integers(min_value=0), after=st.integers(min_value=0))
def test_frozen_counts_remain_unchanged(before: int, after: int) -> None:
    counter = WorkCounter()
    counter.hit(KERNEL, before)
    snapshot = counter.freeze()

    counter.hit(KERNEL, after)

    assert snapshot[KERNEL] == before
    assert counter.freeze()[KERNEL] == before + after
