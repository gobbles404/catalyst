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
$xll = Build-HostAddIn -Root $root
$path = (Resolve-Path $Workbook).Path

try {
    $excel = New-Object -ComObject Excel.Application
}
catch {
    Write-Host "Excel is not installed here."
    exit 2
}
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {
    if (-not $excel.RegisterXLL($xll)) { throw "Excel refused to load $xll" }
    $book = $excel.Workbooks.Open($path, 0, $true)
    $excel.CalculateFullRebuild()
    foreach ($sheet in $book.Worksheets) {
        Write-Host "--- $($sheet.Name)"
        foreach ($cell in $sheet.UsedRange.Cells) {
            if ($cell.Formula -eq "") { continue }
            $formula = if ($cell.HasFormula) { $cell.Formula } else { "" }
            Write-Host ("{0,-5} {1,-52} {2}" -f $cell.Address($false, $false), $formula, $cell.Text)
        }
    }
    foreach ($name in $book.Names) {
        # Excel keeps names of its own, such as _xlfn.SINGLE, for functions newer than the file format.
        if ($name.Name -like "_xlfn.*") { continue }
        Write-Host ("name  {0} refers to {1}" -f $name.Name, $name.RefersTo)
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
