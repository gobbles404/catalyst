# Proves, without Excel, what the Excel tools do when Excel refuses a call as busy. It drives
# Invoke-ExcelCall of hidden_excel.ps1 with calls that fail on purpose: refused and then taken,
# refused under nested errors, refused until the deadline, and failing for another reason. It
# drives Read-ExcelProperty with a stand-in whose property read is refused, and with a real COM
# object whose property read fails, to show both what PowerShell's dot hides and that the read
# made here keeps it. It asks for a failure and the report again under a decimal comma, since
# what is said must not change with the machine. A run of the smoke or the lifetime checks may
# meet no busy Excel at all, so green runs alone would not show that any of this works.
# check.ps1 and CI run it.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "hidden_excel.ps1")
$ExcelBusyPause = 10  # the pause between tries, shortened so the checks take a second, not thirty
# A deadline of 0.3 s at 10 ms a try allows thirty tries, and a few more for the clock's grain.
# A deadline that is kept is shown by this count, not by a stopwatch a slow machine could fail.
$MostTries = 40

$script:checks = 0
$script:failures = 0
function Check([string]$What, [bool]$Ok, [string]$Saw = "") {
    $script:checks++
    if (-not $Ok) { $script:failures++ }
    Write-Host ("{0} {1}{2}" -f $(if ($Ok) { "ok  " } else { "FAIL" }), $What, $(if ($Saw) { ": $Saw" } else { "" }))
}

# The two results that mean busy, as Excel raises them, and the wrapping PowerShell may add.
$Rejected = -2147418111    # RPC_E_CALL_REJECTED
$RetryLater = -2147417846  # RPC_E_SERVERCALL_RETRYLATER
function Busy([int]$Result = $Rejected) { return [Runtime.InteropServices.COMException]::new("Call was rejected by callee.", $Result) }
function Wrapped($Inner) { return [Exception]::new("outer", [Exception]::new("middle", $Inner)) }
# What a failed call left behind: the error's own text and the exception that carried it.
function Failure([scriptblock]$Call) {
    try { & $Call | Out-Null } catch { return $_ }
    return $null
}
# Every result in an error's chain of exceptions, as Excel writes them: 800A03EC.
function Results($Record) {
    $found = @()
    $fault = $Record.Exception
    while ($fault) { $found += ("{0:X8}" -f $fault.HResult); $fault = $fault.InnerException }
    return $found
}

# --- before anything has waited ----------------------------------------------------------------
$lines = @(Write-ExcelBusyReport 6>&1 | ForEach-Object { "$_" })
Check "a run in which no call waited says so in one line" ($lines.Count -eq 1 -and $lines[0] -eq "busy Excel: no call had to wait") $lines[0]

# --- refused, then taken -----------------------------------------------------------------------
$script:tries = 0
$got = Invoke-ExcelCall "type input" { $script:tries++; if ($script:tries -le 2) { throw (Busy) }; "taken" } "A1"
Check "a call refused twice and then taken hands back its own value and nothing else" ($got -is [string] -and $got -eq "taken") "$got"
Check "after being made three times" ($script:tries -eq 3) "$($script:tries) tries"
$wait = $ExcelBusyWaits[$ExcelBusyWaits.Count - 1]
Check "and the wait is recorded apart from the value: the operation, the cell, the refusals" ($ExcelBusyWaits.Count -eq 1 -and $wait.What -eq "type input at A1" -and $wait.Refusals -eq 2 -and $wait.Taken) "$($wait.What); $($wait.Refusals) refusals; taken $($wait.Taken)"

$script:tries = 0
$got = Invoke-ExcelCall "type formula" { $script:tries++; if ($script:tries -eq 1) { throw (Busy $RetryLater) }; "later" } "K3"
Check "the second busy result, retry later, is waited on in the same way" ($got -eq "later" -and $script:tries -eq 2) "$got after $($script:tries) tries"

# --- the busy result under other errors --------------------------------------------------------
$script:tries = 0
$got = Invoke-ExcelCall "type formula" { $script:tries++; if ($script:tries -eq 1) { throw (Wrapped (Busy)) }; "unwrapped" } "K4"
Check "a refusal two errors deep is still a refusal, and the call is made again" ($got -eq "unwrapped" -and $script:tries -eq 2) "$got after $($script:tries) tries"

# --- refused until the deadline ----------------------------------------------------------------
$script:tries = 0
$waits = $ExcelBusyWaits.Count
$failed = Failure { Invoke-ExcelCall "type the counts formula" { $script:tries++; throw (Busy) } "Z1" ([datetime]::UtcNow.AddMilliseconds(300)) }
$words = "$failed"
$shape = '^Excel stayed busy: type the counts formula at Z1 was refused (\d+) time\(s\) over (\d+\.\d) s, the last time with RPC_E_CALL_REJECTED \(0x80010001\)$'
Check "a call refused until its deadline fails" ($null -ne $failed) $words
Check "naming the operation, the cell, the result, the tries and the time" ($words -match $shape) $words
Check "with the tries it really made, more than one" ($words -match $shape -and [int]$Matches[1] -eq $script:tries -and $script:tries -gt 1) "$($script:tries) tries"
Check "and no more than its deadline of 0.3 s allows" ($script:tries -le $MostTries) "$($script:tries) tries, at most $MostTries"
$wait = $ExcelBusyWaits[$ExcelBusyWaits.Count - 1]
Check "the report keeps it as a call never taken" ($ExcelBusyWaits.Count -eq $waits + 1 -and -not $wait.Taken -and $wait.Refusals -eq $script:tries) "taken $($wait.Taken); $($wait.Refusals) refusals"

$script:tries = 0
$failed = Failure { Invoke-ExcelCall "type the counts formula" { $script:tries++; throw (Busy) } "Z1" ([datetime]::UtcNow.AddSeconds(-1)) }
Check "a deadline already past still lets the call be made, once" ($null -ne $failed -and $script:tries -eq 1) "$($script:tries) tries; $failed"

# --- any other failure leaves at once, as it came ----------------------------------------------
$script:tries = 0
$waits = $ExcelBusyWaits.Count
$other = [Runtime.InteropServices.COMException]::new("Exception from HRESULT: 0x800A03EC", -2146827284)
$failed = Failure { Invoke-ExcelCall "type formula" { $script:tries++; throw $other } "K5" }
Check "a COM error that is not busy is not tried again" ($script:tries -eq 1) "$($script:tries) tries"
Check "and leaves as the same error" ($null -ne $failed -and [object]::ReferenceEquals($failed.Exception, $other)) "$failed"

$script:tries = 0
$failed = Failure { Invoke-ExcelCall "read the counts" { $script:tries++; throw "CatalystHandles showed: nonsense" } "Z1" }
Check "a failure of the tool's own, a malformed count, leaves at once in its own words" ($script:tries -eq 1 -and "$failed" -eq "CatalystHandles showed: nonsense") "$($script:tries) tries; $failed"
Check "and neither is recorded as a wait" ($ExcelBusyWaits.Count -eq $waits) "$($ExcelBusyWaits.Count - $waits) recorded"

$script:tries = 0
$got = Invoke-ExcelCall "calculation" { $script:tries++; "#ERROR f: a wrong answer" } "K6"
Check "a wrong answer is no failure of the call: handed back as it is, once" ($got -eq "#ERROR f: a wrong answer" -and $script:tries -eq 1) "$got"

# --- what a call hands back --------------------------------------------------------------------
$list = [Collections.ArrayList]@(1, 2, 3)
$back = Invoke-ExcelCall "range" { , $list }
Check "an object handed back with a leading comma arrives whole, not walked" ([object]::ReferenceEquals($back, $list)) "$($back.GetType().Name) of $($back.Count)"
$none = Invoke-ExcelCall "type input" { }
Check "a call that hands back nothing hands back nothing" ($null -eq $none)
$no = Invoke-ExcelCall "register the add-in" { $false }
Check "and false is handed back as false, not as nothing" ($no -is [bool] -and -not $no)

# --- a property read ---------------------------------------------------------------------------
# A stand-in for an Excel object: a property whose read is refused a number of times and then
# answered. PowerShell treats a failed read of it as it treats one of a COM object's.
if (-not ("Catalyst.Tools.BusyStandIn" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
namespace Catalyst.Tools {
    public class BusyStandIn {
        public int Reads;
        public int Refusals;
        public int Result;
        public object Answer;
        public object Text {
            get {
                Reads++;
                if (Reads <= Refusals) { throw new COMException("Call was rejected by callee.", Result); }
                return Answer;
            }
        }
    }
}
"@
}
function StandIn([int]$Refusals, $Answer = "the text", [int]$Result = $Rejected) {
    $made = New-Object Catalyst.Tools.BusyStandIn
    $made.Refusals = $Refusals
    $made.Answer = $Answer
    $made.Result = $Result
    return $made
}

$cell = StandIn 1
$dot = "unset"
$failed = Failure { $script:dot = $cell.Text }
Check "the trap: read with a dot, a refused read hands back nothing and raises nothing" ($null -eq $failed -and $null -eq $script:dot -and $cell.Reads -eq 1) "error [$failed]; value is nothing: $($null -eq $script:dot)"

$cell = StandIn 2
$waits = $ExcelBusyWaits.Count
$got = Read-ExcelProperty $cell "Text" "K7"
Check "read through Read-ExcelProperty, a read refused twice is made again and answered" ($got -is [string] -and $got -eq "the text" -and $cell.Reads -eq 3) "$got after $($cell.Reads) reads"
$wait = $ExcelBusyWaits[$ExcelBusyWaits.Count - 1]
Check "and recorded as any refused call is: the property, the cell, the refusals" ($ExcelBusyWaits.Count -eq $waits + 1 -and $wait.What -eq "read Text at K7" -and $wait.Refusals -eq 2 -and $wait.Taken) "$($wait.What); $($wait.Refusals) refusals; taken $($wait.Taken)"

$cell = StandIn 1 "x" $RetryLater
$got = Read-ExcelProperty $cell "Text" "K8"
Check "a read refused with retry later is made again too" ($got -eq "x" -and $cell.Reads -eq 2) "$got after $($cell.Reads) reads"

$cell = StandIn 1000000
$waits = $ExcelBusyWaits.Count
$failed = Failure { Read-ExcelProperty $cell "Value2" "Z1" }
Check "a property the object does not have is no refusal: the read fails and is not made again" ($null -ne $failed -and "$failed" -notmatch "^Excel stayed busy" -and $cell.Reads -eq 0 -and $ExcelBusyWaits.Count -eq $waits) "$failed"

$failed = Failure { Read-ExcelProperty $cell "Text" "Z1" ([datetime]::UtcNow.AddMilliseconds(300)) }
$words = "$failed"
$shape = '^Excel stayed busy: read Text at Z1 was refused (\d+) time\(s\) over (\d+\.\d) s, the last time with RPC_E_CALL_REJECTED \(0x80010001\)$'
Check "a read refused until its deadline fails, naming the property, the cell, the tries and the time" ($words -match $shape -and [int]$Matches[1] -eq $cell.Reads -and $cell.Reads -gt 1) $words
Check "and no more than its deadline of 0.3 s allows" ($cell.Reads -le $MostTries) "$($cell.Reads) reads, at most $MostTries"

$waits = $ExcelBusyWaits.Count
$cell = StandIn 1 "x" -2146827284
$failed = Failure { Read-ExcelProperty $cell "Text" "K9" }
Check "a read that fails for another reason is not made again and leaves with its own result" ($null -ne $failed -and $cell.Reads -eq 1 -and (Results $failed) -contains "800A03EC") "$($cell.Reads) reads; results $((Results $failed) -join ' <- ')"
Check "and is not recorded as a wait" ($ExcelBusyWaits.Count -eq $waits) "$($ExcelBusyWaits.Count - $waits) recorded"

$cell = StandIn 0 ""
$got = Read-ExcelProperty $cell "Text" "K10"
Check "an empty text is an answer: handed back as it is, once" ($got -is [string] -and $got -eq "" -and $cell.Reads -eq 1) "$($cell.Reads) reads"
$cell = StandIn 0 "#ERROR f: a wrong text"
$got = Read-ExcelProperty $cell "Text" "K11"
Check "and so is a wrong text" ($got -eq "#ERROR f: a wrong text" -and $cell.Reads -eq 1) "$got"
$cell = StandIn 0 $false
$got = Read-ExcelProperty $cell "Text"
Check "a property that is false is handed back as false, not as nothing" ($got -is [bool] -and -not $got)
$cell = StandIn 0 $null
$got = Read-ExcelProperty $cell "Text"
Check "a property that holds nothing hands back nothing" ($null -eq $got -and $cell.Reads -eq 1)
$cell = StandIn 0 $list
$back = Read-ExcelProperty $cell "Text"
Check "a property that holds a collection hands it back whole, not walked" ([object]::ReferenceEquals($back, $list)) "$($back.GetType().Name) of $($back.Count)"

# A real COM object, with no Excel: a recordset that is closed cannot say how many records it
# has (error 3704, 0x800A0E78). The dot hides that failure as it hides Excel's refusal.
$records = New-Object -ComObject ADODB.Recordset
try {
    $dot = "unset"
    $failed = Failure { $script:dot = $records.RecordCount }
    Check "a real COM object: read with a dot, a failed read hands back nothing and raises nothing" ($null -eq $failed -and $null -eq $script:dot) "error [$failed]; value is nothing: $($null -eq $script:dot)"
    $failed = Failure { Read-ExcelProperty $records "RecordCount" }
    Check "read through Read-ExcelProperty, the same read fails with the object's own result" ($null -ne $failed -and (Results $failed) -contains "800A0E78") "results $((Results $failed) -join ' <- ')"
    $state = Read-ExcelProperty $records "State"
    Check "and a read that works hands back the value the dot hands back" ($state -eq 0 -and $state -eq $records.State -and $state.GetType() -eq $records.State.GetType()) "$state"
}
finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($records) }

# --- the report --------------------------------------------------------------------------------
$lines = @(Write-ExcelBusyReport 6>&1 | ForEach-Object { "$_" })
$all = $lines -join "|"
Check "the report counts the calls that waited and their refusals" ($lines[0] -match '^busy Excel: 8 call\(s\) had to wait, \d+ refusal\(s\) in all, the longest wait \d+\.\d\d s$') $lines[0]
Check "and names each: what it was, how often it was refused, how it ended" ($lines.Count -eq 9 -and $all -match 'type input at A1: refused 2 time\(s\) over \d+\.\d\d s, then taken' -and $all -match 'read Text at K7: refused 2 time\(s\) over \d+\.\d\d s, then taken' -and $all -match 'read Text at Z1: refused \d+ time\(s\) over \d+\.\d\d s, never taken') "$($lines.Count) lines"

# --- a machine whose decimal mark is a comma ---------------------------------------------------
# What is said about a busy Excel must not change with the regional settings. A failure and the
# report are asked for again under a culture that writes 0.3 as 0,3, and worded as above.
$comma = [Globalization.CultureInfo]::InvariantCulture.Clone()
$comma.NumberFormat.NumberDecimalSeparator = ","
$machine = [Globalization.CultureInfo]::CurrentCulture
[Globalization.CultureInfo]::CurrentCulture = $comma
try {
    $written = "{0:F1}" -f 0.3
    $cell = StandIn 1000000
    $failed = Failure { Read-ExcelProperty $cell "Text" "Z2" ([datetime]::UtcNow.AddMilliseconds(300)) }
    $lines = @(Write-ExcelBusyReport 6>&1 | ForEach-Object { "$_" })
}
finally { [Globalization.CultureInfo]::CurrentCulture = $machine }
Check "on a machine with a decimal comma, where PowerShell itself writes 0.3 as 0,3" ($written -eq "0,3") $written
Check "a failure is worded as on any other, with a decimal point" ("$failed" -match '^Excel stayed busy: read Text at Z2 was refused \d+ time\(s\) over \d+\.\d s, the last time with RPC_E_CALL_REJECTED \(0x80010001\)$') "$failed"
Check "and so is the report" ($lines.Count -eq 10 -and $lines[0] -match '^busy Excel: 9 call\(s\) had to wait, \d+ refusal\(s\) in all, the longest wait \d+\.\d\d s$' -and ($lines -join "|") -match 'read Text at Z2: refused \d+ time\(s\) over \d+\.\d\d s, never taken') $lines[0]

Write-Host "excel busy self-test: $($script:checks) checks, $($script:failures) failed"
exit $script:failures
