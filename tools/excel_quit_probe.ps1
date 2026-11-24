# Shows how a hidden Excel quits on this machine. Run it where a tool's ending fails with
# "did not exit", and read the rows: docs/seam/host.md, "When a hidden Excel quits", says what
# they mean. It starts a hidden Excel of its own for each row, loads the built add-in, asks Excel
# to quit at the row's moment and prints how long the exit took, or what the process looked like
# when it had not exited in the time a tool's ending gives it. It ends only the Excel it started.
#
#     .\tools\excel_quit_probe.ps1
#
#   at once      Quit as soon as the add-in has loaded, while Excel may still be starting: the
#                case that fails. Excel may take a minute to end by itself here.
#   when still   Quit after the wait every tool's ending makes, until Excel's processor time has
#                stood still. These rows must exit, and the probe exits with the count that did not.
#   after N s    Quit N seconds after the add-in has loaded, with no other wait: where the first
#                of these rows exits shows how long this machine's Excel takes to finish starting.
param([int[]]$After = @(5, 10), [int]$Times = 2)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "host_build.ps1")
. (Join-Path $PSScriptRoot "hidden_excel.ps1")
$xll = Build-HostAddIn -Root $root

# One hidden Excel with the add-in loaded, asked to quit at the row's moment. The ending is the
# tools' own order, the command, Quit and the release, without the workbook a tool would close.
function Measure-Quit([string]$Row, [switch]$WhenStill, [int]$Pause = 0) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $session = Start-HiddenExcel
    $ready = $clock.Elapsed.TotalSeconds
    $exited = $false
    $line = ""
    try {
        if (-not (Invoke-ExcelCall "register the add-in" { $session.Excel.RegisterXLL($xll) })) { throw "Excel refused to load $xll" }
        if ($Pause) { Start-Sleep -Seconds $Pause }
        $waited = if ($WhenStill) { ", " + (Wait-HiddenExcelStill $session.Process) } else { "" }
        try { [void]$session.Excel.Run("CatalystPrepareToQuit") } catch { $line += "the add-in's preparation failed: $_; " }
        $age = ([datetime]::Now - $session.Process.StartTime).TotalSeconds
        $processorTime = Get-HiddenExcelProcessorTime $session.Process
        $exit = [Diagnostics.Stopwatch]::StartNew()
        try { $session.Excel.Quit() } catch { $line += "Quit failed: $_; " }
    }
    finally {
        # The release is what lets Excel go, and it waits while Excel is busy with its exit.
        try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($session.Excel) } catch { $line += "the release failed: $_; " }
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
        try {
            # As a tool's ending does it: never a wait shorter than a second, and an Excel that
            # went while it was being looked at is not one to stop.
            $left = [int][Math]::Max(1000, $HiddenExcelExitSeconds * 1000 - $(if ($exit) { $exit.ElapsedMilliseconds } else { 0 }))
            $exited = $session.Process.WaitForExit($left)
            if (-not $exited) {
                $state = Get-HiddenExcelState $session.Process $processorTime
                $exited = $session.Process.HasExited
            }
            if ($exited -and $exit) { $line += Format-ExcelBusyText "exited {0:F1} s after Quit" $exit.Elapsed.TotalSeconds }
            elseif ($exited) { $line += "exited" }
            else {
                $line += "did not exit in $HiddenExcelExitSeconds s: $state; ended by the probe"
                $session.Process.Kill()
                if (-not $session.Process.WaitForExit(5000)) { $line += ", and still there" }
            }
        }
        finally { $session.Process.Dispose() }
    }
    Write-Host (Format-ExcelBusyText "{0,-11} Excel ready after {1:F1} s, {2:F1} s old at Quit{3}: {4}" $Row $ready $age $waited $line)
    return ($exited -and $exit.Elapsed.TotalSeconds -le $HiddenExcelExitSeconds)
}

$unexited = 0
$rows = @()
1..$Times | ForEach-Object { $rows += , @("at once", $false, 0) }
1..$Times | ForEach-Object { $rows += , @("when still", $true, 0) }
foreach ($seconds in $After) { $rows += , @("after $seconds s", $false, $seconds) }
foreach ($row in $rows) {
    $ok = Measure-Quit $row[0] -WhenStill:$row[1] -Pause $row[2]
    if ($row[1] -and -not $ok) { $unexited++ }
}
Write-Host "this machine: $($script:HiddenExcelFacts)"
Write-ExcelBusyReport
Write-Host "excel quit probe: $($rows.Count) rows; of the $Times made as a tool's ending, $unexited did not exit in time"
exit $unexited
