# Reads a folder a release was assembled into and says whether it is an end user's: what the
# add-in needs is there, and no probe is. It reads; it writes, moves and deletes nothing, and it
# starts neither Excel nor Python. Run it on the folder a release script made:
#   .\tools\release_check.ps1 -Folder C:\path\to\the\release
# before the add-in is first loaded from it, and again after if wanted: a Python that runs from
# the folder may write bytecode beside the library, and the count of __pycache__ folders printed
# is what was there when the folder was read, so the two runs tell packed bytecode from written.
# Each line is ok, note or FAULT. A fault is a probe in the folder, or the library missing from
# it; a note is something to look at that this script cannot judge. It exits with the number of
# faults, 0 for a folder that passes. The probes are test support, test_support\catalyst_probes
# in the repository, and no part of what an end user loads.
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

Write-Host "release check: $top"
$byKind = $files | Group-Object { if ($_.Extension) { $_.Extension.ToLower() } else { "(none)" } } | Sort-Object Count -Descending
Write-Host ("  {0} files: {1}" -f $files.Count, (($byKind | ForEach-Object { "$($_.Count) $($_.Name)" }) -join ", "))

# --- what the add-in needs ---------------------------------------------------

$addIns = @($files | Where-Object { $_.Extension -eq ".xll" })
if ($addIns.Count -eq 0) { Say "FAULT" "no .xll in the folder: there is no add-in for Excel to load" }
foreach ($addIn in $addIns) {
    Say "ok" "the add-in: $(Inside $addIn.FullName)"
    foreach ($beside in "Catalyst.Host.dll", "Python.Runtime.dll", "ExcelDna.IntelliSense.dll") {
        if (Test-Path -LiteralPath (Join-Path $addIn.DirectoryName $beside)) { Say "ok" "beside it: $beside" }
        else { Say "note" "$beside is not beside $($addIn.Name); that is right only if the .xll has it packed inside" }
    }
}

# The host reads catalyst.cfg beside the .xll: where Python is, the folders it searches, and, in
# a test or a measurement build alone, a probes line naming the probes' package.
$searched = [Collections.Generic.List[string]]::new()
$configs = @($files | Where-Object { $_.Name -eq "catalyst.cfg" })
if ($configs.Count -eq 0) { Say "note" "no catalyst.cfg in the folder; the add-in needs one beside the .xll before Excel loads it" }
foreach ($config in $configs) {
    $keys = @{}
    foreach ($line in Get-Content -LiteralPath $config.FullName) {
        $line = $line.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith("#")) { continue }
        $split = $line.IndexOf("=")
        if ($split -gt 0) { $keys[$line.Substring(0, $split).Trim()] = $line.Substring($split + 1).Trim() }
    }
    $name = Inside $config.FullName
    foreach ($key in "pythondll", "pythonpath") {
        if (-not $keys.ContainsKey($key)) { Say "FAULT" "$name has no $key line; the host cannot start Python without it" }
    }
    if ($keys.ContainsKey("probes")) { Say "FAULT" "$name has a probes line, '$($keys["probes"])': this is a test build's config, and its Excel would register every probe" }
    else { Say "ok" "${name}: no probes line" }
    if ($keys.ContainsKey("pythonpath")) {
        foreach ($entry in $keys["pythonpath"].Split(";")) {
            $entry = $entry.Trim().TrimEnd("\")
            if ($entry.Length -eq 0) { continue }
            $searched.Add($entry)
            if (Test-Path -LiteralPath (Join-Path $entry "catalyst_probes")) { Say "FAULT" "$name searches $entry, which holds catalyst_probes: the probes could be imported" }
            elseif ((Split-Path $entry -Leaf) -eq "test_support") { Say "FAULT" "$name searches $entry, the probes' folder in a checkout" }
            elseif (Test-Path -LiteralPath (Join-Path $entry "pyproject.toml")) { Say "note" "$name searches $entry, which looks like a checkout, not a delivered folder" }
            elseif ((Split-Path $entry -Leaf) -eq "src" -and (Test-Path -LiteralPath (Join-Path (Split-Path $entry -Parent) "pyproject.toml"))) {
                Say "note" "$name searches $entry, a checkout's src: the library loaded would be the checkout's, not this folder's"
            }
        }
    }
}

# The library: a folder named catalyst, in this folder or in one the config searches.
$homes = [Collections.Generic.List[string]]::new()
foreach ($found in $files | Where-Object { $_.Name -eq "__init__.py" -and $_.Directory.Name -eq "catalyst" }) { $homes.Add($found.DirectoryName) }
foreach ($entry in $searched) {
    $candidate = Join-Path $entry "catalyst"
    if ((Test-Path -LiteralPath (Join-Path $candidate "__init__.py")) -and -not $homes.Contains($candidate)) { $homes.Add($candidate) }
}
if ($homes.Count -eq 0) { Say "FAULT" "no catalyst package: no folder named catalyst with an __init__.py, here or where the config searches" }
foreach ($library in $homes) {
    Say "ok" "the library: $library"
    foreach ($part in "py.typed", "excel\__init__.py", "excel\bridge.py", "instrumentation\__init__.py") {
        if (-not (Test-Path -LiteralPath (Join-Path $library $part))) { Say "FAULT" "the library is missing $part" }
    }
    foreach ($left in @(Get-ChildItem -LiteralPath $library -Recurse -Force | Where-Object { $_.Name -like "*probes*" })) {
        if ($left.FullName.StartsWith($top)) { continue }  # inside the folder: found and said below
        Say "FAULT" "named for the probes, in the library the config searches: $($left.FullName)"
    }
}

# --- what must not be there --------------------------------------------------

# A probe's source, the bytecode a run left of it, or the probes' package: by name, wherever it is.
$named = @(@($files) + @($folders) | Where-Object { $_.Name -like "*probes*" -or $_.Name -eq "test_support" })
foreach ($one in $named) { Say "FAULT" "named for the probes: $(Inside $one.FullName)" }
if ($named.Count -eq 0) { Say "ok" "no file or folder named for the probes, source or bytecode" }

$caches = @($folders | Where-Object { $_.Name -eq "__pycache__" })
if ($caches.Count -eq 0) { Say "note" "no __pycache__ folder: no bytecode was packed, and none has been written here" }
else { Say "note" "$($caches.Count) __pycache__ folder(s): bytecode that was packed, or that a Python wrote when it ran from this folder; none is a probe's unless a FAULT above names it" }

Write-Host "release check: $faults faults"
exit $faults
