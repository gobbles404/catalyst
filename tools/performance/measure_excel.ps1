# Warm timings in a hidden Excel: the number a user feels, one formula shape at a time.
#
# Run: .\tools\performance\measure_excel.ps1               (opt-in, local; nothing gates on it)
#      .\tools\performance\measure_excel.ps1 -Rows 10000   (the batching control; its files carry the row count)
#
# The clock is Range.Calculate or Application.Calculate over COM from this PowerShell loop, so
# it includes Excel, Excel-DNA, the host, and Python, plus the COM round trips. It excludes
# startup, building the sheets, and checking answers, which happen before and after. A single
# Range.Calculate costs about 0.4 ms over COM before any formula runs, so every single-formula
# case is placed a hundred times and timed as one range. Each row of profiles/excel-timing.csv
# is one batch of calibrated length; per_call_us is that batch's mean per formula the
# recalculation reaches, per_recalc_us its mean per recalculation. Case order rotates between
# batches so drift does not favour one case. Every answer is checked before and after timing.
#
# Sweeps: call count (Add beside the Excel-DNA floor HostAdd and native arithmetic); cells in
# (SumArray beside SUM); cells out (Grid spilled); the same answers three ways (one formula per
# row, ten spills of a tenth each, one spill of the whole), for a plain echo and for RowSums;
# and a local edit of each arrangement: one input changed, then Application.Calculate, which
# in manual mode recalculates only what depends on it. Two facts about Excel shape the edit
# cases. Range.Calculate leaves its cells dirty, so an edit batch is preceded by one cleaning
# Application.Calculate off the clock. And a recalculation with any dirty cell does bookkeeping
# for every formula in the workbook, so each arrangement lives in a workbook of its own and
# the edit's floor, the same write and calculate with nothing dependent, is measured in one
# more. Calls are counted from the formulas placed and what an edit reaches, never observed.
param(
    [ValidateScript({ $_ % 10 -eq 0 })][ValidateRange(100, 100000)][int]$Rows = 1000,
    [ValidateRange(3, 20)][int]$Batches = 5,
    [ValidateRange(5, 500)][int]$BatchMs = 50
)
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$reports = Join-Path $root "profiles"
New-Item -ItemType Directory -Force -Path $reports | Out-Null
. (Join-Path (Split-Path $PSScriptRoot -Parent) "host_build.ps1")
$xll = Build-HostAddIn -Root $root
$copies = 100   # how many times a single-formula case is placed
$suffix = if ($Rows -eq 1000) { "" } else { "-rows$Rows" }   # the working workload keeps the plain name

# Every COM object taken is kept here and released at the end, so Excel can quit.
$owned = [Collections.Generic.List[object]]::new()
function Own($object) { $owned.Add($object); Write-Output -NoEnumerate $object }   # a Range enumerates its cells if returned plainly

function Triangle([long]$n) { return [double]$n * ($n + 1) / 2 }   # 1 + 2 + ... + n

function Sum-Values($values) {
    $total = 0.0
    foreach ($value in $values) { $total += [double]$value }
    return $total
}

# A sheet whose inputs are 1, 2, 3, ... across then down over A1 to the last column, so every
# sum below has a closed form to check against.
function New-InputSheet([string]$name, [int]$rows, [int]$cols) {
    $sheet = Own $book.Worksheets.Add()
    $sheet.Name = $name
    $values = [object[,]]::new($rows, $cols)
    for ($r = 0; $r -lt $rows; $r++) {
        for ($c = 0; $c -lt $cols; $c++) { $values[$r, $c] = [double]($r * $cols + $c + 1) }
    }
    (Own $sheet.Range($sheet.Cells.Item(1, 1), $sheet.Cells.Item($rows, $cols))).Value2 = $values
    return $sheet
}

# A case is data: what to recalculate, what to read back, and the sum it must show. An edit
# case changes one input before Application.Calculate; its Flip is shared with the full case
# of the same sheet, so both checks know the sheet's current state.
function Add-Case([string]$probe, [string]$scenario, [int]$calls, [int]$in, [int]$out, $target, $check, [double]$want, $state = $null, $edit = $null) {
    $cases.Add(@{
        Probe = $probe; Scenario = $scenario; Calls = $calls; CellsIn = $in; CellsOut = $out
        Target = $target; Check = $check; Want = $want; State = $state; Edit = $edit
    })
}

function Invoke-Recalc([hashtable]$case) {
    if ($case.Edit) {
        $case.State.Flip = 1 - $case.State.Flip
        $case.Edit.Value2 = $case.State.Base + $case.State.Flip
        [void]$excel.Calculate()
    }
    else {
        [void]$case.Target.Calculate()
    }
}

# One timed batch: milliseconds for the iterations. An edit case first cleans the workbook
# off the clock, so the clock sees the edit's dependents and nothing left dirty by other cases.
function Invoke-Batch([hashtable]$case, [int]$iterations) {
    if ($case.Edit) { [void]$excel.Calculate() }
    $watch = [Diagnostics.Stopwatch]::StartNew()
    for ($i = 0; $i -lt $iterations; $i++) { Invoke-Recalc $case }
    $watch.Stop()
    return $watch.Elapsed.TotalMilliseconds
}

function Test-Case([hashtable]$case) {
    $shown = Sum-Values $case.Check.Value2
    $want = $case.Want
    if ($case.State) { $want += $case.State.Flip }
    if ($shown -ne $want) { throw "$($case.Probe), $($case.Scenario): shows $shown, expected $want" }
}

$results = [Collections.Generic.List[object]]::new()

# A group is one workbook: build its sheets and cases, warm and check each case, calibrate its
# iterations, time the cases in rotated batches, then close the workbook.
function Measure-Group([scriptblock]$build) {
    $script:book = Own $excel.Workbooks.Add()
    $script:cases = [Collections.Generic.List[hashtable]]::new()
    & $build
    foreach ($case in $cases) {
        Invoke-Recalc $case
        Test-Case $case
        $iterations = 1
        while ((Invoke-Batch $case $iterations) -lt $BatchMs -and $iterations -lt 4096) { $iterations *= 2 }
        $case.Iterations = $iterations
    }
    for ($batch = 1; $batch -le $Batches; $batch++) {
        for ($offset = 0; $offset -lt $cases.Count; $offset++) {
            $case = $cases[($batch + $offset) % $cases.Count]
            $elapsed = Invoke-Batch $case $case.Iterations
            Test-Case $case
            $perRecalc = $elapsed * 1000 / $case.Iterations
            $results.Add([pscustomobject]@{
                layer = "excel"
                probe = $case.Probe
                scenario = $case.Scenario
                calls = $case.Calls
                cells_in = $case.CellsIn
                cells_out = $case.CellsOut
                batch = $batch
                iterations = $case.Iterations
                elapsed_ms = [math]::Round($elapsed, 3)
                per_call_us = if ($case.Calls) { [math]::Round($perRecalc / $case.Calls, 3) } else { "" }
                per_recalc_us = [math]::Round($perRecalc, 3)
            })
        }
    }
    foreach ($case in $cases) {
        $means = @($results | Where-Object { $_.probe -eq $case.Probe -and $_.scenario -eq $case.Scenario -and $_.cells_in -eq $case.CellsIn -and $_.cells_out -eq $case.CellsOut } | ForEach-Object { $_.per_recalc_us } | Sort-Object)
        Write-Host ("{0,-11} {1,-34} {2,5} calls {3,6} in {4,5} out  median {5,11:N1} us/recalc  ({6:N1}..{7:N1})" -f $case.Probe, $case.Scenario, $case.Calls, $case.CellsIn, $case.CellsOut, $means[[int]($means.Count / 2)], $means[0], $means[-1])
    }
    $book.Close($false)
    $script:book = $null
}

$excel = New-Object -ComObject Excel.Application
try {
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.ScreenUpdating = $false
    $excel.EnableEvents = $false
    if (-not $excel.RegisterXLL($xll)) { throw "Excel refused to load $xll" }
    $book = Own $excel.Workbooks.Add()
    $excel.Calculation = -4135   # xlCalculationManual, for every workbook this Excel opens
    $status = Own $book.Worksheets.Item(1).Range("A1")
    $status.Formula = "=GoosedoveStatus()"
    [void]$status.Calculate()
    if ($status.Value2 -ne "ok: python started and functions registered") { throw $status.Text }
    $book.Close($false)
    $book = $null

    # --- 1 to 3: size curves, all Range.Calculate, one workbook -------------------------------
    Measure-Group {
        # 1. call count: the same formula down 100, 1,000 and 10,000 rows
        $calls = New-InputSheet "calls" 10000 2
        $column = 3
        foreach ($n in 100, 1000, 10000) {
            foreach ($shape in @(
                @{ Probe = "Add"; Formula = "=Add(RC1,RC2)" },
                @{ Probe = "HostAdd"; Formula = "=HostAdd(RC1,RC2)" },
                @{ Probe = "native +"; Formula = "=RC1+RC2" }
            )) {
                $range = Own $calls.Range($calls.Cells.Item(1, $column), $calls.Cells.Item($n, $column))
                $range.FormulaR1C1 = $shape.Formula
                Add-Case $shape.Probe "call count" $n (2 * $n) $n $range $range (Triangle (2 * $n))
                $column++
            }
        }
        # 2. cells in: a hundred copies of one formula over a growing column
        $cellsIn = New-InputSheet "cells_in" 10000 1
        $column = 3
        foreach ($n in 100, 1000, 10000) {
            foreach ($shape in @(
                @{ Probe = "SumArray"; Formula = "=SumArray(R1C1:R${n}C1)" },
                @{ Probe = "native SUM"; Formula = "=SUM(R1C1:R${n}C1)" }
            )) {
                $range = Own $cellsIn.Range($cellsIn.Cells.Item(1, $column), $cellsIn.Cells.Item($copies, $column))
                $range.FormulaR1C1 = $shape.Formula
                Add-Case $shape.Probe "cells in" $copies $n 1 $range $range ($copies * (Triangle $n))
                $column++
            }
        }
        # 2b. the same count two ways, over numbers and over a mixed column, with Excel's own
        # counts beside each: what accepting three kinds instead of one costs a user.
        $mixedIn = Own $book.Worksheets.Add()
        $mixedIn.Name = "mixed_in"
        $values = [object[,]]::new(10000, 1)
        for ($r = 0; $r -lt 10000; $r++) {
            $values[$r, 0] = switch ($r % 3) { 0 { "n$r" } 1 { [double]$r } default { $r % 2 -eq 0 } }
        }
        (Own $mixedIn.Range($mixedIn.Cells.Item(1, 1), $mixedIn.Cells.Item(10000, 1))).Value2 = $values
        $column = 3
        foreach ($n in 100, 1000, 10000) {
            foreach ($shape in @(
                @{ Probe = "CountArray"; Formula = "=CountArray(cells_in!R1C1:R${n}C1)" },
                @{ Probe = "native COUNT"; Formula = "=COUNT(cells_in!R1C1:R${n}C1)" },
                @{ Probe = "CountMixed"; Formula = "=CountMixed(R1C1:R${n}C1)" },
                @{ Probe = "native COUNTA"; Formula = "=COUNTA(R1C1:R${n}C1)" }
            )) {
                $range = Own $mixedIn.Range($mixedIn.Cells.Item(1, $column), $mixedIn.Cells.Item($copies, $column))
                $range.FormulaR1C1 = $shape.Formula
                Add-Case $shape.Probe "cells in" $copies $n 1 $range $range ($copies * $n)
                $column++
            }
        }
        # 3. cells out: a hundred copies of one formula spilling a growing column
        $cellsOut = Own $book.Worksheets.Add()
        $cellsOut.Name = "cells_out"
        $column = 1
        foreach ($n in 100, 1000, 10000) {
            for ($c = 0; $c -lt $copies; $c++) {
                $cellsOut.Cells.Item(1, $column + $c).Formula2 = "=Grid($n,1)"
            }
            $anchors = Own $cellsOut.Range($cellsOut.Cells.Item(1, $column), $cellsOut.Cells.Item(1, $column + $copies - 1))
            $spills = Own $cellsOut.Range($cellsOut.Cells.Item(1, $column), $cellsOut.Cells.Item($n, $column + $copies - 1))
            Add-Case "Grid" "cells out" $copies 2 $n $anchors $spills ($copies * (Triangle $n))
            $column += $copies
        }
    }

    # --- 4 and 5: the same answers three ways, then one input changed; a workbook each ---------
    # The full case recalculates every formula of the arrangement; the edit case changes the
    # middle input and lets Excel recalculate what depends on it: one row's formula, or one array.
    $each = $Rows / 10
    $middle = $Rows / 2
    $arrangements = @(
        @{ Name = "echo one per row"; Probe = "Times"; Cols = 1; Calls = $Rows; Kind = "rows"; Formula = "=Times(RC1)" },
        @{ Name = "echo ten arrays"; Probe = "EchoColumn"; Cols = 1; Calls = 10; Kind = "arrays"; Formula = "=EchoColumn(A{0}:A{1})" },
        @{ Name = "echo one array"; Probe = "EchoColumn"; Cols = 1; Calls = 1; Kind = "one"; Formula = "=EchoColumn(A1:A$Rows)" },
        @{ Name = "rowsums one per row"; Probe = "RowSums"; Cols = 10; Calls = $Rows; Kind = "rows"; Formula = "=RowSums(RC1:RC10)" },
        @{ Name = "rowsums ten arrays"; Probe = "RowSums"; Cols = 10; Calls = 10; Kind = "arrays"; Formula = "=RowSums(A{0}:J{1})" },
        @{ Name = "rowsums one array"; Probe = "RowSums"; Cols = 10; Calls = 1; Kind = "one"; Formula = "=RowSums(A1:J$Rows)" }
    )
    foreach ($arrangement in $arrangements) {
        Measure-Group {
            $cols = $arrangement.Cols
            $sheet = New-InputSheet $arrangement.Name.Replace(" ", "_") $Rows $cols
            $out = Own $sheet.Range($sheet.Cells.Item(1, 12), $sheet.Cells.Item($Rows, 12))   # column L, clear of every input
            switch ($arrangement.Kind) {
                "rows" { $out.FormulaR1C1 = $arrangement.Formula }
                "arrays" {
                    for ($b = 0; $b -lt 10; $b++) {
                        $top = $b * $each + 1
                        $sheet.Cells.Item($top, 12).Formula2 = ($arrangement.Formula -f $top, ($top + $each - 1))
                    }
                }
                "one" { $sheet.Cells.Item(1, 12).Formula2 = $arrangement.Formula }
            }
            $reach = $Rows / $arrangement.Calls   # rows one formula answers, so what one edit reaches
            $edit = Own $sheet.Range("A$middle")
            $state = @{ Flip = 0; Base = [double]$edit.Value2 }
            $answer = Own $sheet.Cells.Item($middle, 12)
            # Row r holds (r-1)*cols+1 ... r*cols; its sum is cols*(r-1)*cols + cols*(cols+1)/2.
            $middleSum = $cols * ($middle - 1) * $cols + (Triangle $cols)
            Add-Case $arrangement.Probe "$($arrangement.Name): full" $arrangement.Calls ($Rows * $cols) $Rows $out $out (Triangle ($Rows * $cols)) $state
            Add-Case $arrangement.Probe "$($arrangement.Name): edit one input" 1 ($reach * $cols) $reach $null $answer $middleSum $state $edit
        }
    }
    # The floor under every edit: the same COM write and Application.Calculate, nothing dependent.
    Measure-Group {
        $floor = Own $book.Worksheets.Item(1).Range("A1")
        $floor.Value2 = 0.0
        Add-Case "no formula" "edit one input" 0 0 0 $null $floor 0.0 @{ Flip = 0; Base = 0.0 } $floor
    }

    $results | Export-Csv -LiteralPath (Join-Path $reports "excel-timing$suffix.csv") -NoTypeInformation
    $threads = Own $excel.MultiThreadedCalculation
    [ordered]@{
        timestamp_utc = [DateTime]::UtcNow.ToString("o")
        revision = (git -C $root rev-parse HEAD).Trim()
        host_sha256 = (Get-FileHash -LiteralPath (Join-Path (Split-Path $xll -Parent) "Goosedove.Host.dll") -Algorithm SHA256).Hash.ToLower()
        bridge_sha256 = (Get-FileHash -LiteralPath (Join-Path $root "src/goosedove/excel/bridge.py") -Algorithm SHA256).Hash.ToLower()
        probes_sha256 = (Get-FileHash -LiteralPath (Join-Path $root "src/goosedove/excel/probes.py") -Algorithm SHA256).Hash.ToLower()
        excel_version = $excel.Version
        excel_build = $excel.Build
        excel_multithreaded_calculation = $threads.Enabled
        excel_calculation_threads = $threads.ThreadCount
        logical_processors = [Environment]::ProcessorCount
        configuration = "Release"
        rows = $Rows
        copies = $copies
        batch_target_ms = $BatchMs
        batches = $Batches
        timed_scope = "Range.Calculate or Application.Calculate over COM from a PowerShell loop: Excel, Excel-DNA, the host, Python, and the COM round trips. Excludes startup, building the sheets, and checking answers. per_call_us is a batch mean per formula the recalculation reaches; per_recalc_us per recalculation. Calls are counted from the formulas placed, never observed. Single-formula cases are placed a hundred times and timed as one range. The size curves share one workbook; each batching arrangement and the edit floor have a workbook of their own."
        edit_scope = "One input cell written over COM, then Application.Calculate in manual mode: Excel recalculates that cell's dependents and nothing else. The workbook is cleaned by one Application.Calculate off the clock first, because Range.Calculate leaves cells dirty. The full case of the same arrangement is Range.Calculate over every formula it placed. The 'no formula' row is the same write and calculate with nothing dependent, in an otherwise empty workbook."
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reports "excel-timing$suffix-environment.json") -Encoding utf8
    Write-Host "Results: profiles/excel-timing$suffix.csv"
}
finally {
    if ($book) { $book.Close($false) }
    $excel.Quit()
    for ($i = $owned.Count - 1; $i -ge 0; $i--) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($owned[$i]) }
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
