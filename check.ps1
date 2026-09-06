$steps = @(
  "uv run ruff format --check .",
  "uv run ruff check .",
  "uv run pyright",
  "uv run pytest -n auto"
)
foreach ($s in $steps) {
  Write-Host ">> $s"
  Invoke-Expression $s
  if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
Write-Host "all checks passed"