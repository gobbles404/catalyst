# Getting started

From a clone to a formula in Excel, on a Windows machine with nothing installed but Python 3.13.13. Every step says what to type and how to see that it worked; the last section says what to do when it did not. Budget half an hour, most of it downloads. The Python side, the library and its tests, also runs on macOS and Linux with steps 1 to 3 alone; the add-in needs Windows and Excel.

## What you need

| Need | Version | How to check |
|---|---|---|
| Windows 10 or 11, 64-bit | any current | Settings > System > About |
| Excel, 64-bit, with dynamic arrays | Microsoft 365, or Excel 2021 or later | File > Account > About Excel shows `64-bit` in its first line |
| Python, 64-bit | 3.13.13 exactly, pinned in `.python-version`; `pyproject.toml` allows any 3.13 | `py -3.13 --version` shows `Python 3.13.13`; `py -3.13 -c "import struct; print(struct.calcsize('P') * 8)"` shows `64` |
| uv | 0.12.9, the version CI uses | `uv --version` |
| .NET SDK | 8.0.423, pinned in `global.json`; any later 8.0.4xx patch also satisfies it | `dotnet --version`, run inside the repository folder |
| Git | any | you have cloned, so it is there |

Not needed: Visual Studio, an IDE, or the .NET Framework 4.8 targeting pack. The add-in targets .NET Framework 4.8, which Windows 10 and 11 already include, and the SDK restores the reference assemblies it needs from NuGet at the first build. Installers may ask for administrator rights; nothing else does.

## 1. Open a terminal in the repository

Use PowerShell: Windows PowerShell 5.1 is built in, and PowerShell 7 works too. Change into the clone; every command below runs from the repository root.

Windows refuses to run `.ps1` scripts until you allow it once for your account:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Answer `Y`. If you would rather not change the policy, run each script as `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_dev.ps1` instead of `.\tools\excel_dev.ps1`.

## 2. Install uv

uv manages the Python environment, the dependencies and every Python command in this repository. Install it with the Python you already have:

```powershell
py -3.13 -m pip install uv==0.12.9
uv --version
```

The second line shows `uv 0.12.9`. If PowerShell says `uv` is not recognized, the install worked but that Python's `Scripts` folder is not on your PATH, and it has to be: `.\check.ps1`, `.\measure.ps1` and the host build that `.\tools\excel_dev.ps1` runs all call `uv` by name, so writing `py -3.13 -m uv` for the commands you type would carry you through step 3 and fail at step 5. pip named the folder in a warning at the end of the install; if it has scrolled away, this prints it:

```powershell
py -3.13 -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```

Add that folder to your account's Path (Settings, System, About, Advanced system settings, Environment Variables, then Path under User variables, New), close and reopen the terminal, and run `uv --version` again.

## 3. Create the environment

```powershell
uv sync --locked
```

This creates `.venv` in the repository with Python 3.13.13 and the exact versions `uv.lock` records, numpy and scipy for the library and the tools for the checks. uv uses your installed 3.13.13 when it finds one and otherwise downloads a 3.13.13 of its own into the environment; both are fine, since the add-in follows whichever Python the environment holds. `--locked` refuses to change the lock file, which is what you want: if it complains that the lock needs updating, your clone differs from `main`, so run `git status` and `git pull` rather than editing anything.

Check it:

```powershell
uv run python -c "import goosedove, numpy; print('ok')"
uv run pytest -n auto
```

The first prints `ok`. The second runs every Python test in about a minute and ends with a line saying they all passed; among them, `tests\test_smoke.py` checks that the environment's Python is 64-bit, which the add-in needs.

## 4. Install the .NET SDK

Download the .NET 8.0 SDK for Windows x64 from Microsoft's .NET download page and run the installer. Any 8.0.4xx patch at or above 8.0.423 satisfies `global.json`; a newer major version alone, 9 or 10, does not, so install 8.0 even if another is present. Close and reopen the terminal afterwards, then, inside the repository folder:

```powershell
dotnet --version
```

It shows the 8.0.4xx version the repository will use.

## 5. Build the add-in and open it in Excel

```powershell
.\tools\excel_dev.ps1
```

This builds the add-in in Release, writes `goosedove.cfg` beside it so that Excel finds this clone's `src` and this environment's Python, and opens a fresh, visible Excel with the add-in loaded. The first run takes a minute or two while NuGet restores packages; later runs take seconds. Run it again after a change: it closes the Excel it opened last time, offers to save, and opens a new one.

In the sheet, type each of these in a cell:

| Formula | Shows | Which proves |
|---|---|---|
| `=GoosedoveStatus()` | `ok: python started and functions registered` | the add-in loaded and started Python |
| `=Ping()` | `goosedove` and a version, then `from` and a path inside this clone's `src\goosedove` | this clone's code is the one running |
| `=Add(1,2)` | `3` | a call crosses to Python and comes back |
| `=_CreateValuationDate(DATE(2026,9,11),0.5)` | `valuation_date:` followed by two numbers | the library's first creator works |
| `=util_ReadHandle(A4)`, with the creator in A4 | the object spilled as a small table | a handle resolves and spills |

`Add` is a probe of the seam, so Excel's function wizard does not offer it; type it in full. Typing `_` in a cell lists the library's own functions. To see every function on a real sheet, open the shared workbook instead, recalculated so that its handles belong to your session:

```powershell
.\tools\excel_dev.ps1 workbooks\handles.xlsx
```

## 6. Load the add-in in your own Excel, permanently

Step 5 loads the add-in for one session. To have it in every Excel you open: File > Options > Add-ins, set Manage to Excel Add-ins, Go, Browse, pick `host\Goosedove.Host\bin\Release\net48\Goosedove.Host-AddIn64.xll`, OK. It loads at every start until you clear its tick in that list. Pick the `AddIn64` file: the `Goosedove.Host-AddIn.xll` beside it is the 32-bit build, which cannot load a 64-bit Python.

Two things to know. `goosedove.cfg` holds absolute paths, so keep the clone where it is; after moving it or recreating `.venv`, run `.\tools\excel_dev.ps1` once to rewrite the file. And Excel holds the `.xll` while it is open, so close every Excel before rebuilding.

After every `git pull`:

```powershell
uv sync --locked
dotnet build host\Goosedove.Host -c Release
```

The second line rebuilds the add-in; `.\tools\excel_dev.ps1` does the same and opens Excel.

## 7. Run the whole check

```powershell
.\check.ps1
```

Six steps in order, stopping at the first failure: formatting, lint, types, the Python tests, the host's own tests, and the add-in in a hidden Excel of its own, one formula per row compared with the text it must show. It takes a few minutes. Without Excel installed, the first five pass and the last stops and says so.

## When something fails

| What you see | Why | What to do |
|---|---|---|
| `uv` is not recognized | not installed, the terminal was opened before the install, or that Python's `Scripts` folder is not on your PATH | step 2: install it, put the folder on your PATH, then close and reopen the terminal |
| `dotnet` is not recognized | not installed, or the terminal was opened before the install | install it, or close and reopen the terminal |
| `uv sync --locked` says the lock file needs updating | `pyproject.toml` or `uv.lock` differs from `main` | `git status`, then `git pull`; never edit the lock by hand |
| `dotnet` says a compatible SDK was not found, requested 8.0.423 | only another major version of the SDK is installed | install the .NET 8.0 SDK |
| the build says the reference assemblies for .NETFramework v4.8 were not found | the first restore could not reach NuGet | check the network or proxy, then `dotnet restore host\Goosedove.Host` |
| `running scripts is disabled on this system` | the execution policy of step 1 | set it, or use the `-ExecutionPolicy Bypass` form |
| `=GoosedoveStatus()` shows `#NAME?` | the add-in is not loaded in this Excel, or this Excel is 32-bit | check File > Account > About Excel; load it by step 5 or 6 |
| `=GoosedoveStatus()` shows an error naming Python or the config | `goosedove.cfg` is missing or stale, after a move or a new `.venv` | run `.\tools\excel_dev.ps1` once |
| the build says the `.xll` is in use | an Excel still has it loaded | close every Excel, including any hidden one in Task Manager, and build again |
| Excel warns of a potential security concern when loading the `.xll` | it is a file built on this machine, unsigned | Enable |
| `tests\test_smoke.py` fails about 64-bit | the environment's Python is 32-bit | install the 64-bit 3.13.13, delete `.venv`, run `uv sync --locked` again |
| `excel_smoke.ps1` cannot start a hidden Excel | Excel is not installed or not activated | the five steps before it have already passed; run the smoke on a machine with Excel |

## Where to read next

[README.md](../README.md) lists the daily commands. [docs/seam/working.md](seam/working.md) says how a change is checked and, in its section 8, how the add-in is loaded by hand and what `goosedove.cfg` holds. [docs/library/README.md](library/README.md) is one page per worksheet function, and [docs/seam/README.md](seam/README.md) is the way into everything written about the seam, the one place Excel and Python meet.
