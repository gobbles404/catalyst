"""`tools/release_check.ps1` on folders made here: one laid out as an end user's passes, and each
way a release could be wrong is a fault the script names. The script only reads, so a folder of
empty files with the right names is all it needs. Two of the faults were once passes, found in
review of #248: a config that loads the library from a checkout, and a config that is not beside
the add-in.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "release_check.ps1"
PARTS = (
    "__init__.py",
    "py.typed",
    "excel/__init__.py",
    "excel/bridge.py",
    "instrumentation/__init__.py",
)


def library(home: Path) -> None:
    """A catalyst package under `home`, every part the check asks for."""
    for part in PARTS:
        (home / "catalyst" / part).parent.mkdir(parents=True, exist_ok=True)
        (home / "catalyst" / part).touch()


def installed(folder: Path) -> Path:
    """The installed libraries, outside the release as they may be: numpy and no catalyst."""
    site = folder.parent / (folder.name + "-site-packages")
    (site / "numpy").mkdir(parents=True, exist_ok=True)
    (site / "numpy" / "__init__.py").touch()
    return site


def end_user_folder(folder: Path) -> Path:
    """The host's files beside the library, and beside the add-in a config that searches this
    folder first and the installed libraries after it."""
    folder.mkdir(exist_ok=True)
    for name in (
        "Catalyst.xll",
        "Catalyst.Host.dll",
        "Python.Runtime.dll",
        "ExcelDna.IntelliSense.dll",
    ):
        (folder / name).touch()
    library(folder)
    config(folder, f"pythonpath={folder};{installed(folder)}")
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
    """Python and the installed libraries are outside the folder, and that is no fault."""
    code, said = checked(end_user_folder(tmp_path / "release"))
    assert code == 0, said
    assert "release check: 0 faults" in said
    assert "ok    catalyst.cfg: no probes line" in said
    assert (
        "ok    the library: catalyst, the first catalyst package on the path of catalyst.cfg"
        in said
    )
    assert "ok    Catalyst.Host.dll holds no HostAdd" in said
    assert "ok    no file or folder named for the probes, source, bytecode or library" in said
    assert "=Add(1,2) and =HostAdd(1,2) both show #NAME?" in said
    assert "FAULT" not in said


def test_bytecode_a_run_left_is_a_note_and_never_a_fault(tmp_path: Path) -> None:
    folder = end_user_folder(tmp_path / "release")
    (folder / "catalyst" / "excel" / "__pycache__").mkdir()
    (folder / "catalyst" / "excel" / "__pycache__" / "bridge.cpython-313.pyc").touch()
    code, said = checked(folder)
    assert code == 0, said
    assert "note  1 __pycache__ folder(s)" in said


def checkout_beside(folder: Path) -> Path:
    """A checkout's `src`, the library whole in it, beside the release and no part of it."""
    src = folder.parent / "checkout" / "src"
    library(src)
    return src


def library_only_in_a_checkout(folder: Path) -> None:
    """The first false pass: the release holds no library, and its config names a checkout's."""
    for part in reversed(PARTS):
        (folder / "catalyst" / part).unlink()
    for emptied in ("excel", "instrumentation", ""):
        (folder / "catalyst" / emptied).rmdir()
    config(folder, f"pythonpath={checkout_beside(folder)};{installed(folder)}")


def checkout_searched_first(folder: Path) -> None:
    """The release holds its library, and a checkout's is found before it."""
    config(folder, f"pythonpath={checkout_beside(folder)};{folder};{installed(folder)}")


def config_in_a_subfolder(folder: Path) -> None:
    """The second false pass: a config the host never reads, since it is not beside the add-in."""
    (folder / "config").mkdir()
    (folder / "catalyst.cfg").rename(folder / "config" / "catalyst.cfg")


def old_host(folder: Path) -> None:
    """A host built before HostAdd left it, packed beside the new library."""
    (folder / "Catalyst.Host.dll").write_bytes(b"MZ\x00\x00Floor\x00HostAdd\x00CatalystStatus\x00")


def probe_source(folder: Path) -> None:
    (folder / "catalyst" / "excel" / "probes.py").touch()


def probe_bytecode(folder: Path) -> None:
    (folder / "catalyst" / "excel" / "__pycache__").mkdir()
    (folder / "catalyst" / "excel" / "__pycache__" / "probes.cpython-313.pyc").touch()


def probes_package(folder: Path) -> None:
    (folder / "catalyst_probes").mkdir()
    (folder / "catalyst_probes" / "__init__.py").touch()


def probes_library(folder: Path) -> None:
    (folder / "Catalyst.Probes.dll").touch()


def probes_line(folder: Path) -> None:
    config(folder, f"pythonpath={folder}", "probes=catalyst_probes")


def probes_searched(folder: Path) -> None:
    elsewhere = folder.parent / (folder.name + "-elsewhere")
    (elsewhere / "catalyst_probes").mkdir(parents=True)
    config(folder, f"pythonpath={folder};{elsewhere}")


def relative_path(folder: Path) -> None:
    config(folder, "pythonpath=.;site-packages")


def no_bridge(folder: Path) -> None:
    (folder / "catalyst" / "excel" / "bridge.py").unlink()


def no_library_searched(folder: Path) -> None:
    (folder / "catalyst").rename(folder / "library")


def no_path_line(folder: Path) -> None:
    config(folder)


@pytest.mark.parametrize(
    ("spoil", "named"),
    [
        (library_only_in_a_checkout, "checkout\\src\\catalyst, outside this folder"),
        (checkout_searched_first, "checkout\\src\\catalyst, outside this folder"),
        (config_in_a_subfolder, "FAULT no catalyst.cfg beside Catalyst.xll"),
        (old_host, "FAULT Catalyst.Host.dll beside Catalyst.xll holds HostAdd"),
        (probe_source, "FAULT named for the probes: catalyst\\excel\\probes.py"),
        (
            probe_bytecode,
            "FAULT named for the probes: catalyst\\excel\\__pycache__\\probes.cpython-313.pyc",
        ),
        (probes_package, "FAULT named for the probes: catalyst_probes"),
        (probes_library, "FAULT named for the probes: Catalyst.Probes.dll"),
        (probes_line, "FAULT catalyst.cfg has a probes line, 'catalyst_probes'"),
        (probes_searched, "which holds catalyst_probes: the probes could be imported"),
        (relative_path, "FAULT catalyst.cfg searches '.', which is not a full path"),
        (no_bridge, "FAULT the library is missing excel\\bridge.py"),
        (
            no_library_searched,
            "FAULT catalyst.cfg searches no folder that holds a catalyst package",
        ),
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


def test_a_config_beside_no_add_in_is_said_to_be_unread(tmp_path: Path) -> None:
    folder = end_user_folder(tmp_path / "release")
    config_in_a_subfolder(folder)
    _, said = checked(folder)
    assert "note  config\\catalyst.cfg is beside no .xll, so no host reads it" in said
