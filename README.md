# goosedove

A commodities derivatives pricing library for Excel.

The [library planning review](docs/library-review.md) is the entry point for the
draft Globals, interpolation utility, and handle research. These documents capture
the approach before implementation and mark decisions that remain open.

## Setup

Requires Python 3.13.13 and uv 0.12.9 (`py -3.13 -m pip install uv==0.12.9`).

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

How the seam is measured, what is counted and what is timed, is in [docs/seam/measuring.md](docs/seam/measuring.md).

## The add-in

The host finds Python through `goosedove.cfg` beside the `.xll`, two lines:

    pythondll=C:\...\python313.dll
    pythonpath=C:\...\goosedove\src;C:\...\site-packages

`tools\excel_dev.ps1` and `tools\excel_smoke.ps1` write it from the project's own environment. An add-in deployed elsewhere needs one written by hand.
