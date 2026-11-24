# Dot-source this file for an Excel automation session that must end before the script returns.
if (-not ("Catalyst.Tools.ExcelWindow" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
namespace Catalyst.Tools {
    public static class ExcelWindow {
        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);

        private delegate bool WindowVisitor(IntPtr window, IntPtr unused);
        [DllImport("user32.dll")]
        private static extern bool EnumWindows(WindowVisitor visitor, IntPtr unused);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern int GetClassName(IntPtr window, StringBuilder name, int capacity);
        [DllImport("user32.dll")]
        private static extern IntPtr SendMessageTimeout(IntPtr window, uint message, IntPtr first, IntPtr second, uint flags, uint milliseconds, out IntPtr result);
        [DllImport("kernel32.dll")]
        private static extern bool IsWow64Process(IntPtr process, out bool underEmulation);

        // What a process's Excel window does with a message that asks for nothing: "answers",
        // "does not answer" within the time, or "is gone" when the process has no such window.
        public static string Answer(uint processId, uint milliseconds) {
            IntPtr found = IntPtr.Zero;
            EnumWindows(delegate(IntPtr window, IntPtr unused) {
                uint owner;
                GetWindowThreadProcessId(window, out owner);
                if (owner != processId) return true;
                StringBuilder name = new StringBuilder(64);
                GetClassName(window, name, 64);
                if (name.ToString() != "XLMAIN") return true;
                found = window;
                return false;
            }, IntPtr.Zero);
            if (found == IntPtr.Zero) return "is gone";
            IntPtr result;
            return SendMessageTimeout(found, 0, IntPtr.Zero, IntPtr.Zero, 2, milliseconds, out result) != IntPtr.Zero ? "answers" : "does not answer";
        }

        // 64 or 32, the kind of program a process is, from its handle.
        public static int Bits(IntPtr process) {
            bool underEmulation;
            if (!Environment.Is64BitOperatingSystem) return 32;
            if (!IsWow64Process(process, out underEmulation)) throw new InvalidOperationException("the process could not be asked");
            return underEmulation ? 32 : 64;
        }
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

# --- what this machine's Excel is -----------------------------------------------------------------
# Read once a run, from the first hidden Excel, and said where an ending fails and by the quit
# probe: Excel's version and build, whether it is a 32-bit or a 64-bit program, the COM add-ins it
# has connected and the add-ins it has open. An Excel started from outside loads its COM add-ins
# and opens no others by itself. Nothing here can fail a session: what cannot be read is said so.
$script:HiddenExcelFacts = $null

# The names of the members of one of Excel's collections for which a property of theirs is true.
function Read-HiddenExcelNames($Excel, [string]$Collection, [string]$Flag, [string]$Name) {
    $members = $null
    try {
        $members = Read-ExcelProperty $Excel $Collection
        $names = [Collections.Generic.List[string]]::new()
        foreach ($member in $members) {
            try { if ([bool](Read-ExcelProperty $member $Flag)) { $names.Add([string](Read-ExcelProperty $member $Name)) } }
            finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($member) }
        }
        if ($names.Count) { return ($names -join ", ") }
        return "none"
    }
    catch { return "not read" }
    finally { if ($null -ne $members) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($members) } }
}

function Read-HiddenExcelFacts($Session) {
    if ($script:HiddenExcelFacts) { return }
    $version = try { "Excel " + [string](Read-ExcelProperty $Session.Excel "Version") + " build " + [string](Read-ExcelProperty $Session.Excel "Build") } catch { "Excel's version not read" }
    $bits = try { [string][Catalyst.Tools.ExcelWindow]::Bits($Session.Process.Handle) + "-bit" } catch { "bitness not read" }
    $connected = Read-HiddenExcelNames $Session.Excel "COMAddIns" "Connect" "ProgId"
    $open = Read-HiddenExcelNames $Session.Excel "AddIns2" "IsOpen" "Name"
    $script:HiddenExcelFacts = "$version, $bits; COM add-ins connected: $connected; add-ins open: $open"
}

function Start-HiddenExcel {
    $session = [pscustomobject]@{ Excel = (New-Object -ComObject Excel.Application); Process = $null }
    try {
        $session.Process = Get-HiddenExcelProcess $session.Excel
        Invoke-ExcelCall "hide Excel" { $session.Excel.Visible = $false }
        Invoke-ExcelCall "silence alerts" { $session.Excel.DisplayAlerts = $false }
        Read-HiddenExcelFacts $session
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

# --- ending a hidden Excel ------------------------------------------------------------------------
# An Excel told to quit while Excel itself is still starting does not exit: with the add-in loaded
# it closes its window and then stands, using no processor time, for sixty seconds before it ends
# without running the add-in's exit work. A session that lives only a few seconds can reach its end
# inside that time, on a machine whose Excel starts slowly. So an ending first waits until Excel
# has finished starting, then runs the terminal order, and counts Excel's exit from the Quit call.
# docs/seam/host.md, "When a hidden Excel quits", has the measurements.
$HiddenExcelStillSeconds = 1   # Excel has finished starting once its processor time has stood still this long
$HiddenExcelStartSeconds = 30  # the most an ending waits for that before it goes on regardless
$HiddenExcelExitSeconds = 20   # how long Excel may take to exit, counted from the Quit call
$HiddenExcelSlowSeconds = 5    # an exit slower than this passes, and is said

# A process's processor time so far, or nothing where it cannot be read.
function Get-HiddenExcelProcessorTime($Process) {
    try {
        $Process.Refresh()
        return $Process.TotalProcessorTime.Ticks
    }
    catch { return $null }
}

# Waits until a hidden Excel has finished starting, by the one sign of it seen from outside: its
# processor time, which goes on moving while Excel starts and stands still once it has. A session
# that has long been idle waits the still time and no more. Returns what it saw, in words for a
# report, and never fails: after the start time it goes on, and says so.
function Wait-HiddenExcelStill($Process) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $last = Get-HiddenExcelProcessorTime $Process
    if ($null -eq $last) { return "its processor time could not be read, so nothing was waited for" }
    $stillFrom = [TimeSpan]::Zero
    while ($true) {
        $still = ($clock.Elapsed - $stillFrom).TotalSeconds
        if ($still -ge $HiddenExcelStillSeconds) {
            return (Format-ExcelBusyText "its processor time had stood still for {0:F1} s after a wait of {1:F1} s" $still $clock.Elapsed.TotalSeconds)
        }
        if ($clock.Elapsed.TotalSeconds -ge $HiddenExcelStartSeconds) {
            return (Format-ExcelBusyText "its processor time never stood still for {0} s in the {1} s it was given" $HiddenExcelStillSeconds $HiddenExcelStartSeconds)
        }
        Start-Sleep -Milliseconds 100
        $now = Get-HiddenExcelProcessorTime $Process
        if ($now -ne $last) {
            $last = $now
            $stillFrom = $clock.Elapsed
        }
    }
}

# What an Excel that has not exited looks like from outside, for the failure that reports it: its
# window, its threads and the processor time it has used since the Quit call. A window that is
# gone means Excel is on its way out; one that answers means Excel is alive and something holds
# it; little processor time means it is waiting, not working.
function Get-HiddenExcelState($Process, $ProcessorTimeAtQuit) {
    $window = try { [Catalyst.Tools.ExcelWindow]::Answer([uint32]$Process.Id, 1000) } catch { "was not read" }
    $now = Get-HiddenExcelProcessorTime $Process
    $used = if ($null -ne $now -and $null -ne $ProcessorTimeAtQuit) { Format-ExcelBusyText "{0:F2} s" (($now - $ProcessorTimeAtQuit) / 1e7) } else { "an unread amount" }
    $threads = if ($Process.Threads) { [string]$Process.Threads.Count } else { "an unread number of" }
    return "its window $window, it has $threads threads and has used $used of processor time since Quit"
}

function Stop-HiddenExcel($Session, $Objects, $Book, [switch]$AddInLoaded, [switch]$FailureInFlight) {
    $problems = [Collections.Generic.List[string]]::new()
    $clock = [Diagnostics.Stopwatch]::new()
    $stages = [Collections.Generic.List[string]]::new()
    # Each step still runs if the one before it failed. The host command is terminal: after
    # it releases the add-in's own Excel references, only closing the automation client remains.
    if ($Book) {
        $clock.Restart()
        try { Close-HiddenExcelWorkbook $Session.Excel $Book } catch { $problems.Add("closing the workbook: $_") }
        $stages.Add((Format-ExcelBusyText "the workbook's close took {0:F2} s" $clock.Elapsed.TotalSeconds))
    }
    $started = if ($Session.Process) { Wait-HiddenExcelStill $Session.Process } else { "its process was not identified, so nothing was waited for" }
    if ($AddInLoaded) {
        $clock.Restart()
        try { [void]$Session.Excel.Run("CatalystPrepareToQuit") }
        catch { $problems.Add("preparing the add-in to quit: $_") }
        $stages.Add((Format-ExcelBusyText "the add-in's preparation took {0:F2} s" $clock.Elapsed.TotalSeconds))
    }
    $age = try { Format-ExcelBusyText "{0:F1} s old" ([datetime]::Now - $Session.Process.StartTime).TotalSeconds } catch { "of an unread age" }
    $processorTimeAtQuit = if ($Session.Process) { Get-HiddenExcelProcessorTime $Session.Process } else { $null }
    # Excel begins to exit when the last reference from outside is released, and a release waits
    # while Excel is busy with its exit. So the exit is counted from the Quit call, whichever of
    # the release and the wait the time falls in.
    $exit = [Diagnostics.Stopwatch]::StartNew()
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
    $stages.Add((Format-ExcelBusyText "Quit and the releases took {0:F2} s" $exit.Elapsed.TotalSeconds))
    if ($Session.Process) {
        # What a failure says beyond its first words: the stage the time went in, and the machine.
        $told = "It was $age at Quit and $started; " + ($stages -join ", ")
        $machine = if ($script:HiddenExcelFacts) { "; $($script:HiddenExcelFacts)" } else { "" }
        try {
            # A release that waited past the limit returns as Excel goes, a moment before the
            # process is seen to have exited: the wait is never shorter than a second, and an
            # Excel that went while it was being looked at is not one to stop.
            $left = [int][Math]::Max(1000, $HiddenExcelExitSeconds * 1000 - $exit.ElapsedMilliseconds)
            $exited = $Session.Process.WaitForExit($left)
            if (-not $exited) {
                $state = Get-HiddenExcelState $Session.Process $processorTimeAtQuit
                $exited = [bool]$Session.Process.HasExited
            }
            if ($exited) {
                $took = $exit.Elapsed.TotalSeconds
                if ($took -gt $HiddenExcelExitSeconds) {
                    $problems.Add((Format-ExcelBusyText "hidden Excel process {0} exited by itself only {1:F1} s after Quit, past the {2} seconds it is given. {3}{4}" $Session.Process.Id $took $HiddenExcelExitSeconds $told $machine))
                }
                elseif ($took -gt $HiddenExcelSlowSeconds) {
                    Write-Warning (Format-ExcelBusyText "hidden Excel process {0} took {1:F1} s to exit after Quit" $Session.Process.Id $took) -WarningAction Continue
                }
            }
            else {
                $problems.Add("hidden Excel process $($Session.Process.Id) did not exit within $HiddenExcelExitSeconds seconds of Quit; terminating this session's process. $told; at the limit $state$machine")
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
