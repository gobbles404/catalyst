# Validation helpers for the Henry Hub IFERC and Gas Daily tabs. Dot-source after the
# range/assertion helpers in validate_ng_workbook.ps1; the caller owns its hidden Excel
# session and disposable workbook. These functions never attach to or start Excel.

function Read-HenryHandles([string]$Name) {
    $values = Read-Range $tabs[$Name] "C12:C19"
    $result = @{}
    for ($i = 1; $i -le 8; $i++) { $result["C$($i + 11)"] = [string]$values[$i, 1] }
    return $result
}

function Assert-HenryHandles([string]$Name, $Before, [string[]]$Changed) {
    $after = Read-HenryHandles $Name
    foreach ($address in $Before.Keys) {
        if ($Changed -contains $address) {
            if ($after[$address] -eq $Before[$address]) { throw "$Name!$address did not publish a new handle" }
        }
        else { Assert-Equal $after[$address] $Before[$address] "$Name!$address changed unnecessarily" }
    }
}

function Assert-HenryError([string]$Name, [string]$Address, [string]$Contains) {
    $value = [string](Read-Range $tabs[$Name] $Address)
    if (-not $value.StartsWith("#ERROR ") -or -not $value.Contains($Contains)) {
        throw "$Name!$Address`: expected a visible error containing '$Contains', got '$value'"
    }
}

function Read-HenryFormula($Sheet, [string]$Address) {
    $range = $Sheet.Range($Address)
    try { return [string]$range.Formula2 }
    finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
}

# This oracle uses only input cells and ordinary PowerShell date arithmetic. In particular,
# monthly rows are prompt-tenure dates, and Gas Daily rows are assessment-date adapter rows;
# neither this oracle nor the displayed native calendar claims physical delivery coverage.
function Assert-HenryView([string]$Name, [switch]$WorksheetChecks) {
    $main = $tabs[$Name]
    $inputs = $tabs["$Name inputs"]
    $dateSheet = $tabs["$Name dates"]
    $monthly = $Name -ceq "IFERC"
    $mode = if ($monthly) { "monthly" } else { "daily" }
    $asOf = Read-Date (Read-Range $main "C6") "$Name!C6"
    Assert-Equal (Read-Range $main "C8") $mode "$Name fixing mode"
    $fixingCount = [int](Read-Range $main "C10")
    $holidayCount = [int](Read-Range $main "F10")
    if ($fixingCount -lt 1 -or $holidayCount -lt 1) { throw "$Name has empty fixture input counts" }
    $fixingEnd = $fixingCount + 9
    $holidayEnd = $holidayCount + 9
    $schedule = Read-Range $inputs "B10:E105"
    $codes = [Collections.Generic.List[string]]::new()
    $expiries = [Collections.Generic.List[datetime]]::new()
    $publications = [Collections.Generic.List[datetime]]::new()
    for ($i = 1; $i -le 96; $i++) {
        $codes.Add([string]($schedule[$i, 1]))
        $expiries.Add((Read-Date $schedule[$i, 2] "$Name inputs!C$($i + 9)"))
        if ($i -gt 1 -and $expiries[$i - 1] -le $expiries[$i - 2]) { throw "$Name expiries do not increase" }
        if ($monthly) {
            $publications.Add((Read-Date $schedule[$i, 3] "$Name inputs!D$($i + 9)"))
            if ($i -gt 1 -and $publications[$i - 1] -le $publications[$i - 2]) {
                throw "$Name publication dates do not increase"
            }
        }
    }
    Assert-Equal $codes[0] "F23" "$Name expiry anchor"
    Assert-Equal $codes[1] "G23" "$Name first represented contract"
    Assert-Equal $codes[95] "Z30" "$Name last represented contract"
    $first = $expiries[0].AddDays(1)
    $last = $expiries[95]
    $days = ($last - $first).Days + 1
    $lastRow = $days + 9
    if ($asOf -lt $first -or $asOf -gt $last) { throw "$Name valuation lies outside its calendar" }

    $holidays = [Collections.Generic.HashSet[datetime]]::new()
    $holidayValues = Read-Range $inputs "H10:H$holidayEnd"
    if ($holidayCount -eq 1) { [void]$holidays.Add((Read-Date $holidayValues "$Name holiday")) }
    else {
        for ($i = 1; $i -le $holidayCount; $i++) {
            [void]$holidays.Add((Read-Date $holidayValues[$i, 1] "$Name inputs!H$($i + 9)"))
        }
    }
    $fixings = [Collections.Generic.Dictionary[datetime, double]]::new()
    $fixingValues = Read-Range $inputs "L10:M$fixingEnd"
    for ($i = 1; $i -le $fixingCount; $i++) {
        $date = Read-Date $fixingValues[$i, 1] "$Name inputs!L$($i + 9)"
        $price = $fixingValues[$i, 2]
        if ($price -isnot [double]) { throw "$Name inputs!M$($i + 9) is not a number" }
        if (-not $monthly -and $date -ge $asOf) { throw "$Name oracle received a nonhistorical daily fixing" }
        $fixings.Add($date, $price)
    }
    $firstContract = 1
    while ($expiries[$firstContract] -lt $asOf) { $firstContract++ }
    Assert-Equal (96 - $firstContract) 51 "$Name baseline live price count"
    $priceByCode = [Collections.Generic.Dictionary[string, double]]::new()
    $priceValues = Read-Range $inputs "Q10:R60"
    for ($i = 1; $i -le 51; $i++) {
        $code = [string]$priceValues[$i, 1]
        Assert-Equal $code $codes[$firstContract + $i - 1] "$Name live price order at row $($i + 9)"
        if ($priceValues[$i, 2] -isnot [double]) { throw "$Name inputs!R$($i + 9) is not a number" }
        $priceByCode.Add($code, ($priceValues[$i, 2]))
    }

    $view = Read-Range $dateSheet "B8:F$lastRow"
    $history = Read-Range $dateSheet "H8:L$lastRow"
    $headers = @("date", "prompt_contract", "is_business_day", "is_past", "price")
    $types = @("datetime64[D]", "str", "bool", "bool", "float64")
    for ($column = 1; $column -le 5; $column++) {
        Assert-Equal $view[1, $column] $headers[$column - 1] "$Name market header $column"
        $historyHeader = if ($column -eq 5) { "fixing_price" } else { $headers[$column - 1] }
        Assert-Equal $history[1, $column] $historyHeader "$Name history header $column"
        Assert-Equal $view[2, $column] $types[$column - 1] "$Name market type $column"
        Assert-Equal $history[2, $column] $types[$column - 1] "$Name history type $column"
    }
    $prices = [Collections.Generic.List[object]]::new()
    $dates = [Collections.Generic.List[datetime]]::new()
    $promptCodes = [Collections.Generic.List[string]]::new()
    $liveRows = [Collections.Generic.List[bool]]::new()
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
        $fixed = if ($monthly) { $expiries[$prompt] -lt $asOf } else { $past -and $business }
        $live = if ($monthly) { -not $fixed } else { -not $past -and $business }
        $row = $i + 3
        foreach ($table in @($view, $history)) {
            Assert-Number $table[$row, 1] $date.ToOADate() "$Name date at offset $i"
            Assert-Equal $table[$row, 2] $codes[$prompt] "$Name prompt on $date"
            foreach ($column in @(3, 4)) {
                if ($table[$row, $column] -isnot [bool]) { throw "$Name offset $i column $column is not boolean" }
            }
            Assert-Equal $table[$row, 3] $business "$Name business flag on $date"
            Assert-Equal $table[$row, 4] $past "$Name past flag on $date"
        }
        if ($fixed) {
            $key = if ($monthly) { $publications[$prompt] } else { $date }
            if (-not $fixings.ContainsKey($key)) { throw "$Name oracle has no fixing for $key" }
            $expected = $fixings[$key]
            Assert-Number $view[$row, 5] $expected "$Name fixed market price on $date"
            Assert-Number $history[$row, 5] $expected "$Name history price on $date"
            $fixedCount++
        }
        elseif ($live) {
            Assert-Number $view[$row, 5] $priceByCode[$codes[$prompt]] "$Name live price on $date"
            Assert-Equal $history[$row, 5] "unfixed" "$Name live history on $date"
            $liveCount++
        }
        else {
            Assert-Equal $view[$row, 5] "closed" "$Name closed market day $date"
            Assert-Equal $history[$row, 5] "closed" "$Name closed history day $date"
            $closedCount++
        }
        $dates.Add($date)
        $prices.Add(($view[$row, 5]))
        $promptCodes.Add($codes[$prompt])
        $liveRows.Add($live)
    }
    if ($WorksheetChecks) {
        $answers = Read-Range $dateSheet "T10:T$lastRow"
        for ($i = 1; $i -le $days; $i++) {
            Assert-Equal $answers[$i, 1] "PASS" "$Name dates!T$($i + 9)"
        }
    }
    foreach ($address in @("R10", "R60", "M10", "M$fixingEnd")) {
        $range = $inputs.Range($address)
        try {
            if ([string]$range.NumberFormat -notmatch '0\.000(?!0)') {
                throw "$Name inputs!$address must display prices to three decimal places"
            }
        }
        finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($range) }
    }
    return [pscustomobject]@{
        Dates = $dates.ToArray(); Prices = $prices.ToArray(); Codes = $promptCodes.ToArray()
        LiveRows = $liveRows.ToArray(); Prompt = $codes[$firstContract]; FirstContract = $firstContract
        Fixed = $fixedCount; Live = $liveCount; Closed = $closedCount; Days = $days
        FixingCount = $fixingCount; First = $first; Last = $last
    }
}

function Assert-HenryBaseline([string]$Name = "") {
    $names = if ($Name) { @($Name) } else { @("IFERC", "Gas Daily") }
    $results = [ordered]@{}
    foreach ($caseName in $names) {
        foreach ($tabName in @($caseName, "$caseName dates", "$caseName inputs")) {
            if (-not $tabs.Contains($tabName)) { throw "Workbook has no '$tabName' worksheet" }
        }
        Assert-Equal (Read-Date (Read-Range $tabs[$caseName] "C6") "$caseName valuation") ([datetime]"2026-09-18") "$caseName baseline valuation"
        Assert-Number (Read-Range $tabs[$caseName] "C7") 1 "$caseName baseline day fraction"
        $results[$caseName] = Assert-HenryView $caseName -WorksheetChecks
        Assert-Equal $results[$caseName].Prompt "V26" "$caseName baseline prompt"
        Assert-Equal $results[$caseName].Days 2891 "$caseName baseline rows"
        Assert-Equal $results[$caseName].First ([datetime]"2022-12-31") "$caseName first date"
        Assert-Equal $results[$caseName].Last ([datetime]"2030-11-29") "$caseName last date"
        if ($caseName -ceq "IFERC") {
            Assert-Equal $results[$caseName].Fixed 1340 "IFERC fixed rows"
            Assert-Equal $results[$caseName].Live 1551 "IFERC live rows"
            Assert-Equal $results[$caseName].Closed 0 "IFERC closed rows"
            Assert-Equal (Read-Date (Read-Range $tabs["IFERC inputs"] "D46") "F26 publication") ([datetime]"2026-01-05") "Actual January publication exception"
            foreach ($value in (Read-Range $tabs[$caseName] "G49:G52")) {
                Assert-Equal $value "Different date axis" "IFERC delivery/prompt comparison"
            }
        }
        else {
            Assert-Equal $results[$caseName].Fixed 926 "Gas Daily fixed rows"
            Assert-Equal $results[$caseName].Live 1051 "Gas Daily live rows"
            Assert-Equal $results[$caseName].Closed 914 "Gas Daily closed rows"
            foreach ($value in (Read-Range $tabs[$caseName] "G49:G56")) {
                Assert-Equal $value "GAP" "Gas Daily delivery gap remains visible"
            }
        }
    }
    if ($Name) { return $results[$Name] }
    return $results
}

function Assert-HenryChangedRows($Before, $After, [string[]]$Expected, [string]$Where) {
    $changed = [Collections.Generic.List[string]]::new()
    for ($i = 0; $i -lt $Before.Dates.Count; $i++) {
        if ($Before.Prices[$i] -cne $After.Prices[$i]) { $changed.Add($Before.Dates[$i].ToString("yyyy-MM-dd")) }
    }
    Assert-Equal ($changed -join ",") ($Expected -join ",") $Where
}

# A small, isolated January scenario exercises the actual Jan-2026 publication delay. It
# uses provisional values only in MonthlyFixings, never keeps the expired contract in the
# live vector, and checks immutable earlier handles after the published replacement.
function Invoke-HenryProvisionalChecks {
    $sheet = $tabs["IFERC"]
    $scratch = "AA10:AK110"
    foreach ($value in (Read-Range $sheet $scratch)) {
        if ($null -ne $value -and $value -ne "") { throw "IFERC!$scratch is not empty; scratch validation cannot overwrite it" }
    }
    try {
        $rows = @(
            @("Z25", "2025-11-28", "2025-12-01"),
            @("F26", "2025-12-31", "2026-01-05"),
            @("G26", "2026-01-30", "2026-02-02")
        )
        for ($i = 0; $i -lt 3; $i++) {
            $r = 10 + $i
            Write-Value $sheet "AA$r" ([string]$rows[$i][0])
            Write-Value $sheet "AB$r" ([datetime]$rows[$i][1]).ToOADate()
            Write-Value $sheet "AC$r" ([datetime]$rows[$i][2]).ToOADate()
        }
        Write-Value $sheet "AE10" ([datetime]"2026-01-01").ToOADate()
        Write-Value $sheet "AE11" ([datetime]"2026-01-02").ToOADate()
        Write-Value $sheet "AA14" ([datetime]"2025-12-01").ToOADate()
        Write-Value $sheet "AB14" 3.000
        Write-Value $sheet "AE14" 3.200
        Write-Value $sheet "AE15" 3.300
        Write-Value $sheet "AA16" ([datetime]"2025-12-31").ToOADate()
        $formulas = [ordered]@{
            AA18 = "=_CreateValuationDate(AA16,1)"
            AA19 = "=_CreateExpirySchedule(AA10:AA12,AB10:AB12,,AC10:AC12)"
            AA20 = "=_CreateHolidayCalendar(AE10:AE11)"
            AA21 = '=_CreateCalendar(AA18,"monthly",AA19,AA20)'
            AA22 = "=_CreateMonthlyFixings(AA14,AB14,AA19)"
            AA23 = "=_CreateMarketHistory(AA21,AA22)"
            AA24 = "=_CreatePriceVector(AE14:AE15)"
            AA25 = "=_CreateMarket(AA23,AA24)"
            AA28 = "=util_ReadHandle(AA25)"
            AG28 = "=util_ReadHandle(AA23)"
        }
        foreach ($address in $formulas.Keys) { Write-Formula $sheet $address $formulas[$address] }
        $excel.Calculate()
        $view = Read-Range $sheet "AA28:AE92"
        $history = Read-Range $sheet "AG28:AK92"
        for ($i = 0; $i -lt 63; $i++) {
            $date = ([datetime]"2025-11-29").AddDays($i)
            $price = if ($date -le [datetime]"2025-12-31") { 3.200 } else { 3.300 }
            Assert-Number $view[($i + 3), 5] $price "IFERC expiry-day live price on $date"
            Assert-Equal $history[($i + 3), 5] "unfixed" "IFERC expiry-day history on $date"
        }
        Write-Value $sheet "AA16" ([datetime]"2026-01-01").ToOADate()
        Write-Formula $sheet "AA24" "=_CreatePriceVector(AE15)"
        $excel.Calculate()
        Assert-HenryError "IFERC" "AA23" "no fixing for 'F26' published 2026-01-05"
        Write-Value $sheet "AA14" ([datetime]"2026-01-05").ToOADate()
        Write-Value $sheet "AB14" 3.123
        $excel.Calculate()
        $provisionalHandle = [string](Read-Range $sheet "AA23")
        $view = Read-Range $sheet "AA28:AE92"
        $history = Read-Range $sheet "AG28:AK92"
        for ($i = 0; $i -lt 63; $i++) {
            $date = ([datetime]"2025-11-29").AddDays($i)
            $expired = $date -le [datetime]"2025-12-31"
            $price = if ($expired) { 3.123 } else { 3.300 }
            Assert-Number $view[($i + 3), 5] $price "IFERC provisional price on $date"
            if ($expired) { Assert-Number $history[($i + 3), 5] 3.123 "IFERC provisional history on $date" }
            else { Assert-Equal $history[($i + 3), 5] "unfixed" "IFERC next-contract history on $date" }
        }
        Write-Value $sheet "AA16" ([datetime]"2026-01-05").ToOADate()
        Write-Value $sheet "AB14" 3.157
        $excel.Calculate()
        $publishedHandle = [string](Read-Range $sheet "AA23")
        if ($publishedHandle -eq $provisionalHandle) { throw "Published monthly value reused the provisional history handle" }
        $view = Read-Range $sheet "AA28:AE92"
        for ($i = 0; $i -lt 33; $i++) {
            Assert-Number $view[($i + 3), 5] 3.157 "IFERC published replacement row $i"
        }
        Write-Formula $sheet "AG28" ('=util_ReadHandle("' + $provisionalHandle + '")')
        $excel.Calculate()
        $oldHistory = Read-Range $sheet "AG28:AK92"
        for ($i = 0; $i -lt 33; $i++) {
            Assert-Number $oldHistory[($i + 3), 5] 3.123 "Earlier IFERC provisional history remains immutable at row $i"
        }
        Write-Value $sheet "AA104" "date"
        Write-Value $sheet "AB104" "settle"
        Write-Value $sheet "AA105" ([datetime]"2026-09-19").ToOADate()
        Write-Value $sheet "AB105" 2.750
        Write-Formula $sheet "AA107" "=_CreateDailyFixings(AA104:AB104,AA105:AB105,AA20)"
        $excel.Calculate()
        Assert-HenryError "IFERC" "AA107" "a Saturday, expected a business day"
    }
    finally { Clear-Range $sheet $scratch; $excel.Calculate() }
    Write-Host "IFERC January roll: expiry-day live, missing-value refusal, provisional Jan-5 key on Jan-1, published replacement and immutable prior history pass."
    Write-Host "Gas Daily limitation: a Saturday delivery-date fixing is visibly rejected by the daily creator."
}

function Invoke-HenryBenchmarkChecks {
    $baseline = Assert-HenryBaseline
    foreach ($name in @("IFERC", "Gas Daily")) {
        $main = $tabs[$name]
        $inputs = $tabs["$name inputs"]
        $monthly = $name -ceq "IFERC"
        $saved = @{
            Price = [double](Read-Range $inputs "R10")
            Fixing = [double](Read-Range $inputs "M10")
            C16 = Read-HenryFormula $main "C16"
            C18 = Read-HenryFormula $main "C18"
        }
        if ($monthly) { $saved.Publication = Read-Range $inputs "D10" }
        try {
            $before = $baseline[$name]
            $handles = Read-HenryHandles $name
            Write-Value $inputs "R10" ($saved.Price + 0.100)
            $excel.Calculate()
            Assert-HenryHandles $name $handles @("C18", "C19")
            $bumped = Assert-HenryView $name
            $expected = [Collections.Generic.List[string]]::new()
            for ($i = 0; $i -lt $before.Dates.Count; $i++) {
                if ($before.LiveRows[$i] -and $before.Codes[$i] -ceq $before.Prompt) {
                    $expected.Add($before.Dates[$i].ToString("yyyy-MM-dd"))
                }
            }
            Assert-HenryChangedRows $before $bumped $expected.ToArray() "$name price bump dates"
            Write-Value $inputs "R10" $saved.Price
            $excel.Calculate()

            $handles = Read-HenryHandles $name
            Write-Value $inputs "M10" ($saved.Fixing + 0.025)
            $excel.Calculate()
            Assert-HenryHandles $name $handles @("C16", "C17", "C19")
            $bumped = Assert-HenryView $name
            $expected = [Collections.Generic.List[string]]::new()
            $firstFixingDate = Read-Date (Read-Range $inputs "L10") "$name first fixing"
            $firstFixingCode = if ($monthly) { [string](Read-Range $inputs "N10") } else { "" }
            for ($i = 0; $i -lt $before.Dates.Count; $i++) {
                if (($monthly -and $before.Codes[$i] -ceq $firstFixingCode) -or
                    (-not $monthly -and $before.Dates[$i] -eq $firstFixingDate)) {
                    $expected.Add($before.Dates[$i].ToString("yyyy-MM-dd"))
                }
            }
            Assert-HenryChangedRows $before $bumped $expected.ToArray() "$name fixing bump dates"
            Write-Value $inputs "M10" $saved.Fixing
            $excel.Calculate()

            Clear-Range $inputs "R10"
            $excel.Calculate()
            Assert-HenryError $name "C18" "is blank"
            Assert-HenryError $name "C19" "creator's failure"
            Write-Value $inputs "R10" $saved.Price
            Write-Formula $main "C18" "=_CreatePriceVector('$name inputs'!R11:R60)"
            $excel.Calculate()
            Assert-HenryError $name "C19" "expected 51"
            Write-Formula $main "C18" $saved.C18

            $end = $before.FixingCount + 9
            if ($monthly) {
                Write-Formula $main "C16" "=_CreateMonthlyFixings('$name inputs'!L11:L$end,'$name inputs'!M11:M$end,C13)"
                $excel.Calculate()
                Assert-HenryError $name "C17" "no fixing for"
                $liveRow = $before.FirstContract + 10
                Write-Formula $main "C16" "=_CreateMonthlyFixings('$name inputs'!D$liveRow,'$name inputs'!R10,C13)"
                $excel.Calculate()
                Assert-HenryError $name "C17" "not expired on 2026-09-18"
                Write-Formula $main "C16" "='Gas Daily'!C16"
                $excel.Calculate()
                Assert-HenryError $name "C17" "expected monthly fixings for a monthly calendar"
                Write-Formula $main "C16" $saved.C16
                Write-Value $inputs "D10" (Read-Range $inputs "D11")
                $excel.Calculate()
                Assert-HenryError $name "C17" "calendar publication date row 2"
                Write-Value $inputs "D10" $saved.Publication
            }
            else {
                Write-Formula $main "C16" "=_CreateDailyFixings('$name inputs'!L9:M9,'$name inputs'!L11:M$end,C14)"
                $excel.Calculate()
                Assert-HenryError $name "C17" "no fixing for"
                Write-Formula $main "C16" "=IFERC!C16"
                $excel.Calculate()
                Assert-HenryError $name "C17" "expected daily fixings for a daily calendar"
            }
        }
        finally {
            Write-Value $inputs "R10" $saved.Price
            Write-Value $inputs "M10" $saved.Fixing
            if ($monthly) { Write-Value $inputs "D10" $saved.Publication }
            Write-Formula $main "C16" $saved.C16
            Write-Formula $main "C18" $saved.C18
            $excel.Calculate()
        }
        $restored = Assert-HenryBaseline $name
        Assert-HenryChangedRows $baseline[$name] $restored @() "$name restored baseline"
        Write-Host "$name`: all $($restored.Days) market/history rows, worksheet oracle, price/fixing edits and failure cases pass; baseline restored."
    }
    Invoke-HenryProvisionalChecks
    [void](Assert-HenryBaseline)
}
