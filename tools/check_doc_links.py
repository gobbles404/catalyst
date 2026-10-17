"""Every local link in the repository's Markdown resolves, and every fragment names a heading.

Run with `uv run python tools/check_doc_links.py` from anywhere; `tests/test_doc_links.py` runs the
same check under pytest, so `check.ps1` and CI fail on a broken reference. The view is the working
tree of the Git-indexed files: `git ls-files` says which files exist, and their text is read from
disk, so an edit saved but not committed is seen, a staged new file counts, and a file that exists
only untracked, ignored or in another checkout is a missing target. Section 11 of
docs/seam/working.md says what is checked, what the diagnostics mean and how an exception is made.
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

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS_FILE = PurePosixPath("tools/doc_link_exceptions.toml")
DECISION_SECTIONS = (PurePosixPath("docs/seam/inputs.md"), PurePosixPath("docs/seam/outputs.md"))

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
ATX_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
SETEXT_UNDERLINE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
INLINE_CODE = re.compile(r"(`+)(.+?)\1")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
EXPLICIT_ANCHOR = re.compile(r"""<a\s+(?:id|name)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
DEFINITION = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]*(<[^>]*>|\S+)")
LINK_TEXT = r"(?:[^\[\]]|\[[^\[\]]*\])*"
INLINE_LINK = re.compile(
    r"!?\[" + LINK_TEXT + r"\]\((<[^>]*>|(?:[^()\s]|\([^()\s]*\))*)"
    r"(?:[ \t]+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?[ \t]*\)"
)
REFERENCE_LINK = re.compile(r"!?\[(" + LINK_TEXT + r")\]\[([^\]]*)\]")
SHORTCUT_LINK = re.compile(r"(?<![\]!])\[([^\[\]]+)\](?![\[(:])")
MARKDOWN_LINK_IN_HEADING = re.compile(r"!?\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])")
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


def tracked_files(root: Path) -> tuple[str, ...]:
    """The Git index's files as posix paths, one subprocess for the whole scan."""
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True, text=True
    )
    return tuple(name for name in listing.stdout.split("\0") if name)


def active_text(lines: list[str]) -> list[str]:
    """The lines with code fences, indented code and HTML comments blanked out, line numbers
    kept, so nothing inside them is read as a link, a heading or an anchor. Inline code stays,
    since a heading's anchor includes its words; the link and anchor readers blank it themselves."""
    out: list[str] = []
    fence: tuple[str, int] | None = None
    indented = False
    previous_blank = True
    previous_text = ""
    for line in lines:
        blank = not line.strip()
        if fence is not None:
            closing = FENCE.match(line)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= fence[1]:
                fence = None
            out.append("")
            continue
        opening = FENCE.match(line)
        if opening:
            fence = (opening.group(1)[0], len(opening.group(1)))
            out.append("")
            continue
        is_indented = line.startswith("    ") or line.startswith("\t")
        if indented and (is_indented or blank):
            out.append("")
            continue
        indented = is_indented and previous_blank and not LIST_ITEM.match(previous_text)
        if indented:
            out.append("")
            continue
        out.append(line)
        previous_blank = blank
        if not blank:
            previous_text = line
    joined = "\n".join(out)
    joined = HTML_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), joined)
    return joined.split("\n")


def without_inline_code(line: str) -> str:
    return INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line)


def slug(heading: str) -> str:
    """A heading's anchor as GitHub makes it: links reduced to their text, lowercase, punctuation
    and symbols dropped but hyphens and underscores, spaces to hyphens."""
    text = MARKDOWN_LINK_IN_HEADING.sub(r"\1", heading).strip().lower()
    kept = (ch for ch in text if ch in "-_" or not unicodedata.category(ch).startswith(("P", "S")))
    return "".join(kept).replace(" ", "-")


def heading_texts(lines: list[str]) -> list[tuple[int, str]]:
    """Every ATX and setext heading of the active text, with its line number."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        atx = ATX_HEADING.match(line)
        if atx:
            found.append((number, atx.group(1)))
            continue
        if number < 2 or not SETEXT_UNDERLINE.match(line):
            continue
        above = lines[number - 2].strip()
        if above and above[0] not in "|#>-*+" and not LIST_ITEM.match(above):
            found.append((number - 1, above))
    return found


def anchors_of(path: str, lines: list[str]) -> tuple[frozenset[str], tuple[Diagnostic, ...]]:
    """The anchors a page offers: each heading's slug, a repeated one suffixed as GitHub suffixes
    it, and the explicit `<a id>` anchors, which may not repeat or shadow a heading's."""
    anchors: dict[str, int] = {}
    seen: dict[str, int] = {}
    for number, text in heading_texts(lines):
        base = slug(text)
        count = seen.get(base, 0)
        seen[base] = count + 1
        anchors[base if count == 0 else f"{base}-{count}"] = number
    from_headings = frozenset(anchors)
    faults: list[Diagnostic] = []
    for number, line in enumerate(lines, start=1):
        for name in EXPLICIT_ANCHOR.findall(without_inline_code(line)):
            if name in from_headings:
                heading = anchors[name]
                reason = (
                    f"explicit anchor '{name}' collides with a heading's anchor (line {heading})"
                )
                faults.append(Diagnostic(path, number, name, reason))
            elif name in anchors:
                reason = f"duplicate explicit anchor '{name}' (first at line {anchors[name]})"
                faults.append(Diagnostic(path, number, name, reason))
            else:
                anchors[name] = number
    return frozenset(anchors), tuple(faults)


def normalized(label: str) -> str:
    return " ".join(label.split()).casefold()


def strip_brackets(destination: str) -> str:
    if destination.startswith("<") and destination.endswith(">"):
        return destination[1:-1]
    return destination


def links_of(lines: list[str]) -> tuple[Link, ...]:
    """Inline links and images, then reference links through their definitions: full, collapsed
    and the shortcut form, which counts only when a definition exists."""
    plain = [without_inline_code(line) for line in lines]
    definitions: dict[str, tuple[str, int]] = {}
    for number, line in enumerate(plain, start=1):
        definition = DEFINITION.match(line)
        if definition:
            definitions.setdefault(
                normalized(definition.group(1)), (strip_brackets(definition.group(2)), number)
            )
    links: list[Link] = []
    for number, line in enumerate(plain, start=1):
        if DEFINITION.match(line):
            continue
        for match in INLINE_LINK.finditer(line):
            links.append(Link(number, strip_brackets(match.group(1))))
        rest = INLINE_LINK.sub(lambda m: " " * len(m.group(0)), line)
        for match in REFERENCE_LINK.finditer(rest):
            label = normalized(match.group(2) or match.group(1))
            if label in definitions:
                destination, defined = definitions[label]
                links.append(Link(number, destination, defined))
        rest = REFERENCE_LINK.sub(lambda m: " " * len(m.group(0)), rest)
        for match in SHORTCUT_LINK.finditer(rest):
            label = normalized(match.group(1))
            if label in definitions:
                destination, defined = definitions[label]
                links.append(Link(number, destination, defined))
    return tuple(links)


def read_page(root: Path, path: str) -> Page | None:
    """A tracked Markdown page as it stands on disk, or None when it is deleted there."""
    file = root / path
    if not file.is_file():
        return None
    lines = active_text(file.read_text(encoding="utf-8").split("\n"))
    anchors, faults = anchors_of(path, lines)
    return Page(path, links_of(lines), anchors, faults)


def split_destination(destination: str) -> tuple[str, str]:
    """The path and the fragment of a local destination, each percent-decoded, a query string
    on the path dropped since it changes neither the file nor the anchor."""
    path, _, fragment = destination.partition("#")
    path = path.partition("?")[0]
    return unquote(path), unquote(fragment)


def resolve(source: str, path: str) -> str | None:
    """The repository-relative posix path a link names, or None when it escapes the repository."""
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

    def is_directory(self, path: str) -> bool:
        prefix = path + "/"
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
        if self.is_directory(target):
            if fragment:
                return self.fault(page, link, "fragment on a directory", target)
            return None
        on_disk = (self.root / target).exists()
        reason = "missing tracked target"
        if on_disk:
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
        if target is not None and target != link.destination.partition("#")[0].rstrip("/"):
            destination += f" -> {target}"
        return Diagnostic(page.path, link.line, destination, reason)

    def decision_numbers(self, path: str) -> list[Diagnostic]:
        """The top-level decision numbers of the page's Decided section are unique."""
        page = self.pages.get(path)
        if page is None:
            return []
        lines = active_text((self.root / path).read_text(encoding="utf-8").split("\n"))
        faults: list[Diagnostic] = []
        first: dict[str, int] = {}
        inside = False
        for number, line in enumerate(lines, start=1):
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
