"""Type validation of tables: a header row and a mixed body, bound by name into typed columns."""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from goosedove.excel import bridge
from goosedove.excel.bridge import (
    MISSING,
    BooleanColumn,
    Cells,
    DateColumn,
    NumberArray,
    NumberColumn,
    Table,
    TextColumn,
    TextRow,
    excel_function,
)

cells = Cells.from_rows


# --- the schemas and functions of this file ----------------------------------


class Trades(Table):
    date: DateColumn
    product: TextColumn
    quantity: NumberColumn
    cleared: BooleanColumn


@excel_function
def TotalQuantity(header_row: TextRow, trades: Trades) -> float:
    return float(trades.quantity.sum())


@excel_function
def TradePayload(header_row: TextRow, trades: Trades) -> str:
    """Everything the record holds, so an assertion sees all of it, not a sum."""
    return (
        f"{trades.date.astype(str).tolist()} {trades.product!r} "
        f"{trades.quantity.tolist()} {trades.cleared.tolist()}"
    )


@excel_function
def HeadersAsTyped(header_row: TextRow, trades: Trades) -> str:
    """The header row reaches the function as the tuple it is; the record does not carry it."""
    return ", ".join(header_row)


class Flag(Table):
    cleared: BooleanColumn


@excel_function
def AnyCleared(header_row: TextRow, flags: Flag) -> bool:
    return bool(flags.cleared.any())


class Pair(Table):
    a: NumberColumn
    b: NumberColumn


@excel_function
def SumPair(header_row: TextRow, pair: Pair) -> float:
    return float(pair.a.sum() + pair.b.sum())


class Labels(Table):
    left: TextColumn
    middle: NumberColumn
    right: TextColumn


@excel_function
def JoinLabels(header_row: TextRow, labels: Labels) -> str:
    return " ".join(labels.left) + " | " + " ".join(labels.right)


# The toy table of the alignment note: a date, a text, a number and a flag per trade.
HEADERS = cells([["date", "product", "quantity", "cleared"]])
TRADES = cells(
    [
        [46276.0, "CL", 10.0, True],  # 11-Sep-2026
        [46277.0, "NG", 3.5, False],
        [46280.0, "CL", 7.0, True],
    ]
)
PAYLOAD = (
    "['2026-09-11', '2026-09-12', '2026-09-15'] ('CL', 'NG', 'CL') [10.0, 3.5, 7.0] "
    "[True, False, True]"
)
MIXED = "number, nonempty text or boolean"
ONE_OF = "expected one of date, product, quantity or cleared"
ERROR = "#ERROR TotalQuantity: "


# --- what passes, and what the function receives ---------------------------


def test_the_toy_table_sums_its_quantity_column() -> None:
    assert bridge.call("TotalQuantity", [HEADERS, TRADES]) == 20.5


def test_every_column_arrives_typed_and_aligned() -> None:
    assert bridge.call("TradePayload", [HEADERS, TRADES]) == PAYLOAD


def test_columns_bind_by_name_in_any_order() -> None:
    headers = cells([["cleared", "quantity", "product", "date"]])
    body = cells(
        [
            [True, 10.0, "CL", 46276.0],
            [False, 3.5, "NG", 46277.0],
            [True, 7.0, "CL", 46280.0],
        ]
    )
    assert bridge.call("TradePayload", [headers, body]) == PAYLOAD


def test_case_is_ignored_in_a_header() -> None:
    headers = cells([["DATE", "Product", "quantity", "CLEARED"]])
    assert bridge.call("TotalQuantity", [headers, TRADES]) == 20.5


def test_the_header_row_reaches_the_function_as_typed() -> None:
    headers = cells([["DATE", "Product", "quantity", "CLEARED"]])
    assert bridge.call("HeadersAsTyped", [headers, TRADES]) == "DATE, Product, quantity, CLEARED"


def test_a_scalar_header_and_a_scalar_body_are_a_one_cell_table() -> None:
    assert bridge.call("AnyCleared", ["cleared", True]) is True
    assert bridge.call("AnyCleared", ["CLEARED", False]) is False


def test_a_table_may_hold_two_columns_of_text() -> None:
    headers = cells([["product", "date", "quantity", "cleared"]])
    body = cells([["CL", 46276.0, 10.0, True], ["NG", 46277.0, 3.5, False]])
    assert bridge.call("TradePayload", [headers, body]) == (
        "['2026-09-11', '2026-09-12'] ('CL', 'NG') [10.0, 3.5] [True, False]"
    )


# --- messages, exactly: the headers, then the cells as INDEX counts within the body --------


@pytest.mark.parametrize(
    ("headers", "body", "text"),
    [
        (
            cells([["date", "ticker", "quantity", "cleared"]]),
            TRADES,
            f"{ERROR}header_row cell (1, 2) is text 'ticker', {ONE_OF}",
        ),
        (
            cells([["date", "date", "quantity", "cleared"]]),
            TRADES,
            f"{ERROR}header_row cell (1, 2) is text 'date', already given at cell (1, 1)",
        ),
        (
            cells([["date", "DATE", "quantity", "cleared"]]),
            TRADES,
            f"{ERROR}header_row cell (1, 2) is text 'DATE', already given at cell (1, 1)",
        ),
        (
            cells([["date", "product", "quantity"]]),
            TRADES,
            f"{ERROR}header_row has 3 headers, expected 4, one per column of trades",
        ),
        (
            cells([["date", "product", "cleared"]]),
            cells([[46276.0, "CL", True]]),
            f"{ERROR}header_row has no quantity, expected date, product, quantity and cleared",
        ),
        # Whitespace is not forgiven: a header is text as typed, and the message quotes it.
        (
            cells([[" date", "product", "quantity", "cleared"]]),
            TRADES,
            f"{ERROR}header_row cell (1, 1) is text ' date', {ONE_OF}",
        ),
        (HEADERS, 5.0, f"{ERROR}header_row has 4 headers, expected 1, one per column of trades"),
        (
            HEADERS,
            cells([[46276.0, "CL", 10.0, True], [46277.5, "NG", 3.5, False]]),
            f"{ERROR}trades cell (2, 1) is number 46277.5, expected date",
        ),
        (
            HEADERS,
            cells([[46276.0, "CL", 10.0, True], ["12-Sep-2026", "NG", 3.5, False]]),
            f"{ERROR}trades cell (2, 1) is text '12-Sep-2026', expected date",
        ),
        (
            HEADERS,
            cells([[60.0, "CL", 10.0, True]]),
            f"{ERROR}trades cell (1, 1) is number 60.0, expected date",
        ),
        (
            HEADERS,
            cells([[True, "CL", 10.0, True]]),
            f"{ERROR}trades cell (1, 1) is boolean TRUE, expected date",
        ),
        (
            HEADERS,
            cells([[46276.0, "CL", True, True]]),
            f"{ERROR}trades cell (1, 3) is boolean TRUE, expected number",
        ),
        (
            HEADERS,
            cells([[46276.0, "CL", "10", True]]),
            f"{ERROR}trades cell (1, 3) is text '10', expected number",
        ),
        (
            HEADERS,
            cells([[46276.0, 7.0, 10.0, True]]),
            f"{ERROR}trades cell (1, 2) is number 7.0, expected text",
        ),
        (
            HEADERS,
            cells([[46276.0, "CL", 10.0, True], [46277.0, "NG", 3.5, 1.0]]),
            f"{ERROR}trades cell (2, 4) is number 1.0, expected boolean",
        ),
        (
            HEADERS,
            cells([[46276.0, "CL", 10.0, "TRUE"]]),
            f"{ERROR}trades cell (1, 4) is text 'TRUE', expected boolean",
        ),
        # The mixed rule admits the body before any header is read, with its own words.
        (
            HEADERS,
            cells(
                [
                    [46276.0, "CL", 10.0, True],
                    [46277.0, "NG", 3.5, False],
                    [46280.0, None, 7.0, True],
                ]
            ),
            f"{ERROR}trades cell (3, 2) is blank, expected {MIXED}",
        ),
        (
            HEADERS,
            cells([[46276.0, "", 10.0, True]]),
            f"{ERROR}trades cell (1, 2) is empty text, expected {MIXED}",
        ),
        (HEADERS, None, f"{ERROR}trades is blank, expected table"),
        (HEADERS, MISSING, f"{ERROR}trades is missing, expected table"),
        (HEADERS, "", f"{ERROR}trades is empty text, expected table"),
        # The header row is a row of text first, as it is for any function.
        (
            cells([["date"], ["product"]]),
            TRADES,
            f"{ERROR}header_row is 2x1 array, expected row of text",
        ),
        (
            cells([["date", 2.0, "quantity", "cleared"]]),
            TRADES,
            f"{ERROR}header_row cell (1, 2) is number 2.0, expected text",
        ),
        (MISSING, TRADES, f"{ERROR}header_row is missing, expected row of text"),
    ],
)
def test_rejected(headers: object, body: object, text: str) -> None:
    assert bridge.call("TotalQuantity", [headers, body]) == text


# --- precedence: each argument alone, then the headers, then the columns in sheet order ----


def test_each_argument_is_checked_alone_before_the_headers_are_read() -> None:
    # A blank in the body is the mixed rule's failure, reported before the unknown header.
    headers = cells([["date", "ticker", "quantity", "cleared"]])
    body = cells([[46276.0, None, 10.0, True]])
    assert bridge.call("TotalQuantity", [headers, body]) == (
        f"{ERROR}trades cell (1, 2) is blank, expected {MIXED}"
    )
    # And a header row that is not a row of text is reported before the body is looked at.
    headers = cells([["date", 2.0, "quantity", "cleared"]])
    assert bridge.call("TotalQuantity", [headers, body]) == (
        f"{ERROR}header_row cell (1, 2) is number 2.0, expected text"
    )


def test_the_headers_are_read_before_any_column_is() -> None:
    headers = cells([["date", "ticker", "quantity", "cleared"]])
    body = cells([[46276.5, "CL", True, 1.0]])  # every column is wrong, and none is named
    assert bridge.call("TotalQuantity", [headers, body]) == (
        f"{ERROR}header_row cell (1, 2) is text 'ticker', {ONE_OF}"
    )


def test_the_count_is_checked_before_any_header_name() -> None:
    headers = cells([["ticker", "product", "quantity"]])
    assert bridge.call("TotalQuantity", [headers, TRADES]) == (
        f"{ERROR}header_row has 3 headers, expected 4, one per column of trades"
    )


def test_columns_are_checked_in_sheet_order_and_a_column_from_the_top() -> None:
    # (3, 1) is named before (1, 2): the earlier column wins whatever its row.
    body = cells([[46276.0, 5.0, 10.0, True], [46277.0, "NG", 3.5, False], ["x", "CL", 7.0, True]])
    assert bridge.call("TotalQuantity", [HEADERS, body]) == (
        f"{ERROR}trades cell (3, 1) is text 'x', expected date"
    )


@given(rows=st.integers(1, 8), data=st.data())
def test_the_earliest_column_wins_and_within_it_the_earliest_row(
    rows: int, data: st.DataObject
) -> None:
    first = data.draw(st.tuples(st.integers(0, rows - 1), st.integers(0, 1)))
    second = data.draw(st.tuples(st.integers(0, rows - 1), st.integers(0, 1)))
    assume(first != second)
    grid: list[list[object]] = [[1.0, 2.0] for _ in range(rows)]
    for r, c in (first, second):
        grid[r][c] = "x"
    c, r = min((first[1], first[0]), (second[1], second[0]))  # column first, then row
    assert bridge.call("SumPair", [cells([["a", "b"]]), cells(grid)]) == (
        f"#ERROR SumPair: pair cell ({r + 1}, {c + 1}) is text 'x', expected number"
    )


# Each text cell must reach the column it sits in, whatever text sits in other columns, so the
# k-th text of the body is never mistaken for a column's k-th cell.
@given(rows=st.integers(1, 8), data=st.data())
def test_a_column_of_text_keeps_its_own_texts_whatever_sits_beside_it(
    rows: int, data: st.DataObject
) -> None:
    word = st.text(alphabet="ab", min_size=1, max_size=3)
    lefts = data.draw(st.lists(word, min_size=rows, max_size=rows))
    rights = data.draw(st.lists(word, min_size=rows, max_size=rows))
    order = data.draw(st.permutations(["left", "middle", "right"]))
    columns: dict[str, list[object]] = {
        "left": list(lefts),
        "middle": [1.0] * rows,
        "right": list(rights),
    }
    body = cells([[columns[name][r] for name in order] for r in range(rows)])
    assert bridge.call("JoinLabels", [cells([order]), body]) == (
        " ".join(lefts) + " | " + " ".join(rights)
    )


# --- the declaration itself is checked at registration ----------------------


def test_a_table_with_no_row_of_text_before_it_refuses_to_register() -> None:
    def Bare(trades: Trades) -> float:
        return 0.0

    with pytest.raises(
        TypeError,
        match="Bare: trades declares a table with no row of text before it to hold its headers",
    ):
        excel_function(Bare)

    def Mislabelled(header_row: NumberColumn, trades: Trades) -> float:
        return 0.0

    with pytest.raises(TypeError, match="Mislabelled: trades declares a table with no row"):
        excel_function(Mislabelled)


def test_a_schema_column_that_is_not_a_column_type_refuses_to_register() -> None:
    class Wide(Table):
        values: NumberArray

    def Grid2(header_row: TextRow, wide: Wide) -> float:
        return 0.0

    with pytest.raises(
        TypeError,
        match=r"Grid2: wide column values declares goosedove\.excel\.bridge\.NumberArray, "
        r"which is not a column type",
    ):
        excel_function(Grid2)


def test_two_schema_columns_that_are_one_header_refuse_to_register() -> None:
    class Shouting(Table):
        date: DateColumn
        Date: NumberColumn

    def Loud(header_row: TextRow, table: Shouting) -> float:
        return 0.0

    with pytest.raises(
        TypeError, match="Loud: table declares columns date and Date, which are one header"
    ):
        excel_function(Loud)


def test_a_schema_with_no_columns_refuses_to_register() -> None:
    class Empty(Table):
        pass

    def Hollow(header_row: TextRow, table: Empty) -> float:
        return 0.0

    with pytest.raises(TypeError, match="Hollow: table declares a table with no columns"):
        excel_function(Hollow)


def test_the_bare_table_class_is_not_a_declared_type() -> None:
    def Plain(header_row: TextRow, table: Table) -> float:
        return 0.0

    with pytest.raises(
        TypeError, match=r"Plain: table declares <class 'goosedove\.excel\.bridge\.Table'>"
    ):
        excel_function(Plain)


def test_a_table_may_be_taken_but_not_returned() -> None:
    def OutTable() -> Trades:
        raise AssertionError("never called")

    with pytest.raises(
        TypeError, match=r"OutTable declares <class '.*Trades'> as its result, which the seam"
    ):
        excel_function(OutTable)
