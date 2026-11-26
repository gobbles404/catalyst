"""A fixed_float on a published index through the seam, as a sheet books and values it: issue
#271's worked example, a month's volume shared equally by its prints, a print's exposure
leaving the day after its date, the stand-in, a month's roll, a strip settled month by month,
the payment counted from the last publication date, and every field value the kind refuses."""

from collections.abc import Sequence
from typing import Any

import pytest
from test_trade_valuation import (
    ENTRY,
    NG_HEADERS,
    a_market,
    an_index,
    by_header,
    column,
    row,
    rows,
    serial,
    spilled,
    templated,
    valued,
)

from catalyst.excel import bridge

DIESEL = "DOE Diesel"
# Weekly prints from the last of August to the end of December 2026, each dated its Monday and
# counted toward the month the Monday falls in: August one here, September and October four,
# November five, its last on the month's last day, December four.
PRINTS: list[tuple[str, str]] = [
    ("Q26", "2026-08-31"),
    *[("U26", f"2026-09-{d:02d}") for d in (7, 14, 21, 28)],
    *[("V26", f"2026-10-{d:02d}") for d in (5, 12, 19, 26)],
    *[("X26", f"2026-11-{d:02d}") for d in (2, 9, 16, 23, 30)],
    *[("Z26", f"2026-12-{d:02d}") for d in (7, 14, 21, 28)],
]
# Hypothetical published prices, the issue's for August and September.
PUBLISHED = {
    "2026-08-31": 2.95,
    "2026-09-07": 3.00,
    "2026-09-14": 3.20,
    "2026-09-21": 3.55,
    "2026-09-28": 3.60,
    "2026-10-05": 3.70,
    "2026-10-12": 3.72,
    "2026-10-19": 3.74,
    "2026-10-26": 3.76,
    "2026-11-02": 3.80,
    "2026-11-09": 3.82,
    "2026-11-16": 3.84,
    "2026-11-23": 3.86,
    "2026-11-30": 3.88,
    "2026-12-07": 3.90,
}
TEMPLATE: dict[str, object] = {
    "quantity_unit": "gal",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "asian",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "TEST_CLEARER",
    "payment_day": "+5bd",
}
TICKET: list[object] = [1001.0, serial("2026-08-20"), "U26", 40_000.0, 3.10]
DELTA = f"{DIESEL} nominal_delta [gal]"


@pytest.fixture(scope="module")
def diesel() -> dict[str, Any]:
    """The diesel index through the seam, quoted and settled in dollars a gallon, its delta
    reported in gallons, and a payment calendar closed on Christmas Day alone."""
    schedule = ENTRY["_CreatePublishedSchedule"](
        rows(*[[code] for code, _ in PRINTS]), column([serial(day) for _, day in PRINTS])
    )
    conventions = ENTRY["_CreateIndexConventions"]("DOLLAR", "GAL", "DOLLAR", "VOLUME", "GAL")
    specifications = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        rows(["gal", 1.0, "GAL", 0.0, 0.0]),
    )
    index = ENTRY["_CreateIndex"](
        DIESEL,
        "U.S. national retail diesel - EIA weekly",
        schedule,
        conventions,
        specifications,
        bridge.MISSING,
        "gal",
        bridge.MISSING,
    )
    _, pays = an_index(
        "PAY", [("X26", "2026-10-28"), ("Z26", "2026-11-25")], ["2026-12-25"], [("L", 1.0)]
    )
    return {"index": str(index), "pays": pays}


def a_template(diesel: dict[str, Any], **changed: object) -> object:
    """The cleared template with a field changed, or left out where the change is None."""
    fields = {**TEMPLATE, "payment_holiday_key": diesel["pays"], **changed}
    fields = {name: value for name, value in fields.items() if value is not None}
    return templated([*fields], [*fields.values()])


def booked(
    diesel: dict[str, Any],
    *tickets: Sequence[object],
    headers: tuple[str, ...] = NG_HEADERS,
    **changed: object,
) -> str:
    """A batch on the diesel index from those ticket rows under the template, a field changed."""
    lines = [list(line) for line in tickets or (TICKET,)]
    made = ENTRY["_CreateTrades"](
        diesel["index"], row(*headers), rows(*lines), a_template(diesel, **changed)
    )
    return str(made)


def state(
    diesel: dict[str, Any],
    trades: str,
    as_of: str,
    quotes: tuple[float, ...],
    **stand_ins: float,
) -> str:
    """The batch valued on that day: a price for every print dated before it, the published one
    or the stand-in given for its date, the market over those quotes, one per month from the
    month of the first print still to come; the results handle."""
    given = {**PUBLISHED, **{day.replace("_", "-"): price for day, price in stand_ins.items()}}
    fixed = [(day, given[day]) for _, day in PRINTS if day < as_of][::-1]
    fixings = ENTRY["_CreatePublishedFixings"](
        column([serial(day) for day, _ in fixed]),
        column([price for _, price in fixed]),
        diesel["index"],
    )
    calendar = ENTRY["_CreateCalendar"](
        ENTRY["_CreateValuationDate"](serial(as_of), 0.5), diesel["index"]
    )
    history = str(ENTRY["_CreateMarketHistory"](calendar, fixings))
    market = a_market(history, DIESEL, *quotes)
    prepared = ENTRY["_PrepareTrades"](trades, history)
    return str(ENTRY["_EvaluateTrades"](prepared, market, bridge.MISSING))


def risk(results: str, bucket: str) -> list[list[object]]:
    return spilled(ENTRY["_ReportRisk"](results, "nominal_delta", bucket))


# --- the issue's worked example ----------------------------------------------------------------

# 40,000 gallons of September against a fixed 3.10, the month's quote 3.50: a quarter of the
# month on each of its four prints. On Monday the 14th that day's print is still live; from
# Tuesday it is fixed, at a stand-in until its publisher releases it and at 3.20 after.
SEPTEMBER = (3.50, 3.65, 3.70, 3.80)


@pytest.mark.parametrize(
    ("as_of", "stand_ins", "mark", "gallons"),
    [
        ("2026-09-16", {}, 8_000.0, 20_000.0),
        ("2026-09-14", {}, 11_000.0, 30_000.0),
        ("2026-09-15", {"2026_09_14": 3.50}, 11_000.0, 20_000.0),
        ("2026-09-15", {}, 8_000.0, 20_000.0),
    ],
    ids=[
        "the 16th: two prints fixed, two live",
        "Monday the 14th: that day's print still live",
        "Tuesday the 15th, before the release: fixed at the stand-in",
        "Tuesday the 15th, after it: fixed at the published price",
    ],
)
def test_the_worked_example_values_as_the_issue_says(
    diesel: dict[str, Any], as_of: str, stand_ins: dict[str, float], mark: float, gallons: float
) -> None:
    value, cash, delta = valued(state(diesel, booked(diesel), as_of, SEPTEMBER, **stand_ins))
    assert value == pytest.approx(mark)
    assert cash == 0.0
    assert delta == pytest.approx(gallons)


# Replacing the stand-in moves the value by its miss on the one print, 10,000 gallons at 30
# cents, and leaves the exposure as it was.
def test_replacing_the_stand_in_moves_the_value_by_its_miss_and_no_exposure(
    diesel: dict[str, Any],
) -> None:
    trades = booked(diesel)
    stood_in = valued(state(diesel, trades, "2026-09-15", SEPTEMBER, **{"2026_09_14": 3.50}))
    released = valued(state(diesel, trades, "2026-09-15", SEPTEMBER))
    assert stood_in[0] - released[0] == pytest.approx(10_000.0 * (3.50 - 3.20))
    assert stood_in[2] == released[2]


def test_the_risk_report_puts_each_live_print_on_its_date_and_its_month(
    diesel: dict[str, Any],
) -> None:
    results = state(diesel, booked(diesel), "2026-09-16", SEPTEMBER)
    as_of = serial("2026-09-16")
    head = [["as_of", as_of], ["period", DELTA], ["str | datetime64[D]", "float64"]]
    assert risk(results, "day") == [
        *head,
        ["Total", 20_000.0],
        [serial("2026-09-07"), 0.0],
        [serial("2026-09-14"), 0.0],
        [serial("2026-09-21"), 10_000.0],
        [serial("2026-09-28"), 10_000.0],
    ]
    assert risk(results, "month") == [*head, ["Total", 20_000.0], [serial("2026-09-01"), 20_000.0]]
    assert risk(results, "year") == [*head, ["Total", 20_000.0], [serial("2026-01-01"), 20_000.0]]
    values = spilled(ENTRY["_ReportValues"](results))
    assert values[0][:2] == ["cleared_mark", "cleared_cash"]
    assert values[2][:2] == [pytest.approx(8_000.0), 0.0]


# --- four prints and five, a month's roll, and the payment -------------------------------------


# November 2026 has five prints, a fifth of the month on each: 8,000 gallons a print.
def test_a_five_print_month_puts_a_fifth_of_the_volume_on_each_print(
    diesel: dict[str, Any],
) -> None:
    november = booked(diesel, [1002.0, serial("2026-08-20"), "X26", 40_000.0, 3.10])
    results = state(diesel, november, "2026-11-17", (3.90, 4.00))
    value, cash, delta = valued(results)
    assert delta == pytest.approx(16_000.0)  # the 23rd's and the 30th's prints
    average = (3.80 + 3.82 + 3.84 + 3.90 + 3.90) / 5
    assert value == pytest.approx(40_000.0 * (average - 3.10)) and cash == 0.0
    assert [line[1] for line in risk(results, "day")[4:]] == [0.0, 0.0, 0.0, 8_000.0, 8_000.0]


# November's last print is dated Monday the 30th and fixed from Tuesday 1 December: no print of
# the month is live in the month after, so December's month report shows no November exposure
# and is not refused. The month pays five business days after its last publication date, on
# Monday 7 December, and is cash from the day after.
def test_a_months_last_print_is_fixed_on_the_first_day_of_the_next_month(
    diesel: dict[str, Any],
) -> None:
    november = booked(diesel, [1002.0, serial("2026-08-20"), "X26", 40_000.0, 3.10])
    assert by_header(november, "payment_date") == [serial("2026-12-07")]
    final = 40_000.0 * ((3.80 + 3.82 + 3.84 + 3.86 + 3.88) / 5 - 3.10)
    still_live = valued(state(diesel, november, "2026-11-30", (3.95, 4.00)))
    assert still_live[2] == pytest.approx(8_000.0)
    fixed = state(diesel, november, "2026-12-01", (4.00,))
    value, cash, delta = valued(fixed)
    assert (value, cash, delta) == (pytest.approx(final), 0.0, 0.0)
    month = risk(fixed, "month")
    assert month[3] == ["Total", 0.0]
    assert month[4] == [serial("2026-12-01"), 0.0]
    paid = valued(state(diesel, november, "2026-12-08", (4.00,)))
    assert (paid[0], paid[1], paid[2]) == (0.0, pytest.approx(final), 0.0)


# A strip settles month by month: a quarter is three months, each on the average of its own
# prints, each paid from its own last publication date, never one average over the quarter.
def test_a_strip_settles_month_by_month_each_on_its_own_average(diesel: dict[str, Any]) -> None:
    quarter = booked(diesel, [1003.0, serial("2026-08-20"), "4Q26", 40_000.0, 3.10])
    assert by_header(quarter, "booked_period") == ["V26", "X26", "Z26"]
    assert by_header(quarter, "entered_contract_code") == ["4Q26"] * 3
    assert by_header(quarter, "payment_date") == [
        serial("2026-11-02"),
        serial("2026-12-07"),
        serial("2027-01-04"),
    ]
    assert by_header(quarter, "component_quantity") == [40_000.0] * 3
    results = state(diesel, quarter, "2026-09-16", SEPTEMBER)
    value, _, delta = valued(results)
    assert value == pytest.approx(40_000.0 * ((3.65 - 3.10) + (3.70 - 3.10) + (3.80 - 3.10)))
    assert delta == pytest.approx(120_000.0)
    # October has four prints and November five: each month's volume is shared by its own.
    by_day = {line[0]: line[1] for line in risk(results, "day")[4:]}
    assert by_day[serial("2026-10-05")] == pytest.approx(10_000.0)
    assert by_day[serial("2026-11-30")] == pytest.approx(8_000.0)


# quantity_per sets the month's volume and never the weights: 1,000 gallons a calendar day is
# 30,000 for September's thirty days, shared equally by its four prints.
def test_a_calday_quantity_sets_the_months_volume_and_the_prints_share_it_equally(
    diesel: dict[str, Any],
) -> None:
    daily = booked(
        diesel, [1004.0, serial("2026-08-20"), "U26", 1_000.0, 3.10], quantity_per="calday"
    )
    assert by_header(daily, "covered_days") == [30.0]
    assert by_header(daily, "component_quantity") == [30_000.0]
    results = state(diesel, daily, "2026-09-16", SEPTEMBER)
    assert valued(results)[2] == pytest.approx(15_000.0)
    assert [line[1] for line in risk(results, "day")[4:]] == [0.0, 0.0, 7_500.0, 7_500.0]


# A payment rule counts from the month's last publication date, its last observation, as on
# every index: September's last print is dated Monday the 28th.
@pytest.mark.parametrize(
    ("rule", "pays"),
    [("+5bd", "2026-10-05"), ("+1bd", "2026-09-29"), ("+0em+5bd", "2026-10-07")],
)
def test_a_payment_rule_counts_from_the_last_publication_date(
    diesel: dict[str, Any], rule: str, pays: str
) -> None:
    assert by_header(booked(diesel, payment_day=rule), "payment_date") == [serial(pays)]


# --- what a published index refuses, by its field ----------------------------------------------

TRADE = "trade 1001 at row 1"
AVERAGE = "expected 'asian' on a published index; a published month is the average of its prints"


@pytest.mark.parametrize(
    ("changed", "message"),
    [
        (
            {"schedule_method": "lastday"},
            f"schedule_method of {TRADE} is 'lastday', {AVERAGE}",
        ),
        (
            {"schedule_method": "penultimate"},
            f"schedule_method of {TRADE} is 'penultimate', {AVERAGE}",
        ),
        (
            {"schedule_method": "last3day"},
            f"schedule_method of {TRADE} is 'last3day', {AVERAGE}",
        ),
        (
            {"settlement_method": "physical", "payment_day": None, "payment_holiday_key": None},
            "settlement_method is 'physical', expected 'financial' on a published index; nothing "
            "is delivered against a published price",
        ),
        (
            {"nearby": 2.0},
            f"nearby of {TRADE} is 2, expected 1 on a published index; a print counts toward its "
            "own month, and there is no contract to roll",
        ),
        (
            {"settlement_frequency": "onetime", "quantity_per": "period"},
            f"settlement_frequency of {TRADE} is 'onetime', expected 'monthly' on a published "
            "index; one average across months would weight each month by its number of prints, "
            "and a strip settles month by month",
        ),
    ],
    ids=["lastday", "penultimate", "last3day", "physical", "a later nearby", "onetime"],
)
def test_a_field_value_a_published_index_does_not_take_is_refused_by_its_message(
    diesel: dict[str, Any], changed: dict[str, Any], message: str
) -> None:
    assert booked(diesel, **changed) == f"#ERROR _CreateTrades: ValueError: {message}"


# A part of a month, booked by two dates, waits for date windows; a month the schedule does not
# list names no prints.
def test_a_part_of_a_month_and_a_month_the_schedule_lacks_are_refused(
    diesel: dict[str, Any],
) -> None:
    headers = ("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price")
    dated = [
        1001.0,
        serial("2026-08-20"),
        serial("2026-09-16"),
        serial("2026-09-30"),
        40_000.0,
        3.1,
    ]
    assert booked(diesel, dated, headers=headers) == (
        f"#ERROR _CreateTrades: ValueError: U26 of {TRADE} is covered from 2026-09-16 to "
        "2026-09-30, part of its month, expected the whole month under asian; a published month "
        "averages every print that counts toward it, and a part of a month is not built"
    )
    # The whole month typed as two dates is the month.
    whole = [
        1001.0,
        serial("2026-08-20"),
        serial("2026-09-01"),
        serial("2026-09-30"),
        40_000.0,
        3.1,
    ]
    by_dates = booked(diesel, whole, headers=headers)
    assert by_header(by_dates, "payment_date") == [serial("2026-10-05")]
    unlisted = booked(diesel, [1001.0, serial("2026-08-20"), "F27", 40_000.0, 3.1])
    assert unlisted.startswith("#ERROR _CreateTrades: ValueError:")


# A batch stands on the prints the history has: valued before the first print of its month is
# dated, every print is live and the month's whole volume is exposed.
def test_a_month_wholly_to_come_carries_its_whole_volume(diesel: dict[str, Any]) -> None:
    value, cash, delta = valued(state(diesel, booked(diesel), "2026-09-01", SEPTEMBER))
    assert (value, cash, delta) == (
        pytest.approx(40_000.0 * (3.50 - 3.10)),
        0.0,
        pytest.approx(40_000.0),
    )
