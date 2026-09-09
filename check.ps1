$ErrorActionPreference = "Stop"
$steps = @(
  "uv run ruff format .",
  "uv run ruff check --fix .",
  "uv run pyright",
  "uv run pytest -n auto",
  "dotnet test host\Goosedove.Host.Tests --nologo -v q",
  "powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_smoke.ps1"
)
foreach ($s in $steps) {
  Write-Host ">> $s"
  Invoke-Expression $s
  if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
Write-Host "all checks passed"
