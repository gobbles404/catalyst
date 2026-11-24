# Proves, without Excel, that a hidden Excel session whose start fails is still ended, that a
# session's end goes on past each step that fails, that it waits for a starting Excel and no
# longer than its time, and that the exit is counted from the Quit call, an Excel still there at
# the limit stopped and a late exit failing too. Nothing here starts Excel or touches a process.
# check.ps1 and CI run it.
# A real, unopened ADO recordset stands in for Excel so releasing its COM reference is real;
# added members fail where the Excel calls can fail. Process discovery and the retained
# process are stand-ins. The real smoke and lifetime runs check discovery against Excel.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "hidden_excel.ps1")

$script:checks = 0
$script:failures = 0
$script:references = [Collections.Generic.List[object]]::new()
function Check([string]$What, [bool]$Ok, [string]$Saw = "") {
    $script:checks++
    if (-not $Ok) { $script:failures++ }
    Write-Host ("{0} {1}{2}" -f $(if ($Ok) { "ok  " } else { "FAIL" }), $What, $(if ($Saw) { ": $Saw" } else { "" }))
}
function Failure([scriptblock]$Action) {
    try {
        & $Action 3>&1 | ForEach-Object {
            if ($_ -is [Management.Automation.WarningRecord]) { $script:fixture.Warnings.Add($_.Message) }
        }
    }
    catch { return $_ }
    return $null
}
function Carries($Record, $Expected) {
    $fault = $Record.Exception
    while ($fault) {
        if ([object]::ReferenceEquals($fault, $Expected)) { return $true }
        $fault = $fault.InnerException
    }
    return $false
}
function Released($Reference) {
    try { [void]$Reference.GetType().InvokeMember("State", [Reflection.BindingFlags]::GetProperty, $null, $Reference, $null) }
    catch [Runtime.InteropServices.InvalidComObjectException] { return $true }
    return $false
}
function Recordset {
    $reference = Microsoft.PowerShell.Utility\New-Object -ComObject ADODB.Recordset
    $script:references.Add($reference)
    return , $reference
}
function Fixture([string]$FailAt = "") {
    $script:fixture = [pscustomobject]@{
        FailAt = $FailAt
        Fault = [InvalidOperationException]::new("injected $FailAt failure")
        QuitFails = $false
        RunFails = $false
        NeedsKill = $false
        Killed = $false
        QuitSeconds = 0
        Moves = 0
        Ticks = 0
        Waits = [Collections.Generic.List[int]]::new()
        Trace = [Collections.Generic.List[string]]::new()
        Warnings = [Collections.Generic.List[string]]::new()
        Excel = (Recordset)
        Process = [pscustomobject]@{ Id = 123456 }
    }
    Add-Member -InputObject $fixture.Excel -MemberType ScriptProperty -Name Visible -Value { $true } -SecondValue {
        param($value)
        $script:fixture.Trace.Add("hide")
        if ($script:fixture.FailAt -eq "hide") { throw $script:fixture.Fault }
    }
    Add-Member -InputObject $fixture.Excel -MemberType ScriptProperty -Name DisplayAlerts -Value { $true } -SecondValue {
        param($value)
        $script:fixture.Trace.Add("alerts")
        if ($script:fixture.FailAt -eq "alerts") { throw $script:fixture.Fault }
    }
    Add-Member -InputObject $fixture.Excel -MemberType ScriptMethod -Name Quit -Value {
        $script:fixture.Trace.Add("quit")
        if ($script:fixture.QuitFails) { throw [Runtime.InteropServices.COMException]::new("Quit was refused", -2147418111) }
        if ($script:fixture.QuitSeconds) { Start-Sleep -Milliseconds ([int]($script:fixture.QuitSeconds * 1000)) }
    }
    Add-Member -InputObject $fixture.Excel -MemberType ScriptMethod -Name Run -Value {
        param($command)
        $script:fixture.Trace.Add("prepare")
        if ($script:fixture.RunFails) { throw "prepare failed" }
    }
    Add-Member -InputObject $fixture.Process -MemberType ScriptMethod -Name WaitForExit -Value {
        param($milliseconds)
        $script:fixture.Trace.Add("wait")
        $script:fixture.Waits.Add($milliseconds)
        return -not $script:fixture.NeedsKill -or $script:fixture.Killed
    }
    Add-Member -InputObject $fixture.Process -MemberType ScriptMethod -Name Kill -Value {
        $script:fixture.Trace.Add("kill")
        $script:fixture.Killed = $true
    }
    Add-Member -InputObject $fixture.Process -MemberType ScriptMethod -Name Dispose -Value { $script:fixture.Trace.Add("dispose") }
}
# Gives the stand-in process a processor time that can be read: it moves on each of the first
# reads and stands still from then on. Without this the stand-in has none, and an ending waits
# for nothing, as the checks above it expect.
function Moving([int]$Reads) {
    $script:fixture.Moves = $Reads
    Add-Member -InputObject $fixture.Process -MemberType ScriptMethod -Name Refresh -Value {
        $script:fixture.Trace.Add("sample")
        if ($script:fixture.Moves -gt 0) {
            $script:fixture.Moves--
            $script:fixture.Ticks++
        }
    }
    Add-Member -InputObject $fixture.Process -MemberType ScriptProperty -Name TotalProcessorTime -Value { [TimeSpan]::FromTicks($script:fixture.Ticks) }
}

# These two boundaries are replaced; Start-HiddenExcel and Stop-HiddenExcel run unchanged.
# The factory refuses any other request rather than accidentally starting a real Excel.
function New-Object([string]$ComObject) {
    if ($ComObject -ne "Excel.Application") { throw "unexpected COM request: $ComObject" }
    return , $script:fixture.Excel
}
function Get-HiddenExcelProcess($Excel) {
    $script:fixture.Trace.Add("identify")
    if ($script:fixture.FailAt -eq "identify") { throw $script:fixture.Fault }
    return $script:fixture.Process
}

try {
    Fixture
    $session = Start-HiddenExcel
    Check "successful startup hands its Excel and owned process to the caller" ([object]::ReferenceEquals($session.Excel, $fixture.Excel) -and [object]::ReferenceEquals($session.Process, $fixture.Process))
    Check "ownership is captured before either configuration call, without cleanup" (($fixture.Trace -join ",") -eq "identify,hide,alerts") ($fixture.Trace -join ",")
    Check "the caller still has a usable COM reference" (-not (Released $fixture.Excel))
    $failed = Failure { Stop-HiddenExcel $session ([Collections.Generic.List[object]]::new()) $null }
    Check "ordinary shutdown quits, waits and disposes without killing or reporting failure" ($null -eq $failed -and $fixture.Warnings.Count -eq 0 -and ($fixture.Trace -join ",") -eq "identify,hide,alerts,quit,wait,dispose") "$failed"
    Check "ordinary shutdown releases the COM reference" (Released $fixture.Excel)

    foreach ($stage in @("hide", "alerts")) {
        Fixture $stage
        $fixture.QuitFails = $true
        $fixture.NeedsKill = $true
        $warningPolicy = $WarningPreference
        $WarningPreference = "Stop"
        try { $failed = Failure { Start-HiddenExcel } }
        finally { $WarningPreference = $warningPolicy }
        $expected = if ($stage -eq "hide") { "identify,hide,quit,wait,kill,wait,dispose" } else { "identify,hide,alerts,quit,wait,kill,wait,dispose" }
        Check "$stage failure retains the original exception despite rejected Quit and WarningPreference Stop" (Carries $failed $fixture.Fault) "$failed"
        Check "$stage failure still waits, kills only its retained stand-in, waits again and disposes" (($fixture.Trace -join ",") -eq $expected) ($fixture.Trace -join ",")
        Check "$stage failure releases its COM reference" (Released $fixture.Excel)
        $words = $fixture.Warnings -join "; "
        Check "$stage failure reports both rejected Quit and forced termination" ($fixture.Warnings.Count -eq 1 -and $words -match "quitting Excel" -and $words -match "terminating this session's process") $words
    }

    Fixture "identify"
    $failed = Failure { Start-HiddenExcel }
    Check "identification failure retains the original exception" (Carries $failed $fixture.Fault) "$failed"
    Check "without ownership, cleanup quits but never waits on, kills or disposes a process" (($fixture.Trace -join ",") -eq "identify,quit") ($fixture.Trace -join ",")
    Check "identification failure still releases the COM reference" (Released $fixture.Excel)
    Check "unverified exit is reported explicitly" ($fixture.Warnings.Count -eq 1 -and $fixture.Warnings[0] -match "could not verify Excel exit because its process was not identified") ($fixture.Warnings -join "; ")

    # Each terminal step continues after an earlier failure. The extra non-COM entry makes
    # ReleaseComObject fail before it reaches the real child reference behind it in the list.
    Fixture
    $fixture.RunFails = $true
    $fixture.QuitFails = $true
    $fixture.NeedsKill = $true
    function Close-HiddenExcelWorkbook($Excel, $Book) { $script:fixture.Trace.Add("close"); throw "close failed" }
    $child = Recordset
    $owned = [Collections.Generic.List[object]]::new()
    $owned.Add($child)
    $owned.Add([object]::new())
    $session = [pscustomobject]@{ Excel = $fixture.Excel; Process = $fixture.Process }
    $failed = Failure { Stop-HiddenExcel $session $owned ([object]::new()) -AddInLoaded }
    Check "failed close, prepare and Quit do not skip process cleanup" (($fixture.Trace -join ",") -eq "close,prepare,quit,wait,kill,wait,dispose") ($fixture.Trace -join ",")
    Check "a failed child release does not skip later releases or clearing ownership" ((Released $child) -and (Released $fixture.Excel) -and $owned.Count -eq 0)
    Check "without an originating failure, cleanup fails with every problem retained" ($null -ne $failed -and "$failed" -match "closing the workbook" -and "$failed" -match "preparing the add-in" -and "$failed" -match "quitting Excel" -and "$failed" -match "releasing an Excel object" -and "$failed" -match "terminating this session's process") "$failed"

    # An ending waits for a starting Excel: no Quit while its processor time still moves. The
    # times are shortened here, as the stand-in has no real start to wait for.
    $HiddenExcelStillSeconds = 0.2
    Fixture
    Moving 3
    $session = [pscustomobject]@{ Excel = $fixture.Excel; Process = $fixture.Process }
    $failed = Failure { Stop-HiddenExcel $session ([Collections.Generic.List[object]]::new()) $null }
    $quitAt = $fixture.Trace.IndexOf("quit")
    $before = @($fixture.Trace | Select-Object -First $quitAt)
    Check "an ending reads the processor time until it has stood still, and only then quits" ($null -eq $failed -and $quitAt -gt 4 -and @($before | Where-Object { $_ -ne "sample" }).Count -eq 0) ($fixture.Trace -join ",")
    Check "and then ends as any other: quit, wait, dispose, nothing killed" ((@($fixture.Trace | Select-Object -Skip $quitAt) -join ",") -eq "quit,wait,dispose") ($fixture.Trace -join ",")

    # A processor time that never stands still is given up on, and the ending goes on.
    $HiddenExcelStartSeconds = 0.5
    Fixture
    Moving ([int]::MaxValue)
    $session = [pscustomobject]@{ Excel = $fixture.Excel; Process = $fixture.Process }
    $failed = Failure { Stop-HiddenExcel $session ([Collections.Generic.List[object]]::new()) $null }
    Check "an Excel that never stands still is waited for no longer than its time, and still ended" ($null -eq $failed -and $fixture.Trace.Contains("quit") -and $fixture.Trace[-1] -eq "dispose" -and -not $fixture.Trace.Contains("kill")) ($fixture.Trace -join ",")

    # The exit is counted from the Quit call: the wait is given what is left of the time, and
    # the failure says the stage, the limit and what the process looked like.
    $HiddenExcelExitSeconds = 2
    Fixture
    Moving 0
    $fixture.NeedsKill = $true
    $fixture.QuitSeconds = 0.5
    $session = [pscustomobject]@{ Excel = $fixture.Excel; Process = $fixture.Process }
    $failed = Failure { Stop-HiddenExcel $session ([Collections.Generic.List[object]]::new()) $null }
    Check "the wait for the exit is what the Quit call and the releases left of the time" ($fixture.Waits.Count -eq 2 -and $fixture.Waits[0] -gt 0 -and $fixture.Waits[0] -le 1500 -and $fixture.Waits[1] -eq 5000) ($fixture.Waits -join ",")
    Check "an Excel still there at the limit is terminated and reported as a failure" ($null -ne $failed -and "$failed" -match "did not exit within 2 seconds of Quit; terminating this session's process" -and $fixture.Trace.Contains("kill")) "$failed"
    Check "and the failure says where the time went and what the process looked like" ("$failed" -match "at Quit" -and "$failed" -match "its processor time had stood still" -and "$failed" -match "Quit and the releases took" -and "$failed" -match "at the limit its window" -and "$failed" -match "of processor time since Quit") "$failed"

    # An Excel that exits by itself, but only after the limit, is a failure too, and is not killed.
    # A release that waited past the limit returns as Excel goes, so the wait that follows is
    # still a second long, for the exit to show.
    $HiddenExcelExitSeconds = 0.2
    Fixture
    $fixture.QuitSeconds = 0.5
    $session = [pscustomobject]@{ Excel = $fixture.Excel; Process = $fixture.Process }
    $failed = Failure { Stop-HiddenExcel $session ([Collections.Generic.List[object]]::new()) $null }
    Check "an exit that comes only after the limit fails, with no process terminated" ($null -ne $failed -and "$failed" -match "exited by itself only" -and "$failed" -match "past the 0.2 seconds it is given" -and -not $fixture.Trace.Contains("kill")) "$failed"
    Check "and the wait for it is a second, though the limit had passed" ($fixture.Waits.Count -eq 1 -and $fixture.Waits[0] -eq 1000) ($fixture.Waits -join ",")

    # An Excel that goes while it is being looked at, after the wait ran out, is not stopped.
    $HiddenExcelExitSeconds = 2
    Fixture
    $fixture.NeedsKill = $true
    Add-Member -InputObject $fixture.Process -MemberType ScriptProperty -Name HasExited -Value { $true }
    $session = [pscustomobject]@{ Excel = $fixture.Excel; Process = $fixture.Process }
    $failed = Failure { Stop-HiddenExcel $session ([Collections.Generic.List[object]]::new()) $null }
    Check "an Excel that went while it was being looked at is not terminated" ($null -eq $failed -and ($fixture.Trace -join ",") -eq "quit,wait,dispose") (($fixture.Trace -join ",") + " $failed")
}
finally {
    # A broken implementation must not leave even these harmless COM references behind.
    foreach ($reference in $script:references) {
        if (-not (Released $reference)) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($reference) }
    }
}

Write-Host "excel session self-test: $($script:checks) checks, $($script:failures) failed"
exit $script:failures
