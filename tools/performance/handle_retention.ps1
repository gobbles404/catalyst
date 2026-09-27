# Retention under a feed: a thousand changed updates of a wide price vector and its market in a
# hidden Excel, the store's live count and the bytes of prices it holds read at settled
# checkpoints, and everything released when the workbook closes. Evidence for a pull request,
# never a gate: run it and paste the table. docs/seam/handles.md is the page.
param([int]$Updates = 1000, [int]$Prices = 150, [int]$Checkpoint = 250, [int]$Patience = 30)
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
. (Join-Path $root "tools\host_build.ps1")
. (Join-Path $root "tools\hidden_excel.ps1")
$xll = Build-HostAddIn -Root $root

function Counts($Cell) {
    $Cell.Formula = "=GoosedoveHandles()"
    $text = [string]$Cell.Value2
    if ($text -notmatch "^live (-?\d+); price bytes (-?\d+); published (\d+); reused (\d+); released (\d+); release misses (\d+); disposal errors (\d+)") {
        throw "GoosedoveHandles showed: $text"
    }
    return [pscustomobject]@{ Live = [int]$Matches[1]; PriceBytes = [int]$Matches[2]; Published = [int]$Matches[3]; Reused = [int]$Matches[4]; Released = [int]$Matches[5]; Misses = [int]$Matches[6]; DisposalErrors = [int]$Matches[7]; Text = $text }
}
function Settle($Cell, [int]$Live) {
    $deadline = (Get-Date).AddSeconds($Patience)
    do {
        $counts = Counts $Cell
        if ($counts.Live -eq $Live) { return $counts }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    return (Counts $Cell)
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
    if ($counts.Live -ne $baseline) { throw "the chain did not settle at $baseline live: $($counts.Text); market shows $($reader.Text)" }
    if ([string]$reader.Text -ne "70") { throw "the market shows $($reader.Text), expected 70" }
    Write-Host ("baseline: {0}" -f $counts.Text)
    $rows.Add([pscustomobject]@{ Updates = 0; Live = $counts.Live; PriceBytes = $counts.PriceBytes; Published = $counts.Published; Released = $counts.Released; Seconds = 0.0 })

    $clock = [Diagnostics.Stopwatch]::StartNew()
    $wrong = 0
    for ($n = 1; $n -le $Updates; $n++) {
        $first = 70.0 + $n
        for ($i = 0; $i -lt $Prices; $i++) { $quotes[$i, 0] = $first + $i * 0.01 }
        $priceRange.Value2 = $quotes
        if ([string]$reader.Text -ne "$first") { $wrong++ }
        if ($n % $Checkpoint -eq 0) {
            $counts = Settle $watch $baseline
            Write-Host ("after {0} updates: {1}; wrong readings so far {2}" -f $n, $counts.Text, $wrong)
            $rows.Add([pscustomobject]@{ Updates = $n; Live = $counts.Live; PriceBytes = $counts.PriceBytes; Published = $counts.Published; Released = $counts.Released; Seconds = [math]::Round($clock.Elapsed.TotalSeconds, 1) })
        }
    }
    Close-HiddenExcelWorkbook $excel $book
    $book = $null
    $scratch = Own $books.Add()
    $book = $scratch
    $watch = Own (Own (Own $scratch.Worksheets).Item(1)).Range("A1")
    $counts = Settle $watch 0
    Write-Host ("after closing the workbook: {0}" -f $counts.Text)
    $rows.Add([pscustomobject]@{ Updates = "closed"; Live = $counts.Live; PriceBytes = $counts.PriceBytes; Published = $counts.Published; Released = $counts.Released; Seconds = [math]::Round($clock.Elapsed.TotalSeconds, 1) })
    Write-Host ""
    Write-Host "| updates | live | price bytes | published | released | seconds |"
    Write-Host "|---|---|---|---|---|---|"
    foreach ($row in $rows) { Write-Host ("| {0} | {1} | {2} | {3} | {4} | {5} |" -f $row.Updates, $row.Live, $row.PriceBytes, $row.Published, $row.Released, $row.Seconds) }
    Write-Host ""
    Write-Host ("wrong readings: {0} of {1}; misses {2}; disposal errors {3}" -f $wrong, $Updates, $counts.Misses, $counts.DisposalErrors)
}
catch { $scriptError = $_; throw }
finally {
    Stop-HiddenExcel $session $owned $book -AddInLoaded:$loaded -FailureInFlight:($null -ne $scriptError)
}
