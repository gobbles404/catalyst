$steps = @(
  "uv run ruff format .",
  "uv run ruff check --fix .",
  "uv run pyright",
  "uv run pytest -n auto"
)
foreach ($s in $steps) {
  Write-Host ">> $s"
  Invoke-Expression $s
  if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
Write-Host "all checks passed"
