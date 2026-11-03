# Dot-source this file for an Excel automation session that must end before the script returns.
if (-not ("Catalyst.Tools.ExcelWindow" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
namespace Catalyst.Tools {
    public static class ExcelWindow {
        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    }
}
"@
}

# --- a busy Excel ------------------------------------------------------------------------------
# Excel refuses a call from outside while it is busy: an add-in still loading, a calculation, a
# live-data callback being delivered, a dialog. A refused call was never made, so making it
# again is safe, and waiting and trying again is what Office automation is told to do
# (learn.microsoft.com, "Threading support in Office"). Two results mean busy and only they are
# tried again; every other failure leaves at once, as it came.
#
# PowerShell shows a refusal in two ways. A method call, or a property written, fails with the
# error. A property read with a dot does not: PowerShell answers any read that failed with
# nothing, so `$cell.Text` on a busy Excel is $null and no error at all. Read-ExcelProperty reads
# a property so that the failure is kept, and a refused read is then made again like any other
# call. Every property of Excel's read in this file, the smoke and the lifetime checks goes
# through it.
$ExcelBusyResults = @{
    -2147418111 = "RPC_E_CALL_REJECTED (0x80010001)"
    -2147417846 = "RPC_E_SERVERCALL_RETRYLATER (0x8001010A)"
}
$ExcelBusySeconds = 30  # how long one call may go on being refused before it fails
$ExcelBusyPause = 50    # milliseconds between two tries
# One record for every call that had to wait, for the report a tool prints when it ends. What a
# call returns is never touched by any of it.
$ExcelBusyWaits = [Collections.Generic.List[object]]::new()

# What is said about a busy Excel is worded the same on every machine: a number is written with
# a decimal point whatever the regional settings, since the words are compared by the self-test
# and quoted in the docs. PowerShell's own -f follows the machine and writes 0,3 on some.
function Format-ExcelBusyText([string]$ExcelFormat) {
    return [string]::Format([Globalization.CultureInfo]::InvariantCulture, $ExcelFormat, $args)
}

# The busy result an error carries, or nothing. PowerShell wraps a COM error, sometimes twice,
# so the whole chain of exceptions is read.
function Get-ExcelBusyResult($ErrorRecord) {
    $excelFault = $ErrorRecord.Exception
    while ($excelFault) {
        if ($ExcelBusyResults.ContainsKey($excelFault.HResult)) { return $excelFault.HResult }
        $excelFault = $excelFault.InnerException
    }
    return $null
}

# Makes one call into Excel, and makes it again while Excel refuses it as busy, until it is taken
# or its time runs out. The time is a deadline: the caller's, when the caller has one of its own
# that this call must not outlast, and otherwise $ExcelBusySeconds from now. The call is always
# made once. When the time runs out the failure names the operation, the cell, the result, the
# tries and the time taken.
#
# An action that hands back a COM object writes it with a leading comma, so that PowerShell
# passes it on whole and does not walk it as a collection, and the caller registers the reference
# once, after it has been handed over. An action never reads a property with a dot: the failure
# would be hidden from this function too. The names in here are kept apart from any an action
# could mean: the action runs under this function and reads its caller's variables through it.
function Invoke-ExcelCall([string]$ExcelOperation, [scriptblock]$ExcelAction, [string]$ExcelAddress = "", $ExcelDeadline = $null) {
    $excelClock = [Diagnostics.Stopwatch]::StartNew()
    $excelLimit = if ($null -ne $ExcelDeadline) { $ExcelDeadline } else { [datetime]::UtcNow.AddSeconds($ExcelBusySeconds) }
    $excelWhere = if ($ExcelAddress) { "$ExcelOperation at $ExcelAddress" } else { $ExcelOperation }
    $excelResult = $null
    for ($excelTry = 1; ; $excelTry++) {
        try {
            $excelResult = & $ExcelAction
            break
        }
        catch {
            $excelBusy = Get-ExcelBusyResult $_
            if ($null -eq $excelBusy) { throw }
            if ([datetime]::UtcNow -ge $excelLimit) {
                $excelSeconds = $excelClock.Elapsed.TotalSeconds
                $ExcelBusyWaits.Add([pscustomobject]@{ What = $excelWhere; Refusals = $excelTry; Seconds = $excelSeconds; Taken = $false })
                throw (Format-ExcelBusyText "Excel stayed busy: {0} was refused {1} time(s) over {2:F1} s, the last time with {3}" $excelWhere $excelTry $excelSeconds ($ExcelBusyResults[$excelBusy]))
            }
            Start-Sleep -Milliseconds $ExcelBusyPause
        }
    }
    if ($excelTry -gt 1) {
        $ExcelBusyWaits.Add([pscustomobject]@{ What = $excelWhere; Refusals = $excelTry - 1; Seconds = $excelClock.Elapsed.TotalSeconds; Taken = $true })
    }
    if ($null -ne $excelResult) { Write-Output -NoEnumerate $excelResult }
}

# Reads one property of an Excel object through InvokeMember, which keeps the failure that
# PowerShell's dot would hide, and makes the read again while Excel refuses it, as
# Invoke-ExcelCall does for any call. What the property holds is handed back whole, a collection
# included, and judged by the caller.
function Read-ExcelProperty($ExcelObject, [string]$ExcelName, [string]$ExcelAddress = "", $ExcelDeadline = $null) {
    Invoke-ExcelCall "read $ExcelName" { , $ExcelObject.GetType().InvokeMember($ExcelName, [Reflection.BindingFlags]::GetProperty, $null, $ExcelObject, $null) } $ExcelAddress $ExcelDeadline
}

# What a run met: how many calls had to wait, how often they were refused and for how long.
# Printed for the reader of the run; never part of what a call returns.
function Write-ExcelBusyReport {
    if ($ExcelBusyWaits.Count -eq 0) {
        Write-Host "busy Excel: no call had to wait"
        return
    }
    $refusals = ($ExcelBusyWaits | Measure-Object -Property Refusals -Sum).Sum
    $longest = ($ExcelBusyWaits | Measure-Object -Property Seconds -Maximum).Maximum
    Write-Host (Format-ExcelBusyText "busy Excel: {0} call(s) had to wait, {1} refusal(s) in all, the longest wait {2:F2} s" $ExcelBusyWaits.Count $refusals $longest)
    foreach ($wait in ($ExcelBusyWaits | Select-Object -First 10)) {
        $end = if ($wait.Taken) { "then taken" } else { "never taken" }
        Write-Host (Format-ExcelBusyText "     {0}: refused {1} time(s) over {2:F2} s, {3}" $wait.What $wait.Refusals $wait.Seconds $end)
    }
}

# Return ownership only once the window's process has been verified and its handle retained.
# A failed lookup never supplies a process that cleanup could accidentally terminate.
function Get-HiddenExcelProcess($Excel) {
    $excelProcessId = [uint32]0
    [void][Catalyst.Tools.ExcelWindow]::GetWindowThreadProcessId([IntPtr](Read-ExcelProperty $Excel "Hwnd"), [ref]$excelProcessId)
    if (-not $excelProcessId) { throw "could not identify the hidden Excel process" }
    $process = [Diagnostics.Process]::GetProcessById($excelProcessId)
    try {
        # Retain the process handle, not just its reusable numeric ID.
        [void]$process.Handle
        if ($process.ProcessName -ne "EXCEL") { throw "the hidden Excel window belongs to $($process.ProcessName)" }
        return $process
    }
    catch {
        $process.Dispose()
        throw
    }
}

function Start-HiddenExcel {
    $session = [pscustomobject]@{ Excel = (New-Object -ComObject Excel.Application); Process = $null }
    try {
        $session.Process = Get-HiddenExcelProcess $session.Excel
        Invoke-ExcelCall "hide Excel" { $session.Excel.Visible = $false }
        Invoke-ExcelCall "silence alerts" { $session.Excel.DisplayAlerts = $false }
        return $session
    }
    catch {
        # A startup failure has no caller-owned session yet. End it here through the same
        # terminal path as a completed session, even when Quit is refused.
        Stop-HiddenExcel $session ([Collections.Generic.List[object]]::new()) $null -FailureInFlight
        throw
    }
}

function Close-HiddenExcelWorkbook($Excel, $Book, $Deadline = [datetime]::UtcNow) {
    # IntelliSense releases its workbook references on WorkbookBeforeClose. The timing runner
    # disables events during measurement, but closing a workbook must still deliver that event.
    # Without a deadline each call is made once, as it always was: the cleanup path gives none,
    # so a busy Excel there fails at once and the terminal order goes on. A tool that closes a
    # workbook as a step of its own gives one, and waits for a busy Excel as for any call of its.
    $eventsEnabled = Read-ExcelProperty $Excel "EnableEvents" "" $Deadline
    try {
        Invoke-ExcelCall "enable events" { $Excel.EnableEvents = $true } "" $Deadline
        Invoke-ExcelCall "close the workbook" { $Book.Close($false) } "" $Deadline
    }
    finally { Invoke-ExcelCall "restore EnableEvents" { $Excel.EnableEvents = $eventsEnabled } "" $Deadline }
}

function Stop-HiddenExcel($Session, $Objects, $Book, [switch]$AddInLoaded, [switch]$FailureInFlight) {
    $problems = [Collections.Generic.List[string]]::new()
    # Each step still runs if the one before it failed. The host command is terminal: after
    # it releases the add-in's own Excel references, only closing the automation client remains.
    if ($Book) {
        try { Close-HiddenExcelWorkbook $Session.Excel $Book } catch { $problems.Add("closing the workbook: $_") }
    }
    if ($AddInLoaded) {
        try { [void]$Session.Excel.Run("CatalystPrepareToQuit") }
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
    if ($Session.Process) {
        try {
            if (-not $Session.Process.WaitForExit(5000)) {
                $problems.Add("hidden Excel process $($Session.Process.Id) did not exit within five seconds; terminating this session's process")
                $Session.Process.Kill()
                if (-not $Session.Process.WaitForExit(5000)) { $problems.Add("the owned Excel process still has not exited") }
            }
        }
        catch { $problems.Add("waiting for the owned Excel process: $_") }
        finally { $Session.Process.Dispose() }
    }
    else {
        $problems.Add("could not verify Excel exit because its process was not identified")
    }
    if ($problems.Count) {
        $message = "hidden Excel cleanup failed: " + ($problems -join "; ")
        if ($FailureInFlight) { Write-Warning $message -WarningAction Continue }
        else { throw $message }
    }
}
