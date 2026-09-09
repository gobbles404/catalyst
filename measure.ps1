$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    Write-Host ">> uv run python tools/performance/profile_workload.py"
    & uv run python tools/performance/profile_workload.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Profiles written to profiles/."
}
finally {
    Pop-Location
}
