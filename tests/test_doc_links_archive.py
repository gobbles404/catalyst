"""The documentation tests also run during setup from a source ZIP, without a Git index or Git
installed. Exercise that deployment boundary in a separate pytest process, while keeping a
broken real checkout a failure."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    for name in (
        "pyproject.toml",
        "tools/check_doc_links.py",
        "tests/test_doc_links.py",
        "tests/test_doc_decision_numbers.py",
        "docs/seam/inputs.md",
        "docs/seam/outputs.md",
    ):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return root


def run_archive(root: Path, git_available: bool) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if not git_available:
        environment["PATH"] = str(root / "no-executables")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-vv", "--tb=short", "tests"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("git_available", [True, False], ids=["with-git", "without-git"])
def test_documentation_checks_allow_source_zip_setup(archive: Path, git_available: bool) -> None:
    if git_available and shutil.which("git") is None:
        pytest.skip("Git is not installed; the installed-Git case needs it")
    result = run_archive(archive, git_available)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Git metadata is absent in a source ZIP" in result.stdout
    assert "test_slug_matches_github PASSED" in result.stdout
    assert "test_the_two_pages_have_unique_decision_numbers PASSED" in result.stdout
    if git_available:
        assert "test_fragments_follow_github_identifiers PASSED" in result.stdout
    else:
        assert "Git is not installed; this fixture tests Git-indexed documentation" in result.stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is needed to test a broken checkout")
def test_broken_checkout_metadata_is_not_treated_as_a_source_zip(archive: Path) -> None:
    (archive / ".git").write_text("gitdir: missing-metadata\n", encoding="utf-8")
    result = run_archive(archive, git_available=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "CalledProcessError" in result.stdout
    assert "test_the_repository_itself FAILED" in result.stdout
