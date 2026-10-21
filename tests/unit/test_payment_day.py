"""The payment day of a financial fixed_float, payment-day-date-or-rule.md: first the kernel's one
rule that a payment falls after the last observation it pays for, the owner the encoding and the
quote both call."""

import numpy as np
import pytest

from goosedove.trades.terms import payments_after_observations


def days(*texts: str) -> np.ndarray:
    return np.array(texts, dtype="datetime64[D]")


def test_payments_after_their_observations_pass_in_silence() -> None:
    payments_after_observations(
        days("2027-02-02", "2027-03-02"), days("2027-01-29", "2027-02-24"), lambda k: f"item {k}"
    )


def test_the_first_payment_on_or_before_its_observation_is_named_in_the_callers_words() -> None:
    # The first early item in the caller's order is the one named, equality refused as a day
    # before is, with both days.
    with pytest.raises(
        ValueError,
        match=(
            r"^G27 pays on 2027-02-24, expected a day after its last observation, 2027-02-24, "
            r"when its final price exists$"
        ),
    ):
        payments_after_observations(
            days("2027-02-02", "2027-02-24", "2027-03-01"),
            days("2027-01-29", "2027-02-24", "2027-03-29"),
            lambda k: ("F27", "G27", "H27")[k],
        )
