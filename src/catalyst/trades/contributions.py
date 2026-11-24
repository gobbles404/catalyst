"""The risk a result keeps per curve, named-curves-slice-2.md: a contribution is one curve's share
of a result's DV01 or cross-gamma, the curve object that made it, the saved vectors on the saved
axes by reference, and the facts refusing a month or a year view standing before the valuation
day's period. Today's single-curve evaluation makes one of each, a cleared batch none and a batch
of cashflows one rate contribution per curve its keys name, since cashflow-curve-keys.md; a
result on several curves keeps several, and the collection sums contributions, never results,
onto its groups, so a rate group is the exact curve object and the currency unit over every
contribution on them wherever it came from.
docs/library/trades/report-risk.md owns the labels and docs/library/trades/aggregate-results.md
the collection."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from catalyst.globals.discount_curve import DiscountCurve
from catalyst.trades.display_axes import EarlyRisk

# The word a heading gives a batch on no curve, `cleared USD dv01 [USD per basis point]` and
# `HNG cleared cross_gamma [LOT per basis point]`; never a curve's word.
CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class RateContribution:
    """One curve's share of a result's DV01: the curve object; the currency and, since
    currency-and-currency-unit.md, currency_unit, the unit of it the DV01 is in, a trade's its
    index's settlement unit and a cashflow's its currency's reference unit; dv01, the total in
    that unit per basis point, negative for an amount receivable; the DV01 by payment day,
    month and year, each beside the saved axis it stands on, the encoding's payment axes for a
    batch of trades and the batch's distinct days, months and years for cashflows, by reference
    and never copied; and the facts refusing a month or a year view of it standing before the
    valuation day's period."""

    curve: DiscountCurve
    currency: str
    currency_unit: str
    dv01: float
    days: NDArray[np.datetime64]
    dv01_by_day: NDArray[np.float64]
    months: NDArray[np.datetime64]
    dv01_by_month: NDArray[np.float64]
    years: NDArray[np.datetime64]
    dv01_by_year: NDArray[np.float64]
    early_dv01: EarlyRisk


@dataclass(frozen=True, slots=True)
class CrossContribution:
    """One curve's share of a result's cross-gamma, single-curve-cross-gamma.md: the curve
    object; the cross-gamma by reference on the batch's references, by observation day, by
    contract month and by contract year, each beside the saved axis it stands on, the delta's
    axes by reference; the total, in the reporting lot per basis point; and the facts refusing a
    month or a year view of it standing before the valuation day's period."""

    curve: DiscountCurve
    references: NDArray[np.intp]
    cross_gamma: NDArray[np.float64]
    days: NDArray[np.datetime64]
    cross_gamma_by_day: NDArray[np.float64]
    months: NDArray[np.datetime64]
    cross_gamma_by_month: NDArray[np.float64]
    years: NDArray[np.datetime64]
    cross_gamma_by_year: NDArray[np.float64]
    cross_gamma_total: float
    early_cross_gamma: EarlyRisk


def curve_words(curves: Sequence[DiscountCurve]) -> dict[int, str]:
    """Each distinct curve object's word in a heading, keyed by the object's identity: its name as
    typed, or, where two or more distinct objects share a name, the name qualified by the object's
    place among that name's objects in the order given, `SOFR (curve_1)` and `SOFR (curve_2)`, both
    of them and never the first left bare. Every word is distinct: a qualifier never repeats a
    word the report already uses, a name one of the curves carries, `cleared` or an earlier
    qualifier, the place counting on past it, so a curve named `SOFR (curve_1)` keeps its name
    beside `SOFR (curve_2)` and `SOFR (curve_3)`; and a curve named `cleared` is qualified as a
    shared name is, `cleared (curve_1)`, the bare word kept for a batch on no curve. Display, not
    identity: nothing groups by the word. A single result's one curve is its bare name; a
    collection's words follow the first appearance of each object among its sources'
    contributions."""
    first: dict[int, DiscountCurve] = {}
    for curve in curves:
        first.setdefault(id(curve), curve)
    by_name: dict[str, list[int]] = {}
    for key, curve in first.items():
        by_name.setdefault(curve.name, []).append(key)
    words: dict[int, str] = {}
    qualifying = False
    for name, keys in by_name.items():
        if len(keys) == 1 and name != CLEARED:
            words[keys[0]] = name
        else:
            qualifying = True
    if not qualifying:
        return words  # every name its own and none the cleared word: nothing more is made
    taken = {CLEARED, *words.values()}
    for name, keys in by_name.items():
        if len(keys) == 1 and name != CLEARED:
            continue
        place = 0
        for key in keys:
            place += 1
            while (word := f"{name} (curve_{place})") in taken:
                place += 1
            taken.add(word)
            words[key] = word
    return words
