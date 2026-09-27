# Retention under a feed: a thousand changed updates of a wide price vector and its market in a
# hidden Excel, the market's first quote read back as a number after every update, the store's
# live count and the bytes of prices it holds read at settled checkpoints, and everything
# released when the workbook closes. Evidence for a pull request, never a gate in check.ps1, with
# a verdict of its own: every reading, taken once Excel reports its calculation done, must be the
# expected number, every checkpoint must settle
# at the baseline within the patience, the store must be empty after the close, and no release
# may miss or fail, or the run exits nonzero after its cleanup. What the cell's text showed and
# how long the run took are reported beside, and decide nothing. -Fault expects the wrong price
# at the first update and the wrong live count at the first checkpoint, to prove that the verdict
# exits nonzero: run it with -Updates 1 -Checkpoint 1 -Patience 5. docs/seam/handles.md is the page.
param([int]$Updates = 1000, [int]$Prices = 150, [int]$Checkpoint = 250, [int]$Patience = 30, [switch]$Fault)
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
. (Join-Path $root "tools\host_build.ps1")
. (Join-Path $root "tools\hidden_excel.ps1")
$xll = Build-HostAddIn -Root $root

$failures = [Collections.Generic.List[string]]::new()
function Fail([string]$What) { $failures.Add($What); Write-Host "FAIL $What" }

function Counts($Cell) {
    $Cell.Formula = "=GoosedoveHandles()"
    $text = [string]$Cell.Value2
    if ($text -notmatch "^live (-?\d+); price bytes (-?\d+); published (\d+); reused (\d+); released (\d+); release misses (\d+); disposal errors (\d+)") {
        throw "GoosedoveHandles showed: $text"
    }
    return [pscustomobject]@{ Live = [int]$Matches[1]; PriceBytes = [int]$Matches[2]; Published = [int]$Matches[3]; Reused = [int]$Matches[4]; Released = [int]$Matches[5]; Misses = [int]$Matches[6]; DisposalErrors = [int]$Matches[7]; Text = $text }
}
# Waits, giving Excel time to deliver its callbacks, until the store holds that many live
# publications or the patience runs out; either way the last counts come back.
function Settle($Cell, [int]$Live) {
    $deadline = (Get-Date).AddSeconds($Patience)
    do {
        $counts = Counts $Cell
        if ($counts.Live -eq $Live) { return $counts }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    return (Counts $Cell)
}
# What a checkpoint must hold: the live count the wait was for, no release missed, none failed.
function Assert-Counts([string]$When, $Counts, [int]$Live) {
    if ($Counts.Live -ne $Live) { Fail ("{0}: live {1}, expected {2} within {3} s: {4}" -f $When, $Counts.Live, $Live, $Patience, $Counts.Text) }
    if ($Counts.Misses -ne 0) { Fail ("{0}: release misses {1}, expected 0: {2}" -f $When, $Counts.Misses, $Counts.Text) }
    if ($Counts.DisposalErrors -ne 0) { Fail ("{0}: disposal errors {1}, expected 0: {2}" -f $When, $Counts.DisposalErrors, $Counts.Text) }
}
# A cell's value in words: a number, a blank, text, or an Excel error, which Value2 hands over
# as a whole number of its own type.
function Describe($Value) {
    if ($null -eq $Value) { return "blank" }
    if ($Value -is [double]) { return "number $Value" }
    if ($Value -is [int]) { return "Excel error $Value" }
    return "text '$Value'"
}
# Waits, within the patience, until Excel reports its calculation done, so that the verdict read
# below never crosses a recalculation Excel is still running: its live-data refresh starts one
# after every update, and a cell read during it can show blank for a moment.
function Wait-Calculated {
    $deadline = (Get-Date).AddSeconds($Patience)
    do {
        $state = 1
        try { $state = $excel.CalculationState } catch { $state = 1 }  # a call Excel rejects is a busy Excel
        if ($state -eq 0) { return $true }  # xlDone
        Start-Sleep -Milliseconds 50
    } while ((Get-Date) -lt $deadline)
    return $false
}
# The market's first quote read once as a number, once Excel's calculation is done: that read is
# the verdict, and the text beside it is for the eye. When it is not the expected number the cell
# is read again within the patience, so that the failure can say whether the number arrived late
# or never; those later reads change nothing.
function Read-Quote($Cell, [double]$Expected) {
    $calculated = Wait-Calculated
    $value = $Cell.Value2
    $text = [string]$Cell.Text
    $ok = ($value -is [double] -and $value -eq $Expected)
    $afterwards = ""
    if (-not $calculated) { $afterwards = "Excel still calculating after $Patience s; " }
    if (-not $ok) {
        $outcome = "never the expected number within $Patience s"
        $deadline = (Get-Date).AddSeconds($Patience)
        $reads = 1
        do {
            Start-Sleep -Milliseconds 100
            $reads++
            $again = $Cell.Value2
            if ($again -is [double] -and $again -eq $Expected) { $outcome = "the expected number on read $reads"; break }
        } while ((Get-Date) -lt $deadline)
        $afterwards += $outcome
    }
    return [pscustomobject]@{ Value = $value; Text = $text; Ok = $ok; Afterwards = $afterwards }
}

$session = Start-HiddenExcel
$excel = $session.Excel
$owned = [Collections.Generic.List[object]]::new()
function Own($object) { $owned.Add($object); Write-Output -NoEnumerate $object }
$loaded = $false
$scriptError = $null
$book = $null
$rows = [Collections.Generic.List[object]]::new()
try {
    if (-not $excel.RegisterXLL($xll)) { throw "Excel refused to load $xll" }
    $loaded = $true
    $books = Own $excel.Workbooks
    $book = Own $books.Add()
    $sheet = Own (Own $book.Worksheets).Item(1)
    function Put([string]$Address, [string]$Formula) { (Own $sheet.Range($Address)).Formula = $Formula }

    # A schedule of one contract more than the prices, monthly from 21-Jul-2026, valued on
    # 26-May-2026 before its calendar begins, so the first calendar day's contract is the second
    # and the vector holds one quote per contract from it: as many quotes as prices.
    $contracts = $Prices + 1
    $codes = New-Object 'object[,]' $contracts, 1
    $expiries = New-Object 'object[,]' $contracts, 1
    $start = Get-Date "2026-07-21"
    for ($i = 0; $i -lt $contracts; $i++) {
        $codes[$i, 0] = "c$i"
        $expiries[$i, 0] = $start.AddMonths($i).ToOADate()
    }
    (Own $sheet.Range("A1").Resize($contracts, 1)).Value2 = $codes
    (Own $sheet.Range("B1").Resize($contracts, 1)).Value2 = $expiries
    $quotes = New-Object 'object[,]' $Prices, 1
    for ($i = 0; $i -lt $Prices; $i++) { $quotes[$i, 0] = 70.0 + $i * 0.01 }
    $priceRange = Own $sheet.Range("C1").Resize($Prices, 1)
    $priceRange.Value2 = $quotes
    Put "F1" "WTI NYMEX"
    Put "F2" "25-May-2026"
    Put "F3" "26-May-2026"
    Put "F4" "20-May-2026"; Put "G4" "70.85"
    Put "F5" "21-May-2026"; Put "G5" "71.1"
    Put "H1" "name"; Put "I1" "lot_size"; Put "J1" "brokerage_rate_per_lot"; Put "K1" "clearing_rate_per_lot"; Put "L1" "lot_unit"
    Put "H2" "NYMEX"; Put "I2" "1000"; Put "J2" "0"; Put "K2" "0"; Put "L2" "BBL"
    Put "M1" "=_CreateFuturesSchedule(A1:A$contracts,B1:B$contracts)"
    Put "M2" "=_CreateHolidayCalendar(F2)"
    Put "M3" '=_CreateIndexConventions("USD","BBL","USD","volume","BBL")'
    Put "M4" "=_CreateContractSpecifications(H1:L1,H2:L2)"
    Put "M5" "=_CreateIndex(F1,M1,M3,M4,M2)"
    Put "M6" "=_CreateValuationDate(F3,0.5)"
    Put "M7" "=_CreateCalendar(M6,M5)"
    Put "M8" "=_CreateFuturesFixings(F4:F5,G4:G5,M5)"
    Put "M9" "=_CreateMarketHistory(M7,M8)"
    Put "M10" "=_CreatePriceVector(F1,C1:C$Prices)"
    Put "M11" "=_CreateMarket(M9,M10)"
    Put "M12" "=INDEX(util_ReadHandle(M11),3,5)"  # the first calendar day's quote: the first price
    $reader = Own $sheet.Range("M12")
    $watch = Own $sheet.Range("O1")
    $baseline = 11
    $counts = Settle $watch $baseline
    Assert-Counts "at the baseline" $counts $baseline
    $read = Read-Quote $reader 70.0
    if (-not $read.Ok) { Fail ("at the baseline: the market shows {0} (text '{1}'), expected 70; afterwards {2}" -f (Describe $read.Value), $read.Text, $read.Afterwards) }
    Write-Host ("baseline: {0}; market shows {1}" -f $counts.Text, $read.Text)
    $rows.Add([pscustomobject]@{ Updates = 0; Live = $counts.Live; PriceBytes = $counts.PriceBytes; Published = $counts.Published; Released = $counts.Released; Seconds = 0.0 })

    # The updates run only on a chain that built: a baseline failure is reported, and the close
    # below is still checked.
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $textDiffers = 0
    $samples = [Collections.Generic.List[string]]::new()
    $ready = $failures.Count -eq 0
    for ($n = 1; $n -le $Updates -and $ready; $n++) {
        $first = 70.0 + $n
        for ($i = 0; $i -lt $Prices; $i++) { $quotes[$i, 0] = $first + $i * 0.01 }
        $priceRange.Value2 = $quotes
        $expected = $first
        if ($Fault -and $n -eq 1) { $expected = $first + 1 }
        $read = Read-Quote $reader $expected
        if (-not $read.Ok) {
            Fail ("update {0}: the market shows {1} (text '{2}'), expected {3}; afterwards {4}" -f $n, (Describe $read.Value), $read.Text, $expected, $read.Afterwards)
        }
        if ($read.Ok -and $read.Text -ne "$expected") {
            $textDiffers++
            if ($samples.Count -lt 5) { $samples.Add("update $n showed text '$($read.Text)' for the number $expected") }
        }
        if ($n % $Checkpoint -eq 0) {
            $expectedLive = $baseline
            if ($Fault -and $n -eq $Checkpoint) { $expectedLive = $baseline + 1 }
            $counts = Settle $watch $expectedLive
            Assert-Counts "after $n updates" $counts $expectedLive
            Write-Host ("after {0} updates: {1}; text differing so far {2}" -f $n, $counts.Text, $textDiffers)
            $rows.Add([pscustomobject]@{ Updates = $n; Live = $counts.Live; PriceBytes = $counts.PriceBytes; Published = $counts.Published; Released = $counts.Released; Seconds = [math]::Round($clock.Elapsed.TotalSeconds, 1) })
        }
    }
    Close-HiddenExcelWorkbook $excel $book
    $book = $null
    $scratch = Own $books.Add()
    $book = $scratch
    $watch = Own (Own (Own $scratch.Worksheets).Item(1)).Range("A1")
    $counts = Settle $watch 0
    Assert-Counts "after closing the workbook" $counts 0
    Write-Host ("after closing the workbook: {0}" -f $counts.Text)
    $rows.Add([pscustomobject]@{ Updates = "closed"; Live = $counts.Live; PriceBytes = $counts.PriceBytes; Published = $counts.Published; Released = $counts.Released; Seconds = [math]::Round($clock.Elapsed.TotalSeconds, 1) })
    Write-Host ""
    Write-Host "| updates | live | price bytes | published | released | seconds |"
    Write-Host "|---|---|---|---|---|---|"
    foreach ($row in $rows) { Write-Host ("| {0} | {1} | {2} | {3} | {4} | {5} |" -f $row.Updates, $row.Live, $row.PriceBytes, $row.Published, $row.Released, $row.Seconds) }
    Write-Host ""
    # Diagnostics, deciding nothing: how often the cell's text was not the expected number's while
    # the number was right, and the run's clock.
    Write-Host ("text differing from the expected number while the number was right: {0} of {1}; {2} s in all" -f $textDiffers, $Updates, [math]::Round($clock.Elapsed.TotalSeconds, 1))
    foreach ($sample in $samples) { Write-Host "     $sample" }
}
catch { $scriptError = $_; throw }
finally {
    Stop-HiddenExcel $session $owned $book -AddInLoaded:$loaded -FailureInFlight:($null -ne $scriptError)
}
if ($failures.Count) {
    Write-Host ("retention: {0} failed" -f $failures.Count)
    foreach ($failure in $failures) { Write-Host "  $failure" }
    exit 1
}
Write-Host "retention: every reading the expected number, every checkpoint at the baseline, the store empty after the close, no release missed or failed"
exit 0
