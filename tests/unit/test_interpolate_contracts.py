"""Contract prices interpolated between anchors, interpolate-contract-prices.md: every month from
the first anchor's through the last's on the index's schedule, each priced on the straight line
between the adjacent anchors weighted by the calendar days between the index's futures expiries.
The figures are the ticket's, priced by hand here: a CL-style index whose J27, K27 and M27 expire
on 22 March, 20 April and 20 May 2027, quoted 70 in April and 76 in June, so that May is 29 of
59 days along, 72.94915254237289. The production code is never asked for an expected answer; an
anchor's own price is held exactly and a line's point to 1e-12, the kernel's tolerance. The seam
spills the three columns under two heading rows and refuses in its own words.
docs/library/utilities/interpolate-contracts.md is the page."""

from typing import Any, cast

import numpy as np
import pytest
from test_trade_valuation import ENTRY, column, serial, spilled
from test_trade_valuation import an_index as seam_index
from test_trades import WAHA, an_index, dates

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.index import Index
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market_data.interpolated_contracts import (
    InterpolatedContracts,
    interpolate_contracts,
)

TIGHT: dict[str, Any] = {"rtol": 1e-12, "atol": 1e-12}  # np.testing.assert_allclose
CLOSE: dict[str, Any] = {"rel": 1e-12, "abs": 1e-12}  # pytest.approx
MAY = 70.0 + 29.0 / 59.0 * 6.0  # 72.94915254237289, the ticket's hand figure


def futures(name: str, *contracts: tuple[str, str]) -> Index:
    """A one-thousand-barrel index of those contracts, dollars a barrel, closed on nothing that
    matters."""
    return an_index(
        name, contracts, ("2030-01-01",), ("USD", "BBL"), ("VOLUME", "BBL"), ("LOT", 1000.0, "BBL")
    )


CL = futures("CL", ("J27", "2027-03-22"), ("K27", "2027-04-20"), ("M27", "2027-05-20"))
# Thirteen months, December 2027 to December 2028, each expiring on the 20th or the business
# day after in the month before, 2028 a leap year: the ticket's December-to-December case.
YEAR = futures(
    "YEAR",
    ("Z27", "2027-11-22"),
    ("F28", "2027-12-20"),
    ("G28", "2028-01-20"),
    ("H28", "2028-02-22"),
    ("J28", "2028-03-21"),
    ("K28", "2028-04-20"),
    ("M28", "2028-05-22"),
    ("N28", "2028-06-20"),
    ("Q28", "2028-07-20"),
    ("U28", "2028-08-22"),
    ("V28", "2028-09-20"),
    ("X28", "2028-10-20"),
    ("Z28", "2028-11-20"),
)


def made(
    ix: Index, anchors: tuple[str, ...], *prices: float, counter: WorkCounter | None = None
) -> InterpolatedContracts:
    return interpolate_contracts(
        ix, anchors, np.array(prices, dtype=np.float64), counter or WorkCounter()
    )


def days_between(first: str, second: str) -> float:
    return float((np.datetime64(second) - np.datetime64(first)).astype(np.int64))


# --- the worked example -----------------------------------------------------------------------


def test_the_worked_example_prices_may_twenty_nine_of_fifty_nine_days_along() -> None:
    counter = WorkCounter()
    result = made(CL, ("202704", "202706"), 70.0, 76.0, counter=counter)
    assert result.codes == ("J27", "K27", "M27")
    np.testing.assert_array_equal(result.expiries, dates("2027-03-22", "2027-04-20", "2027-05-20"))
    assert result.prices[0] == 70.0 and result.prices[2] == 76.0  # the anchors, exactly
    assert result.prices[1] == pytest.approx(MAY, **CLOSE)
    assert result.prices.dtype == np.float64 and not result.prices.flags.writeable
    assert not result.expiries.flags.writeable
    assert counter.freeze().as_dict() == {
        "anchors_read": 2,
        "interpolations": 1,
        "months_generated": 3,
        "schedule_rows_read": 3,
    }
    # The same by code, in either case: the labels name months and nothing more.
    for labels in (("J27", "M27"), ("j27", "m27"), ("J27", "202706")):
        np.testing.assert_array_equal(made(CL, labels, 70.0, 76.0).prices, result.prices)
    # A supplied May stands at its own price exactly, and the line is not drawn through it.
    with_may = made(CL, ("J27", "K27", "M27"), 70.0, 74.0, 76.0)
    assert with_may.prices.tolist() == [70.0, 74.0, 76.0]
    # Two adjacent anchors with no month between: the endpoints and nothing else.
    pair = made(CL, ("K27", "M27"), 74.0, 76.0)
    assert pair.codes == ("K27", "M27") and pair.prices.tolist() == [74.0, 76.0]
    # The index is read and not changed: its schedule's dates stand, frozen, and the spill is
    # another array.
    assert result.expiries is not cast(FuturesSchedule, CL.schedule).future_expiry
    np.testing.assert_array_equal(
        cast(FuturesSchedule, CL.schedule).future_expiry,
        dates("2027-03-22", "2027-04-20", "2027-05-20"),
    )


def test_december_to_december_is_thirteen_months_each_on_its_own_expiry_days() -> None:
    # Z27 at 60 and Z28 at 72 over 364 days: F28 is 28 days along, H28 92, 2028's leap day
    # counted, and Z28 the anchor itself; the weights are the expiries' days, never the months'.
    result = made(YEAR, ("Z27", "Z28"), 60.0, 72.0)
    assert result.codes == (
        "Z27", "F28", "G28", "H28", "J28", "K28", "M28", "N28", "Q28", "U28", "V28", "X28", "Z28",
    )  # fmt: skip
    span = days_between("2027-11-22", "2028-11-20")
    assert span == 364.0
    expected = [
        60.0 + days_between("2027-11-22", str(day)) / span * 12.0 for day in result.expiries
    ]
    np.testing.assert_allclose(result.prices, expected, **TIGHT)
    assert result.prices[1] == pytest.approx(60.0 + 28.0 / 364.0 * 12.0, **CLOSE)
    assert result.prices[0] == 60.0 and result.prices[-1] == 72.0


def test_a_leap_day_interval_counts_its_twenty_nine_days() -> None:
    # G28 expiring 20 January 2028 and J28 21 March: 61 days, H28's 22 February 33 of them.
    result = made(YEAR, ("G28", "J28"), 50.0, 56.1)
    assert result.codes == ("G28", "H28", "J28")
    assert days_between("2028-01-20", "2028-03-21") == 61.0
    assert result.prices[1] == pytest.approx(50.0 + 33.0 / 61.0 * 6.1, **CLOSE)


def test_three_anchors_price_each_missing_month_against_its_own_pair() -> None:
    # Z27, H28 and X28 at 60, 63 and 70: F28 and G28 on the first line, 92 days long, J28 through
    # V28 on the second, 242 days long, each month by its own expiry's days.
    result = made(YEAR, ("Z27", "H28", "X28"), 60.0, 63.0, 70.0)
    assert result.codes[:4] == ("Z27", "F28", "G28", "H28") and result.codes[-1] == "X28"
    first, second = (
        days_between("2027-11-22", "2028-02-22"),
        days_between("2028-02-22", "2028-10-20"),
    )
    assert (first, second) == (92.0, 241.0)
    assert result.prices[1] == pytest.approx(60.0 + 28.0 / first * 3.0, **CLOSE)
    assert result.prices[2] == pytest.approx(60.0 + 59.0 / first * 3.0, **CLOSE)
    assert result.prices[3] == 63.0
    assert result.prices[4] == pytest.approx(63.0 + 28.0 / second * 7.0, **CLOSE)  # J28, 21 March
    assert result.prices[-2] == pytest.approx(63.0 + 211.0 / second * 7.0, **CLOSE)  # V28, 20 Sept
    assert result.prices[-1] == 70.0


def test_a_moved_expiry_moves_the_price_and_the_month_starts_do_not() -> None:
    # The same codes with K27 expiring a week later, 27 April: 36 of 59 days along.
    moved = futures("CL2", ("J27", "2027-03-22"), ("K27", "2027-04-27"), ("M27", "2027-05-20"))
    result = made(moved, ("J27", "M27"), 70.0, 76.0)
    assert result.prices[1] == pytest.approx(70.0 + 36.0 / 59.0 * 6.0, **CLOSE)
    assert result.prices[1] != pytest.approx(MAY, **CLOSE)


def test_prices_rise_fall_stay_flat_pass_zero_and_go_negative_as_supplied() -> None:
    falling = made(CL, ("J27", "M27"), 76.0, 70.0)
    assert falling.prices[1] == pytest.approx(76.0 - 29.0 / 59.0 * 6.0, **CLOSE)
    flat = made(CL, ("J27", "M27"), 3.5, 3.5)
    assert flat.prices.tolist() == [3.5, 3.5, 3.5]
    through_zero = made(CL, ("J27", "M27"), -3.0, 3.0)
    assert through_zero.prices[1] == pytest.approx(-3.0 + 29.0 / 59.0 * 6.0, **CLOSE)
    negative = made(CL, ("J27", "M27"), -10.0, -4.0)
    assert negative.prices[1] == pytest.approx(-10.0 + 29.0 / 59.0 * 6.0, **CLOSE)
    zero = made(CL, ("J27", "M27"), 0.0, 0.0)
    assert zero.prices.tolist() == [0.0, 0.0, 0.0]
    # An anchor placed on the line leaves the line where it was, within float.
    on_the_line = made(CL, ("J27", "K27", "M27"), 70.0, MAY, 76.0)
    np.testing.assert_allclose(
        on_the_line.prices, made(CL, ("J27", "M27"), 70.0, 76.0).prices, **TIGHT
    )


# --- the rules ---------------------------------------------------------------------------------


def refused(ix: Index, anchors: tuple[str, ...], *prices: float) -> str:
    with pytest.raises(ValueError) as caught:
        made(ix, anchors, *prices)
    return str(caught.value)


def test_the_rules_refuse_in_order_naming_the_row_the_month_or_the_contract() -> None:
    assert refused(WAHA, ("F27", "G27"), 1.0, 2.0) == (
        "index is an IFERC index, expected a futures index, whose schedule has a futures expiry "
        "per contract"
    )
    assert refused(CL, ("J27", "M27"), 70.0) == (
        "anchor_prices has 1 price, expected 2, one per anchor contract"
    )
    assert refused(CL, ("J27",), 70.0) == (
        "anchor_contracts has 1 contract, expected at least two to interpolate between"
    )
    for label in (
        "202713",
        "202700",
        "199912",
        "F2027",
        "CAL27",
        "1Q27",
        " J27",
        "J27 ",
        "20270",
        "I27",
    ):
        assert refused(CL, ("J27", label), 70.0, 76.0) == (
            f"anchor_contracts row 2 is {label!r}, expected a contract code such as F26 or the "
            "month as CME spells it, such as 202601"
        )
    assert refused(CL, ("J27", "M27"), np.inf, 76.0) == (
        "anchor_prices row 1 is inf, expected a finite price"
    )
    assert refused(CL, ("J27", "M27"), 70.0, np.nan) == (
        "anchor_prices row 2 is nan, expected a finite price"
    )
    # A repeat is named by both rows even when the prices agree, the labels as typed.
    assert refused(CL, ("J27", "202704"), 70.0, 70.0) == (
        "anchor_contracts rows 1 and 2 are 'J27' and '202704', both 2027-04, expected each "
        "month once"
    )
    assert refused(CL, ("J27", "K27", "j27"), 70.0, 74.0, 70.0) == (
        "anchor_contracts rows 1 and 3 are 'J27' and 'j27', both 2027-04, expected each month once"
    )
    assert refused(CL, ("M27", "J27"), 76.0, 70.0) == (
        "anchor_contracts row 2 is 'J27', 2027-04, expected a month after row 1's 'M27', 2027-06"
    )
    # The schedule's own reader refuses a code that is no month and two rows of one month in its
    # words, every row read, inside the range or out.
    odd = futures("ODD", ("J27", "2027-03-22"), ("CAL28", "2027-04-20"), ("M27", "2027-05-20"))
    assert refused(odd, ("J27", "M27"), 70.0, 76.0) == (
        "index schedule row 2 is 'CAL28', expected a contract code, a month letter and a "
        "two-digit year such as F26"
    )
    twice = futures("TWICE", ("J27", "2027-03-22"), ("K27", "2027-04-20"), ("k27", "2027-04-21"))
    assert refused(twice, ("J27", "K27"), 70.0, 76.0) == (
        "index schedule rows 2 and 3 are 'K27' and 'k27', both 2027-05, expected one contract "
        "per month"
    )
    # A month missing from the schedule, an anchor's or one between, named by month and code.
    gap = futures("GAP", ("J27", "2027-03-22"), ("M27", "2027-05-20"))
    assert refused(gap, ("J27", "M27"), 70.0, 76.0) == (
        "the index's schedule has no contract for 2027-05, K27, expected every month from "
        "2027-04 to 2027-06, the anchors' range"
    )
    assert refused(CL, ("H27", "M27"), 70.0, 76.0) == (
        "the index's schedule has no contract for 2027-03, H27, expected every month from "
        "2027-03 to 2027-06, the anchors' range"
    )
    # Expiries equal or reversed among the selected months, named with their contracts.
    same_day = futures("SAME", ("J27", "2027-04-20"), ("K27", "2027-04-20"), ("M27", "2027-05-20"))
    assert refused(same_day, ("J27", "M27"), 70.0, 76.0) == (
        "the futures expiry of 'K27', 2027-04-20, is not after that of 'J27', 2027-04-20, "
        "expected the expiries of the months from 2027-04 to 2027-06 increasing"
    )
    reversed_days = futures(
        "BACK", ("J27", "2027-03-22"), ("K27", "2027-05-21"), ("M27", "2027-05-20")
    )
    assert refused(reversed_days, ("J27", "M27"), 70.0, 76.0) == (
        "the futures expiry of 'M27', 2027-05-20, is not after that of 'K27', 2027-05-21, "
        "expected the expiries of the months from 2027-04 to 2027-06 increasing"
    )
    # A line between the largest numbers outruns them at the month between, refused by that
    # month with the anchors on either side, the flags down and the rule the judge.
    assert refused(CL, ("J27", "M27"), 1e308, -1e308) == (
        "the price of 'K27' is -inf, expected a finite price; the line from row 1's 1e+308 to "
        "row 2's -1e+308 outruns the largest number"
    )


def test_a_schedule_out_of_row_order_is_read_by_month() -> None:
    # The schedule's rows in any order: the months are resolved by month, the codes spelled as
    # the schedule spells them.
    shuffled = futures("MIX", ("m27", "2027-05-20"), ("J27", "2027-03-22"), ("k27", "2027-04-20"))
    result = made(shuffled, ("202704", "202706"), 70.0, 76.0)
    assert result.codes == ("J27", "k27", "m27")
    np.testing.assert_array_equal(result.expiries, dates("2027-03-22", "2027-04-20", "2027-05-20"))
    assert result.prices[1] == pytest.approx(MAY, **CLOSE)


# --- through the seam --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    index, calendar = seam_index(
        "CL",
        [("J27", "2027-03-22"), ("K27", "2027-04-20"), ("M27", "2027-05-20")],
        ["2030-01-01"],
        [("LOT", 1000.0)],
        ("VOLUME", "BBL"),
    )
    return {"index": index, "calendar": calendar}


def anchors(*labels: object) -> Cells:
    return Cells.from_rows([[label] for label in labels])


def test_the_spill_pairs_each_month_with_its_expiry_and_price(sheet: dict[str, Any]) -> None:
    live = bridge.live_handles()
    table = spilled(
        ENTRY["util_InterpolateContracts"](
            sheet["index"], anchors("202704", "202706"), column([70.0, 76.0])
        )
    )
    assert table == [
        ["contract_code", "future_expiry", "price"],
        ["str", "datetime64[D]", "float64"],
        ["J27", serial("2027-03-22"), 70.0],
        ["K27", serial("2027-04-20"), pytest.approx(MAY, **CLOSE)],
        ["M27", serial("2027-05-20"), 76.0],
    ]
    assert bridge.live_handles() == live  # a utility publishes nothing
    by_code = spilled(
        ENTRY["util_InterpolateContracts"](
            sheet["index"], anchors("j27", "M27"), column([70.0, 76.0])
        )
    )
    assert by_code == table
    three = spilled(
        ENTRY["util_InterpolateContracts"](
            sheet["index"], anchors("J27", "K27", "M27"), column([70.0, 74.0, 76.0])
        )
    )
    assert [line[2] for line in three[2:]] == [70.0, 74.0, 76.0]


def test_the_seam_refuses_the_wrong_kinds_and_the_library_its_rules_in_their_words(
    sheet: dict[str, Any],
) -> None:
    live = bridge.live_handles()
    call = ENTRY["util_InterpolateContracts"]
    index = sheet["index"]
    assert call(sheet["calendar"], anchors("J27", "M27"), column([70.0, 76.0])) == (
        f"#ERROR util_InterpolateContracts: index is holiday calendar handle "
        f"{sheet['calendar']!r}, expected index handle"
    )
    assert call(index, anchors(202704.0, "202706"), column([70.0, 76.0])) == (
        "#ERROR util_InterpolateContracts: anchor_contracts cell (1, 1) is number 202704.0, "
        "expected text"
    )
    assert call(index, anchors("J27", None), column([70.0, 76.0])) == (
        "#ERROR util_InterpolateContracts: anchor_contracts cell (2, 1) is blank, expected text"
    )
    assert call(index, anchors("J27", "M27"), Cells.from_rows([["70"], [76.0]])) == (
        "#ERROR util_InterpolateContracts: anchor_prices cell (1, 1) is text '70', expected number"
    )
    assert call(index, anchors("J27", "M27"), bridge.MISSING) == (
        "#ERROR util_InterpolateContracts: anchor_prices is missing, expected column of numbers"
    )
    assert call(index, Cells.from_rows([["J27", "M27"]]), column([70.0, 76.0])) == (
        "#ERROR util_InterpolateContracts: anchor_contracts is 1x2 array, expected column of text"
    )
    assert call(index, anchors("J27", "M27"), column([70.0])) == (
        "#ERROR util_InterpolateContracts: ValueError: anchor_prices has 1 price, expected 2, one "
        "per anchor contract"
    )
    assert call(index, anchors("M27", "J27"), column([76.0, 70.0])) == (
        "#ERROR util_InterpolateContracts: ValueError: anchor_contracts row 2 is 'J27', 2027-04, "
        "expected a month after row 1's 'M27', 2027-06"
    )
    assert call(index, anchors("H27", "M27"), column([70.0, 76.0])) == (
        "#ERROR util_InterpolateContracts: ValueError: the index's schedule has no contract for "
        "2027-03, H27, expected every month from 2027-03 to 2027-06, the anchors' range"
    )
    assert bridge.live_handles() == live


def test_the_spill_feeds_an_ordinary_price_vector(sheet: dict[str, Any]) -> None:
    # The price column selected by the sheet, its two heading rows left out, is a column of
    # numbers the price-vector creator takes as any other.
    table = spilled(
        ENTRY["util_InterpolateContracts"](
            sheet["index"], anchors("J27", "M27"), column([70.0, 76.0])
        )
    )
    prices = column([cast(float, line[2]) for line in table[2:]])
    vector = ENTRY["_CreatePriceVector"]("CL", prices)
    shown = spilled(ENTRY["util_ReadHandle"](vector))
    assert [line[0] for line in shown[2:]] == [70.0, pytest.approx(MAY, **CLOSE), 76.0]
