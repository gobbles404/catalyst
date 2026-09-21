# Validate the NG workbook in a separate Excel process and a disposable copy. The source is
# replaced only when every check passes and -SaveCalculated was requested. Never uses an
# existing Excel session. -SnapshotPath writes the final baseline's cell values for rendering.
param(
    [string]$Workbook = (Join-Path (Split-Path $PSScriptRoot -Parent) "workbooks\ng-validation.xlsx"),
    [switch]$SaveCalculated,
    [string]$SnapshotPath
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "host_build.ps1")
. (Join-Path $PSScriptRoot "hidden_excel.ps1")

function Assert-Equal($Actual, $Expected, [string]$Where) {
    if ($Actual -cne $Expected) { throw "$Where`: expected '$Expected', got '$Actual'" }
}

function Assert-Number($Actual, [double]$Expected, [string]$Where) {
    if (($Actual -isnot [double] -and $Actual -isnot [int]) -or
        [double]::IsNaN([double]$Actual) -or [math]::Abs([double]$Actual - $Expected) -gt 0.00000001) {
        throw "$Where`: expected number $Expected, got '$Actual'"
    }
}

function Read-Range($Sheet, [string]$Address) {
    $range = $Sheet.Range($Address)
    try { Write-Output -NoEnumerate $range.Value2 }
    finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
}

function Write-Value($Sheet, [string]$Address, $Value) {
    $range = $Sheet.Range($Address)
    try {
        # Explicitly unwrap PowerShell's string wrapper at the COM boundary.
        if ($Value -is [string]) { $range.Value2 = [string]$Value }
        else { $range.Value2 = $Value }
    }
    finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
}

function Write-Formula($Sheet, [string]$Address, [string]$Formula) {
    $range = $Sheet.Range($Address)
    try { $range.Formula2 = $Formula }
    finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
}

function Clear-Range($Sheet, [string]$Address) {
    $range = $Sheet.Range($Address)
    try { [void]$range.ClearContents() }
    finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
}

function Read-Date($Value, [string]$Where) {
    if ($Value -isnot [double] -or $Value -ne [math]::Truncate($Value)) {
        throw "$Where`: expected a numeric whole-day Excel date, got '$Value'"
    }
    return [datetime]::FromOADate($Value).Date
}

function Read-Handles {
    $values = Read-Range $tabs["NG"] "C12:C19"
    $result = @{}
    for ($i = 1; $i -le 8; $i++) { $result["C$($i + 11)"] = [string]$values[$i, 1] }
    return $result
}

function Assert-Handles($Before, [string[]]$Changed) {
    $after = Read-Handles
    foreach ($address in $Before.Keys) {
        if ($Changed -contains $address) {
            if ($after[$address] -eq $Before[$address]) { throw "$address did not publish a new handle" }
        }
        else { Assert-Equal $after[$address] $Before[$address] "$address changed unnecessarily" }
    }
}

function Assert-Error([string]$Address, [string]$Contains) {
    $value = [string](Read-Range $tabs["NG"] $Address)
    if (-not $value.StartsWith("#ERROR ") -or -not $value.Contains($Contains)) {
        throw "$Address`: expected a visible error containing '$Contains', got '$value'"
    }
}

# This oracle uses only the workbook's inputs and ordinary PowerShell date arithmetic. It
# neither calls the Python library nor derives expected answers from the displayed calendar.
function Assert-DailyView([int]$FixingEnd = 942, [int]$PriceStart = 10) {
    $asOf = Read-Date (Read-Range $tabs["NG"] "C6") "NG!C6"
    Assert-Equal (Read-Range $tabs["NG"] "C8") "daily" "NG!C8"
    $schedule = Read-Range $tabs["Definitions"] "B10:C105"
    $codes = [Collections.Generic.List[string]]::new()
    $expiries = [Collections.Generic.List[datetime]]::new()
    for ($i = 1; $i -le 96; $i++) {
        $codes.Add([string]($schedule[$i, 1]))
        $expiries.Add((Read-Date $schedule[$i, 2] "Definitions!C$($i + 9)"))
        if ($i -gt 1 -and $expiries[$i - 1] -le $expiries[$i - 2]) { throw "Expiries do not increase" }
    }
    Assert-Equal $codes[0] "F23" "Expiry anchor"
    Assert-Equal $codes[1] "G23" "First represented contract"
    Assert-Equal $codes[95] "Z30" "Last represented contract"
    $first = $expiries[0].AddDays(1)
    $last = $expiries[95]
    Assert-Equal $first ([datetime]"2022-12-29") "First calendar date"
    Assert-Equal $last ([datetime]"2030-11-26") "Last calendar date"
    $days = ($last - $first).Days + 1
    Assert-Equal $days 2890 "Calendar day count"

    $holidays = [Collections.Generic.HashSet[datetime]]::new()
    $holidayValues = Read-Range $tabs["Definitions"] "G10:G89"
    for ($i = 1; $i -le 80; $i++) {
        [void]$holidays.Add((Read-Date $holidayValues[$i, 1] "Definitions!G$($i + 9)"))
    }
    $fixings = [Collections.Generic.Dictionary[datetime, double]]::new()
    $fixingValues = Read-Range $tabs["Fixings"] "B10:C$FixingEnd"
    for ($i = 1; $i -le $FixingEnd - 9; $i++) {
        $date = Read-Date $fixingValues[$i, 1] "Fixings!B$($i + 9)"
        $price = $fixingValues[$i, 2]
        if ($price -isnot [double]) { throw "Fixings!C$($i + 9) is not a number" }
        if ($date -ge $asOf) { throw "The oracle received a fixing on or after valuation" }
        $fixings.Add($date, $price)
    }
    $firstContract = 1
    while ($expiries[$firstContract] -lt $asOf) { $firstContract++ }
    $livePrices = Read-Range $tabs["Prices"] "B${PriceStart}:C60"
    Assert-Equal (61 - $PriceStart) (96 - $firstContract) "Live price count"
    $priceByCode = [Collections.Generic.Dictionary[string, double]]::new()
    for ($i = 1; $i -le 61 - $PriceStart; $i++) {
        $code = [string]$livePrices[$i, 1]
        Assert-Equal $code $codes[$firstContract + $i - 1] "Prices!B$($PriceStart + $i - 1) order"
        if ($livePrices[$i, 2] -isnot [double]) { throw "Prices!C$($PriceStart + $i - 1) is not a number" }
        $priceByCode.Add($code, ($livePrices[$i, 2]))
    }

    $view = Read-Range $tabs["Daily view"] "B8:F2899"
    $history = Read-Range $tabs["Daily view"] "H8:L2899"
    $headers = @("date", "prompt_contract", "is_business_day", "is_past", "price")
    $types = @("datetime64[D]", "str", "bool", "bool", "float64")
    for ($column = 1; $column -le 5; $column++) {
        Assert-Equal $view[1, $column] $headers[$column - 1] "Market header $column"
        $historyHeader = if ($column -eq 5) { "fixing_price" } else { $headers[$column - 1] }
        Assert-Equal $history[1, $column] $historyHeader "History header $column"
        Assert-Equal $view[2, $column] $types[$column - 1] "Market type $column"
        Assert-Equal $history[2, $column] $types[$column - 1] "History type $column"
    }
    $expiryRow = (([datetime]"2026-09-28") - $first).Days + 3
    Assert-Equal $view[$expiryRow, 2] "V26" "V26 remains prompt on its September 28 expiry"
    Assert-Equal $view[($expiryRow + 1), 2] "X26" "X26 becomes prompt on September 29"
    $prices = [Collections.Generic.List[object]]::new()
    $dates = [Collections.Generic.List[datetime]]::new()
    $prompt = 1
    $fixedCount = 0
    $liveCount = 0
    $closedCount = 0
    for ($i = 0; $i -lt $days; $i++) {
        $date = $first.AddDays($i)
        while ($expiries[$prompt] -lt $date) { $prompt++ }
        $business = $date.DayOfWeek -ne [DayOfWeek]::Saturday -and
            $date.DayOfWeek -ne [DayOfWeek]::Sunday -and -not $holidays.Contains($date)
        $past = $date -lt $asOf
        $row = $i + 3
        foreach ($table in @($view, $history)) {
            Assert-Number $table[$row, 1] $date.ToOADate() "Date at daily offset $i"
            Assert-Equal $table[$row, 2] $codes[$prompt] "Prompt on $($date.ToString('yyyy-MM-dd'))"
            foreach ($column in @(3, 4)) {
                if ($table[$row, $column] -isnot [bool]) { throw "Daily offset $i column $column is not boolean" }
            }
            Assert-Equal $table[$row, 3] $business "Business flag at daily offset $i"
            Assert-Equal $table[$row, 4] $past "Past flag at daily offset $i"
        }
        if (-not $business) {
            $closedCount++
            $expected = "closed"
            Assert-Equal $view[$row, 5] $expected "Closed market day $date"
            Assert-Equal $history[$row, 5] $expected "Closed history day $date"
        }
        elseif ($past) {
            $fixedCount++
            if (-not $fixings.ContainsKey($date)) { throw "Oracle: no fixing for $date" }
            $expected = $fixings[$date]
            Assert-Number $view[$row, 5] $expected "Historical market price on $date"
            Assert-Number $history[$row, 5] $expected "History fixing on $date"
        }
        else {
            $liveCount++
            $expected = $priceByCode[$codes[$prompt]]
            Assert-Number $view[$row, 5] $expected "Live market price on $date"
            Assert-Equal $history[$row, 5] "unfixed" "Live history day $date"
        }
        $dates.Add($date)
        $prices.Add(($view[$row, 5]))
    }
    return [pscustomobject]@{
        Dates = $dates.ToArray(); Prices = $prices.ToArray(); Prompt = $codes[$firstContract]
        Fixed = $fixedCount; Live = $liveCount; Closed = $closedCount
    }
}

function Assert-ChangedDates($Before, $After, [string[]]$Expected) {
    $changed = [Collections.Generic.List[string]]::new()
    for ($i = 0; $i -lt $Before.Dates.Count; $i++) {
        if ($Before.Prices[$i] -cne $After.Prices[$i]) { $changed.Add($Before.Dates[$i].ToString("yyyy-MM-dd")) }
    }
    Assert-Equal ($changed -join ",") ($Expected -join ",") "Dates whose market price changed"
}

function Assert-BaselineChecks {
    foreach ($cell in @(@("Prices", "C10"), @("Prices", "C60"), @("Fixings", "C10"), @("Fixings", "C942"))) {
        $range = $tabs[$cell[0]].Range($cell[1])
        try {
            if ([string]$range.NumberFormat -notmatch '0\.000(?!0)') {
                throw "$($cell[0])!$($cell[1]) must display prices to three decimal places"
            }
        }
        finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
    }
    $answers = Read-Range $tabs["Checks"] "H36:H2925"
    for ($i = 1; $i -le 2890; $i++) { Assert-Equal $answers[$i, 1] "PASS" "Checks!H$($i + 35)" }
    foreach ($sheet in $tabs.Values) {
        $charts = $sheet.ChartObjects()
        try { Assert-Equal $charts.Count 0 "Unexpected chart on '$($sheet.Name)'" }
        finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($charts) }
        $used = $sheet.UsedRange
        try {
            $values = $used.Value2
            # COM exposes Excel errors as integer error codes. Ordinary numeric cells arrive
            # as doubles, and library failures are text beginning #ERROR.
            foreach ($value in $values) {
                if ($value -is [System.Runtime.InteropServices.ErrorWrapper] -or
                    ($value -is [int] -and $value -lt 0) -or
                    ($value -is [string] -and $value -match '^#(ERROR|REF!|DIV/0!|VALUE!|NAME\?|N/A|NUM!|NULL!|SPILL!|CALC!)')) {
                    throw "Unexpected baseline error on '$($sheet.Name)': $value"
                }
            }
        }
        finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($used) }
    }
}

function Read-Snapshot {
    $snapshot = [Collections.Generic.List[object]]::new()
    foreach ($sheet in $tabs.Values) {
        $used = $sheet.UsedRange
        try {
            $values = $used.Value2
            $rows = [Collections.Generic.List[object]]::new()
            if ($values -is [array]) {
                for ($r = $values.GetLowerBound(0); $r -le $values.GetUpperBound(0); $r++) {
                    $row = [object[]]::new($values.GetLength(1))
                    for ($c = $values.GetLowerBound(1); $c -le $values.GetUpperBound(1); $c++) {
                        $row[$c - $values.GetLowerBound(1)] = $values[$r, $c]
                    }
                    $rows.Add($row)
                }
            }
            else { $rows.Add([object[]]@($values)) }
            $snapshot.Add([pscustomobject]@{
                name = $sheet.Name; range = $used.Address($false, $false); values = $rows.ToArray()
            })
        }
        finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($used) }
    }
    return ConvertTo-Json -InputObject $snapshot.ToArray() -Depth 8
}

. (Join-Path $PSScriptRoot "ng_benchmark_checks.ps1")

$source = (Resolve-Path -LiteralPath $Workbook).Path
$temporary = Join-Path ([IO.Path]::GetTempPath()) ("goosedove-ng-" + [guid]::NewGuid().ToString("N") + ".xlsx")
$session = $null
$book = $null
$loaded = $false
$scriptError = $null
$snapshotJson = $null
$owned = [Collections.Generic.List[object]]::new()
function Own($Object) { $owned.Add($Object); Write-Output -NoEnumerate $Object }

try {
    Copy-Item -LiteralPath $source -Destination $temporary
    $xll = Build-HostAddIn -Root $root
    $session = Start-HiddenExcel
    $excel = $session.Excel
    if (-not $excel.RegisterXLL($xll)) { throw "Excel refused to load $xll" }
    $loaded = $true
    Assert-Equal ($excel.Run("GoosedoveStatus")) "ok: python started and functions registered" "Add-in startup"
    $ping = [string]$excel.Run("Ping")
    if (-not $ping.Contains((Join-Path $root "src\goosedove"))) { throw "Wrong Python checkout: $ping" }
    $books = Own $excel.Workbooks
    $book = Own $books.Open($temporary, 0, $false)
    $excel.Calculation = -4135 # manual during multi-cell changes; Calculate still follows dependencies
    $sheets = Own $book.Worksheets
    $tabs = [ordered]@{}
    for ($i = 1; $i -le $sheets.Count; $i++) {
        $sheet = Own $sheets.Item($i)
        $tabs[$sheet.Name] = $sheet
    }
    foreach ($name in @("NG", "Definitions", "Fixings", "Prices", "Daily view", "Checks")) {
        if (-not $tabs.Contains($name)) { throw "Workbook has no '$name' worksheet" }
    }
    $options = Read-Range $tabs["Definitions"] "D10:D105"
    $optionCount = @($options | Where-Object { $null -ne $_ -and $_ -ne "" }).Count
    if ($optionCount -ne 0 -and $optionCount -ne 96) { throw "Option expiry column is only partly populated" }
    $scheduleFormula = if ($optionCount -eq 96) {
        "=_CreateExpirySchedule(Definitions!B10:B105,Definitions!C10:C105,Definitions!D10:D105)"
    } else { "=_CreateExpirySchedule(Definitions!B10:B105,Definitions!C10:C105)" }
    $formulas = [ordered]@{
        C12 = "=_CreateValuationDate(C6,C7)"
        C13 = $scheduleFormula
        C14 = "=_CreateHolidayCalendar(Definitions!G10:G89)"
        C15 = "=_CreateCalendar(C12,C8,C13,C14)"
        C16 = "=_CreateDailyFixings(Fixings!B9:C9,Fixings!B10:C942,C14)"
        C17 = "=_CreateMarketHistory(C15,C16)"
        C18 = "=_CreatePriceVector(Prices!C10:C60)"
        C19 = "=_CreateMarket(C17,C18)"
    }
    foreach ($address in $formulas.Keys) { Write-Formula $tabs["NG"] $address $formulas[$address] }
    Write-Formula $tabs["Daily view"] "B8" "=util_ReadHandle(NG!C19)"
    Write-Formula $tabs["Daily view"] "H8" "=util_ReadHandle(NG!C17)"
    foreach ($name in @("IFERC", "Gas Daily")) {
        Write-Formula $tabs["$name dates"] "B8" "=util_ReadHandle('$name'!C19)"
        Write-Formula $tabs["$name dates"] "H8" "=util_ReadHandle('$name'!C17)"
    }
    $excel.CalculateFullRebuild()
    Assert-Equal (Read-Date (Read-Range $tabs["NG"] "C6") "NG!C6") ([datetime]"2026-09-18") "Baseline valuation date"
    Assert-Number (Read-Range $tabs["NG"] "C7") 1 "Baseline day fraction"
    $baseline = Assert-DailyView
    Assert-Equal $baseline.Prompt "V26" "Baseline prompt"
    Assert-Equal $baseline.Fixed 933 "Historical priced days"
    Assert-Equal $baseline.Live 1054 "Live priced days"
    Assert-Equal $baseline.Closed 903 "Closed days"
    Assert-BaselineChecks
    Write-Host "NG baseline: all 2,890 market/history rows and independent worksheet checks pass."

    $price = [double](Read-Range $tabs["Prices"] "C10")
    $fixing = [double](Read-Range $tabs["Fixings"] "C10")
    $handles = Read-Handles
    Write-Value $tabs["Prices"] "C10" ($price + 0.100)
    $excel.Calculate()
    Assert-Handles $handles @("C18", "C19")
    $bumped = Assert-DailyView
    Assert-ChangedDates $baseline $bumped @(
        "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23",
        "2026-09-24", "2026-09-25", "2026-09-28"
    )
    Write-Value $tabs["Prices"] "C10" $price
    $excel.Calculate()
    $handles = Read-Handles
    Write-Value $tabs["Fixings"] "C10" ($fixing + 0.025)
    $excel.Calculate()
    Assert-Handles $handles @("C16", "C17", "C19")
    $bumped = Assert-DailyView
    Assert-ChangedDates $baseline $bumped @("2022-12-29")
    Write-Value $tabs["Fixings"] "C10" $fixing
    $excel.Calculate()
    Write-Host "NG edits: price and fixing changes update only their expected dates and dependent handles."

    Clear-Range $tabs["Prices"] "C10"
    $excel.Calculate()
    Assert-Error "C18" "is blank"
    Assert-Error "C19" "creator's failure"
    Write-Value $tabs["Prices"] "C10" $price
    Write-Formula $tabs["NG"] "C18" "=_CreatePriceVector(Prices!C11:C60)"
    $excel.Calculate()
    Assert-Error "C19" "expected 51"
    Write-Formula $tabs["NG"] "C18" $formulas.C18
    Write-Formula $tabs["NG"] "C16" "=_CreateDailyFixings(Fixings!B9:C9,Fixings!B11:C942,C14)"
    $excel.Calculate()
    Assert-Error "C17" "no fixing for 2022-12-29"
    Write-Formula $tabs["NG"] "C16" $formulas.C16
    foreach ($value in (Read-Range $tabs["Fixings"] "B943:C949")) {
        if ($null -ne $value -and $value -ne "") { throw "The fixing roll test needs B943:C949 empty" }
    }
    Write-Value $tabs["Fixings"] "B943" ([datetime]"2026-09-18").ToOADate()
    Write-Value $tabs["Fixings"] "C943" $price
    Write-Formula $tabs["NG"] "C16" "=_CreateDailyFixings(Fixings!B9:C9,Fixings!B10:C943,C14)"
    $excel.Calculate()
    Assert-Error "C17" "on or after valuation date 2026-09-18"
    Write-Host "NG failures: blank price, wrong vector count, missing fixing and current-day fixing are visible."

    Write-Value $tabs["NG"] "C6" ([datetime]"2026-09-29").ToOADate()
    $rollDates = @("2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28")
    for ($i = 0; $i -lt $rollDates.Count; $i++) {
        $row = 944 + $i
        Write-Value $tabs["Fixings"] "B$row" ([datetime]$rollDates[$i]).ToOADate()
        Write-Value $tabs["Fixings"] "C$row" $price
    }
    Write-Formula $tabs["NG"] "C16" "=_CreateDailyFixings(Fixings!B9:C9,Fixings!B10:C949,C14)"
    Write-Formula $tabs["NG"] "C18" "=_CreatePriceVector(Prices!C11:C60)"
    $excel.Calculate()
    $rolled = Assert-DailyView -FixingEnd 949 -PriceStart 11
    Assert-Equal $rolled.Prompt "X26" "Rolled prompt"
    Assert-Equal $rolled.Fixed 940 "Rolled historical priced days"
    Assert-Equal $rolled.Live 1047 "Rolled live priced days"
    Write-Host "NG roll: September 29 uses X26 first, 50 prices, and the seven new historical fixings."

    Write-Value $tabs["NG"] "C6" ([datetime]"2026-09-18").ToOADate()
    Clear-Range $tabs["Fixings"] "B943:C949"
    Write-Formula $tabs["NG"] "C16" $formulas.C16
    Write-Formula $tabs["NG"] "C18" $formulas.C18
    $excel.Calculate()
    $restored = Assert-DailyView
    Assert-ChangedDates $baseline $restored @()
    Assert-BaselineChecks
    Invoke-HenryBenchmarkChecks
    Assert-BaselineChecks
    $excel.Calculation = -4105 # save in automatic mode for ordinary workbook use
    $book.Save()
    if ($SnapshotPath) { $snapshotJson = Read-Snapshot }
}
catch { $scriptError = $_; Write-Host $_.ScriptStackTrace; throw }
finally {
    try {
        if ($session) {
            Stop-HiddenExcel $session $owned $book -AddInLoaded:$loaded -FailureInFlight:($null -ne $scriptError)
        }
        if ($null -eq $scriptError -and $SaveCalculated) { Copy-Item -LiteralPath $temporary -Destination $source -Force }
        if ($null -eq $scriptError -and $SnapshotPath) {
            $snapshotFile = [IO.Path]::GetFullPath($SnapshotPath)
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($snapshotFile))
            [IO.File]::WriteAllText($snapshotFile, $snapshotJson, [Text.UTF8Encoding]::new($false))
        }
    }
    finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
}
Write-Host "NG validation passed; baseline restored$(if ($SaveCalculated) { ' and saved to the source workbook' })."
