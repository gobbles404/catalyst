"""The payment day of a financial fixed_float, payment-day-date-or-rule.md: one field,
`payment_day`, holding a date or a rule, told apart by type at the seam. First the kernel's
one rule that a payment falls after the last observation it pays for, the owner the encoding
and the quote both
call; then the field through the resolution, the seam, the readbacks, the valuation on the sheet
and the quote, on the ticket's synthetic index and its numbers by hand."""

from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray
from test_bilateral_kernel import CLOSE, curve_of, curve_set
from test_create_trades import (
    WAHA,
    WAHA_PAYS,
    WAHA_TEMPLATE,
    WAHA_TICKET,
    created,
    dates,
    key_of,
    refused,
    seam_key,
)
from test_create_trades import an_index as kernel_index
from test_field_values import ENTRY as PROBES
from test_field_values import bound
from test_quote import DEC_31, STRIP, WEEKENDS_ONLY, bilateral, counts_of, priced, quote_on
from test_quote import refused as quote_refused
from test_trade_valuation import ENTRY, a_history, a_market, curves_of, row, rows, serial, spilled
from test_trade_valuation import an_index as seam_index
from test_trades import bounds_of, ids, numbers, observed_of, picks, spec

from catalyst.excel import bridge
from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.instruments.fields import DatesOrTexts
from catalyst.trades.encoding import encoded
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.schedule_methods import ScheduleMethod
from catalyst.trades.terms import (
    FREQUENCIES,
    PaymentTerms,
    QuantityPer,
    Route,
    Settlement,
    SettlementFrequency,
    one_choice,
    payments_after_observations,
    resolved_trades,
)


def days(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# --- the kernel's one rule --------------------------------------------------------------------


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


# --- the ticket's synthetic index -----------------------------------------------------------------

# Z26 through F28, each month expiring on its own last business day with weekends alone closed,
# so F27 expires Friday 29 January 2027 and Z27 Friday 31 December 2027: the ticket's synthetic
# schedule, not NYMEX's. One specification of one MMBtu, quoted in DOLLAR per MMBtu.
LETTERS = "FGHJKMNQUVXZ"
MONTHS = np.arange("2026-12", "2028-02", dtype="datetime64[M]")
EXPIRIES = np.busday_offset(
    (MONTHS + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D"),
    0,
    roll="backward",
)
CONTRACTS = (
    ("X26", "2026-10-28"),  # bounds the calendar, which starts the day after it expires
    *(
        (f"{LETTERS[int(m.astype(np.int64)) % 12]}{str(m)[2:4]}", str(e))
        for m, e in zip(MONTHS, EXPIRIES, strict=True)
    ),
)
FAR = ("2030-01-01",)  # a calendar closed on weekends alone within these years
SYN = kernel_index("SYN", CONTRACTS, FAR, (("MMBTU", 1.0, "MMBTU"),))
WEEKENDS = holiday_calendar("FAR_WEEKENDS", dates(*FAR))
BILATERAL: dict[str, object] = {
    "quantity_unit": "MMBTU",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "lastday",
    "route": "bilateral",
    "settlement_method": "financial",
    "counterparty": "ACME Trading",
    "discount_curve_key": "SOFR",
    "payment_holiday_key": key_of(WEEKENDS),
}
CLEARED: dict[str, object] = {
    **{k: v for k, v in BILATERAL.items() if k not in ("counterparty", "discount_curve_key")},
    "route": "cleared",
    "clearing_house": "TEST",
}
FEB_25 = np.datetime64("2027-02-25", "D")


def two_rows(*payment: object, codes: tuple[str, str] = ("F27", "F27")) -> dict[str, list[object]]:
    """The ticket's two rows of 10,000 MMBtu of F27 at 2.65, each paying as given."""
    return {
        "trade_id": [1001, 1002],
        "trade_date": ["2026-12-15", "2026-12-15"],
        "contract_code": list(codes),
        "quantity": [10_000, 10_000],
        "fixed_price": [2.65, 2.65],
        "payment_day": list(payment),
    }


def test_a_date_pays_the_row_on_that_day_and_a_rule_as_before() -> None:
    batch, counter = created(SYN, two_rows("+2bd", FEB_25), BILATERAL)
    payment = batch.resolved.payment
    assert payment is not None
    np.testing.assert_array_equal(payment.date, days("2027-02-02", "2027-02-25"))
    # What each row entered is kept apart, a date a date and a rule its text, in row order.
    np.testing.assert_array_equal(payment.entered.is_date, [False, True])
    assert payment.entered.texts == ("+2bd",)
    np.testing.assert_array_equal(payment.entered.dates, days("2027-02-25"))
    assert payment.calendar == (WEEKENDS, WEEKENDS)
    counts = counter.freeze().as_dict()
    assert (counts["payment_rules_read"], counts["payment_shifts"]) == (1, 1)
    # The two payments are two groups of one contract, on their own days.
    np.testing.assert_array_equal(batch.encoded.legs[0].group_contract, [2, 2])  # F27, row 2
    assert batch.encoded.payment_date is not None
    np.testing.assert_array_equal(batch.encoded.payment_date, days("2027-02-02", "2027-02-25"))


def test_a_dated_batch_reads_no_rule_and_shifts_nothing() -> None:
    batch, counter = created(SYN, two_rows(FEB_25, np.datetime64("2027-03-01", "D")), BILATERAL)
    assert batch.resolved.payment is not None
    np.testing.assert_array_equal(batch.resolved.payment.date, days("2027-02-25", "2027-03-01"))
    assert batch.resolved.payment.entered.texts == ()
    counts = counter.freeze().as_dict()
    assert (counts["payment_rules_read"], counts["payment_shifts"]) == (0, 0)
    # The template's one date pays every row on it, as its one rule would rule every row.
    ticket = {k: v for k, v in two_rows("x", "x").items() if k != "payment_day"}
    dated, counter = created(SYN, ticket, {**BILATERAL, "payment_day": FEB_25})
    assert dated.resolved.payment is not None
    np.testing.assert_array_equal(dated.resolved.payment.date, days("2027-02-25", "2027-02-25"))
    np.testing.assert_array_equal(dated.resolved.payment.entered.is_date, [True, True])
    assert counter.freeze().as_dict()["payment_rules_read"] == 0


def test_a_dated_strip_pays_every_component_together_and_a_ruled_one_month_by_month() -> None:
    # CAL27 dated Tuesday 18 January 2028: twelve components, one payment day, twelve groups,
    # one per contract, meeting on the day; under +2bd each month pays from its own expiry.
    ticket: dict[str, list[object]] = {
        **two_rows(np.datetime64("2028-01-18", "D"), "+2bd"),
        "contract_code": ["CAL27"] * 2,
    }
    batch, _ = created(SYN, ticket, CLEARED)
    payment = batch.resolved.payment
    assert payment is not None and payment.date.size == 24
    np.testing.assert_array_equal(payment.date[:12], [np.datetime64("2028-01-18", "D")] * 12)
    ruled = payment.date[12:]
    assert ruled.size == 12 and (np.diff(ruled) > np.timedelta64(0, "D")).all()
    assert ruled[0] == np.datetime64("2027-02-02", "D")  # F27's expiry, Friday the 29th, +2bd
    np.testing.assert_array_equal(
        batch.encoded.legs[0].group_contract, np.repeat(np.arange(2, 14, dtype=np.intp), 2)
    )
    np.testing.assert_array_equal(
        batch.resolved.legs[0].contract[:12], batch.resolved.legs[0].contract[12:]
    )


def test_a_date_on_or_before_the_rows_last_observation_is_refused_by_the_row() -> None:
    expected = (
        "trade 1001 at row 1 pays on {day}, expected a day after its last observation, "
        "{last}, when its final price exists"
    )
    for day in ("2027-01-29", "2027-01-28"):
        message = refused(SYN, two_rows(np.datetime64(day, "D"), "+2bd"), BILATERAL)
        assert message == expected.format(day=day, last="2027-01-29")
    # A strip's last observation is its final month's, so a date before the strip's end names
    # that day, not the first month it fails.
    ticket: dict[str, list[object]] = {
        **two_rows(FEB_25, "+2bd"),
        "contract_code": ["CAL27", "F27"],
    }
    assert refused(SYN, ticket, CLEARED) == expected.format(day="2027-02-25", last="2027-12-31")
    # The second row is named by its own number and trade.
    ticket = two_rows("+2bd", np.datetime64("2027-01-29", "D"))
    assert refused(SYN, ticket, BILATERAL) == (
        "trade 1002 at row 2 pays on 2027-01-29, expected a day after its last observation, "
        "2027-01-29, when its final price exists"
    )


def test_a_date_is_exact_and_a_physical_row_holds_none() -> None:
    # Saturday 27 February 2027 stays the payment day: nothing rolls it.
    saturday = np.datetime64("2027-02-27", "D")
    batch, _ = created(SYN, two_rows(saturday, saturday), BILATERAL)
    assert batch.resolved.payment is not None
    np.testing.assert_array_equal(batch.resolved.payment.date, [saturday, saturday])
    physical = {
        **{k: v for k, v in CLEARED.items() if k != "payment_holiday_key"},
        "settlement_method": "physical",
    }
    assert refused(SYN, two_rows(FEB_25, FEB_25), physical) == (
        "payment_day is 2027-02-25, expected none unless settlement_method = financial"
    )
    assert refused(SYN, two_rows("+2bd", FEB_25), physical) == (
        "payment_day is '+2bd', expected none unless settlement_method = financial"
    )
    # A text that is no rule fails by the grammar's words, a date typed as text among them.
    assert refused(SYN, two_rows("25-Feb-2027", FEB_25), BILATERAL).startswith(
        "payment_day row 1 is '25-Feb-2027', expected one or more of a sign, a whole count and "
    )


def test_a_rule_and_a_date_on_one_day_share_a_group_under_one_key_and_not_under_two() -> None:
    # +2bd from F27's expiry is Tuesday 2 February 2027: a row dated that day joins the ruled
    # row's group on one curve key, and stays apart on another.
    feb_2 = np.datetime64("2027-02-02", "D")
    together, _ = created(SYN, two_rows("+2bd", feb_2), BILATERAL)
    assert together.encoded.legs[0].group_contract.size == 1
    keyed: dict[str, list[object]] = {
        **two_rows("+2bd", feb_2),
        "discount_curve_key": ["SOFR", "FFOIS"],
    }
    template = {k: v for k, v in BILATERAL.items() if k != "discount_curve_key"}
    apart, _ = created(SYN, keyed, template)
    assert apart.encoded.legs[0].group_contract.size == 2
    assert apart.encoded.payment_date is not None
    np.testing.assert_array_equal(apart.encoded.payment_date, [feb_2, feb_2])


def test_the_anchor_is_each_rows_last_observation_on_any_index_and_under_any_method() -> None:
    # An IFERC month observes its publication day: Z26 publishes 1 December 2026, so a date on it
    # is refused and the day after taken; an asian F27 observes every pricing day of January,
    # the last Friday the 29th, the same anchor as lastday on this index.
    template = {k: v for k, v in WAHA_TEMPLATE.items() if k != "payment_day"}
    assert refused(
        WAHA, {**WAHA_TICKET, "payment_day": [np.datetime64("2026-12-01", "D")]}, template
    ) == (
        "trade 1001 at row 1 pays on 2026-12-01, expected a day after its last observation, "
        "2026-12-01, when its final price exists"
    )
    batch, counter = created(
        WAHA, {**WAHA_TICKET, "payment_day": [np.datetime64("2026-12-02", "D")]}, template
    )
    assert batch.resolved.payment is not None
    np.testing.assert_array_equal(batch.resolved.payment.date, days("2026-12-02"))
    assert batch.resolved.payment.calendar == (WAHA_PAYS,)
    assert counter.freeze().as_dict()["payment_rules_read"] == 0
    asian = {**BILATERAL, "schedule_method": "asian"}
    assert refused(SYN, two_rows(np.datetime64("2027-01-29", "D"), "+2bd"), asian) == (
        "trade 1001 at row 1 pays on 2027-01-29, expected a day after its last observation, "
        "2027-01-29, when its final price exists"
    )
    batch, _ = created(SYN, two_rows(np.datetime64("2027-02-01", "D"), "+2bd"), asian)
    assert batch.resolved.payment is not None
    np.testing.assert_array_equal(batch.resolved.payment.date, days("2027-02-01", "2027-02-02"))


# --- the seam: the column typed cell by cell -------------------------------------------------


def test_the_seam_tells_a_date_from_a_text_by_type_and_refuses_the_rest() -> None:
    values = bound(
        "fixed_float",
        row("payment_day", "quantity"),
        rows(["+2bd", 1.0], [serial("2027-02-25"), 2.0], ["+0em+5bd", 3.0]),
        one_row=False,
    )
    entered = values.dates_or_texts("payment_day")
    np.testing.assert_array_equal(entered.is_date, [False, True, False])
    assert not entered.is_date.flags.writeable and not entered.dates.flags.writeable
    np.testing.assert_array_equal(entered.dates, days("2027-02-25"))
    assert entered.texts == ("+2bd", "+0em+5bd")
    count = PROBES["CountFieldRows"]
    for cell, words in (
        (True, "boolean TRUE"),
        (2.5, "number 2.5"),
        (None, "blank"),
        ("", "empty text"),
        (1.0, "number 1.0"),
    ):
        assert count("fixed_float", row("payment_day"), rows(["+2bd"], [cell])) == (
            f"#ERROR CountFieldRows: rows cell (2, 1) is {words}, expected date or text"
        )
    # The echo probe shows a date as its serial and a rule as its text.
    kinds, slots, text = cast(
        tuple[NDArray[np.uint8], NDArray[np.float64], str],
        PROBES["EchoFieldRow"]("fixed_float", row("payment_day"), row(serial("2027-02-25"))),
    )
    assert kinds[1, 0] == bridge.NUMBER_CODE and slots[1, 0] == serial("2027-02-25")
    assert text.split("\0") == ["payment_day"]
    _, _, text = cast(
        tuple[NDArray[np.uint8], NDArray[np.float64], str],
        PROBES["EchoFieldRow"]("fixed_float", row("payment_day"), row("+2bd")),
    )
    assert text.split("\0") == ["payment_day", "+2bd"]
    # The catalog shows the type in those words.
    shown = spilled(ENTRY["_ShowInstrument"]("fixed_float"))
    column = shown[0].index("payment_day")
    assert shown[4][column] == "date or text"


# --- the sheet: the ticket's worked valuation --------------------------------------------------

SEAM_HOLIDAYS: list[str] = list(FAR)
HEADERS = ("trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "payment_day")


@pytest.fixture(scope="module")
def syn() -> dict[str, Any]:
    """The synthetic index on the sheet, with its weekend-only calendar as the payment calendar,
    the bilateral and the cleared templates, and the ticket's two rows as a batch: 10,000 MMBtu of
    F27 at 2.65 each, one paying +2bd and one on 25 February 2027."""
    index, calendar = seam_index("SYN", list(CONTRACTS), SEAM_HOLIDAYS, [("MMBTU", 1.0)])
    fields = {**BILATERAL, "payment_holiday_key": seam_key(calendar)}
    bilateral_template = ENTRY["_CreateTradeTemplate"](
        "fixed_float", row(*fields), row(*fields.values())
    )
    cleared_fields = {**CLEARED, "payment_holiday_key": seam_key(calendar)}
    cleared_template = ENTRY["_CreateTradeTemplate"](
        "fixed_float", row(*cleared_fields), row(*cleared_fields.values())
    )
    body = rows(
        [1001.0, serial("2026-12-15"), "F27", 10_000.0, 2.65, "+2bd"],
        [1002.0, serial("2026-12-15"), "F27", 10_000.0, 2.65, serial("2027-02-25")],
    )
    trades = ENTRY["_CreateTrades"](index, row(*HEADERS), body, bilateral_template)
    return {
        "index": index,
        "calendar": calendar,
        "bilateral": bilateral_template,
        "cleared": cleared_template,
        "trades": trades,
    }


def a_curve(*anchors: tuple[str, float]) -> object:
    curve = ENTRY["_CreateDiscountCurve"](
        "SOFR",
        row("date", "discount_factor"),
        rows(*[[serial(d), f] for d, f in anchors]),
    )
    return curves_of(curve)


def valued_on(
    syn: dict[str, Any], as_of: str, settles: dict[str, float], curve: object, *quotes: float
) -> tuple[str, str, str]:
    history = a_history(syn["index"], "2026-10-29", as_of, SEAM_HOLIDAYS, settles)
    market = a_market(history, "SYN", *quotes)
    prepared = str(ENTRY["_PrepareTrades"](syn["trades"], history))
    return prepared, market, str(ENTRY["_EvaluateTrades"](prepared, market, curve))


def values_of(results: str) -> tuple[float, float]:
    line = spilled(ENTRY["_ReportValues"](results))[2]
    return cast(float, line[0]), cast(float, line[1])


def dv01_by_day(results: str) -> dict[float, float]:
    table = spilled(ENTRY["_ReportRisk"](results, "dv01", "day"))
    return {cast(float, line[0]): cast(float, line[1]) for line in table[4:]}


def test_the_two_rows_value_on_the_sheet_as_the_ticket_says(syn: dict[str, Any]) -> None:
    # Valued 15 December 2026 with F27 quoted 3.10: 4,500 undiscounted each; the +2bd row pays
    # Tuesday 2 February at 0.990, 4,455, and the dated row Thursday 25 February at 0.985,
    # 4,432.50; DV01 the ACT/365F fraction from the valuation day times each NPV, 49 and 72
    # days, both negative on these receivables, the dated row's the larger in size.
    curve = a_curve(("2026-12-15", 1.0), ("2027-02-02", 0.990), ("2027-02-25", 0.985))
    prepared, _, results = valued_on(syn, "2026-12-15", {}, curve, 3.00, 3.10)  # Z26 the prompt
    assert values_of(results) == (pytest.approx(8_887.5, **CLOSE), 0.0)
    by_day = dv01_by_day(results)
    assert by_day[serial("2027-02-02")] == pytest.approx(-49 / 365 * 4_455 / 10_000, **CLOSE)
    assert by_day[serial("2027-02-25")] == pytest.approx(-72 / 365 * 4_432.5 / 10_000, **CLOSE)
    # The batch reads back what each row entered, a date a date and a rule its text, beside the
    # day it resolved to; the column's type says so.
    table = spilled(ENTRY["util_ReadHandle"](syn["trades"]))
    at = table[0].index("payment_day")
    assert table[1][at] == "date or text"
    assert [line[at] for line in table[2:]] == ["+2bd", serial("2027-02-25")]
    resolved = table[0].index("payment_date")
    assert [line[resolved] for line in table[2:]] == [serial("2027-02-02"), serial("2027-02-25")]
    # The preparation's slots carry the resolved days alone, one slot per group here.
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    at = slots[0].index("payment_date")
    assert [line[at] for line in slots[2:]] == [serial("2027-02-02"), serial("2027-02-25")]


def test_after_the_fixing_the_ruled_row_is_cash_and_the_dated_row_waits(
    syn: dict[str, Any],
) -> None:
    # F27 settles 3.10 on its expiry; valued 3 February 2027 on a curve anchored that day, the
    # +2bd row has paid, 4,500 of cash and no mark, and the dated row is still unpaid, 4,500
    # on that day's factor to the 25th; neither has live exposure.
    settles = {"2027-01-29": 3.10}
    curve = a_curve(("2027-02-03", 1.0), ("2027-02-25", 0.99))
    _, _, results = valued_on(syn, "2027-02-03", settles, curve, 3.10)
    assert values_of(results) == (pytest.approx(4_455.0, **CLOSE), pytest.approx(4_500.0))
    assert dv01_by_day(results) == {
        serial("2027-02-02"): 0.0,  # paid: nothing left to discount
        serial("2027-02-25"): pytest.approx(-22 / 365 * 4_455 / 10_000),
    }
    total = spilled(ENTRY["_ReportRisk"](results, "nominal_delta", "year"))[3]
    assert total[1] == 0.0
    # The cutoff: the day before the date the payment is owed, on the date and after it cash.
    eve = a_curve(("2027-02-24", 1.0), ("2027-02-25", 0.9999))
    _, _, before = valued_on(syn, "2027-02-24", settles, eve, 3.10)
    assert values_of(before) == (pytest.approx(4_499.55, **CLOSE), pytest.approx(4_500.0))
    on = a_curve(("2027-02-25", 1.0), ("2027-03-25", 0.99))
    _, _, on_the_day = valued_on(syn, "2027-02-25", settles, on, 3.10)
    assert values_of(on_the_day) == (0.0, pytest.approx(9_000.0))
    assert set(dv01_by_day(on_the_day).values()) == {0.0}
    after = a_curve(("2027-02-26", 1.0), ("2027-03-26", 0.99))
    _, _, later = valued_on(syn, "2027-02-26", settles, after, 3.10)
    assert values_of(later) == (0.0, pytest.approx(9_000.0))


def test_a_cleared_strip_on_one_date_keeps_its_months_and_pays_them_together(
    syn: dict[str, Any],
) -> None:
    # CAL27 dated Tuesday 18 January 2028, cleared: twelve components quoted 3.10 against 2.65,
    # 54,000 of mark on 15 December 2026 and twelve contracts' exposure; after every month has
    # settled at 3.00, valued 20 January 2028, the twelve amounts are cash together, 42,000.
    body = rows([1001.0, serial("2026-12-15"), "CAL27", 10_000.0, 2.65, serial("2028-01-18")])
    trades = str(ENTRY["_CreateTrades"](syn["index"], row(*HEADERS), body, syn["cleared"]))
    batch = {**syn, "trades": trades}
    quotes = (3.00, *(3.10,) * 12)  # Z26 the prompt, then the twelve months
    prepared, _, results = valued_on(batch, "2026-12-15", {}, bridge.MISSING, *quotes)
    assert values_of(results) == (pytest.approx(54_000.0, **CLOSE), 0.0)
    table = spilled(ENTRY["util_ReadHandle"](prepared))
    at = table[0].index("payment_date")
    assert {line[at] for line in table[2:]} == {serial("2028-01-18")}
    assert len(table[2:]) == 12
    by_year = spilled(ENTRY["_ReportRisk"](results, "nominal_delta", "year"))
    assert by_year[3] == ["Total", 120_000.0]  # twelve months of 10,000 MMBtu, in lots of one
    _, _, paid = valued_on(batch, "2028-01-20", {}, bridge.MISSING, 3.10)
    assert values_of(paid) == (0.0, pytest.approx(42_000.0, **CLOSE))


def test_a_template_reads_back_its_day_or_its_rule(syn: dict[str, Any]) -> None:
    names = row(*BILATERAL, "payment_day")
    values = [v for k, v in BILATERAL.items() if k != "payment_holiday_key"]
    values.append(seam_key(syn["calendar"]))
    dated = ENTRY["_CreateTradeTemplate"]("fixed_float", names, row(*values, serial("2027-02-25")))
    table = spilled(ENTRY["util_ReadHandle"](dated))
    at = table[0].index("payment_day")
    assert (table[1][at], table[2][at]) == ("datetime64[D]", serial("2027-02-25"))
    ruled = ENTRY["_CreateTradeTemplate"]("fixed_float", names, row(*values, "+2bd"))
    table = spilled(ENTRY["util_ReadHandle"](ruled))
    assert (table[1][at], table[2][at]) == ("str", "+2bd")
    # The old header is a field of nothing, refused as any unknown header is.
    unknown = str(
        ENTRY["_CreateTradeTemplate"]("fixed_float", row("payment_time_lag"), row("+2bd"))
    )
    assert unknown.startswith(
        "#ERROR _CreateTradeTemplate: fields cell (1, 1) is text 'payment_time_lag', expected a "
        "field of fixed_float: "
    )


# --- the quote ------------------------------------------------------------------------------------

MAR_15 = "2027-03-15"
RATES_MAR = curve_set(curve_of((DEC_31, 1.0), (MAR_15, 0.98)))


def test_a_dated_quote_template_prices_the_strip_on_one_factor_that_cancels() -> None:
    # January 30 and February 60, equal month weights, one payment day at 0.98: the fair price
    # is 45, the factor cancelling, and the same strip booked at 45 on that day marks zero;
    # at 35, 10,000 a month, the mark is 200,000 discounted to 196,000.
    m = priced(STRIP, DEC_31, 3.0, 30.0, 60.0)
    template = bilateral(day=MAR_15)
    assert quote_on(m, "F27-G27", template, RATES_MAR) == pytest.approx(45.0, **CLOSE)
    counts = counts_of(m, "F27-G27", template, RATES_MAR)
    assert (counts["payment_rules_read"], counts["payment_shifts"]) == (0, 0)
    assert (counts["payment_days_made"], counts["payment_factors_read"]) == (2, 1)
    contract = np.array([1, 2], dtype=np.intp)
    for fixed, quantity, mark in ((45.0, 1.0, 0.0), (35.0, 10_000.0, 196_000.0)):
        terms = resolved_trades(
            FIXED_FLOAT,
            STRIP,
            spec(2),
            Route.BILATERAL,
            Settlement.FINANCIAL,
            *picks(ScheduleMethod.ASIAN, QuantityPer.MONTH, 2),
            one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, 2),
            np.ones(2, dtype=np.intp),
            ids(1, 2),
            None,
            None,
            dates(DEC_31, DEC_31),
            np.arange(2, dtype=np.intp),
            contract,
            numbers(quantity, quantity),
            *bounds_of(STRIP, contract),
            numbers(fixed, fixed),
            PaymentTerms(
                DatesOrTexts.of_dates(days(MAR_15, MAR_15)),
                (WEEKENDS_ONLY,) * 2,
                days(MAR_15, MAR_15),
            ),
            counterparty=("ACME Trading",) * 2,
            discount_curve_key=("SOFR",) * 2,
        )
        prep = prepared_trades(
            encoded(terms, (observed_of(terms),), UNITS, WorkCounter()),
            (m.market_history,),
            WorkCounter(),
        )
        result = trade_results(prep, (m,), WorkCounter(), RATES_MAR)
        assert result.mark == pytest.approx(mark, abs=1e-6)
    # A dated template serves any request whose last observation falls before its date, and
    # refuses one on or after it by the month.
    assert quote_on(m, "F27", bilateral(day="2027-02-20"), RATES_MAR) == pytest.approx(30.0)
    quote_refused(
        m,
        "G27",
        bilateral(day="2027-02-20"),
        "G27 pays on 2027-02-20, expected a day after its last observation, 2027-02-26, when its "
        "final price exists",
        RATES_MAR,
    )


def test_a_quote_template_takes_the_date_through_the_seam(syn: dict[str, Any]) -> None:
    fields = {
        "route": "cleared",
        "settlement_method": "financial",
        "schedule_method": "lastday",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "nearby": 1.0,
        "payment_day": serial("2027-03-15"),
        "payment_holiday_key": seam_key(syn["calendar"]),
    }
    template = ENTRY["_CreateQuoteTemplate"]("fixed_float", row(*fields), row(*fields.values()))
    history = a_history(syn["index"], "2026-10-29", "2026-12-15", SEAM_HOLIDAYS, {})
    market = a_market(history, "SYN", 3.00, 3.10, 3.20, 3.30)  # Z26 the prompt
    assert ENTRY["_Quote"](market, "F27", template, "flat", bridge.MISSING) == pytest.approx(3.10)
    assert ENTRY["_Quote"](market, "F27-G27", template, "flat", bridge.MISSING) == pytest.approx(
        3.15
    )
    assert ENTRY["_Quote"](market, "H27", template, "flat", bridge.MISSING) == (
        "#ERROR _Quote: ValueError: H27 pays on 2027-03-15, expected a day after its last "
        "observation, 2027-03-31, when its final price exists"
    )
