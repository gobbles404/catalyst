# Exercises the owned-session failure paths without starting Excel or touching a process.
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
    }
    Add-Member -InputObject $fixture.Excel -MemberType ScriptMethod -Name Run -Value {
        param($command)
        $script:fixture.Trace.Add("prepare")
        if ($script:fixture.RunFails) { throw "prepare failed" }
    }
    Add-Member -InputObject $fixture.Process -MemberType ScriptMethod -Name WaitForExit -Value {
        param($milliseconds)
        $script:fixture.Trace.Add("wait")
        return -not $script:fixture.NeedsKill -or $script:fixture.Killed
    }
    Add-Member -InputObject $fixture.Process -MemberType ScriptMethod -Name Kill -Value {
        $script:fixture.Trace.Add("kill")
        $script:fixture.Killed = $true
    }
    Add-Member -InputObject $fixture.Process -MemberType ScriptMethod -Name Dispose -Value { $script:fixture.Trace.Add("dispose") }
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
}
finally {
    # A broken implementation must not leave even these harmless COM references behind.
    foreach ($reference in $script:references) {
        if (-not (Released $reference)) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($reference) }
    }
}

Write-Host "excel lifecycle self-test: $($script:checks) checks, $($script:failures) failed"
exit $script:failures
