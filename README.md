# goosedove

A commodities derivatives pricing library for Excel.

## Setup

Requires Python 3.13.13 and uv 0.12.9 (`py -3.13 -m pip install uv==0.12.9`).

On a fresh machine, [docs/getting-started.md](docs/getting-started.md) walks from the clone to a formula in Excel, one step at a time, with a check after each and a table of what to do when a step fails.

    uv sync --locked
    .\check.ps1

`check.ps1` runs format, lint, type check, the Python tests, the host's own tests, and then the add-in in a hidden Excel, and stops at the first failure. The last step needs Excel installed; without it the check fails and says so.

## Daily

    uv sync --locked            after pulling
    uv run ruff format .        fix formatting
    .\check.ps1                 before pushing
    uv add <package>            add a dependency and update the lock
    .\measure.ps1               profile and time every probe on the Python side; reports land in profiles/
    .\tools\excel_dev.ps1       build the add-in and open it in a fresh Excel
    .\tools\excel_dev.ps1 workbooks\handles.xlsx    the same, on a saved workbook
    .\tools\excel_show.ps1 workbooks\handles.xlsx   print a workbook as its cells show, with the add-in loaded

How the pieces fit together, from an index to a risk report, and where each responsibility lives, is [docs/architecture.md](docs/architecture.md); which page owns which fact is [docs/seam/working.md](docs/seam/working.md#10-what-each-page-owns). How the seam is measured, what is counted and what is timed, is in [docs/seam/measuring.md](docs/seam/measuring.md). Everything written about the seam, the one place Excel and Python talk, starts at [docs/seam/README.md](docs/seam/README.md); the library's worksheet functions, one page each that is the spec until the function is built, start at [docs/library/README.md](docs/library/README.md).

## The add-in

The host finds Python through `goosedove.cfg` beside the `.xll`, two lines:

    pythondll=C:\...\python313.dll
    pythonpath=C:\...\goosedove\src;C:\...\site-packages

`tools\excel_dev.ps1` and `tools\excel_smoke.ps1` write it from the project's own environment. An add-in deployed elsewhere needs one written by hand.
