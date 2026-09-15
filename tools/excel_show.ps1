# Prints a workbook the way its cells show, with the add-in loaded, in a hidden Excel of its own:
# one line per used cell with its address, its formula if it has one, and the text it displays,
# then the workbook's defined names. Two people reading the same workbook this way read the same
# thing, and a discussion can quote it. The workbook is opened read-only and fully recalculated
# first, so every handle in it belongs to this session, not to the one that saved it.
#
#     .\tools\excel_show.ps1 workbooks\handles.xlsx
param([Parameter(Mandatory = $true)][string]$Workbook)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "host_build.ps1")
. (Join-Path $PSScriptRoot "hidden_excel.ps1")
$xll = Build-HostAddIn -Root $root
$path = (Resolve-Path $Workbook).Path

try {
    $session = Start-HiddenExcel
}
catch {
    Write-Host "Could not start hidden Excel: $_"
    exit 2
}
$excel = $session.Excel
$owned = [Collections.Generic.List[object]]::new()
function Own($object) { $owned.Add($object); Write-Output -NoEnumerate $object }
$loaded = $false
$scriptError = $null
$book = $null
try {
    if (-not $excel.RegisterXLL($xll)) { throw "Excel refused to load $xll" }
    $loaded = $true
    $books = Own $excel.Workbooks
    $book = Own $books.Open($path, 0, $true)
    $excel.CalculateFullRebuild()
    $sheets = Own $book.Worksheets
    for ($sheetIndex = 1; $sheetIndex -le $sheets.Count; $sheetIndex++) {
        $sheet = Own $sheets.Item($sheetIndex)
        Write-Host "--- $($sheet.Name)"
        $used = Own $sheet.UsedRange
        $sheetCells = Own $used.Cells
        for ($cellIndex = 1; $cellIndex -le $sheetCells.Count; $cellIndex++) {
            $cell = $sheetCells.Item($cellIndex)
            try {
                if ($cell.Formula -eq "") { continue }
                $formula = if ($cell.HasFormula) { $cell.Formula } else { "" }
                Write-Host ("{0,-5} {1,-52} {2}" -f $cell.Address($false, $false), $formula, $cell.Text)
            }
            finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($cell) }
        }
    }
    $names = Own $book.Names
    for ($nameIndex = 1; $nameIndex -le $names.Count; $nameIndex++) {
        $name = Own $names.Item($nameIndex)
        # Excel keeps names of its own, such as _xlfn.SINGLE, for functions newer than the file format.
        if ($name.Name -like "_xlfn.*") { continue }
        Write-Host ("name  {0} refers to {1}" -f $name.Name, $name.RefersTo)
    }
}
catch { $scriptError = $_; throw }
finally {
    Stop-HiddenExcel $session $owned $book -AddInLoaded:$loaded -FailureInFlight:($null -ne $scriptError)
}
