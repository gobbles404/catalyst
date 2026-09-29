"""The terms: what the trades require of the market, one row per component per observation it
reads, with the coefficient that multiplies that observation's price, and one constant per
component. The sheet's exploded view, made once when the trades are encoded and holding no
price, no print and no valuation date. docs/library/valuation/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.valuation.columns import finite, frozen, kept, rows


@dataclass(frozen=True, slots=True)
class Terms:
    """One column per component, three aligned by position per term, one of run starts, all
    read-only, and one number. constant[c] is the part of component c's amount that no price
    moves, minus its quantity times its agreed price. component[t] is the component term t adds
    into, counted from zero; observation[t] the observation whose price it multiplies, counted
    from zero over whatever observations a binding prices; coefficient[t] the amount per unit
    of that price, in the settlement currency, with the signed lots, the lot size, the unit
    factors and the weight multiplied in. The terms are kept grouped by component, each
    component's terms one run in the order they were given: first[c] is the row where
    component c's run starts and first[c + 1] where it ends, first[components] being the count
    of terms, so that a component's terms are one slice and the amounts are one sum per run.
    observations is one more than the highest observation any term reads, so that the kernel
    checks a binding covers the terms in one comparison."""

    constant: NDArray[np.float64]
    component: NDArray[np.intp]
    observation: NDArray[np.intp]
    coefficient: NDArray[np.float64]
    first: NDArray[np.intp]
    observations: int

    @property
    def components(self) -> int:
        return self.constant.size


def terms(
    constant: NDArray[np.float64],
    component: NDArray[np.intp],
    observation: NDArray[np.intp],
    coefficient: NDArray[np.float64],
) -> Terms:
    """The one way to make Terms: six rules, checked once, vectorized, in this order, the first
    failure being the message; then the terms grouped by component in one stable sort, the run
    starts found, the constants copied, every column frozen, and one number found.

    At least one component, since an amount is per component and a record of none prices
    nothing. The three term columns of one length, one row per term. Every constant and every
    coefficient a finite number. Every term's component a row of the constants, counted from
    zero, and every term's observation zero or more; how many observations exist is the
    binding's to say, and the highest read here is kept so that the kernel checks a binding
    covers it in one comparison. A component with no term is allowed, its run being empty and
    its amount its constant, and a term with a coefficient of zero does nothing. The record
    owns its columns, so a caller keeps whatever it passed. Rows count as the sheet counts
    them, the first being row 1.
    """
    if constant.size == 0:
        raise ValueError("constant has 0 rows, expected 1 or more, one per component")
    for name, column in (("component", component), ("observation", observation)):
        if column.size != coefficient.size:
            raise ValueError(
                f"{name} has {column.size} {rows(column.size)}, expected {coefficient.size}, "
                "one per term as coefficient has"
            )
    finite("constant", constant)
    finite("coefficient", coefficient)
    outside = (component < 0) | (component >= constant.size)
    if outside.any():
        t = int(outside.argmax())
        raise ValueError(
            f"component row {t + 1} is {int(component[t])}, "
            f"expected 0 through {constant.size - 1}, the components counted from zero"
        )
    negative = observation < 0
    if negative.any():
        t = int(negative.argmax())
        raise ValueError(f"observation row {t + 1} is {int(observation[t])}, expected 0 or more")
    order = np.argsort(component, kind="stable")
    grouped = component[order]
    first = np.searchsorted(grouped, np.arange(constant.size + 1))
    observations = int(observation.max()) + 1 if observation.size else 0
    return Terms(
        kept(constant),
        frozen(grouped),
        frozen(observation[order]),
        frozen(coefficient[order]),
        frozen(first),
        observations,
    )
