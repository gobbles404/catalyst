$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$xll = Join-Path $root "host\Goosedove.Host\bin\Debug\net48\Goosedove.Host-AddIn64.xll"

Get-Process EXCEL -ErrorAction SilentlyContinue | Stop-Process -Force
dotnet build (Join-Path $root "host\Goosedove.Host") --nologo -v q
if ($LASTEXITCODE) { exit $LASTEXITCODE }
Start-Process excel.exe -ArgumentList "`"$xll`""
