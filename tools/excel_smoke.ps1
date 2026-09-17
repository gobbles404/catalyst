# Runs the built add-in in a hidden Excel and checks what each formula shows.
# One row per formula: the exact text its cell must display. Add a row to add a check.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

$formulas = [ordered]@{
    "=GoosedoveStatus()"          = "ok: python started and functions registered"
    "=HostAdd(1,2)"               = "3"
    "=Zero()"                     = "0"
    "=Add(1,2)"                   = "3"
    "=Add(1,)"                    = "#ERROR Add: b is missing, expected number"
    "=Add(1,TRUE)"                = "#ERROR Add: b is boolean TRUE, expected number"
    "=Times(5)"                   = "5"
    "=Times(5,2)"                 = "10"
    "=Times(5,C2)"                = "#ERROR Times: factor is blank, expected number"
    "=EchoText(E1)"               = "x"
    "=EchoText(I2)"               = "#ERROR EchoText: label is empty text, expected text"
    "=EchoBoolean(TRUE)"          = "TRUE"
    "=EchoBoolean(1)"             = "#ERROR EchoBoolean: flag is number 1.0, expected boolean"
    "=SumArray(A1:A3)"            = "6"
    "=SumArray(A1)"               = "1"
    "=SumArray(B1:B3)"            = "#ERROR SumArray: values cell (1, 1) is text 'n/a', expected number"
    "=SumArray(C1:C3)"            = "#ERROR SumArray: values cell (2, 1) is blank, expected number"
    "=SumArray(D1:D3)"            = "#N/A"
    "=SumArray(F1:F2)"            = "#N/A"
    "=SumArray(H1:H2)"            = "#ERROR SumArray: values cell (2, 1) is boolean TRUE, expected number"
    "=CountArray(A1:A3)"          = "3"
    "=CountArray(B1:B3)"          = "#ERROR CountArray: values cell (1, 1) is text 'n/a', expected number"
    "=CountMixed(J1:J4)"          = "4"
    "=CountMixed(A1:A3)"          = "3"
    "=CountMixed(E1:E2)"          = "2"
    "=CountMixed(A1)"             = "1"
    "=CountMixed(H1:H2)"          = "2"
    "=CountMixed(C1:C3)"          = "#ERROR CountMixed: values cell (2, 1) is blank, expected number, nonempty text or boolean"
    "=CountMixed(I1:I2)"          = "#ERROR CountMixed: values cell (2, 1) is empty text, expected number, nonempty text or boolean"
    "=CountMixed(D1:D3)"          = "#N/A"
    "=SumQuantity(L1:O1,L2:O4)"   = "20.5"
    "=SumQuantity(P1:S1,L2:O4)"   = "20.5"
    "=SumQuantity(T1:W1,L2:O4)"   = "#ERROR SumQuantity: header_row cell (1, 2) is text 'ticker', expected one of date, product, quantity or cleared"
    "=SumQuantity(L1:O1,L2:N4)"   = "#ERROR SumQuantity: header_row has 4 headers, expected 3, one per column of trades"
    "=SumQuantity(L1:O1,L6:O8)"   = "#ERROR SumQuantity: trades cell (2, 3) is text 'seven', expected number"
    "=Dot(A1:A3,{10;20;30})"      = "140"
    "=Dot(A1:A3,{10,20,30})"      = "#ERROR Dot: b is 1x3 array, expected column of numbers"
    "=ROWS(EchoColumn(A1:A3))"    = "3"
    "=COLUMNS(EchoRow({1,2,3}))"  = "3"
    "=SUM(EchoColumn(A1:A3))"     = "6"
    "=ROWS(RowSums({1,2;3,4;5,6}))" = "3"
    "=INDEX(RowSums({1,2;3,4;5,6}),2,1)" = "7"
    "=INDEX(Grid(2,3),2,1)"       = "4"
    # The mixed road out: a trade's own row, text, a date, a number and a flag, echoed back one
    # tagged value per cell, and a row of headers echoed across.
    "=INDEX(EchoMixed(J1:J4),1,1)" = "CL"
    "=INDEX(EchoMixed(J1:J4),2,1)" = "46164"
    "=INDEX(EchoMixed(J1:J4),3,1)" = "10"
    "=INDEX(EchoMixed(J1:J4),4,1)" = "TRUE"
    "=COLUMNS(EchoMixed(L1:O1))"  = "4"
    "=Grid(2.5,3)"                = "#ERROR Grid: rows is number 2.5, expected whole number"
    "=Fail()"                     = "#ERROR Fail: ValueError: as asked"
    "=RegisterAll()"              = "#NAME?"
    # Handles. A creator cell shows its handle, whose session part changes every start, so LEFT
    # pins the kind; the reader rows refer to creator cells the way a sheet does, and read the
    # spill one cell at a time with INDEX.
    "=LEFT(AA1,15)"               = "discount_curve:"
    "=LEFT(AA2,15)"               = "valuation_date:"
    "=INDEX(ReadHandle(AA1),1,1)" = "date"
    "=INDEX(ReadHandle(AA1),2,2)" = "float64"
    "=INDEX(ReadHandle(AA1),3,1)" = "46276"
    "=INDEX(ReadHandle(AA1),4,2)" = "0.9999"
    "=ROWS(ReadHandle(AA1))"      = "5"
    "=INDEX(ReadHandle(AA2),3,2)" = "0.5"
    "=INDEX(ReadHandle(AI1),3,1)" = "m26"
    "=INDEX(ReadHandle(AI1),8,3)" = "46310"
    "=COLUMNS(ReadHandle(AI2))"   = "2"
    "=ReadHandle(Y2)"             = "#ERROR ReadHandle: handle is number 46276.0, expected a handle"
    "=ReadHandle(AA3)"            = "#ERROR ReadHandle: handle is the creator's failure, expected a handle: #ERROR CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    "=ReadHandle(AA4)"            = "#ERROR ReadHandle: handle is the creator's failure, expected a handle: #ERROR CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    '=ReadHandle("discount_curve:000000:000001")' = "#ERROR ReadHandle: handle is text 'discount_curve:000000:000001' naming no live object, expected a handle"
    "=CreateValuationDate(Y2,1.5)" = "#ERROR CreateValuationDate: ValueError: day_fraction_elapsed is number 1.5, expected a number from 0 to 1"
    "=CreateDiscountCurve(Y1:Z1,AB2:AC4)" = "#ERROR CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    "=CreateDiscountCurve(Y1:Z1,Y1:Z3)" = "#ERROR CreateDiscountCurve: table cell (1, 1) is text 'date', expected date"
    # The curve from anchors: three anchors over eleven days, read back day by day through
    # ReadHandle, an anchor exact and a day between on the straight line; dates that run
    # backwards; and a span no sheet could show.
    "=ROWS(ReadHandle(AW1))"      = "13"
    "=INDEX(ReadHandle(AW1),5,2)" = "0.9998"
    "=INDEX(ReadHandle(AW1),6,2)" = "0.9997"
    "=INDEX(ReadHandle(AW1),13,1)" = "46286"
    "=CreateDiscountCurve(Y1:Z1,AX2:AY3)" = "#ERROR CreateDiscountCurve: ValueError: date row 2 is 2026-09-11, expected a date after row 1's 2026-09-14"
    "=CreateDiscountCurve(Y1:Z1,BA2:BB3)" = "#ERROR CreateDiscountCurve: ValueError: date row 2 is 4897-08-04, expected within 1048573 days of row 1's 2026-09-11"
    # The expiry schedule: a creator with three columns and one with two, a futures column one
    # row short, and a blank in the options column.
    "=LEFT(AI1,16)"               = "expiry_schedule:"
    "=LEFT(AI2,16)"               = "expiry_schedule:"
    "=CreateExpirySchedule(AE2:AE7,AF2:AF6,AG2:AG7)" = "#ERROR CreateExpirySchedule: ValueError: future_expiry has 5 dates, expected 6, one per future_code"
    "=CreateExpirySchedule(AE2:AE7,AF2:AF7,AH2:AH7)" = "#ERROR CreateExpirySchedule: option_expiry cell (3, 1) is blank, expected date"
    # The holiday calendar: a creator over three days and one over a single cell, the first read
    # back through ReadHandle, a blank in the column, and a row where a column is expected.
    "=LEFT(AM1,17)"               = "holiday_calendar:"
    "=LEFT(AM2,17)"               = "holiday_calendar:"
    "=INDEX(ReadHandle(AM1),1,1)" = "holiday"
    "=INDEX(ReadHandle(AM1),2,1)" = "datetime64[D]"
    "=INDEX(ReadHandle(AM1),4,1)" = "46041"
    "=ROWS(ReadHandle(AM2))"      = "3"
    "=CreateHolidayCalendar(AL2:AL4)" = "#ERROR CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date"
    "=CreateHolidayCalendar(AK2:AL2)" = "#ERROR CreateHolidayCalendar: holiday is 1x2 array, expected column of dates"
    # The market conventions: a creator over five text cells, read back through ReadHandle, a
    # blank and a number where a code is expected, and a code left out.
    "=LEFT(AP1,19)"               = "market_conventions:"
    "=INDEX(ReadHandle(AP1),1,4)" = "quantity_type"
    "=INDEX(ReadHandle(AP1),3,4)" = "VOLUME"
    "=COLUMNS(ReadHandle(AP1))"   = "5"
    "=CreateMarketConventions(AO2,AO3,AO4,AO5,C2)" = "#ERROR CreateMarketConventions: quantity_unit is blank, expected text"
    "=CreateMarketConventions(AO2,AO3,A1,AO5,AO6)" = "#ERROR CreateMarketConventions: currency_unit is number 1.0, expected text"
    "=CreateMarketConventions(AO2,AO3,AO4,AO5)" = "#ERROR CreateMarketConventions: quantity_unit is missing, expected text"
    # The contract spec: a creator over a name and three numbers, read back through ReadHandle, a
    # lot size with a fraction and one beyond what a cell holds exactly, text where a fee is
    # expected, and a fee left out.
    "=LEFT(AS1,14)"               = "contract_spec:"
    "=INDEX(ReadHandle(AS1),1,3)" = "brokerage_rate_per_lot"
    "=INDEX(ReadHandle(AS1),2,2)" = "int"
    "=INDEX(ReadHandle(AS1),3,2)" = "1000"
    "=COLUMNS(ReadHandle(AS1))"   = "4"
    "=CreateContractSpec(AR2,2.5,AR4,AR5)" = "#ERROR CreateContractSpec: lot_size is number 2.5, expected whole number"
    "=CreateContractSpec(AR2,1E16,AR4,AR5)" = "#ERROR CreateContractSpec: lot_size is number 1e+16, beyond what a cell holds exactly"
    "=CreateContractSpec(AR2,AR3,E1,AR5)" = "#ERROR CreateContractSpec: brokerage_rate_per_lot is text 'x', expected number"
    "=CreateContractSpec(AR2,AR3,AR4)" = "#ERROR CreateContractSpec: clearing_rate_per_lot is missing, expected number"
}

# What the cells hold before the formulas run, typed the way a person would type them.
$cells = [ordered]@{
    "A1" = "1"; "A2" = "2"; "A3" = "3"
    "B1" = "n/a"; "B2" = "2"; "B3" = "3"
    "C1" = "1"; "C3" = "3"
    "D1" = "1"; "D2" = "=NA()"; "D3" = "3"
    "E1" = "x"; "E2" = "y"
    "F1" = "x"; "F2" = "=NA()"
    "H1" = "1"; "H2" = "TRUE"
    "I1" = "x"; "I2" = '=""'
    # A trade's own row: a product, an expiry shown as a date, a quantity, a flag.
    "J1" = "CL"; "J2" = "22-May-2026"; "J3" = "10"; "J4" = "TRUE"
    # A table: its header row and three trades; the same headers in capitals; one header
    # unknown; and a second body with text where a quantity should be.
    "L1" = "date"; "M1" = "product"; "N1" = "quantity"; "O1" = "cleared"
    "L2" = "11-Sep-2026"; "M2" = "CL"; "N2" = "10"; "O2" = "TRUE"
    "L3" = "12-Sep-2026"; "M3" = "NG"; "N3" = "3.5"; "O3" = "FALSE"
    "L4" = "15-Sep-2026"; "M4" = "CL"; "N4" = "7"; "O4" = "TRUE"
    "P1" = "DATE"; "Q1" = "PRODUCT"; "R1" = "QUANTITY"; "S1" = "CLEARED"
    "T1" = "date"; "U1" = "ticker"; "V1" = "quantity"; "W1" = "cleared"
    "L6" = "11-Sep-2026"; "M6" = "CL"; "N6" = "10"; "O6" = "TRUE"
    "L7" = "12-Sep-2026"; "M7" = "NG"; "N7" = "seven"; "O7" = "FALSE"
    "L8" = "15-Sep-2026"; "M8" = "CL"; "N8" = "7"; "O8" = "TRUE"
    # A curve's table: its header row and three days; a second body whose first factor is not 1;
    # then three creator cells, a curve, a valuation date and a curve that fails, so the reader
    # rows above can refer to a creator cell the way a sheet does, and a reader of the failed
    # curve, so a row can relay a relay.
    "Y1" = "date"; "Z1" = "discount_factor"
    "Y2" = "11-Sep-2026"; "Z2" = "1"
    "Y3" = "12-Sep-2026"; "Z3" = "0.9999"
    "Y4" = "13-Sep-2026"; "Z4" = "0.9998"
    "AB2" = "11-Sep-2026"; "AC2" = "0.98"
    "AB3" = "12-Sep-2026"; "AC3" = "0.9"
    "AB4" = "13-Sep-2026"; "AC4" = "0.8"
    "AA1" = "=CreateDiscountCurve(Y1:Z1,Y2:Z4)"
    "AA2" = "=CreateValuationDate(Y2,0.5)"
    "AA3" = "=CreateDiscountCurve(Y1:Z1,AB2:AC4)"
    "AA4" = "=ReadHandle(AA3)"
    # An expiry schedule: six contract codes as the desk types them, the futures and options
    # expiry beside each, a copy of the options column with a blank, and two creator cells, one
    # with the options column and one without.
    "AE2" = "m26"; "AF2" = "19-May-2026"; "AG2" = "14-May-2026"; "AH2" = "14-May-2026"
    "AE3" = "n26"; "AF3" = "22-Jun-2026"; "AG3" = "16-Jun-2026"; "AH3" = "16-Jun-2026"
    "AE4" = "q26"; "AF4" = "21-Jul-2026"; "AG4" = "16-Jul-2026"
    "AE5" = "u26"; "AF5" = "20-Aug-2026"; "AG5" = "17-Aug-2026"; "AH5" = "17-Aug-2026"
    "AE6" = "V26"; "AF6" = "22-Sep-2026"; "AG6" = "17-Sep-2026"; "AH6" = "17-Sep-2026"
    "AE7" = "X26"; "AF7" = "20-Oct-2026"; "AG7" = "15-Oct-2026"; "AH7" = "15-Oct-2026"
    "AI1" = "=CreateExpirySchedule(AE2:AE7,AF2:AF7,AG2:AG7)"
    "AI2" = "=CreateExpirySchedule(AE2:AE7,AF2:AF7)"
    # A holiday calendar: three days one market is closed, a copy of the column with a blank, and
    # two creator cells, one over the column and one over a single cell.
    "AK2" = "1-Jan-2026"; "AL2" = "1-Jan-2026"
    "AK3" = "19-Jan-2026"
    "AK4" = "16-Feb-2026"; "AL4" = "16-Feb-2026"
    "AM1" = "=CreateHolidayCalendar(AK2:AK4)"
    "AM2" = "=CreateHolidayCalendar(AK2)"
    # The market conventions: five codes as the desk types them, and one creator cell.
    "AO2" = "USD"; "AO3" = "BBL"; "AO4" = "USD"; "AO5" = "VOLUME"; "AO6" = "BBL"
    "AP1" = "=CreateMarketConventions(AO2,AO3,AO4,AO5,AO6)"
    # The contract spec: a name, a lot size and two fees as the desk types them, and one creator cell.
    "AR2" = "WTI"; "AR3" = "1000"; "AR4" = "3"; "AR5" = "2"
    "AS1" = "=CreateContractSpec(AR2,AR3,AR4,AR5)"
    # A curve's anchors: three dates over eleven days and their factors, a pair whose dates run
    # backwards, and the creator cell over the anchors, under the curve's headers at Y1:Z1.
    "AU2" = "11-Sep-2026"; "AV2" = "1"
    "AU3" = "14-Sep-2026"; "AV3" = "0.9997"
    "AU4" = "21-Sep-2026"; "AV4" = "0.999"
    "AX2" = "14-Sep-2026"; "AY2" = "1"
    "AX3" = "11-Sep-2026"; "AY3" = "0.9997"
    "AW1" = "=CreateDiscountCurve(Y1:Z1,AU2:AV4)"
    # Two anchors 1,048,574 days apart, typed as serials: one day more than a sheet can show.
    "BA2" = "46276"; "BB2" = "1"
    "BA3" = "1094850"; "BB3" = "0.5"
}

# --- build the host and tell it where Python is -----------------------------

. (Join-Path $PSScriptRoot "host_build.ps1")
. (Join-Path $PSScriptRoot "hidden_excel.ps1")
$xll = Build-HostAddIn -Root $root

# --- a hidden Excel of our own; nothing the user has open is touched --------

try {
    $session = Start-HiddenExcel
}
catch {
    Write-Host "Could not start hidden Excel, so the host is unchecked: $_"
    exit 2
}
$excel = $session.Excel
$owned = [Collections.Generic.List[object]]::new()
function Own($object) { $owned.Add($object); Write-Output -NoEnumerate $object }
$loaded = $false
$scriptError = $null
$book = $null
$failures = 0
try {
    if (-not $excel.RegisterXLL($xll)) { throw "Excel refused to load $xll" }
    $loaded = $true
    $books = Own $excel.Workbooks
    $book = Own $books.Add()
    $sheets = Own $book.Worksheets
    $sheet = Own $sheets.Item(1)
    # Formula takes text for everything and lets Excel parse it, as typing into the cell would.
    foreach ($address in $cells.Keys) {
        (Own $sheet.Range($address)).Formula = $cells[$address]
    }
    $row = 1
    foreach ($formula in $formulas.Keys) {
        $cell = Own $sheet.Range("K$row")
        $cell.Formula = $formula
        $shown = $cell.Text
        $ok = ($shown -eq $formulas[$formula])
        if (-not $ok) { $failures++ }
        Write-Host ("{0} {1,-28} {2}" -f $(if ($ok) { "ok  " } else { "FAIL" }), $formula, $shown)
        if (-not $ok) { Write-Host ("     expected                    {0}" -f $formulas[$formula]) }
        $row++
    }
}
catch { $scriptError = $_; throw }
finally {
    Stop-HiddenExcel $session $owned $book -AddInLoaded:$loaded -FailureInFlight:($null -ne $scriptError)
}
Write-Host "excel smoke: $($formulas.Count) formulas, $failures failed"
exit $failures
