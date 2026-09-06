$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    foreach ($measurementScript in @(
        "tools/performance/profile_workload.py"
        "tools/performance/measure_resources.py"
    )) {
        Write-Host ">> uv run python $measurementScript"
        & uv run python $measurementScript
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    Write-Host "Measurement smoke checks completed."
}
finally {
    Pop-Location
}
