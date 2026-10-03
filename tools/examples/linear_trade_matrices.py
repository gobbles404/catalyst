"""A small dense-array specimen, not a production trade or valuation API.

Run with ``uv run python -m tools.examples.linear_trade_matrices``. All quantities
are barrels and all prices USD/barrel. The Asian uses four selected illustrative
days, NOT a real December averaging calendar. Its second fixing is also used by
the illustrative penultimate swap; that date is NOT an exchange penultimate date.
Results mix futures lifetime trading P&L and projected swap payment amounts.
They are not current unpaid cash or discounted values. The existing Market and
Excel APIs are deliberately not used or changed by this specimen.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import WorkCounter


class ObservationKind(StrEnum):
    CURRENT_MARK = "current_mark"
    SETTLEMENT = "settlement"


@dataclass(frozen=True, slots=True)
class MarketPoint:
    """A current input: a contract mark or a dated projection-curve point.

    Index is an explicit specimen identifier, not the production Index.name label.
    """

    index: str
    contract: str
    projection_date: date | None = None


@dataclass(frozen=True, slots=True)
class Observation:
    """Identity is the required price, not the product consuming it or its value."""

    index: str
    contract: str
    kind: ObservationKind
    day: date | None


@dataclass(frozen=True, slots=True, eq=False)
class ObservationSchedule:
    """Shared immutable contractual observations and weights, with no fixing state."""

    name: str
    observations: tuple[Observation, ...]
    weights: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class TradeTerms:
    """One deal component. Repeated rows and repeated IDs remain separate occurrences."""

    trade_id: str
    product: str
    signed_quantity: float
    agreed_price: float
    schedule: ObservationSchedule
    payment_date: date | None


@dataclass(frozen=True, slots=True, eq=False)
class LinearTradePlan:
    trades: tuple[TradeTerms, ...]
    observations: tuple[Observation, ...]
    A: NDArray[np.float64]
    c: NDArray[np.float64]


@dataclass(frozen=True, slots=True, eq=False)
class MarketSnapshot:
    """Explicitly prepared inputs: k on fixed rows, B @ p on the remaining rows.

    Zero is a valid fixing. The mask distinguishes it from a missing observation.
    B is a stated projection assumption, not inferred from equal price values.
    """

    point_keys: tuple[MarketPoint, ...]
    p: NDArray[np.float64]
    observations: tuple[Observation, ...]
    B: NDArray[np.float64]
    k: NDArray[np.float64]
    is_fixed: NDArray[np.bool_]


@dataclass(frozen=True, slots=True, eq=False)
class CompressedPlan:
    """Derived for one fixing/projection state; only current prices may change."""

    source: LinearTradePlan
    point_keys: tuple[MarketPoint, ...]
    W: NDArray[np.float64]
    b: NDArray[np.float64]


def _readonly[T: np.generic](values: NDArray[T]) -> NDArray[T]:
    values.setflags(write=False)
    return values


def prepare(
    trades: tuple[TradeTerms, ...],
    observations: tuple[Observation, ...],
    counter: WorkCounter,
) -> LinearTradePlan:
    """Bind each shared schedule once; assemble trade weights with array operations."""
    positions = {observation: i for i, observation in enumerate(observations)}
    if len(positions) != len(observations):
        raise ValueError("observation axis repeats an identity")
    quantities = np.fromiter((t.signed_quantity for t in trades), dtype=float, count=len(trades))
    strikes = np.fromiter((t.agreed_price for t in trades), dtype=float, count=len(trades))
    if not np.isfinite(quantities).all() or not np.isfinite(strikes).all():
        raise ValueError("trade quantities and agreed prices must be finite")
    A = np.zeros((len(trades), len(observations)))
    groups: dict[ObservationSchedule, list[int]] = {}
    for row, trade in enumerate(trades):  # structural grouping, not scalar numerical work
        groups.setdefault(trade.schedule, []).append(row)
    for schedule, rows in groups.items():
        if len(schedule.observations) != len(schedule.weights):
            raise ValueError(f"schedule {schedule.name!r} needs one weight per observation")
        if len(set(schedule.observations)) != len(schedule.observations):
            raise ValueError(f"schedule {schedule.name!r} repeats an observation")
        try:
            columns = np.fromiter(
                (positions[o] for o in schedule.observations),
                dtype=np.intp,
                count=len(schedule.observations),
            )
        except KeyError as error:
            raise ValueError(f"schedule {schedule.name!r} names an unknown observation") from error
        weights = np.asarray(schedule.weights, dtype=float)
        if not np.isfinite(weights).all():
            raise ValueError("observation weights must be finite")
        A[np.ix_(rows, columns)] = quantities[rows, None] * weights[None, :]
        counter.hit("schedule_build", 1)
        counter.hit("observation_binding", len(columns))
        counter.hit("weighted_observation", len(rows) * len(columns))
    counter.hit("plan_build")
    counter.hit("trade_row", len(trades))
    counter.hit("dense_exposure_cell", A.size)
    return LinearTradePlan(trades, observations, _readonly(A), _readonly(-quantities * strikes))


def market_snapshot(
    point_keys: tuple[MarketPoint, ...],
    prices: NDArray[np.float64],
    observations: tuple[Observation, ...],
    projection: NDArray[np.float64],
    known_fixings: NDArray[np.float64],
    is_fixed: NDArray[np.bool_],
) -> MarketSnapshot:
    """Own a coherent snapshot; no observation is silently filled or left unbound."""
    n, m = len(observations), len(point_keys)
    if len(set(point_keys)) != m or len(set(observations)) != n:
        raise ValueError("market axes repeat an identity")
    if prices.shape != (m,) or projection.shape != (n, m):
        raise ValueError("price/projection shape does not match the market axes")
    if known_fixings.shape != (n,) or is_fixed.shape != (n,):
        raise ValueError("fixing columns do not match the observation axis")
    if not all(np.isfinite(values).all() for values in (prices, projection, known_fixings)):
        raise ValueError("market inputs must be finite")
    if np.any(projection[is_fixed] != 0.0) or np.any(known_fixings[~is_fixed] != 0.0):
        raise ValueError("fixed rows need only k; unfixed rows need only B")
    if np.any(np.all(projection[~is_fixed] == 0.0, axis=1)):
        raise ValueError("an unfixed observation has no projection")
    _check_marks(point_keys, observations, projection, is_fixed)
    return MarketSnapshot(
        point_keys,
        _readonly(prices.copy()),
        observations,
        _readonly(projection.copy()),
        _readonly(known_fixings.copy()),
        _readonly(is_fixed.copy()),
    )


def _check_marks(
    points: tuple[MarketPoint, ...],
    observations: tuple[Observation, ...],
    B: NDArray[np.float64],
    fixed: NDArray[np.bool_],
) -> None:
    for row, observation in enumerate(observations):  # bind observation metadata
        match observation.kind:
            case ObservationKind.SETTLEMENT:
                if observation.day is None:
                    raise ValueError("a settlement observation needs a date")
                continue
            case ObservationKind.CURRENT_MARK:
                pass
            case _:
                assert_never(observation.kind)
        if observation.day is not None or fixed[row]:
            raise ValueError("a current mark has no fixing date and is never a historical fixing")
        point = MarketPoint(observation.index, observation.contract)
        if point not in points:
            raise ValueError("a current mark names an unknown market point")
        expected = np.zeros(len(points))
        expected[points.index(point)] = 1.0
        if not np.array_equal(B[row], expected):
            raise ValueError("a current mark must select its own market point")


def _aligned(plan: LinearTradePlan, market: MarketSnapshot) -> None:
    if plan.observations != market.observations:
        raise ValueError("market observation axis differs from the prepared trade axis")


def full_amounts(
    plan: LinearTradePlan,
    market: MarketSnapshot,
    counter: WorkCounter,
) -> NDArray[np.float64]:
    _aligned(plan, market)
    counter.hit("matrix_vector", 2)
    counter.hit("dense_product_term", market.B.size + plan.A.size)
    x = market.B @ market.p + market.k
    return plan.A @ x + plan.c


def compact(
    plan: LinearTradePlan,
    market: MarketSnapshot,
    counter: WorkCounter,
) -> CompressedPlan:
    _aligned(plan, market)
    counter.hit("matrix_matrix")
    counter.hit("matrix_vector")
    counter.hit("dense_product_term", plan.A.size * (len(market.point_keys) + 1))
    return CompressedPlan(
        plan, market.point_keys, _readonly(plan.A @ market.B), _readonly(plan.c + plan.A @ market.k)
    )


def compact_amounts(
    plan: CompressedPlan,
    point_keys: tuple[MarketPoint, ...],
    prices: NDArray[np.float64],
    counter: WorkCounter,
) -> NDArray[np.float64]:
    """The price-update path; a changed fixing/projection state requires compact again."""
    if point_keys != plan.point_keys or prices.shape != (len(point_keys),):
        raise ValueError("current price axis differs from the compressed market axis")
    if not np.isfinite(prices).all():
        raise ValueError("current prices must be finite")
    counter.hit("matrix_vector")
    counter.hit("dense_product_term", plan.W.size)
    return plan.W @ prices + plan.b


def example() -> tuple[tuple[TradeTerms, ...], MarketSnapshot]:
    """Five deal components, six observations, two current market prices, one known fixing."""
    F, G = MarketPoint("NYMEX CL", "F27"), MarketPoint("NYMEX CL", "G27")
    mark_f = Observation(F.index, F.contract, ObservationKind.CURRENT_MARK, None)
    mark_g = Observation(G.index, G.contract, ObservationKind.CURRENT_MARK, None)
    days = tuple(
        Observation("NYMEX CL", contract, ObservationKind.SETTLEMENT, date(2026, 12, day))
        for contract, day in (("F27", 1), ("F27", 2), ("G27", 22), ("G27", 23))
    )
    f = ObservationSchedule("F27 current mark", (mark_f,), (1.0,))
    g = ObservationSchedule("G27 current mark", (mark_g,), (1.0,))
    average = ObservationSchedule("illustrative four-day average", days, (0.25,) * 4)
    pen = ObservationSchedule("illustrative single dated fixing", (days[1],), (1.0,))
    trades = (
        TradeTerms("O001", "future", 10_000.0, 70.0, f, None),
        TradeTerms("O002", "future", -4_000.0, 71.0, g, None),
        TradeTerms("O003", "asian_swap", 6_000.0, 70.5, average, date(2027, 1, 15)),
        TradeTerms("O004", "asian_swap", -2_000.0, 71.0, average, date(2027, 2, 16)),
        TradeTerms("O005", "penultimate_swap", -3_000.0, 70.75, pen, date(2026, 12, 23)),
    )
    market = market_snapshot(
        (F, G),
        np.array([72.0, 73.0]),
        (mark_f, mark_g, *days),
        np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]]),
        np.array([0.0, 0.0, 70.0, 0.0, 0.0, 0.0]),
        np.array([False, False, True, False, False, False]),
    )
    return trades, market


def main() -> None:
    trades, market = example()
    plan = prepare(trades, market.observations, WorkCounter())
    compressed = compact(plan, market, WorkCounter())
    full = full_amounts(plan, market, WorkCounter())
    reduced = compact_amounts(compressed, market.point_keys, market.p, WorkCounter())
    print("ILLUSTRATIVE FOUR-SELECTED-DAY AVERAGE; NOT A REAL MONTHLY CONTRACT SCHEDULE")
    print("Amounts are futures lifetime P&L / projected swap payments, not discounted value.")
    for label, values in (
        ("A", plan.A),
        ("c", plan.c),
        ("B", market.B),
        ("k", market.k),
        ("p", market.p),
        ("W = A @ B", compressed.W),
        ("b = c + A @ k", compressed.b),
    ):
        print(f"{label}:\n{values}")
    print("Rows:", tuple(trade.trade_id for trade in trades))
    print("Full:", full)
    print("Compressed:", reduced)


if __name__ == "__main__":
    main()
