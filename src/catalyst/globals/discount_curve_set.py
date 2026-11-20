"""A collection of named discount curves, multiple-discount-curves.md: the curves a batch of
trades will select among by name, gathered as they are and held by reference, nothing of their
factors constructed or combined; each name once, since a key must select one curve. Which curves
must start on the valuation day and cover which payments is the evaluation's to decide, for the
curves a batch selects, so a collection checks no date and holds curves of any spans, and a
curve nobody selects costs nothing. And, since shared-curve-binding.md, the one step that binds
a key to its curve, the exact name found or refused in one sentence, which the trades' evaluation
and the quotes share. docs/library/globals/collect-discount-curves.md is the page."""

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


def curve_named(curve_set: DiscountCurveSet, key: str) -> DiscountCurve | None:
    """The collection's curve of that exact name, or none, shared-curve-binding.md: the one rule
    a key is bound by, whoever binds it, a batch of trades for each of its keys or a quote for
    its template's one. The name is matched as it is, case and all; there is no fallback to the
    first curve, a collection of one included; and no curve is read for anything but its name.
    A caller that finds none raises no_curve_named, with who booked the key where it has
    someone to name."""
    for curve in curve_set.curves:
        if curve.name == key:
            return curve
    return None


def no_curve_named(curve_set: DiscountCurveSet, key: str, booked_by: str = "") -> ValueError:
    """The one refusal of a key that names no curve of the collection, for whoever looked to
    raise: the key, who booked it where the caller says, a trade by its row, and the names the
    collection holds, each quoted as a name is in every message, in the collection's order.
    Made on the failing path alone, so that naming who booked a key costs nothing where the
    key is found."""
    whose = f" of {booked_by}" if booked_by else ""
    return ValueError(
        f"discount_curve_key {key!r}{whose} names no curve of the collection, which holds "
        f"{_quoted(curve_set.names)}; expected a curve of that name"
    )


def _quoted(names: tuple[str, ...]) -> str:
    """Names in a message: `'SOFR'`, `'SOFR' and 'FFOIS'`, `'SOFR', 'FFOIS' and 'SONIA'`."""
    quoted = [repr(name) for name in names]
    if len(quoted) == 1:
        return quoted[0]
    return f"{', '.join(quoted[:-1])} and {quoted[-1]}"
