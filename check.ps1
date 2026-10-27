$ErrorActionPreference = "Stop"
$steps = @(
  "uv run ruff format .",
  "uv run ruff check --fix .",
  "uv run pyright",
  "uv run pytest -n auto",
  "dotnet test host\Goosedove.Host.Tests -c Release --nologo -v q",
  "powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_busy_selftest.ps1",
  "powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_session_selftest.ps1",
  "powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_smoke.ps1",
  "powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_lifetime.ps1 -Groups core,processes,trades,valuation,calendars,bumps,curves,cashflows,quotes,pairs"
)
foreach ($s in $steps) {
  Write-Host ">> $s"
  Invoke-Expression $s
  if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
Write-Host "all checks passed"
