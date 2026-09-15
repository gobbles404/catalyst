# Dot-source this file for an Excel automation session that must end before the script returns.
if (-not ("Goosedove.Tools.ExcelWindow" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
namespace Goosedove.Tools {
    public static class ExcelWindow {
        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    }
}
"@
}

function Start-HiddenExcel {
    $process = $null
    $excel = New-Object -ComObject Excel.Application
    try {
        $excel.Visible = $false
        $excel.DisplayAlerts = $false
        $excelProcessId = [uint32]0
        [void][Goosedove.Tools.ExcelWindow]::GetWindowThreadProcessId([IntPtr]$excel.Hwnd, [ref]$excelProcessId)
        if (-not $excelProcessId) { throw "could not identify the hidden Excel process" }
        $process = [Diagnostics.Process]::GetProcessById($excelProcessId)
        # Retain the process handle, not just its reusable numeric ID.
        [void]$process.Handle
        if ($process.ProcessName -ne "EXCEL") { throw "the hidden Excel window belongs to $($process.ProcessName)" }
        return [pscustomobject]@{ Excel = $excel; Process = $process }
    }
    catch {
        try { $excel.Quit() } catch { Write-Warning "Excel startup cleanup: $_" -WarningAction Continue }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
        if ($process) { $process.Dispose() }
        throw
    }
}

function Close-HiddenExcelWorkbook($Excel, $Book) {
    # IntelliSense releases its workbook references on WorkbookBeforeClose. The timing runner
    # disables events during measurement, but closing a workbook must still deliver that event.
    $eventsEnabled = $Excel.EnableEvents
    try {
        $Excel.EnableEvents = $true
        $Book.Close($false)
    }
    finally { $Excel.EnableEvents = $eventsEnabled }
}

function Stop-HiddenExcel($Session, $Objects, $Book, [switch]$AddInLoaded, [switch]$FailureInFlight) {
    $problems = [Collections.Generic.List[string]]::new()
    # Each step still runs if the one before it failed. The host command is terminal: after
    # it releases the add-in's own Excel references, only closing the automation client remains.
    if ($Book) {
        try { Close-HiddenExcelWorkbook $Session.Excel $Book } catch { $problems.Add("closing the workbook: $_") }
    }
    if ($AddInLoaded) {
        try { [void]$Session.Excel.Run("GoosedovePrepareToQuit") }
        catch { $problems.Add("preparing the add-in to quit: $_") }
    }
    try { $Session.Excel.Quit() } catch { $problems.Add("quitting Excel: $_") }
    for ($i = $Objects.Count - 1; $i -ge 0; $i--) {
        try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($Objects[$i]) }
        catch { $problems.Add("releasing an Excel object: $_") }
    }
    try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($Session.Excel) }
    catch { $problems.Add("releasing Excel: $_") }
    $Objects.Clear()
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    try {
        if (-not $Session.Process.WaitForExit(5000)) {
            $problems.Add("hidden Excel process $($Session.Process.Id) did not exit within five seconds; terminating this session's process")
            $Session.Process.Kill()
            if (-not $Session.Process.WaitForExit(5000)) { $problems.Add("the owned Excel process still has not exited") }
        }
    }
    catch { $problems.Add("waiting for the owned Excel process: $_") }
    finally { $Session.Process.Dispose() }
    if ($problems.Count) {
        $message = "hidden Excel cleanup failed: " + ($problems -join "; ")
        if ($FailureInFlight) { Write-Warning $message -WarningAction Continue }
        else { throw $message }
    }
}
