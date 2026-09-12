$ErrorActionPreference = "Stop"

# The Python side: a sampling profile per probe, warm timings per probe and size, and the
# one-table summary. The host runner and the Excel runner have their own commands; see
# docs/seam/measuring.md.
Push-Location $PSScriptRoot
try {
    foreach ($script in @(
        "tools/performance/profile_workload.py",
        "tools/performance/measure_python.py",
        "tools/performance/summarize.py"
    )) {
        Write-Host ">> uv run python $script"
        & uv run python $script
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    Write-Host "Reports written to profiles/."
}
finally {
    Pop-Location
}
