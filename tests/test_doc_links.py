"""Local documentation links resolve and fragments name headings: `tools/check_doc_links.py`, run
here so that `check.ps1` and CI fail on a broken reference. The fixtures are small repositories
made with `git init` and `git add`, since the checker's view is the working tree of the
Git-indexed files; the last test is the repository itself."""

import subprocess
from pathlib import Path

import check_doc_links as checker
from check_doc_links import check, slug


def repository(root: Path, files: dict[str, str]) -> None:
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
            "docs/a.md": "# A\n\n[up](../README.md) [self](a.md) [dot](./a.md) [top](/)",
            "docs/img/p.png": "not really a png",
        },
    )
    assert failures(tmp_path) == []


def test_fragments_follow_github_anchors(tmp_path: Path) -> None:
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
        "a.md:2: unknown fragment: b.md#repeat-2",
        "a.md:2: unknown fragment: b.md#what-each-page-owns",
    ]


def test_formatting_leaves_the_anchor_and_a_literal_underscore_stays(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "# A _helpful_ section\n\n## The `fixed_float` and **bold**\n\n"
            "[ok](#a-helpful-section) [bad](#a-_helpful_-section) [u](#the-fixed_float-and-bold)",
        },
    )
    assert failures(tmp_path) == ["a.md:5: unknown fragment: #a-_helpful_-section"]


def test_generated_anchors_stay_unique(tmp_path: Path) -> None:
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


def test_reference_links_and_explicit_anchors(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "[full][one] [collapsed][] [one] [not a link] [bad][two]\n\n"
            "[one]: b.md#here\n[collapsed]: b.md\n[two]:\n  nowhere.md\n",
            "b.md": '<a class="anchor" id="here"></a>\n\n# Top\n\n'
            '<a name="here"></a>\n\n<a href="x" id="top"></a>\n',
        },
    )
    assert failures(tmp_path) == [
        "a.md:1: missing tracked target (definition at line 5): nowhere.md",
        "b.md:5: duplicate explicit anchor 'here' (first at line 1): here",
        "b.md:7: explicit anchor 'top' collides with a heading's anchor (line 3): top",
    ]


def test_a_link_wrapped_over_two_lines_is_still_a_link(tmp_path: Path) -> None:
    repository(tmp_path, {"a.md": "Some words, then a [link](\nmissing.md) and more.\n"})
    assert failures(tmp_path) == ["a.md:1: missing tracked target: missing.md"]


def test_missing_renamed_and_wrongly_cased_targets_fail(tmp_path: Path) -> None:
    repository(tmp_path, {"a.md": "[x](b.md) [y](B.md) [z](docs/) [w](../out.md)", "b.md": "# B"})
    found = failures(tmp_path)  # in path, line and destination order
    assert found[0] == "a.md:1: path escapes the repository: ../out.md"
    assert found[1].startswith("a.md:1: missing tracked target") and found[1].endswith(": B.md")
    assert found[2] == "a.md:1: missing tracked target: docs/"
    assert len(found) == 3


def test_an_untracked_target_counts_once_it_is_added(tmp_path: Path) -> None:
    repository(tmp_path, {"a.md": "[x](c.md)"})
    put(tmp_path, {"c.md": "# C"})
    assert failures(tmp_path) == [
        "a.md:1: missing tracked target (exists on disk but is not tracked by git): c.md"
    ]
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
    assert failures(tmp_path) == ["a.md:1: unknown fragment: odd%23name.md#a-b -> odd#name.md"]


def test_code_comments_and_external_links_are_not_checked(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {
            "a.md": "```\n[x](gone.md)\n# In code\n```\n\n"
            "    [y](gone.md)\n\n"
            "> ```\n> [q](gone.md)\n> ```\n\n"
            "`[z](gone.md)` and text\n"
            "<!-- [w](gone.md)\n```\n# Commented -->\n"
            "[ext](https://example.invalid/missing) [mail](mailto:x@y.z) <https://a.b/c>\n"
            "[k](#in-code) [c](#commented) [real](gone.md)",
        },
    )
    assert failures(tmp_path) == [
        "a.md:17: unknown fragment: #commented",
        "a.md:17: unknown fragment: #in-code",
        "a.md:17: missing tracked target: gone.md",
    ]


def test_machine_specific_paths_are_not_repository_links(tmp_path: Path) -> None:
    repository(
        tmp_path,
        {"a.md": "[d](C:/x/b.md) [u](\\\\server\\share\\b.md) [f](file:///x/b.md) [bs](sub\\b.md)"},
    )
    assert [fault.reason for fault in check(tmp_path)[0]] == [
        "machine-specific path, not a repository link",
        "machine-specific path, not a repository link",
        "file: URL, not a repository link",
        "backslash in a path, which GitHub reads as a character",
    ]


def test_decision_numbers_are_unique_in_the_two_decided_sections(tmp_path: Path) -> None:
    decided = (
        "## Decided\n\n1. One.\n2. Two.\n2. Two again.\n\n```\n2. in code\n```\n\n"
        "## Steps\n\n1. a\n1. b\n"
    )
    repository(
        tmp_path,
        {
            "docs/seam/inputs.md": decided,
            "docs/seam/outputs.md": "## Decided\n\n3. Three.\n\n## Repeat\n\n## Repeat\n",
            "docs/other.md": "## Decided\n\n1. x\n1. y\n",
        },
    )
    assert failures(tmp_path) == [
        "docs/seam/inputs.md:5: duplicate decision number 2 (first at line 4): 2"
    ]


def test_an_exception_excuses_one_failure_and_an_unused_one_fails(tmp_path: Path) -> None:
    exceptions = (
        '[[exception]]\nsource = "docs/old.md"\ndestination = "../gone/page.md"\n'
        'reason = "frozen record of a page removed in September"\n\n'
        '[[exception]]\nsource = "docs/old.md"\ndestination = "also-gone.md"\nreason = "stale"\n'
    )
    repository(
        tmp_path,
        {
            "docs/old.md": "[a](../gone/page.md) [b](../gone/page.md)",
            "tools/doc_link_exceptions.toml": exceptions,
        },
    )
    assert failures(tmp_path) == [
        "tools/doc_link_exceptions.toml:0: unused exception for 'also-gone.md' (stale): docs/old.md"
    ]


def test_the_repository_itself() -> None:
    faults, followed = check(checker.ROOT)
    assert faults == []
    assert followed > 1000
