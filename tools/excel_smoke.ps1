# Runs the built add-in in a hidden Excel and checks what each formula shows.
# One row per formula: the exact text its cell must display. Add a row to add a check.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

$formulas = [ordered]@{
    "=GoosedoveStatus()" = "ok: python started and functions registered"
    "=Add(1,2)"          = "3"
    "=Add(1,)"           = "#ERROR Add: b is missing, expected number"
    "=Add(1,TRUE)"       = "#ERROR Add: b is boolean TRUE, expected number"
    "=SumColumn(A1:A3)"  = "6"
    "=SumColumn(A1)"     = "1"
    "=SumColumn(B1:B3)"  = "#ERROR SumColumn: values cell (1, 1) is text 'n/a', expected number"
    "=SumColumn(C1:C3)"  = "#ERROR SumColumn: values cell (2, 1) is blank, expected number"
    "=SumColumn(D1:D3)"  = "#N/A"
    "=SumColumn(F1:F2)"  = "#N/A"
    "=SumColumn(H1:H2)"  = "#ERROR SumColumn: values cell (2, 1) is boolean TRUE, expected number"
    "=SumRow(A1:A3)"     = "#ERROR SumRow: values is 3x1 array, expected row of numbers"
    "=JoinColumn(E1:E2)" = "x, y"
    "=JoinColumn(I1:I2)" = "#ERROR JoinColumn: names cell (2, 1) is empty text, expected text"
    "=DateText(G1)"      = "2026-05-22"
    "=RegisterAll()"     = "#NAME?"
}

# What the cells hold before the formulas run, typed the way a person would type them.
$cells = [ordered]@{
    "A1" = "1"; "A2" = "2"; "A3" = "3"
    "B1" = "n/a"; "B2" = "2"; "B3" = "3"
    "C1" = "1"; "C3" = "3"
    "D1" = "1"; "D2" = "=NA()"; "D3" = "3"
    "E1" = "x"; "E2" = "y"
    "F1" = "x"; "F2" = "=NA()"
    "G1" = "46164"
    "H1" = "1"; "H2" = "TRUE"
    "I1" = "x"; "I2" = '=""'
}

# --- build the host and tell it where Python is -----------------------------

. (Join-Path $PSScriptRoot "host_build.ps1")
$xll = Build-HostAddIn -Root $root

# --- a hidden Excel of our own; nothing the user has open is touched --------

try {
    $excel = New-Object -ComObject Excel.Application
}
catch {
    Write-Host "Excel is not installed here, so the host is unchecked. Install Excel or run this elsewhere."
    exit 2
}
$excel.Visible = $false
$excel.DisplayAlerts = $false
$failures = 0
try {
    if (-not $excel.RegisterXLL($xll)) { throw "Excel refused to load $xll" }
    $book = $excel.Workbooks.Add()
    $sheet = $book.Worksheets.Item(1)
    # Formula takes text for everything and lets Excel parse it, as typing into the cell would.
    foreach ($address in $cells.Keys) {
        $sheet.Range($address).Formula = $cells[$address]
    }
    $row = 1
    foreach ($formula in $formulas.Keys) {
        $cell = $sheet.Range("K$row")
        $cell.Formula = $formula
        $shown = $cell.Text
        $ok = ($shown -eq $formulas[$formula])
        if (-not $ok) { $failures++ }
        Write-Host ("{0} {1,-22} {2}" -f $(if ($ok) { "ok  " } else { "FAIL" }), $formula, $shown)
        if (-not $ok) { Write-Host ("     expected              {0}" -f $formulas[$formula]) }
        $row++
    }
    $book.Close($false)
}
finally {
    # Quit is not enough: Excel stays alive while any COM object of it is still referenced.
    $excel.Quit()
    foreach ($object in @($cell, $sheet, $book, $excel)) {
        if ($object) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($object) }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
Write-Host "excel smoke: $($formulas.Count) formulas, $failures failed"
exit $failures
