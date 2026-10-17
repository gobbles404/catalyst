"""Every local link in the repository's Markdown resolves, and every fragment names a heading.

Run with `uv run python tools/check_doc_links.py` from anywhere; `tests/test_doc_links.py` runs the
same check under pytest, so `check.ps1` and CI fail on a broken reference. The view is the working
tree of the Git-indexed files: `git ls-files` says which files exist, and their text is read from
disk, so an edit saved but not committed is seen, a staged new file counts, and a file that exists
only untracked, ignored or in another checkout is a missing target. Section 11 of
docs/seam/working.md says what is checked, what the diagnostics mean and how an exception is made.

markdown-it-py, a development dependency, reads each page as GitHub does: it says which lines are
code, HTML or comment and which are prose, splits prose into paragraphs, headings and table cells,
and gives a heading's words without their formatting. The links themselves are read from the
page's own text, so a diagnostic quotes a destination as it was written.
"""

import argparse
import re
import subprocess
import sys
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.token import Token

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS_FILE = PurePosixPath("tools/doc_link_exceptions.toml")
DECISION_SECTIONS = (PurePosixPath("docs/seam/inputs.md"), PurePosixPath("docs/seam/outputs.md"))
MARKDOWN = MarkdownIt("commonmark").enable("table")
BLOCKS_WITHOUT_LINKS = frozenset({"fence", "code_block", "html_block"})
CONTAINERS = frozenset(
    {"blockquote_open", "bullet_list_open", "ordered_list_open", "list_item_open"}
)

INLINE_CODE = re.compile(r"(`+)(.+?)\1", re.DOTALL)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
EXPLICIT_ANCHOR = re.compile(r"""<a\b[^>]*?\s(?:id|name)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
DEFINITION = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]*(?:\n[ \t]*)?(<[^>]*>|\S+)", re.MULTILINE)
LINK_TEXT = r"(?:[^\[\]]|\[[^\[\]]*\])*"
INLINE_LINK = re.compile(
    r"!?\[" + LINK_TEXT + r"\]\(\s*(<[^>]*>|(?:[^()\s]|\([^()\s]*\))*)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
REFERENCE_LINK = re.compile(r"!?\[(" + LINK_TEXT + r")\]\[([^\]]*)\]")
SHORTCUT_LINK = re.compile(r"(?<![\]!])\[([^\[\]]+)\](?![\[(:])")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
DECISION_ITEM = re.compile(r"^(\d+)\.\s")


@dataclass(frozen=True, slots=True, order=True)
class Diagnostic:
    """One failure: where it is, what was written, and why it fails."""

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
    definition_line: int | None = None


@dataclass(frozen=True, slots=True)
class Page:
    path: str
    links: tuple[Link, ...]
    anchors: frozenset[str]
    faults: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class Exception_:
    """A documented exception: one source, one destination exactly as written, and why."""

    source: str
    destination: str
    reason: str


@dataclass(frozen=True, slots=True)
class Prose:
    """A page as markdown-it reads it: each run of prose with the line it starts on, each
    heading's words, each HTML block, the lines that are code or HTML and hold no link, and the
    lines any block covers, outside which the parser consumed a reference definition."""

    runs: tuple[tuple[int, str], ...]
    headings: tuple[tuple[int, str], ...]
    html: tuple[tuple[int, str], ...]
    silent_lines: frozenset[int]
    covered_lines: frozenset[int]


def tracked_files(root: Path) -> tuple[str, ...]:
    """The Git index's files as posix paths, one subprocess for the whole scan."""
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True, text=True
    )
    return tuple(name for name in listing.stdout.split("\0") if name)


def plain_text(children: list[Token] | None) -> str:
    """A heading's words as GitHub anchors them: text and code kept, formatting dropped, a line
    break a space, an image its alt text."""
    parts: list[str] = []
    for child in children or ():
        if child.type in ("text", "code_inline", "image"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts)


def read_prose(text: str) -> Prose:
    runs: list[tuple[int, str]] = []
    headings: list[tuple[int, str]] = []
    html: list[tuple[int, str]] = []
    silent: set[int] = set()
    covered: set[int] = set()
    previous = ""
    for token in MARKDOWN.parse(text):
        first = token.map[0] + 1 if token.map else 0
        if token.map and token.nesting != -1 and token.type not in CONTAINERS:
            covered.update(range(token.map[0] + 1, token.map[1] + 1))
        if token.type in BLOCKS_WITHOUT_LINKS and token.map:
            silent.update(range(token.map[0] + 1, token.map[1] + 1))
            if token.type == "html_block":
                html.append((first, token.content))
        elif token.type == "inline":
            runs.append((first, token.content))
            if previous == "heading_open":
                headings.append((first, plain_text(token.children)))
        previous = token.type
    return Prose(tuple(runs), tuple(headings), tuple(html), frozenset(silent), frozenset(covered))


def slug(heading: str) -> str:
    """A heading's anchor as GitHub makes it: lowercase, punctuation and symbols dropped but
    hyphens and underscores, spaces to hyphens."""
    text = heading.strip().lower()
    kept = (ch for ch in text if ch in "-_" or not unicodedata.category(ch).startswith(("P", "S")))
    return "".join(kept).replace(" ", "-")


def heading_anchors(headings: tuple[tuple[int, str], ...]) -> dict[str, int]:
    """Each heading's anchor, a repeated one suffixed as GitHub suffixes it: the second `Foo` is
    `foo-1`, and a later `Foo-1` is `foo-1-1`, since every anchor stays unique."""
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


def blank(pattern: re.Pattern[str], text: str) -> str:
    """The text with every match replaced by spaces, newlines kept, so positions still count."""
    return pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def line_of(start: int, text: str, position: int) -> int:
    return start + text.count("\n", 0, position)


def anchors_of(path: str, prose: Prose) -> tuple[frozenset[str], tuple[Diagnostic, ...]]:
    """The anchors a page offers: the headings' and the explicit `<a id>` ones, which may not
    repeat or shadow a heading's."""
    anchors = heading_anchors(prose.headings)
    from_headings = frozenset(anchors)
    faults: list[Diagnostic] = []
    sources = [(line, blank(HTML_COMMENT, blank(INLINE_CODE, run))) for line, run in prose.runs]
    sources += [(line, blank(HTML_COMMENT, block)) for line, block in prose.html]
    for start, text in sources:
        for match in EXPLICIT_ANCHOR.finditer(text):
            name = match.group(1)
            line = line_of(start, text, match.start())
            if name in from_headings:
                heading = anchors[name]
                reason = (
                    f"explicit anchor '{name}' collides with a heading's anchor (line {heading})"
                )
                faults.append(Diagnostic(path, line, name, reason))
            elif name in anchors:
                reason = f"duplicate explicit anchor '{name}' (first at line {anchors[name]})"
                faults.append(Diagnostic(path, line, name, reason))
            else:
                anchors[name] = line
    return frozenset(anchors), tuple(faults)


def normalized(label: str) -> str:
    return " ".join(label.split()).casefold()


def strip_brackets(destination: str) -> str:
    if destination.startswith("<") and destination.endswith(">"):
        return destination[1:-1]
    return destination


def definitions_of(text: str, covered: frozenset[int]) -> dict[str, tuple[str, int]]:
    """Reference definitions by label, the destination on the same line or the next, read only
    from the lines no block covers, which are the lines the parser gave to its reference rule;
    a definition-shaped line inside a paragraph, a comment or code is not one. The first
    definition of a label wins, as it does for GitHub."""
    found: dict[str, tuple[str, int]] = {}
    for match in DEFINITION.finditer(text):
        line = line_of(1, text, match.start())
        if line not in covered:
            found.setdefault(normalized(match.group(1)), (strip_brackets(match.group(2)), line))
    return found


def links_of(prose: Prose, definitions: dict[str, tuple[str, int]]) -> tuple[Link, ...]:
    """Inline links and images, then reference links through their definitions: full, collapsed
    and the shortcut form, which counts only when a definition exists."""
    links: list[Link] = []
    for start, run in prose.runs:
        text = blank(HTML_COMMENT, blank(INLINE_CODE, run))
        for match in INLINE_LINK.finditer(text):
            line = line_of(start, text, match.start())
            links.append(Link(line, strip_brackets(match.group(1))))
        text = blank(INLINE_LINK, text)
        for match in REFERENCE_LINK.finditer(text):
            label = normalized(match.group(2) or match.group(1))
            if label in definitions:
                destination, defined = definitions[label]
                links.append(Link(line_of(start, text, match.start()), destination, defined))
        text = blank(REFERENCE_LINK, text)
        for match in SHORTCUT_LINK.finditer(text):
            label = normalized(match.group(1))
            if label in definitions:
                destination, defined = definitions[label]
                links.append(Link(line_of(start, text, match.start()), destination, defined))
    return tuple(links)


def read_page(root: Path, path: str) -> Page | None:
    """A tracked Markdown page as it stands on disk, or None when it is deleted there."""
    file = root / path
    if not file.is_file():
        return None
    text = file.read_text(encoding="utf-8")
    prose = read_prose(text)
    anchors, faults = anchors_of(path, prose)
    return Page(path, links_of(prose, definitions_of(text, prose.covered_lines)), anchors, faults)


def split_destination(destination: str) -> tuple[str, str]:
    """The path and the fragment of a local destination, each percent-decoded, a query string
    on the path dropped since it changes neither the file nor the anchor."""
    path, _, fragment = destination.partition("#")
    path = path.partition("?")[0]
    return unquote(path), unquote(fragment)


def resolve(source: str, path: str) -> str | None:
    """The repository-relative posix path a link names, the root being the empty path, or None
    when it escapes the repository."""
    base = PurePosixPath(source).parent
    raw = PurePosixPath(path)
    parts: list[str] = []
    start = () if path.startswith("/") else base.parts
    for part in (*start, *raw.parts):
        if part in ("", "/", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def portable(destination: str) -> str | None:
    """Why a destination is not a portable repository link, or None when it may be one."""
    if not destination:
        return "empty destination"
    if DRIVE.match(destination) or destination.startswith(("\\\\", "//")):
        return "machine-specific path, not a repository link"
    if destination.lower().startswith("file:"):
        return "file: URL, not a repository link"
    if "\\" in destination.partition("#")[0]:
        return "backslash in a path, which GitHub reads as a character"
    return None


class Checker:
    """One scan: the inventory read once, every page parsed once, each link checked against them."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.files = frozenset(tracked_files(root))
        self.pages: dict[str, Page | None] = {
            name: read_page(root, name) for name in self.files if name.endswith(".md")
        }

    def is_tracked_directory(self, path: str) -> bool:
        prefix = path + "/" if path else ""
        return any(name.startswith(prefix) for name in self.files)

    def check_link(self, page: Page, link: Link) -> Diagnostic | None:
        destination = link.destination
        if SCHEME.match(destination) and not DRIVE.match(destination):
            if destination.lower().startswith("file:"):
                return self.fault(page, link, "file: URL, not a repository link")
            return None
        fault = portable(destination)
        if fault:
            return self.fault(page, link, fault)
        path, fragment = split_destination(destination)
        if not path:
            return self.check_fragment(page, link, page, fragment)
        target = resolve(page.path, path)
        if target is None:
            return self.fault(page, link, "path escapes the repository")
        if target in self.files:
            if (self.root / target).is_file():
                return self.check_fragment(page, link, self.pages.get(target), fragment, target)
            return self.fault(page, link, "tracked target is deleted in the working tree", target)
        if self.is_tracked_directory(target):
            if fragment:
                return self.fault(page, link, "fragment on a directory", target)
            if (self.root / target).is_dir():
                return None
            return self.fault(
                page, link, "tracked directory is deleted in the working tree", target
            )
        reason = "missing tracked target"
        if (self.root / target).exists():
            reason += " (exists on disk but is not tracked by git)"
        return self.fault(page, link, reason, target)

    def check_fragment(
        self,
        page: Page,
        link: Link,
        target: Page | None,
        fragment: str,
        target_path: str | None = None,
    ) -> Diagnostic | None:
        if not fragment:
            return None
        if target is None:
            return None  # not a Markdown page: a source line or a PDF page, not read here
        if fragment in target.anchors:
            return None
        return self.fault(page, link, "unknown fragment", target_path)

    def fault(self, page: Page, link: Link, reason: str, target: str | None = None) -> Diagnostic:
        if link.definition_line is not None:
            reason += f" (definition at line {link.definition_line})"
        destination = link.destination
        written = link.destination.partition("#")[0].rstrip("/")
        if target is not None and target != written:
            destination += f" -> {target or '/'}"
        return Diagnostic(page.path, link.line, destination, reason)

    def decision_numbers(self, path: str) -> list[Diagnostic]:
        """The top-level decision numbers of the page's Decided section are unique."""
        if self.pages.get(path) is None:
            return []
        text = (self.root / path).read_text(encoding="utf-8")
        silent = read_prose(text).silent_lines
        faults: list[Diagnostic] = []
        first: dict[str, int] = {}
        inside = False
        for number, line in enumerate(text.split("\n"), start=1):
            if number in silent:
                continue
            if line.startswith("## "):
                inside = line.strip() == "## Decided"
                continue
            item = DECISION_ITEM.match(line) if inside else None
            if not item:
                continue
            decision = item.group(1)
            if decision in first:
                reason = f"duplicate decision number {decision} (first at line {first[decision]})"
                faults.append(Diagnostic(path, number, decision, reason))
            else:
                first[decision] = number
        return faults

    def exceptions(self) -> tuple[Exception_, ...]:
        file = self.root / EXCEPTIONS_FILE
        if str(EXCEPTIONS_FILE) not in self.files or not file.is_file():
            return ()
        with file.open("rb") as handle:
            data = tomllib.load(handle)
        entries = data.get("exception", [])
        found: list[Exception_] = []
        for entry in entries:
            try:
                found.append(
                    Exception_(
                        str(entry["source"]), str(entry["destination"]), str(entry["reason"])
                    )
                )
            except (KeyError, TypeError) as error:
                raise ValueError(
                    f"{EXCEPTIONS_FILE}: each [[exception]] needs source, destination and reason"
                ) from error
        return tuple(found)

    def run(self) -> tuple[list[Diagnostic], int]:
        """Every diagnostic in path and line order, and the number of links followed."""
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
        for path in DECISION_SECTIONS:
            faults.extend(self.decision_numbers(str(path)))
        return self.apply_exceptions(faults), followed

    def apply_exceptions(self, faults: list[Diagnostic]) -> list[Diagnostic]:
        """A documented exception removes exactly the failure it names; one that matches nothing
        is itself a failure, so the list never outlives the breakage it excuses."""
        exceptions = self.exceptions()
        kept: list[Diagnostic] = []
        used: set[Exception_] = set()
        for fault in faults:
            written = fault.destination.partition(" -> ")[0]
            match = next(
                (e for e in exceptions if e.source == fault.path and e.destination == written),
                None,
            )
            if match is None:
                kept.append(fault)
            else:
                used.add(match)
        for exception in exceptions:
            if exception not in used:
                reason = f"unused exception for '{exception.destination}' ({exception.reason})"
                kept.append(Diagnostic(str(EXCEPTIONS_FILE), 0, exception.source, reason))
        return sorted(kept)


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
