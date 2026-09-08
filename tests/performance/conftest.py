"""Shared instruments for budget tests."""

import cProfile
from collections.abc import Callable
from pathlib import Path

import pytest

import goosedove

PACKAGE_DIR = str(Path(goosedove.__file__).parent)


def _call_profile(fn: Callable[[], object]) -> dict[str, int]:
    """Which of the package's own functions ran, and how many times each."""
    profiler = cProfile.Profile()
    profiler.enable()
    fn()
    profiler.disable()
    profile: dict[str, int] = {}
    for entry in profiler.getstats():
        code = entry.code
        if isinstance(code, str):
            continue
        if code.co_filename.startswith(PACKAGE_DIR):
            profile[code.co_qualname] = profile.get(code.co_qualname, 0) + entry.callcount
    return profile


@pytest.fixture
def call_profile() -> Callable[[Callable[[], object]], dict[str, int]]:
    return _call_profile
