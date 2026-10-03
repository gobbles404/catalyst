"""The complete Excel table -> retained trade columns -> spilled table path."""

import pytest
from test_futures_trades import NG
from test_utilities import read, rows

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
from goosedove.index_definitions.index import Index

HEADINGS = ["trade_id", "trade_date", "contract_code", "signed_lots", "trade_price"]
HEADER = Cells.from_rows([HEADINGS])
# 24 and 25 September 2026, represented exactly as Excel supplies date cells.
BODY: list[list[object]] = [
    ["NG-001", 46289.0, "Z26", 10.0, 3.100],
    ["NG-002", 46289.0, "Z26", -4.0, 3.150],
    ["NG-003", 46290.0, "F27", 7.0, 3.400],
    ["NG-004", 46290.0, "F27", -12.0, 3.350],
]


@probe
def FuturesTradesTestIndex() -> Handle[Index]:
    return NG


def create(body: Cells, header: Cells = HEADER, specification: str = "NYMEX NG") -> object:
    index = bridge.call("FuturesTradesTestIndex", [])
    return bridge.call("_CreateFuturesTrades", [index, specification, header, body])


def test_one_row_and_four_rows_follow_the_same_creator_and_reader() -> None:
    many = create(Cells.from_rows(BODY))
    assert isinstance(many, str) and many.startswith("futures_trades:Henry Hub NYMEX:")
    table = rows(read(many))
    assert table == [
        [*HEADINGS, "contract_position"],
        ["str", "datetime64[D]", "str", "float64", "float64", "intp"],
        *[[*row, position] for row, position in zip(BODY, [0.0, 0.0, 1.0, 1.0], strict=True)],
    ]
    for i, row in enumerate(BODY):
        one = rows(read(create(Cells.from_rows([row]))))
        assert one == [*table[:2], table[i + 2]]


def test_header_binding_preserves_meaning_in_another_column_order() -> None:
    order = [4, 2, 0, 3, 1]
    header = Cells.from_rows([[HEADINGS[i].upper() for i in order]])
    body = Cells.from_rows([[row[i] for i in order] for row in BODY])
    assert rows(read(create(body, header))) == rows(read(create(Cells.from_rows(BODY))))


def test_host_buffer_reuse_cannot_change_a_published_trade() -> None:
    body = Cells.from_rows(BODY)
    made = create(body)
    before = rows(read(made))
    body.numbers[:] = 1.0
    assert rows(read(made)) == before


def test_duplicate_rows_survive_the_excel_path() -> None:
    table = rows(read(create(Cells.from_rows([BODY[0], BODY[0]]))))
    assert table[2:] == [[*BODY[0], 0.0], [*BODY[0], 0.0]]


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        (0, None, "table cell (1, 1) is blank, expected number, nonempty text or boolean"),
        (1, "2026-09-24", "table cell (1, 2) is text '2026-09-24', expected date"),
        (3, True, "table cell (1, 4) is boolean TRUE, expected number"),
        (4, "3.100", "table cell (1, 5) is text '3.100', expected number"),
        (3, 0.0, "ValueError: signed_lots row 1 is 0.0, expected nonzero lots"),
        (3, -0.5, "ValueError: signed_lots row 1 is -0.5, expected a whole number"),
        (
            2,
            "G27",
            "ValueError: contract_code row 1 is 'G27', expected a code in the index's schedule",
        ),
    ],
)
def test_bad_cells_fail_visibly(column: int, value: object, message: str) -> None:
    row = BODY[0].copy()
    row[column] = value
    assert create(Cells.from_rows([row])) == f"#ERROR _CreateFuturesTrades: {message}"


def test_blank_and_missing_arguments_stay_distinct() -> None:
    index = bridge.call("FuturesTradesTestIndex", [])
    for value, word in [(None, "blank"), (MISSING, "missing")]:
        result = bridge.call("_CreateFuturesTrades", [index, value, HEADER, Cells.from_rows(BODY)])
        assert (
            result
            == f"#ERROR _CreateFuturesTrades: contract_specification is {word}, expected text"
        )


def test_an_invalid_specification_fails_in_the_librarys_words() -> None:
    assert create(Cells.from_rows(BODY), specification="ICE NG") == (
        "#ERROR _CreateFuturesTrades: ValueError: contract_specification is 'ICE NG', "
        "expected a name in the index's specifications"
    )
