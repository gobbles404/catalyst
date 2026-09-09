# goosedove

A commodities derivatives pricing library for Excel.

## Setup

Requires Python 3.13.13 and uv 0.12.9 (`py -3.13 -m pip install uv==0.12.9`).

    uv sync --locked
    .\check.ps1

`check.ps1` runs format, lint, type check, tests, and then the add-in in a hidden Excel, and stops at the first failure. The last step needs Excel installed; without it the check fails and says so.

## Daily

    uv sync --locked            after pulling
    uv run ruff format .        fix formatting
    .\check.ps1                 before pushing
    uv add <package>            add a dependency and update the lock
    .\measure.ps1               profile every worksheet function; reports land in profiles/
