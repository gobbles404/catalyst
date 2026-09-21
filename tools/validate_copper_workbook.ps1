# Validate the Copper workbook in an owned hidden Excel process and a disposable copy.
# -SaveCalculated replaces the source only after all checks and restoration succeed.
# -SnapshotPath writes the restored baseline values for independent rendering.
param(
    [string]$Workbook = (Join-Path (Split-Path $PSScriptRoot -Parent) "workbooks\copper-validation.xlsx"),
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

function Assert-Blank($Actual, [string]$Where) {
    if ($null -ne $Actual -and $Actual -cne "") { throw "$Where`: expected blank, got '$Actual'" }
}

function Read-Range($Sheet, [string]$Address) {
    $range = $Sheet.Range($Address)
    try { Write-Output -NoEnumerate $range.Value2 }
    finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
}

function Read-Formula($Sheet, [string]$Address) {
    $range = $Sheet.Range($Address)
    try { return [string]$range.Formula2 }
    finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
}

function Write-Value($Sheet, [string]$Address, $Value) {
    $range = $Sheet.Range($Address)
    try {
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

# Input blocks have one header row at 9 and contiguous data from 10. The first blank,
# rather than UsedRange or a research file outside the repository, ends each block.
function Find-InputEnd($Sheet, [string]$Column) {
    $used = $Sheet.UsedRange
    try {
        $rows = $used.Rows
        try { $last = [math]::Max(11, $used.Row + $rows.Count - 1) }
        finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($rows) }
    }
    finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($used) }
    $values = Read-Range $Sheet "${Column}10:${Column}$last"
    $end = 9
    for ($i = 1; $i -le $values.GetLength(0); $i++) {
        $value = $values[$i, 1]
        if ($null -eq $value -or $value -ceq "") { break }
        $end++
    }
    if ($end -lt 10) { throw "$($Sheet.Name)!${Column}10 has no input" }
    return $end
}

function Read-Holidays([string]$Column, [int]$End) {
    $dates = [Collections.Generic.HashSet[datetime]]::new()
    $values = Read-Range $tabs["Definitions"] "${Column}10:${Column}$End"
    if ($End -eq 10) { [void]$dates.Add((Read-Date $values "Definitions!${Column}10")) }
    else {
        for ($i = 1; $i -le $End - 9; $i++) {
            [void]$dates.Add((Read-Date $values[$i, 1] "Definitions!$Column$($i + 9)"))
        }
    }
    Write-Output -NoEnumerate $dates
}

function Test-BusinessDay([datetime]$Day, $Holidays) {
    return $Day.DayOfWeek -ne [DayOfWeek]::Saturday -and
        $Day.DayOfWeek -ne [DayOfWeek]::Sunday -and -not $Holidays.Contains($Day)
}

function Next-BusinessDay([datetime]$Day, $Holidays) {
    do { $Day = $Day.AddDays(1) } while (-not (Test-BusinessDay $Day $Holidays))
    return $Day
}

function Read-Handles {
    $values = Read-Range $tabs["Copper"] "C12:C19"
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
    $value = [string](Read-Range $tabs["Copper"] $Address)
    if (-not $value.StartsWith("#ERROR ") -or -not $value.Contains($Contains)) {
        throw "$Address`: expected a visible error containing '$Contains', got '$value'"
    }
}

# Independent oracle: only input cells and ordinary date arithmetic determine expected
# values. The native view uses last-trading dates; the cash reference uses two different
# calendar steps. A correct native diagnostic can therefore expose an economic GAP.
function Assert-CopperView {
    $asOf = Read-Date (Read-Range $tabs["Copper"] "C6") "Copper!C6"
    Assert-Equal (Read-Range $tabs["Copper"] "C8") "daily" "Copper fixing mode"
    $schedule = Read-Range $tabs["Definitions"] "B10:D$($bounds.Schedule)"
    $codes = [Collections.Generic.List[string]]::new()
    $lastTrades = [Collections.Generic.List[datetime]]::new()
    $prompts = [Collections.Generic.List[datetime]]::new()
    $unique = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    for ($i = 1; $i -le $bounds.Schedule - 9; $i++) {
        $code = [string]$schedule[$i, 1]
        if (-not $unique.Add($code)) { throw "Duplicate code in schedule: $code" }
        $codes.Add($code)
        $lastTrades.Add((Read-Date $schedule[$i, 2] "Definitions!C$($i + 9)"))
        $prompts.Add((Read-Date $schedule[$i, 3] "Definitions!D$($i + 9)"))
        if ($i -gt 1 -and $lastTrades[$i - 1] -le $lastTrades[$i - 2]) {
            throw "Last-trading dates do not increase at schedule row $i"
        }
    }
    $first = $lastTrades[0].AddDays(1)
    $last = $lastTrades[$lastTrades.Count - 1]
    if ($asOf -lt $first -or $asOf -gt $last) { throw "Valuation is outside the native calendar" }
    $days = ($last - $first).Days + 1
    $end = $days + 9
    $tradeHolidays = Read-Holidays "G" $bounds.TradeHolidays
    $settlementHolidays = Read-Holidays "K" $bounds.SettlementHolidays
    $fixings = [Collections.Generic.Dictionary[datetime, double]]::new()
    $fixingValues = Read-Range $tabs["Fixings"] "B10:D$($bounds.Fixings)"
    for ($i = 1; $i -le $bounds.Fixings - 9; $i++) {
        $day = Read-Date $fixingValues[$i, 1] "Fixings!B$($i + 9)"
        if ($day -ge $asOf -or -not (Test-BusinessDay $day $tradeHolidays)) {
            throw "Fixing $day is not a historical LME business day"
        }
        if ($fixingValues[$i, 2] -isnot [double]) { throw "Nonnumeric fixing on $day" }
        $fixings.Add($day, ($fixingValues[$i, 2]))
        $next = Next-BusinessDay $day $tradeHolidays
        $cash = Next-BusinessDay $next $settlementHolidays
        Assert-Number $fixingValues[$i, 3] $cash.ToOADate() "Fixing cash prompt on $day"
    }
    $firstContract = 1
    while ($lastTrades[$firstContract] -lt $asOf) { $firstContract++ }
    $priceValues = Read-Range $tabs["Prompt prices"] "B10:F$($bounds.Prices)"
    Assert-Equal ($bounds.Prices - 9) ($codes.Count - $firstContract) "Vector length"
    $priceByCode = [Collections.Generic.Dictionary[string, double]]::new([StringComparer]::Ordinal)
    $priceByPrompt = [Collections.Generic.Dictionary[datetime, double]]::new()
    for ($i = 1; $i -le $bounds.Prices - 9; $i++) {
        $code = [string]$priceValues[$i, 1]
        Assert-Equal $code $codes[$firstContract + $i - 1] "Prompt prices code order at row $($i + 9)"
        $prompt = Read-Date $priceValues[$i, 2] "Prompt prices!C$($i + 9)"
        Assert-Equal $prompt $prompts[$firstContract + $i - 1] "Prompt prices settlement date for $code"
        Assert-Number $priceValues[$i, 3] $lastTrades[$firstContract + $i - 1].ToOADate() "Last trade for $code"
        if ($priceValues[$i, 5] -isnot [double]) { throw "Nonnumeric prompt price for $code" }
        $priceByCode.Add($code, ($priceValues[$i, 5]))
        $priceByPrompt.Add($prompt, ($priceValues[$i, 5]))
    }
    $view = Read-Range $tabs["Library view"] "B8:F$end"
    $history = Read-Range $tabs["Library view"] "H8:L$end"
    $cashView = Read-Range $tabs["Cash dates"] "B10:K$end"
    $headers = @("date", "prompt_contract", "is_business_day", "is_past", "price")
    $types = @("datetime64[D]", "str", "bool", "bool", "float64")
    for ($c = 1; $c -le 5; $c++) {
        Assert-Equal $view[1, $c] $headers[$c - 1] "Market header $c"
        $historyHeader = if ($c -eq 5) { "fixing_price" } else { $headers[$c - 1] }
        Assert-Equal $history[1, $c] $historyHeader "History header $c"
        Assert-Equal $view[2, $c] $types[$c - 1] "Market type $c"
        Assert-Equal $history[2, $c] $types[$c - 1] "History type $c"
    }
    $dates = [Collections.Generic.List[datetime]]::new()
    $nativePrices = [Collections.Generic.List[object]]::new()
    $referencePrices = [Collections.Generic.List[object]]::new()
    $nativeCodes = [Collections.Generic.List[string]]::new()
    $cashDates = [Collections.Generic.List[object]]::new()
    $prompt = 1
    $fixedCount = 0
    $liveCount = 0
    $closedCount = 0
    $gapCount = 0
    $unavailableCount = 0
    $firstUnavailable = $null
    for ($i = 0; $i -lt $days; $i++) {
        $day = $first.AddDays($i)
        while ($lastTrades[$prompt] -lt $day) { $prompt++ }
        $business = Test-BusinessDay $day $tradeHolidays
        $past = $day -lt $asOf
        $row = $i + 3
        $cashRow = $i + 1
        foreach ($table in @($view, $history)) {
            Assert-Number $table[$row, 1] $day.ToOADate() "Native date $day"
            Assert-Equal $table[$row, 2] $codes[$prompt] "Native prompt code on $day"
            foreach ($c in @(3, 4)) {
                if ($table[$row, $c] -isnot [bool]) { throw "Native flag $c on $day is not boolean" }
            }
            Assert-Equal $table[$row, 3] $business "Native business flag on $day"
            Assert-Equal $table[$row, 4] $past "Native past flag on $day"
        }
        if (-not $business) {
            $closedCount++
            $expected = "closed"
            $historyExpected = "closed"
        }
        elseif ($past) {
            $fixedCount++
            if (-not $fixings.ContainsKey($day)) { throw "Oracle has no fixing for $day" }
            $expected = $fixings[$day]
            $historyExpected = $expected
        }
        else {
            $liveCount++
            $expected = $priceByCode[$codes[$prompt]]
            $historyExpected = "unfixed"
        }
        if ($expected -is [string]) { Assert-Equal $view[$row, 5] $expected "Native price on $day" }
        else { Assert-Number $view[$row, 5] $expected "Native price on $day" }
        if ($historyExpected -is [string]) { Assert-Equal $history[$row, 5] $historyExpected "History on $day" }
        else { Assert-Number $history[$row, 5] $historyExpected "History on $day" }

        Assert-Number $cashView[$cashRow, 1] $day.ToOADate() "Cash row date $day"
        Assert-Equal $cashView[$cashRow, 2] $business "Cash business flag on $day"
        Assert-Number $cashView[$cashRow, 7] $prompts[$prompt].ToOADate() "Native contract prompt shown on $day"
        if ($expected -is [string]) { Assert-Equal $cashView[$cashRow, 8] $expected "Native price comparison on $day" }
        else { Assert-Number $cashView[$cashRow, 8] $expected "Native price comparison on $day" }
        $cash = $null
        if (-not $business) {
            Assert-Blank $cashView[$cashRow, 3] "Next trading day for closed date $day"
            Assert-Blank $cashView[$cashRow, 4] "Cash prompt for closed date $day"
            $reference = "closed"
            $sourceLabel = "Closed"
            $status = "CLOSED"
        }
        else {
            $next = Next-BusinessDay $day $tradeHolidays
            $cash = Next-BusinessDay $next $settlementHolidays
            Assert-Number $cashView[$cashRow, 3] $next.ToOADate() "Next LME business day on $day"
            Assert-Number $cashView[$cashRow, 4] $cash.ToOADate() "Two-stage cash prompt on $day"
            if ($past) {
                $reference = $fixings[$day]
                $sourceLabel = "Historical cash assessment"
                $status = "HISTORY"
            }
            elseif ($priceByPrompt.ContainsKey($cash)) {
                $reference = $priceByPrompt[$cash]
                $sourceLabel = "Current dated future"
                $status = if ($cash -eq $prompts[$prompt]) { "MATCH" } else { "DATE GAP" }
            }
            else {
                $reference = "unavailable"
                $unavailableCount++
                if ($null -eq $firstUnavailable) { $firstUnavailable = $day }
                $sourceLabel = "Missing dated price"
                $status = "NEEDS CURVE"
            }
        }
        Assert-Equal $cashView[$cashRow, 5] $sourceLabel "Cash price source on $day"
        Assert-Equal $cashView[$cashRow, 9] $status "Cash semantic comparison on $day"
        if ($reference -is [string]) {
            Assert-Equal $cashView[$cashRow, 6] $reference "Cash reference price on $day"
            Assert-Blank $cashView[$cashRow, 10] "Cash price difference on $day"
        }
        else {
            Assert-Number $cashView[$cashRow, 6] $reference "Cash reference price on $day"
            Assert-Number $cashView[$cashRow, 10] ($reference - $expected) "Cash reference minus native on $day"
        }
        if ($status -ceq "DATE GAP") { $gapCount++ }
        $dates.Add($day)
        $nativePrices.Add($expected)
        $referencePrices.Add($reference)
        $nativeCodes.Add($codes[$prompt])
        $cashDates.Add($cash)
    }
    return [pscustomobject]@{
        Dates = $dates.ToArray(); Prices = $nativePrices.ToArray(); References = $referencePrices.ToArray()
        Codes = $nativeCodes.ToArray(); CashDates = $cashDates.ToArray(); First = $first
        Fixed = $fixedCount; Live = $liveCount; Closed = $closedCount; Gaps = $gapCount
        Unavailable = $unavailableCount; FirstUnavailable = $firstUnavailable; FirstCode = $codes[$firstContract]
    }
}

function Assert-ChangedDates($Before, $After, [string[]]$Expected, [string]$Field = "Prices") {
    $changed = [Collections.Generic.List[string]]::new()
    for ($i = 0; $i -lt $Before.Dates.Count; $i++) {
        if ($Before.$Field[$i] -cne $After.$Field[$i]) { $changed.Add($Before.Dates[$i].ToString("yyyy-MM-dd")) }
    }
    Assert-Equal ($changed -join ",") ($Expected -join ",") "Dates whose $Field changed"
}

function Assert-BaselineChecks {
    $answers = Read-Range $tabs["Checks"] "B9:F28"
    for ($i = 1; $i -le 20; $i++) {
        Assert-Equal $answers[$i, 5] "PASS" "Checks!F$($i + 8) ($($answers[$i, 1]); expected $($answers[$i, 3]), calculated $($answers[$i, 4]))"
    }
    $tradeHolidays = Read-Holidays "G" $bounds.TradeHolidays
    $settlementHolidays = Read-Holidays "K" $bounds.SettlementHolidays
    $official = Read-Range $tabs["Definitions"] "O10:Q$($bounds.Checker)"
    $lastCheck = $bounds.Checker + 28
    $comparison = Read-Range $tabs["Checks"] "B38:F$lastCheck"
    for ($i = 1; $i -le $bounds.Checker - 9; $i++) {
        $day = Read-Date $official[$i, 1] "Official checker observation at row $i"
        $cash = Read-Date $official[$i, 2] "Official checker cash date at row $i"
        $next = Next-BusinessDay $day $tradeHolidays
        $calculated = Next-BusinessDay $next $settlementHolidays
        Assert-Equal $calculated $cash "Independent comparison with official cash date on $day"
        Assert-Number $comparison[$i, 1] $day.ToOADate() "Checker comparison observation on $day"
        Assert-Number $comparison[$i, 3] $cash.ToOADate() "Checker comparison official cash date on $day"
        Assert-Number $comparison[$i, 4] $cash.ToOADate() "Checker comparison calculated cash date on $day"
        Assert-Equal $comparison[$i, 5] "PASS" "Checks!F$($i + 37)"
    }
    foreach ($sheet in $tabs.Values) {
        $charts = $sheet.ChartObjects()
        try { Assert-Equal $charts.Count 0 "Unexpected chart on '$($sheet.Name)'" }
        finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($charts) }
        $used = $sheet.UsedRange
        try {
            foreach ($value in $used.Value2) {
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

$source = (Resolve-Path -LiteralPath $Workbook).Path
$temporary = Join-Path ([IO.Path]::GetTempPath()) ("goosedove-copper-" + [guid]::NewGuid().ToString("N") + ".xlsx")
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
    $excel.Calculation = -4135
    $sheets = Own $book.Worksheets
    $tabs = [ordered]@{}
    for ($i = 1; $i -le $sheets.Count; $i++) {
        $sheet = Own $sheets.Item($i)
        $tabs[$sheet.Name] = $sheet
    }
    foreach ($name in @("Copper", "Definitions", "Fixings", "Prompt prices", "Library view", "Cash dates", "Checks")) {
        if (-not $tabs.Contains($name)) { throw "Workbook has no '$name' worksheet" }
    }
    $bounds = @{
        Schedule = Find-InputEnd $tabs["Definitions"] "B"
        TradeHolidays = Find-InputEnd $tabs["Definitions"] "G"
        SettlementHolidays = Find-InputEnd $tabs["Definitions"] "K"
        Checker = Find-InputEnd $tabs["Definitions"] "O"
        Fixings = Find-InputEnd $tabs["Fixings"] "B"
        Prices = Find-InputEnd $tabs["Prompt prices"] "B"
    }
    $formulas = [ordered]@{
        C12 = "=_CreateValuationDate(C6,C7)"
        C13 = "=_CreateExpirySchedule(Definitions!B10:B$($bounds.Schedule),Definitions!C10:C$($bounds.Schedule))"
        C14 = "=_CreateHolidayCalendar(Definitions!G10:G$($bounds.TradeHolidays))"
        C15 = "=_CreateCalendar(C12,C8,C13,C14)"
        C16 = "=_CreateDailyFixings(Fixings!B9:C9,Fixings!B10:C$($bounds.Fixings),C14)"
        C17 = "=_CreateMarketHistory(C15,C16)"
        C18 = "=_CreatePriceVector('Prompt prices'!F10:F$($bounds.Prices))"
        C19 = "=_CreateMarket(C17,C18)"
    }
    foreach ($address in $formulas.Keys) { Write-Formula $tabs["Copper"] $address $formulas[$address] }
    Write-Formula $tabs["Library view"] "B8" "=util_ReadHandle(Copper!C19)"
    Write-Formula $tabs["Library view"] "H8" "=util_ReadHandle(Copper!C17)"
    $excel.CalculateFullRebuild()
    Assert-Equal (Read-Date (Read-Range $tabs["Copper"] "C6") "Copper!C6") ([datetime]"2026-09-18") "Baseline valuation"
    Assert-Number (Read-Range $tabs["Copper"] "C7") 1 "Baseline fraction"
    $baseline = Assert-CopperView
    Assert-BaselineChecks
    if ($baseline.Gaps -lt 1 -or $baseline.Unavailable -lt 1) { throw "The workbook must expose cash-date and sparse-curve gaps" }
    foreach ($case in @(@("2026-09-18", "2026-09-22"), @("2026-10-08", "2026-10-13"),
        @("2026-10-09", "2026-10-13"), @("2026-10-12", "2026-10-14"))) {
        $row = (([datetime]$case[0]) - $baseline.First).Days
        Assert-Equal $baseline.CashDates[$row] ([datetime]$case[1]) "Cash date for $($case[0])"
    }
    $valuationRow = (([datetime]"2026-09-18") - $baseline.First).Days + 10
    Assert-Number (Read-Range $tabs["Cash dates"] "H$valuationRow") ([datetime]"2026-09-21").ToOADate() "Native prompt on September 18"
    Write-Host "Copper baseline: $($baseline.Dates.Count) market/history and cash-reference rows verified; $($baseline.Gaps) date gaps and $($baseline.Unavailable) unavailable exact points remain visible."

    $price = [double](Read-Range $tabs["Prompt prices"] "F10")
    $fixing = [double](Read-Range $tabs["Fixings"] "C10")
    $fixingDate = Read-Date (Read-Range $tabs["Fixings"] "B10") "First fixing date"
    $handles = Read-Handles
    Write-Value $tabs["Prompt prices"] "F10" ($price + 25.0)
    $excel.Calculate()
    Assert-Handles $handles @("C18", "C19")
    $bumped = Assert-CopperView
    $expectedDates = @()
    for ($i = 0; $i -lt $baseline.Dates.Count; $i++) {
        if ($baseline.Dates[$i] -ge [datetime]"2026-09-18" -and $baseline.Prices[$i] -isnot [string] -and
            $baseline.Codes[$i] -ceq $baseline.FirstCode) { $expectedDates += $baseline.Dates[$i].ToString("yyyy-MM-dd") }
    }
    Assert-ChangedDates $baseline $bumped $expectedDates
    Assert-ChangedDates $baseline $bumped @() -Field "References"
    Write-Value $tabs["Prompt prices"] "F10" $price
    $excel.Calculate()

    $cashPrice = [double](Read-Range $tabs["Prompt prices"] "F11")
    $handles = Read-Handles
    Write-Value $tabs["Prompt prices"] "F11" ($cashPrice + 25.0)
    $excel.Calculate()
    Assert-Handles $handles @("C18", "C19")
    $bumped = Assert-CopperView
    Assert-ChangedDates $baseline $bumped @("2026-09-21")
    Assert-ChangedDates $baseline $bumped @("2026-09-18") -Field "References"
    Write-Value $tabs["Prompt prices"] "F11" $cashPrice
    $excel.Calculate()
    $handles = Read-Handles
    Write-Value $tabs["Fixings"] "C10" ($fixing + 7.5)
    $excel.Calculate()
    Assert-Handles $handles @("C16", "C17", "C19")
    $bumped = Assert-CopperView
    Assert-ChangedDates $baseline $bumped @($fixingDate.ToString("yyyy-MM-dd"))
    Write-Value $tabs["Fixings"] "C10" $fixing
    $excel.Calculate()
    Write-Host "Copper mutations: cash price affects September 18 in the reference and September 21 natively; fixing and price handles change selectively."

    Clear-Range $tabs["Prompt prices"] "F10"
    $excel.Calculate()
    Assert-Error "C18" "is blank"
    Assert-Error "C19" "creator's failure"
    Write-Value $tabs["Prompt prices"] "F10" $price
    Write-Formula $tabs["Copper"] "C18" "=_CreatePriceVector('Prompt prices'!F11:F$($bounds.Prices))"
    $excel.Calculate()
    Assert-Error "C19" "expected $($bounds.Prices - 9)"
    Write-Formula $tabs["Copper"] "C18" $formulas.C18
    Write-Formula $tabs["Copper"] "C16" "=_CreateDailyFixings(Fixings!B9:C9,Fixings!B11:C$($bounds.Fixings),C14)"
    $excel.Calculate()
    Assert-Error "C17" "no fixing for $($fixingDate.ToString('yyyy-MM-dd'))"
    Write-Formula $tabs["Copper"] "C16" $formulas.C16
    $newRow = $bounds.Fixings + 1
    foreach ($value in (Read-Range $tabs["Fixings"] "B${newRow}:C$newRow")) { Assert-Blank $value "Fixing extension scratch row" }
    Write-Value $tabs["Fixings"] "B$newRow" ([datetime]"2026-09-18").ToOADate()
    Write-Value $tabs["Fixings"] "C$newRow" $price
    Write-Formula $tabs["Copper"] "C16" "=_CreateDailyFixings(Fixings!B9:C9,Fixings!B10:C$newRow,C14)"
    $excel.Calculate()
    Assert-Error "C17" "on or after valuation date 2026-09-18"
    Clear-Range $tabs["Fixings"] "B${newRow}:C$newRow"
    Write-Formula $tabs["Copper"] "C16" $formulas.C16
    $excel.Calculate()
    Write-Host "Copper failures: blank price, wrong vector count, missing fixing, and current-day fixing are visible."

    $secondCode = [string](Read-Range $tabs["Definitions"] "B11")
    $thirdCode = [string](Read-Range $tabs["Definitions"] "B12")
    $secondExpiry = [double](Read-Range $tabs["Definitions"] "C11")
    $thirdExpiry = [double](Read-Range $tabs["Definitions"] "C12")
    Write-Value $tabs["Definitions"] "B12" $secondCode
    $excel.Calculate()
    Assert-Error "C15" "already given at row 2"
    Write-Value $tabs["Definitions"] "B12" $thirdCode
    Write-Value $tabs["Definitions"] "C12" $secondExpiry
    $excel.Calculate()
    Assert-Error "C15" "future_expiry row 3"
    Write-Value $tabs["Definitions"] "C12" $thirdExpiry
    $excel.Calculate()
    Assert-CopperView | Out-Null
    Write-Host "Copper schedule: dated identifiers work; duplicate codes and nonincreasing last-trading dates fail visibly."

    $handles = Read-Handles
    Write-Value $tabs["Copper"] "C7" 0.0
    $excel.Calculate()
    Assert-Handles $handles @("C12", "C15", "C17", "C19")
    $morning = Assert-CopperView
    Assert-ChangedDates $baseline $morning @()
    Write-Value $tabs["Copper"] "C7" 1.0
    $excel.Calculate()
    $restored = Assert-CopperView
    Assert-ChangedDates $baseline $restored @()
    Assert-BaselineChecks
    Write-Host "Copper fraction 0 versus 1: same dated prices, confirming the visible intraday last-trading cut-off gap."
    $excel.Calculation = -4105
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
Write-Host "Copper validation passed; baseline restored$(if ($SaveCalculated) { ' and saved to the source workbook' })."
