"""Two rules may not share a decision number: the top-level items of the Decided section of
`docs/seam/inputs.md` and of `docs/seam/outputs.md` each keep their numbers unique within that
section of that file, the convention two rules numbered 43 once broke. A new rule takes a named
section instead; this holds the numbers that exist. Apart from the link check on purpose."""

from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("docs/seam/inputs.md", "docs/seam/outputs.md")
MARKDOWN = MarkdownIt("commonmark")


def decision_items(text: str) -> list[tuple[int, str]]:
    """The line and the written number of each top-level ordered item inside the Decided section,
    as the parser reads them: a nested item, a number in code or a comment, and a numbered step
    under another heading are not decisions."""
    tokens = MARKDOWN.parse(text)
    items: list[tuple[int, str]] = []
    inside = False
    top_level_list = False
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h2":
            inside = tokens[index + 1].content.strip() == "Decided"
        elif token.type == "ordered_list_open" and token.level == 0:
            top_level_list = True
        elif token.type == "ordered_list_close" and token.level == 0:
            top_level_list = False
        elif inside and top_level_list and token.type == "list_item_open" and token.level == 1:
            items.append(((token.map or [0])[0] + 1, token.info))
    return items


def duplicates(text: str) -> list[str]:
    first: dict[str, int] = {}
    found: list[str] = []
    for line, number in decision_items(text):
        if number in first:
            found.append(f"decision {number} at lines {first[number]} and {line}")
        else:
            first[number] = line
    return found


def test_the_two_pages_have_unique_decision_numbers() -> None:
    for page in PAGES:
        text = (ROOT / page).read_text(encoding="utf-8")
        assert decision_items(text), page
        assert duplicates(text) == [], page


def test_a_duplicate_is_reported_with_both_lines() -> None:
    text = "## Decided\n\n1. One.\n2. Two.\n\nA paragraph between.\n\n2. Two again.\n"
    assert duplicates(text) == ["decision 2 at lines 4 and 8"]


def test_gaps_nested_items_code_comments_and_other_sections_are_not_duplicates() -> None:
    text = (
        "## Steps\n\n1. a\n1. b\n\n"
        "## Decided\n\n1. One.\n3. Three, after a gap.\n   1. nested\n   1. nested again\n\n"
        "```\n1. in code\n```\n\n<!--\n1. in a comment\n-->\n\n"
        "## Parked\n\n1. x\n1. y\n"
    )
    assert decision_items(text) == [(8, "1"), (9, "3")]
    assert duplicates(text) == []
