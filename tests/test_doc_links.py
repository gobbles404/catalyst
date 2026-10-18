"""Local documentation links resolve and fragments name headings: `tools/check_doc_links.py`, run
here so that `check.ps1` and CI fail on a broken reference. The fixtures are small repositories
made with `git init` and `git add`, since the checker's view is the working tree of the
Git-indexed files, and each states its expected answer outright; the last test is the repository
itself. Source ZIPs have no Git index, so that last check is explicitly skipped there. Fixtures
need the Git executable and skip if it is absent; the parser-only tests still run."""

import shutil
import subprocess
from pathlib import Path

import check_doc_links as checker
import pytest
from check_doc_links import check, slug


def repository(root: Path, files: dict[str, str]) -> None:
    if shutil.which("git") is None:
        pytest.skip("Git is not installed; this fixture tests Git-indexed documentation")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    put(root, files)
    stage(root)


def put(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")


def stage(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)


def failures(root: Path) -> list[str]:
    return [str(fault) for fault in check(root)[0]]


def test_existing_files_directories_images_and_root_paths_pass(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "README.md": "[a](docs/a.md) [dir](docs/) [root](/docs/a.md) "
            "![i](docs/img/p.png) [r](/)",
            "docs/a.md": "# A\n\n[up](../README.md) [self](a.md) [dot](./a.md) [top](/)\n\n"
            "- a list item with a [link](../README.md)\n\n> a quote with a [link](a.md#a)",
            "docs/img/p.png": "not really a png",
        },
    )
    assert failures(tmp_path) == []


def test_fragments_follow_github_identifiers(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "b.md": "# 10. What *each* page owns\n\n## Repeat\n\n## Repeat\n\n"
            "## See [inputs](a.md), then `code`!\n\n"
            "[same](#repeat-1) [same](#see-inputs-then-code)",
            "a.md": "[x](b.md#10-what-each-page-owns) [y](b.md#repeat) [z](b.md#repeat-1)\n"
            "[gone](b.md#repeat-2) [renamed](b.md#what-each-page-owns)",
        },
    )
    assert failures(tmp_path) == [
        "a.md:1: unknown fragment: b.md#repeat-2",
        "a.md:1: unknown fragment: b.md#what-each-page-owns",
    ]


def test_formatting_leaves_the_identifier_and_a_literal_underscore_stays(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "# A _helpful_ section\n\n## The `fixed_float` and **bold**\n\n"
            "[ok](#a-helpful-section) [bad](#a-_helpful_-section) [u](#the-fixed_float-and-bold)",
        },
    )
    assert failures(tmp_path) == ["a.md:5: unknown fragment: #a-_helpful_-section"]


def test_generated_identifiers_stay_unique(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {"a.md": "# Foo\n\n# Foo\n\n# Foo-1\n\n[a](#foo) [b](#foo-1) [c](#foo-1-1) [d](#foo-2)"},
    )
    assert failures(tmp_path) == ["a.md:7: unknown fragment: #foo-2"]


def test_slug_matches_github() -> None:
    assert slug("10. What each page owns") == "10-what-each-page-owns"
    assert slug("NUL in input text") == "nul-in-input-text"
    assert slug("As built, #163") == "as-built-163"
    assert slug("a_b and c (d)") == "a_b-and-c-d"


def test_reference_links_resolve_through_their_definitions(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "[full][one] [collapsed][] [one] [not a link] [bad][two]\n\n"
            "[one]: b.md#here\n[collapsed]: b.md\n[two]:\n  nowhere.md\n",
            "b.md": '<a class="anchor" id="here"></a>\n',
        },
    )
    assert failures(tmp_path) == ["a.md:1: missing target: nowhere.md"]


def test_the_first_definition_wins_inside_a_quote_or_a_list(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "> [ref]: first.md\n\n- [ref]: second.md\n\n[ref] and [again][ref]\n",
            "first.md": "",
        },
    )
    assert failures(tmp_path) == []


def test_a_definition_inside_a_comment_is_not_a_definition(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "Intro <!--\n[ref]: target.md\n-->\n\n[ref]\n\n[ref]: missing.md\n",
            "target.md": "",
        },
    )
    assert failures(tmp_path) == ["a.md:5: missing target: missing.md"]


def test_a_link_wrapped_over_two_lines_is_still_a_link(tmp_path: Path) -> None:
    repository(tmp_path, {"a.md": "Some words, then a [link](\nmissing.md) and more.\n"})
    assert failures(tmp_path) == ["a.md:1: missing target: missing.md"]


def test_explicit_anchors_by_attribute_whatever_the_order(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "b.md": '<a class="anchor" id="here"></a>\n\n# Top\n\n<a name="here"></a>\n\n'
            '<a href="x" id="top"></a>\n\n<a title="a>b" id="quoted"></a>\n\n'
            '<a data-id="wrong" id="right"></a>\n\n<!-- <a id="commented"></a> -->\n',
            "a.md": "[q](b.md#quoted) [r](b.md#right) [w](b.md#wrong) [c](b.md#commented)",
        },
    )
    assert failures(tmp_path) == [
        "a.md:1: unknown fragment: b.md#commented",
        "a.md:1: unknown fragment: b.md#wrong",
        "b.md:5: duplicate explicit anchor 'here' (first at line 1): here",
        "b.md:7: explicit anchor 'top' shadows the heading at line 3: top",
    ]


def test_missing_wrongly_cased_and_escaping_targets_fail(tmp_path: Path) -> None:
    repository(tmp_path, {"a.md": "[x](b.md) [y](B.md) [z](docs/) [w](../out.md)", "b.md": "# B"})
    assert failures(tmp_path) == [
        "a.md:1: path escapes the repository: ../out.md",
        "a.md:1: wrong case, tracked as b.md: B.md",
        "a.md:1: missing target: docs/",
    ]


def test_an_untracked_target_counts_once_it_is_added(tmp_path: Path) -> None:
    repository(tmp_path, {"a.md": "[x](c.md)"})
    put(tmp_path, {"c.md": "# C"})
    assert failures(tmp_path) == ["a.md:1: missing target (untracked on disk): c.md"]
    stage(tmp_path)
    assert failures(tmp_path) == []


def test_the_working_tree_text_is_read_never_a_stale_blob(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "[x](b.md#old-name) [y](c.md) [d](sub/)",
            "b.md": "# Old name",
            "c.md": "",
            "sub/s.md": "",
        },
    )
    assert failures(tmp_path) == []
    put(tmp_path, {"b.md": "# New name"})
    (tmp_path / "c.md").unlink()
    (tmp_path / "sub" / "s.md").unlink()
    (tmp_path / "sub").rmdir()
    assert failures(tmp_path) == [
        "a.md:1: unknown fragment: b.md#old-name",
        "a.md:1: tracked target is deleted in the working tree: c.md",
        "a.md:1: tracked directory is deleted in the working tree: sub/",
    ]


def test_encoded_and_bracketed_destinations(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "[s](my%20page.md#a-b) [t](<my page.md>) [q](my%20page.md?v=1#a-b) "
            "[h](odd%23name.md) [bad](odd%23name.md#a-b)",
            "my page.md": "# A b",
            "odd#name.md": "# Odd",
        },
    )
    assert failures(tmp_path) == ["a.md:1: unknown fragment: odd%23name.md#a-b"]


def test_code_comments_undefined_references_and_external_links_are_not_links(
    tmp_path: Path,
) -> None:
    repository(
        tmp_path,
        {
            "a.md": "```\n[x](gone.md)\n# In code\n```\n\n"
            "    [y](gone.md)\n\n"
            "> ```\n> [q](gone.md)\n> ```\n\n"
            "`[z](gone.md)` and text\n"
            "<!-- [w](gone.md)\n```\n# Commented -->\n"
            "[ext](https://example.invalid/missing) [mail](mailto:x@y.z) <https://a.b/c>\n"
            "[k](#in-code) [c](#commented) [real](gone.md) [undefined] [also][nope]",
        },
    )
    assert failures(tmp_path) == [
        "a.md:16: unknown fragment: #commented",
        "a.md:16: unknown fragment: #in-code",
        "a.md:16: missing target: gone.md",
    ]


def test_machine_specific_destinations_are_not_repository_links(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {"a.md": "[d](C:/x/b.md) [u](\\\\server\\share\\b.md) [f](file:///x/b.md) [bs](sub\\b.md)"},
    )
    # three: the parser renders a file: destination as text, so it is no link to check
    assert [fault.reason for fault in check(tmp_path)[0]] == ["not a portable repository link"] * 3


def test_the_repository_itself() -> None:
    # A worktree has a .git file, a clone a directory, and a source ZIP neither. Check this
    # root rather than asking Git, which could discover an unrelated repository above a ZIP.
    if not (checker.ROOT / ".git").exists():
        pytest.skip("Git metadata is absent in a source ZIP; repository links are checked in CI")
    faults, followed = check(checker.ROOT)
    assert faults == []
    assert followed > 1000
