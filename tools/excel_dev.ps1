$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$xll = Join-Path $root "host\Goosedove.Host\bin\Debug\net48\Goosedove.Host-AddIn64.xll"

Get-Process EXCEL -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1
dotnet build (Join-Path $root "host\Goosedove.Host") --nologo -v q
if ($LASTEXITCODE) { exit $LASTEXITCODE }

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $true
$excel.RegisterXLL($xll) | Out-Null
$excel.Workbooks.Add() | Out-Null
