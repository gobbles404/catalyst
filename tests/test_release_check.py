"""`tools/release_check.ps1` on folders made here: one laid out as an end user's passes, and each
way a release could be wrong is a fault the script names. The script only reads, so a folder of
empty files with the right names is all it needs. Six of the faults were once passes, found in
two reviews of #248. In the first: a config that loads the library from a checkout, and a config
that is not beside the add-in. In the second: an empty entry on the path, a path with a drive and
no root, a key in capitals, and a line with no `=`. The host reads none of the last four as the
check did.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "release_check.ps1"
PYTHON = "pythondll=C:\\python\\python313.dll"
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
    folder.mkdir(parents=True, exist_ok=True)
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


def written(folder: Path, *lines: str) -> None:
    """The config beside the add-in, these lines and no other."""
    (folder / "catalyst.cfg").write_text("\n".join(lines) + "\n", encoding="ascii")


def config(folder: Path, *lines: str) -> None:
    """The config beside the add-in: Python's own line, then these."""
    written(folder, PYTHON, *lines)


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
    assert "ok    the library: catalyst, in the first folder catalyst.cfg searches" in said
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


def test_the_folders_above_a_release_are_never_read_for_a_probes_name(tmp_path: Path) -> None:
    """A probe is found by the name of a file or a folder inside the release, never by a word in
    the path that leads to it."""
    folder = end_user_folder(tmp_path / "separate-probes" / "test_support" / "release")
    code, said = checked(folder)
    assert code == 0, said
    assert "FAULT" not in said


def test_the_config_is_read_as_the_host_reads_it(tmp_path: Path) -> None:
    """Comments and blank lines passed over, and every line, key, value and entry trimmed."""
    folder = end_user_folder(tmp_path / "release")
    written(
        folder,
        "# where python lives",
        "",
        "  pythondll = C:\\python\\python313.dll  ",
        f"pythonpath = {folder} ; {installed(folder)} ",
    )
    code, said = checked(folder)
    assert code == 0, said
    assert "ok    the library: catalyst, in the first folder catalyst.cfg searches" in said


def test_a_key_the_host_does_not_read_is_a_note(tmp_path: Path) -> None:
    folder = end_user_folder(tmp_path / "release")
    config(folder, f"pythonpath={folder}", "Probes=catalyst_probes")
    code, said = checked(folder)
    assert code == 0, said
    assert "note  catalyst.cfg has a line the host does not read, 'Probes'" in said


def test_of_two_lines_with_one_key_the_last_is_the_one_judged(tmp_path: Path) -> None:
    folder = end_user_folder(tmp_path / "release")
    outside = checkout_beside(folder)
    config(folder, f"pythonpath={outside}", f"pythonpath={folder}")
    code, said = checked(folder)
    assert code == 0, said
    assert "note  catalyst.cfg has more than one 'pythonpath' line; the host reads the last" in said
    config(folder, f"pythonpath={folder}", f"pythonpath={outside}")
    code, said = checked(folder)
    assert code == 1, said
    assert "checkout\\src\\catalyst, outside this folder" in said


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


def installed_searched_first(folder: Path) -> None:
    """The installed libraries hold no catalyst on this machine. An end user's may."""
    config(folder, f"pythonpath={installed(folder)};{folder}")


def config_in_a_subfolder(folder: Path) -> None:
    """The second false pass: a config the host never reads, since it is not beside the add-in."""
    (folder / "config").mkdir()
    (folder / "catalyst.cfg").rename(folder / "config" / "catalyst.cfg")


def searching(path: str) -> Callable[[Path], None]:
    """A config whose pythonpath is `path`, with `{folder}` standing for the release's folder."""

    def spoil(folder: Path) -> None:
        config(folder, "pythonpath=" + path.format(folder=folder))

    return spoil


def key_in_capitals(folder: Path) -> None:
    """A false pass: the host asks for `pythonpath`, and a key is held as written."""
    config(folder, f"PYTHONPATH={folder};{installed(folder)}")


def dll_key_in_capitals(folder: Path) -> None:
    written(folder, "PythonDll=C:\\python\\python313.dll", f"pythonpath={folder}")


def line_with_no_equals(folder: Path) -> None:
    """A false pass: a comment that lost its `#`, which stops the host where it stands."""
    config(folder, "where the library is", f"pythonpath={folder};{installed(folder)}")


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


def checkout_probes_searched(folder: Path) -> None:
    """A checkout's `test_support` that is not on this machine, known by its name alone."""
    config(folder, f"pythonpath={folder};{folder.parent / 'checkout' / 'test_support'}")


def no_bridge(folder: Path) -> None:
    (folder / "catalyst" / "excel" / "bridge.py").unlink()


def no_library_searched(folder: Path) -> None:
    (folder / "catalyst").rename(folder / "library")


def no_path_line(folder: Path) -> None:
    config(folder)


EMPTY = "on the pythonpath of catalyst.cfg is empty"


@pytest.mark.parametrize(
    ("spoil", "named"),
    [
        (library_only_in_a_checkout, "checkout\\src\\catalyst, outside this folder"),
        (checkout_searched_first, "checkout\\src\\catalyst, outside this folder"),
        (installed_searched_first, "release-site-packages first, outside this folder"),
        (config_in_a_subfolder, "FAULT no catalyst.cfg beside Catalyst.xll"),
        pytest.param(searching(";{folder}"), f"FAULT entry 1 of 2 {EMPTY}", id="leading_semicolon"),
        pytest.param(
            searching("{folder};"), f"FAULT entry 2 of 2 {EMPTY}", id="trailing_semicolon"
        ),
        pytest.param(searching(""), f"FAULT entry 1 of 1 {EMPTY}", id="no_entry"),
        pytest.param(
            searching("C:release;{folder}"),
            "FAULT catalyst.cfg searches 'C:release', which is not a full path",
            id="drive_and_no_root",
        ),
        pytest.param(
            searching("{folder};C:site-packages"),
            "FAULT catalyst.cfg searches 'C:site-packages', which is not a full path",
            id="drive_and_no_root_after_the_library",
        ),
        pytest.param(
            searching("\\release;{folder}"),
            "FAULT catalyst.cfg searches '\\release', which is not a full path",
            id="root_and_no_drive",
        ),
        pytest.param(
            searching(".;site-packages"),
            "FAULT catalyst.cfg searches '.', which is not a full path",
            id="neither_drive_nor_root",
        ),
        pytest.param(
            searching('"{folder}"'),
            "\"', which is not a full path",
            id="in_quotation_marks",
        ),
        (key_in_capitals, "FAULT catalyst.cfg has no pythonpath line"),
        (dll_key_in_capitals, "FAULT catalyst.cfg has no pythondll line"),
        (
            line_with_no_equals,
            "FAULT line 2 of catalyst.cfg, 'where the library is', has no =",
        ),
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
        (checkout_probes_searched, "checkout\\test_support, the probes' folder in a checkout"),
        (no_bridge, "FAULT the library is missing excel\\bridge.py"),
        (no_library_searched, "first, and it holds no catalyst package"),
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


def test_a_key_in_capitals_is_named_as_a_line_the_host_does_not_read(tmp_path: Path) -> None:
    folder = end_user_folder(tmp_path / "release")
    key_in_capitals(folder)
    _, said = checked(folder)
    assert "note  catalyst.cfg has a line the host does not read, 'PYTHONPATH'" in said


def test_a_config_beside_no_add_in_is_said_to_be_unread(tmp_path: Path) -> None:
    folder = end_user_folder(tmp_path / "release")
    config_in_a_subfolder(folder)
    _, said = checked(folder)
    assert "note  config\\catalyst.cfg is beside no .xll, so no host reads it" in said
