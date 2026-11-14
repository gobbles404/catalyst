"""The end user's build holds no probe: the `catalyst` package alone, copied to a folder of its
own and loaded by a Python that is given that folder and the installed libraries and nothing
else, as the host is given its `pythonpath`. Every other test runs with the probes registered,
so this is the one place a function list is read as an end user's Excel would read it. Below
that, the inventory the smoke takes of an end user's folder, on folders made here.
"""

import json
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import cast

import pytest

import catalyst
import catalyst_probes
from catalyst.excel import bridge

ROOT = Path(__file__).resolve().parents[1]

# Every probe by name, read off the package that registers them: a registered function the
# package itself defines. What an end user's Excel must not know.
PROBES = frozenset(
    name
    for name, *_ in bridge.function_specs()
    if getattr(vars(catalyst_probes).get(name), "__module__", None) == catalyst_probes.__name__
)

# What the isolated Python reports of itself: where the library came from, what it registered,
# whether either home of the probes can be imported, and the path it searched.
REPORT = """
import json, sys
sys.path[:0] = sys.argv[1:]
import catalyst
from catalyst.excel import bridge

def importable(name):
    try:
        __import__(name)
    except ModuleNotFoundError:
        return False
    return True

print(json.dumps({
    "file": catalyst.__file__,
    "specs": [[name, hidden] for name, _, _, hidden, _ in bridge.function_specs()],
    "probes_package": importable("catalyst_probes"),
    "probes_module": importable("catalyst.excel.probes"),
    "path": sys.path,
}))
"""


@pytest.fixture(scope="module")
def end_user(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """The report of a Python started with no site of its own, `-I -S`, so nothing reaches its
    path but what it is handed: a clean copy of the package, no bytecode beside it, and the
    folder the installed libraries are in."""
    folder = tmp_path_factory.mktemp("end_user")
    shutil.copytree(
        Path(catalyst.__file__).parent,
        folder / "catalyst",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    ran = subprocess.run(
        [sys.executable, "-I", "-S", "-c", REPORT, str(folder), sysconfig.get_paths()["purelib"]],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr
    report = cast(dict[str, object], json.loads(ran.stdout))
    report["folder"] = str(folder)
    return report


def test_the_library_loaded_is_the_copy_and_no_checkout_folder_is_searched(
    end_user: dict[str, object],
) -> None:
    folder = Path(cast(str, end_user["folder"]))
    assert Path(cast(str, end_user["file"])) == folder / "catalyst" / "__init__.py"
    searched = {Path(entry) for entry in cast(list[str], end_user["path"])}
    assert ROOT / "src" not in searched
    assert Path(catalyst_probes.__file__).parents[1] not in searched


def test_no_probe_is_registered_and_nothing_registered_is_hidden(
    end_user: dict[str, object],
) -> None:
    specs = cast(list[list[object]], end_user["specs"])
    names = {cast(str, name) for name, _ in specs}
    assert names.isdisjoint(PROBES)
    assert [name for name, hidden in specs if hidden] == []
    # The functions a person types are all there: the bridge's own and one from each end.
    assert {"Ping", "_CreateValuationDate", "_EvaluateTrades", "util_ReadHandle"} <= names


def test_the_probes_cannot_be_imported_from_either_home(end_user: dict[str, object]) -> None:
    assert end_user["probes_package"] is False
    assert end_user["probes_module"] is False


def test_the_names_read_off_the_package_are_the_probes() -> None:
    """A reading that came back empty would pass every check above unseen."""
    assert {"Zero", "Add", "EchoFieldRow", "Fail"} <= PROBES


def test_the_library_holds_no_file_named_for_the_probes() -> None:
    """Source alone: bytecode a run left behind is the inventory's to find, in a folder laid out
    for an end user."""
    package = Path(catalyst.__file__).parent
    assert [p for p in package.rglob("*probes*") if "__pycache__" not in p.parts] == []


# `Test-EndUserFolder` in `tools/host_build.ps1`, the inventory the smoke takes of the end user's
# folder before its first Excel starts, on folders made here. It reads names, so empty files do.
RUNS_ON = (
    "Catalyst.xll",
    "Catalyst.dna",
    "Catalyst.Host.dll",
    "Python.Runtime.dll",
    "ExcelDna.IntelliSense.dll",
    "catalyst.cfg",
    "catalyst/__init__.py",
    "catalyst/py.typed",
    "catalyst/excel/bridge.py",
    "catalyst/instrumentation/__init__.py",
)


def laid_out(folder: Path, *more: str) -> Path:
    """Every file the add-in runs on, and `more` beside them."""
    for name in (*RUNS_ON, *more):
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).touch()
    return folder


def inventory(folder: Path) -> tuple[int, str]:
    """The number of faults the inventory found in `folder`, and what it printed."""
    ran = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ". $env:HOST_BUILD; exit (Test-EndUserFolder -Folder $env:END_USER_FOLDER)",
        ],
        env={
            **os.environ,
            "HOST_BUILD": str(ROOT / "tools" / "host_build.ps1"),
            "END_USER_FOLDER": str(folder),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return ran.returncode, ran.stdout


def test_the_inventory_passes_a_folder_laid_out_for_an_end_user(tmp_path: Path) -> None:
    """The library's own bytecode is counted and is no fault: a release may be handed over
    with it."""
    faults, said = inventory(laid_out(tmp_path, "catalyst/__pycache__/__init__.cpython-313.pyc"))
    assert faults == 0, said
    assert "FAIL" not in said
    assert "ok   catalyst\\excel\\bridge.py" in said
    assert "ok   nothing named for the probes" in said
    assert "11 files, 1 __pycache__ folders, 0 faults" in said


def test_the_inventory_names_a_file_the_add_in_runs_on_that_is_missing(tmp_path: Path) -> None:
    (laid_out(tmp_path) / "Python.Runtime.dll").unlink()
    faults, said = inventory(tmp_path)
    assert faults == 1, said
    assert "FAIL Python.Runtime.dll is not in the folder" in said


@pytest.mark.parametrize(
    ("shipped", "named"),
    [
        pytest.param(
            "catalyst/excel/probes.py",
            ["catalyst\\excel\\probes.py"],
            id="the_probes_old_source",
        ),
        pytest.param(
            "catalyst/excel/__pycache__/probes.cpython-313.pyc",
            ["catalyst\\excel\\__pycache__\\probes.cpython-313.pyc"],
            id="the_bytecode_of_it",
        ),
        pytest.param("catalyst_probes/__init__.py", ["catalyst_probes"], id="the_probes_package"),
        pytest.param(
            "test_support/catalyst_probes/__init__.py",
            ["test_support", "test_support\\catalyst_probes"],
            id="the_probes_folder",
        ),
        pytest.param("Catalyst.Probes.dll", ["Catalyst.Probes.dll"], id="the_floors_library"),
    ],
)
def test_the_inventory_names_whatever_is_named_for_the_probes(
    tmp_path: Path, shipped: str, named: list[str]
) -> None:
    faults, said = inventory(laid_out(tmp_path, shipped))
    assert faults == len(named), said
    for name in named:
        assert f"FAIL named for the probes: {name}\n" in said
    assert "ok   nothing named for the probes" not in said
