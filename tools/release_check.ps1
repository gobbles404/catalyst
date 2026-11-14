# Reads a folder a release was assembled into and says whether it is what an end user should be
# handed: the add-in, its config beside it, the library that config would load inside the folder,
# and no probe. It reads; it writes, moves and deletes nothing, and it starts neither Excel nor
# Python. Run it on the folder a release script made:
#   .\tools\release_check.ps1 -Folder C:\path\to\the\release
# It judges the folder as shipped, so what the config names is followed the way the host follows
# it: the host reads catalyst.cfg beside the .xll and nowhere else, and Python takes the first
# catalyst package on that config's path, in order. That package must be the folder's own. Python
# itself and the installed libraries, numpy among them, may be anywhere.
# Each line is ok, note, FAULT or next. A fault is a reason not to ship the folder; a note is
# something to look at that this script cannot judge; next is the check only Excel can make. It
# exits with the number of faults, 0 for a folder that passes. The probes are test support,
# test_support in the repository, and no part of what an end user loads.
param([Parameter(Mandatory = $true)][string]$Folder)
$ErrorActionPreference = "Stop"

$top = (Resolve-Path -LiteralPath $Folder).Path.TrimEnd("\")
$files = @(Get-ChildItem -LiteralPath $top -Recurse -File -Force)
$folders = @(Get-ChildItem -LiteralPath $top -Recurse -Directory -Force)
$faults = 0
function Say([string]$kind, [string]$text) {
    if ($kind -eq "FAULT") { $script:faults++ }
    Write-Host ("  {0,-5} {1}" -f $kind, $text)
}
function Inside([string]$path) { $path.Substring($top.Length).TrimStart("\") }
function Shipped([string]$path) {
    $full = [IO.Path]::GetFullPath($path).TrimEnd("\")
    return $full.Equals($top, [StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith("$top\", [StringComparison]::OrdinalIgnoreCase)
}

Write-Host "release check: $top"
$byKind = $files | Group-Object { if ($_.Extension) { $_.Extension.ToLower() } else { "(none)" } } | Sort-Object Count -Descending
Write-Host ("  {0} files: {1}" -f $files.Count, (($byKind | ForEach-Object { "$($_.Count) $($_.Name)" }) -join ", "))

# --- the add-in, its config beside it, and the library that config loads ----

$addIns = @($files | Where-Object { $_.Extension -eq ".xll" })
if ($addIns.Count -eq 0) { Say "FAULT" "no .xll in the folder: there is no add-in for Excel to load" }
$read = [Collections.Generic.List[string]]::new()   # the configs a host would read
foreach ($addIn in $addIns) {
    $name = Inside $addIn.FullName
    Say "ok" "the add-in: $name"
    foreach ($beside in "Catalyst.Host.dll", "Python.Runtime.dll", "ExcelDna.IntelliSense.dll") {
        if (Test-Path -LiteralPath (Join-Path $addIn.DirectoryName $beside)) { Say "ok" "beside it: $beside" }
        else { Say "note" "$beside is not beside $($addIn.Name); that is right only if the .xll has it packed inside" }
    }
    # A host built before HostAdd left it still holds the method; the name is in its metadata.
    $hostPath = Join-Path $addIn.DirectoryName "Catalyst.Host.dll"
    if (Test-Path -LiteralPath $hostPath) {
        $bytes = [Text.Encoding]::GetEncoding(28591).GetString([IO.File]::ReadAllBytes($hostPath))
        if ($bytes.Contains("HostAdd")) { Say "FAULT" "Catalyst.Host.dll beside $($addIn.Name) holds HostAdd: it is a host built before the probes left it, packed here with whatever library is beside it" }
        else { Say "ok" "Catalyst.Host.dll holds no HostAdd" }
    }

    $configPath = Join-Path $addIn.DirectoryName "catalyst.cfg"
    if (-not (Test-Path -LiteralPath $configPath)) {
        Say "FAULT" "no catalyst.cfg beside $name; the host reads its config there and nowhere else, so this add-in would not start Python"
        continue
    }
    $read.Add($configPath)
    $config = Inside $configPath
    $keys = @{}
    foreach ($line in Get-Content -LiteralPath $configPath) {
        $line = $line.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith("#")) { continue }
        $split = $line.IndexOf("=")
        if ($split -gt 0) { $keys[$line.Substring(0, $split).Trim()] = $line.Substring($split + 1).Trim() }
    }
    foreach ($key in "pythondll", "pythonpath") {
        if (-not $keys.ContainsKey($key)) { Say "FAULT" "$config has no $key line; the host cannot start Python without it" }
    }
    if ($keys.ContainsKey("probes")) { Say "FAULT" "$config has a probes line, '$($keys["probes"])': this is a test build's config, and its Excel would register every probe" }
    else { Say "ok" "${config}: no probes line" }
    if (-not $keys.ContainsKey("pythonpath")) { continue }

    # The folders Python searches, in the config's order; the first that holds a catalyst package
    # is the library Excel would load.
    $library = $null
    foreach ($entry in $keys["pythonpath"].Split(";")) {
        $entry = $entry.Trim().TrimEnd("\")
        if ($entry.Length -eq 0) { continue }
        if (-not [IO.Path]::IsPathRooted($entry)) {
            Say "FAULT" "$config searches '$entry', which is not a full path: the folder Python would search depends on where Excel was started"
            continue
        }
        if (Test-Path -LiteralPath (Join-Path $entry "catalyst_probes")) { Say "FAULT" "$config searches $entry, which holds catalyst_probes: the probes could be imported" }
        elseif ((Split-Path $entry -Leaf) -eq "test_support") { Say "FAULT" "$config searches $entry, the probes' folder in a checkout" }
        if ($null -eq $library -and (Test-Path -LiteralPath (Join-Path $entry "catalyst\__init__.py"))) { $library = Join-Path $entry "catalyst" }
    }
    if ($null -eq $library) {
        Say "FAULT" "$config searches no folder that holds a catalyst package, a folder named catalyst with an __init__.py: Excel would find no library"
        continue
    }
    if (-not (Shipped $library)) {
        Say "FAULT" "the library $config would load is $library, outside this folder: Excel would run that one, not a library this release holds"
        continue
    }
    Say "ok" "the library: $(Inside ([IO.Path]::GetFullPath($library))), the first catalyst package on the path of $config"
    foreach ($part in "py.typed", "excel\__init__.py", "excel\bridge.py", "instrumentation\__init__.py") {
        if (-not (Test-Path -LiteralPath (Join-Path $library $part))) { Say "FAULT" "the library is missing $part" }
    }
}
foreach ($stray in $files | Where-Object { $_.Name -eq "catalyst.cfg" -and -not $read.Contains($_.FullName) }) {
    Say "note" "$(Inside $stray.FullName) is beside no .xll, so no host reads it"
}

# --- what must not be there --------------------------------------------------

# A probe's source, the bytecode a run left of it, the probes' package or HostAdd's library: by
# name, wherever it is.
$named = @(@($files) + @($folders) | Where-Object { $_.Name -like "*probes*" -or $_.Name -eq "test_support" })
foreach ($one in $named) { Say "FAULT" "named for the probes: $(Inside $one.FullName)" }
if ($named.Count -eq 0) { Say "ok" "no file or folder named for the probes, source, bytecode or library" }

$caches = @($folders | Where-Object { $_.Name -eq "__pycache__" })
if ($caches.Count -eq 0) { Say "note" "no __pycache__ folder: no bytecode was packed, and none has been written here" }
else { Say "note" "$($caches.Count) __pycache__ folder(s): bytecode that was packed, or that a Python wrote when it ran from this folder; none is a probe's unless a FAULT above names it" }

Say "next" "in an Excel that loaded the add-in from this folder: =CatalystStatus() says ok, =Ping() names this folder, =_ListInstruments() spills, and =Add(1,2) and =HostAdd(1,2) both show #NAME?"
Write-Host "release check: $faults faults"
exit $faults
