"""A collection of named discount curves, multiple-discount-curves.md: the curves a batch of
trades will select among by name, gathered as they are and held by reference, nothing of their
factors constructed or combined; each name once, since a key must select one curve. Which curves
must start on the valuation day and cover which payments is the evaluation's to decide, for the
curves a batch selects, so a collection checks no date and holds curves of any spans, and a
curve nobody selects costs nothing. docs/library/globals/collect-discount-curves.md is the
page."""

from dataclasses import dataclass

from catalyst.globals.discount_curve import DiscountCurve
from catalyst.instrumentation.work_counts import WorkCounter

CURVES_COLLECTED = "curves_collected"  # one per curve given, its name read once for the rule


@dataclass(frozen=True, slots=True)
class DiscountCurveSet:
    """The curves in the order given, by reference, their names distinct."""

    curves: tuple[DiscountCurve, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple([curve.name for curve in self.curves])


def collect_discount_curves(
    curves: tuple[DiscountCurve, ...], counter: WorkCounter
) -> DiscountCurveSet:
    """The one way to make a DiscountCurveSet: the one rule, each name once, the first repeat
    refused with the cell it repeats, the cells counted from one in the order the sheet gave
    them, and the same curve given twice a repeat too. Nothing else is checked: no date is read,
    no factor copied, and the curves are kept as they are, so a collection is remade when one
    of its curves is and a held one keeps its old members. Work: one curve per curve given,
    reported to the counter."""
    first_cell: dict[str, int] = {}
    for i, curve in enumerate(curves):
        first = first_cell.setdefault(curve.name, i)
        if first != i:
            raise ValueError(
                f"curve_handles cell {first + 1} and cell {i + 1} are both named {curve.name!r}, "
                "expected each name once"
            )
    counter.hit(CURVES_COLLECTED, len(curves))
    return DiscountCurveSet(curves)
