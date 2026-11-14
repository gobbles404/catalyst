"""`tools/release_check.ps1` on folders made here: one laid out as an end user's passes, and each
way a probe could reach a release is a fault the script names. The script only reads, so a
folder of empty files with the right names is all it needs.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "release_check.ps1"


def end_user_folder(folder: Path) -> Path:
    """The host's files beside the library, and a config that searches this folder alone."""
    folder.mkdir(exist_ok=True)
    for name in (
        "Catalyst.xll",
        "Catalyst.Host.dll",
        "Python.Runtime.dll",
        "ExcelDna.IntelliSense.dll",
    ):
        (folder / name).touch()
    for part in ("__init__.py", "py.typed", "excel/__init__.py", "excel/bridge.py"):
        (folder / "catalyst" / part).parent.mkdir(parents=True, exist_ok=True)
        (folder / "catalyst" / part).touch()
    (folder / "catalyst" / "instrumentation").mkdir()
    (folder / "catalyst" / "instrumentation" / "__init__.py").touch()
    config(folder, f"pythonpath={folder}")
    return folder


def config(folder: Path, *lines: str) -> None:
    (folder / "catalyst.cfg").write_text(
        "\n".join(("pythondll=C:\\python\\python313.dll", *lines)) + "\n", encoding="ascii"
    )


def checked(folder: Path) -> tuple[int, str]:
    ran = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-Folder",
            str(folder),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return ran.returncode, ran.stdout


def test_a_folder_laid_out_as_an_end_users_passes(tmp_path: Path) -> None:
    code, said = checked(end_user_folder(tmp_path))
    assert code == 0, said
    assert "release check: 0 faults" in said
    assert "ok    catalyst.cfg: no probes line" in said
    assert "ok    no file or folder named for the probes, source or bytecode" in said
    assert "FAULT" not in said


def test_bytecode_a_run_left_is_a_note_and_never_a_fault(tmp_path: Path) -> None:
    folder = end_user_folder(tmp_path)
    (folder / "catalyst" / "excel" / "__pycache__").mkdir()
    (folder / "catalyst" / "excel" / "__pycache__" / "bridge.cpython-313.pyc").touch()
    code, said = checked(folder)
    assert code == 0, said
    assert "note  1 __pycache__ folder(s)" in said


def probe_source(folder: Path) -> None:
    (folder / "catalyst" / "excel" / "probes.py").touch()


def probe_bytecode(folder: Path) -> None:
    (folder / "catalyst" / "excel" / "__pycache__").mkdir()
    (folder / "catalyst" / "excel" / "__pycache__" / "probes.cpython-313.pyc").touch()


def probes_package(folder: Path) -> None:
    (folder / "catalyst_probes").mkdir()
    (folder / "catalyst_probes" / "__init__.py").touch()


def probes_line(folder: Path) -> None:
    config(folder, f"pythonpath={folder}", "probes=catalyst_probes")


def probes_searched(folder: Path) -> None:
    elsewhere = folder.parent / (folder.name + "-elsewhere")
    (elsewhere / "catalyst_probes").mkdir(parents=True)
    config(folder, f"pythonpath={folder};{elsewhere}")


def no_bridge(folder: Path) -> None:
    (folder / "catalyst" / "excel" / "bridge.py").unlink()


def no_library_searched(folder: Path) -> None:
    (folder / "catalyst").rename(folder / "library")
    config(folder, f"pythonpath={folder}")


def no_path_line(folder: Path) -> None:
    config(folder)


@pytest.mark.parametrize(
    ("spoil", "named"),
    [
        (probe_source, "FAULT named for the probes: catalyst\\excel\\probes.py"),
        (
            probe_bytecode,
            "FAULT named for the probes: catalyst\\excel\\__pycache__\\probes.cpython-313.pyc",
        ),
        (probes_package, "FAULT named for the probes: catalyst_probes"),
        (probes_line, "FAULT catalyst.cfg has a probes line, 'catalyst_probes'"),
        (probes_searched, "which holds catalyst_probes: the probes could be imported"),
        (no_bridge, "FAULT the library is missing excel\\bridge.py"),
        (no_library_searched, "FAULT no catalyst package"),
        (no_path_line, "FAULT catalyst.cfg has no pythonpath line"),
    ],
)
def test_each_fault_is_named_and_counted(
    tmp_path: Path, spoil: Callable[[Path], None], named: str
) -> None:
    folder = end_user_folder(tmp_path / "release")
    spoil(folder)
    code, said = checked(folder)
    assert code >= 1, said
    assert named in said
    assert f"release check: {code} faults" in said
