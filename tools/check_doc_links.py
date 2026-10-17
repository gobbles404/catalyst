"""Every local link in the repository's Markdown resolves, and every fragment names a heading.

Run `uv run python tools/check_doc_links.py` from anywhere; `tests/test_doc_links.py` runs the
same check under pytest, so `check.ps1` and CI fail on a broken reference. The view is the working
tree of the Git-indexed files: `git ls-files` says which files exist, and their text is read from
disk, so an edit saved but not committed is seen, a staged new file counts, and a file that exists
only untracked, ignored or in another checkout is a missing target. Section 11 of
docs/seam/working.md is the usage contract.

Who reads what. markdown-it-py, a development dependency, reads the Markdown: which links, images
and reference links a page has, which definition a reference resolves to, what is code or a
comment, and what a heading says are the parser's to decide. The standard library's HTML parser
reads the HTML the Markdown parser found, for the explicit anchors. This module owns the
repository: the inventory, the path a destination names, its spelling, whether it exists, the
identifiers a page's headings make, and the lookup of one against the other.
"""

import argparse
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.token import Token

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = MarkdownIt("commonmark").enable("table")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
NOT_PORTABLE = "not a portable repository link"


@dataclass(frozen=True, slots=True, order=True)
class Diagnostic:
    """One failure: the page, the line its block starts on, the destination as the parser read
    it, and why it fails."""

    path: str
    line: int
    destination: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.reason}: {self.destination}"


@dataclass(frozen=True, slots=True)
class Link:
    line: int
    destination: str


@dataclass(frozen=True, slots=True)
class Page:
    path: str
    links: tuple[Link, ...]
    anchors: frozenset[str]
    faults: tuple[Diagnostic, ...]


class Anchors(HTMLParser):
    """The `id` or `name` of every `<a>` tag in a piece of HTML; a comment is not a tag, and an
    attribute is a whole name, so `data-id` is not `id`."""

    def __init__(self) -> None:
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name in ("id", "name") and value:
                self.found.append(value)
                return


def tracked_files(root: Path) -> tuple[str, ...]:
    """The Git index's files as posix paths, one subprocess for the whole scan."""
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True, text=True
    )
    return tuple(name for name in listing.stdout.split("\0") if name)


def heading_text(children: list[Token] | None) -> str:
    """A heading's words as the parser read them: text and code kept, formatting dropped, a line
    break a space, an image its alt text."""
    parts: list[str] = []
    for child in children or ():
        if child.type in ("text", "code_inline", "image"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts)


def slug(text: str) -> str:
    """A heading's identifier as GitHub spells it: lowercase, punctuation and symbols dropped but
    hyphens and underscores, spaces to hyphens."""
    kept = (
        ch
        for ch in text.strip().lower()
        if ch in "-_" or not unicodedata.category(ch).startswith(("P", "S"))
    )
    return "".join(kept).replace(" ", "-")


def heading_anchors(headings: list[tuple[int, str]]) -> dict[str, int]:
    """Each heading's identifier with its line, a repeated one suffixed as GitHub suffixes it: the
    second `Foo` is `foo-1`, and a later `Foo-1` is `foo-1-1`, every identifier unique."""
    anchors: dict[str, int] = {}
    occurrences: dict[str, int] = {}
    for line, text in headings:
        original = slug(text)
        anchor = original
        while anchor in occurrences:
            occurrences[original] += 1
            anchor = f"{original}-{occurrences[original]}"
        occurrences[anchor] = 0
        anchors[anchor] = line
    return anchors


def explicit_anchors(html: str) -> list[str]:
    parser = Anchors()
    parser.feed(html)
    parser.close()
    return parser.found


def read_page(root: Path, path: str) -> Page | None:
    """A tracked Markdown page as it stands on disk, or None when it is deleted there: its links
    and its anchors, from the parser's tokens and nothing else."""
    file = root / path
    if not file.is_file():
        return None
    links: list[Link] = []
    headings: list[tuple[int, str]] = []
    html: list[tuple[int, str]] = []
    previous = ""
    for token in MARKDOWN.parse(file.read_text(encoding="utf-8")):
        line = token.map[0] + 1 if token.map else 0
        if token.type == "html_block":
            html.append((line, token.content))
        elif token.type == "inline":
            if previous == "heading_open":
                headings.append((line, heading_text(token.children)))
            for child in token.children or ():
                if child.type == "link_open":
                    links.append(Link(line, str(child.attrGet("href") or "")))
                elif child.type == "image":
                    links.append(Link(line, str(child.attrGet("src") or "")))
                elif child.type == "html_inline":
                    html.append((line, child.content))
        previous = token.type
    anchors, faults = anchors_of(path, headings, html)
    return Page(path, tuple(links), anchors, faults)


def anchors_of(
    path: str, headings: list[tuple[int, str]], html: list[tuple[int, str]]
) -> tuple[frozenset[str], tuple[Diagnostic, ...]]:
    """The identifiers a page offers: its headings' and its explicit anchors', which may not
    repeat or shadow a heading's."""
    anchors = heading_anchors(headings)
    from_headings = frozenset(anchors)
    faults: list[Diagnostic] = []
    for line, fragment in html:
        for name in explicit_anchors(fragment):
            if name in from_headings:
                reason = f"explicit anchor '{name}' shadows the heading at line {anchors[name]}"
                faults.append(Diagnostic(path, line, name, reason))
            elif name in anchors:
                reason = f"duplicate explicit anchor '{name}' (first at line {anchors[name]})"
                faults.append(Diagnostic(path, line, name, reason))
            else:
                anchors[name] = line
    return frozenset(anchors), tuple(faults)


def resolve(source: str, path: str) -> str | None:
    """The repository-relative posix path a destination names, the root being the empty path, or
    None when it escapes the repository."""
    base = PurePosixPath(source).parent
    parts: list[str] = []
    start = () if path.startswith("/") else base.parts
    for part in (*start, *PurePosixPath(path).parts):
        if part in ("", "/", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


class Checker:
    """One scan: the inventory read once, every page parsed once, each link looked up against
    them."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.files = frozenset(tracked_files(root))
        self.lowered = {name.lower(): name for name in self.files}
        self.pages: dict[str, Page | None] = {
            name: read_page(root, name) for name in self.files if name.endswith(".md")
        }

    def check_link(self, page: Page, link: Link) -> Diagnostic | None:
        destination = link.destination
        if SCHEME.match(destination) and not DRIVE.match(destination):
            return None  # external: never fetched; a file: destination is text to the parser
        path_part, _, fragment = destination.partition("#")
        path = unquote(path_part.partition("?")[0])
        fragment = unquote(fragment)
        if DRIVE.match(path) or path.startswith(("\\\\", "//")) or "\\" in path:
            return self.fault(page, link, NOT_PORTABLE)
        if not path:
            return self.check_fragment(page, link, page, fragment)
        target = resolve(page.path, path)
        if target is None:
            return self.fault(page, link, "path escapes the repository")
        if target in self.files:
            if (self.root / target).is_file():
                return self.check_fragment(page, link, self.pages.get(target), fragment, target)
            return self.fault(page, link, "tracked target is deleted in the working tree", target)
        if target.lower() in self.lowered:
            return self.fault(page, link, f"wrong case, tracked as {self.lowered[target.lower()]}")
        return self.check_directory(page, link, target, fragment)

    def check_directory(
        self, page: Page, link: Link, target: str, fragment: str
    ) -> Diagnostic | None:
        prefix = target + "/" if target else ""
        under = [name for name in self.files if name.startswith(prefix)]
        if not under:
            reason = "missing target"
            if (self.root / target).exists():
                reason += " (untracked on disk)"
            return self.fault(page, link, reason, target)
        if not any((self.root / name).is_file() for name in under):
            return self.fault(
                page, link, "tracked directory is deleted in the working tree", target
            )
        if fragment:
            return self.fault(page, link, "fragment on a directory", target)
        return None

    def check_fragment(
        self,
        page: Page,
        link: Link,
        target: Page | None,
        fragment: str,
        target_path: str | None = None,
    ) -> Diagnostic | None:
        if not fragment or target is None:
            return None  # no fragment, or a target that is not a Markdown page: existence is all
        if fragment in target.anchors:
            return None
        return self.fault(page, link, "unknown fragment", target_path)

    def fault(self, page: Page, link: Link, reason: str, target: str | None = None) -> Diagnostic:
        destination = link.destination
        written = unquote(link.destination.partition("#")[0]).rstrip("/")
        if target is not None and target != written:
            destination += f" -> {target or '/'}"
        return Diagnostic(page.path, link.line, destination, reason)

    def run(self) -> tuple[list[Diagnostic], int]:
        """Every diagnostic in page, line and destination order, and the number of links
        followed."""
        faults: list[Diagnostic] = []
        followed = 0
        for page in self.pages.values():
            if page is None:
                continue
            faults.extend(page.faults)
            for link in page.links:
                followed += 1
                fault = self.check_link(page, link)
                if fault:
                    faults.append(fault)
        return sorted(faults), followed


def check(root: Path = ROOT) -> tuple[list[Diagnostic], int]:
    return Checker(root).run()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Follow every local link in the repository's Markdown."
    )
    parser.add_argument("root", nargs="?", type=Path, default=ROOT, help="the repository to scan")
    arguments = parser.parse_args()
    root = Path(arguments.root).resolve()
    faults, followed = check(root)
    for fault in faults:
        print(fault)
    pages = sum(1 for name in tracked_files(root) if name.endswith(".md"))
    print(f"{followed} links followed in {pages} Markdown files, {len(faults)} failures")
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
