# Builds the add-in and opens it in a fresh, visible Excel for trying formulas by hand.
# Run it again after a change: it closes the Excel it opened last time, through that window
# so Excel can offer to save, and never touches any other Excel.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "host_build.ps1")
$pidFile = Join-Path $root "host\Goosedove.Host\bin\excel_dev.pid"

if (Test-Path $pidFile) {
    $previous = Get-Process -Id (Get-Content $pidFile) -ErrorAction SilentlyContinue
    if ($previous -and $previous.ProcessName -eq "EXCEL") {
        # Ask through the window, and keep asking: an Excel still starting has no window yet,
        # and a person asked to save may say no. Refresh, or .NET keeps the first, empty
        # window handle it saw. Give up after a minute either way.
        $deadline = (Get-Date).AddSeconds(60)
        while (-not $previous.HasExited -and (Get-Date) -lt $deadline) {
            $previous.Refresh()
            [void]$previous.CloseMainWindow()
            [void]$previous.WaitForExit(5000)
        }
        if (-not $previous.HasExited) {
            throw "the Excel opened by the last run is still open; save or close it, then run again"
        }
    }
    Remove-Item $pidFile
}

$xll = Build-HostAddIn -Root $root

# Start Excel from a throwaway process. While any automation client holds an Excel, that
# Excel ignores asks to close, so the client must be gone before the person has it.
$start = @"
`$excel = New-Object -ComObject Excel.Application
try {
    if (-not `$excel.RegisterXLL('$xll')) { throw 'Excel refused to load $xll' }
    [void]`$excel.Workbooks.Add()
    `$excel.Visible = `$true
    `$excel.UserControl = `$true
}
catch {
    `$excel.Quit()
    throw
}
"@
$before = @(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
powershell -NoProfile -Command $start
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$started = @(Get-Process EXCEL | Where-Object { $before -notcontains $_.Id })
if ($started.Count -eq 1) {
    Set-Content -Path $pidFile -Value $started[0].Id
    # Hand over only once the window exists, so a run straight after this one can close it.
    $deadline = (Get-Date).AddSeconds(60)
    while ($started[0].MainWindowHandle -eq 0 -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $started[0].Refresh()
    }
}
