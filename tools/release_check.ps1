# Reads a folder a release was assembled into and says whether it is what an end user should be
# handed: the add-in, its config beside it, the library that config would load inside the folder,
# and no probe. It reads; it writes, moves and deletes nothing, and it starts neither Excel nor
# Python. Run it on the folder a release script made:
#   .\tools\release_check.ps1 -Folder C:\path\to\the\release
# It judges the folder as shipped, so the config is read the way the host reads it and what it
# names is followed the way Python follows it. The host reads catalyst.cfg beside the .xll and
# nowhere else, by the rules of Config.Load in host\Catalyst.Host\AddIn.cs: keys exactly as
# written, in lowercase, and a line with no = stops it. It hands Python every entry of pythonpath,
# an empty one included, and Python searches them in order. So every entry must be a full path,
# and the first must be the folder's own and hold the catalyst package: nothing outside the
# release is searched before its library. Python itself and the installed libraries, numpy among
# them, may be anywhere after it.
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
# An entry of pythonpath as one folder wherever Excel is working: a drive and its folders from the
# root, C:\release, or a share, \\server\share\release. Nothing comes back for any other. C:release
# names a drive and no root, \release a root and no drive, and release neither, and Python counts
# each from the folder Excel is working in at the time.
function Whole([string]$entry) {
    if ($entry -notmatch '^([A-Za-z]:[\\/]|[\\/]{2}[^\\/]+[\\/]+[^\\/]+)') { return $null }
    try { return [IO.Path]::GetFullPath($entry) } catch { return $null }
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
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        Say "FAULT" "no catalyst.cfg beside $name; the host reads its config there and nowhere else, so this add-in would not start Python"
        continue
    }
    $read.Add($configPath)
    $config = Inside $configPath

    # The config as the host reads it: each line trimmed, a blank line or one that starts with #
    # passed over, and every other line a key before its first = and a value after it. A line with
    # no = stops the host. A key is held exactly as written, so PYTHONPATH is not pythonpath, and
    # a later line of the same key replaces an earlier one.
    $keys = [Collections.Generic.Dictionary[string, string]]::new()
    $number = 0
    foreach ($line in [IO.File]::ReadAllLines($configPath)) {
        $number++
        $line = $line.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith("#")) { continue }
        $split = $line.IndexOf([char]"=")
        if ($split -lt 0) {
            Say "FAULT" "line $number of $config, '$line', has no =: the host fails on it before it starts Python, and no function is registered"
            continue
        }
        $key = $line.Substring(0, $split).Trim()
        if ($keys.ContainsKey($key)) { Say "note" "$config has more than one '$key' line; the host reads the last" }
        $keys[$key] = $line.Substring($split + 1).Trim()
    }
    foreach ($key in "pythondll", "pythonpath") {
        if (-not $keys.ContainsKey($key)) { Say "FAULT" "$config has no $key line; the host cannot start Python without it" }
    }
    foreach ($key in $keys.Keys) {
        if ($key -cnotin "pythondll", "pythonpath", "probes") { Say "note" "$config has a line the host does not read, '$key'; it reads pythondll, pythonpath and probes, each exactly so, in lowercase" }
    }
    if ($keys.ContainsKey("probes")) { Say "FAULT" "$config has a probes line, '$($keys["probes"])': this is a test build's config, and its Excel would register every probe" }
    else { Say "ok" "${config}: no probes line" }
    if (-not $keys.ContainsKey("pythonpath")) { continue }

    # The folders Python searches, as the host hands them over: the line split at each semicolon,
    # each entry trimmed, none dropped, the first searched first. An empty entry is the folder
    # Excel is working in at the time, to Python, and so is where a path that is not full is
    # counted from: either could find another catalyst, so each is a fault wherever it stands.
    $entries = @($keys["pythonpath"].Split([char]";") | ForEach-Object { $_.Trim() })
    $first = $null
    for ($at = 0; $at -lt $entries.Count; $at++) {
        $entry = $entries[$at]
        if ($entry.Length -eq 0) {
            Say "FAULT" "entry $($at + 1) of $($entries.Count) on the pythonpath of $config is empty: Python reads an empty entry as the folder Excel is working in at the time, and loads what it finds there"
            continue
        }
        $whole = Whole $entry
        if ($null -eq $whole) {
            Say "FAULT" "$config searches '$entry', which is not a full path, a drive and its folders from the root: the folder Python would search depends on where Excel is working at the time"
            continue
        }
        if ($at -eq 0) { $first = $whole }
        if (Test-Path -LiteralPath (Join-Path $whole "catalyst_probes")) { Say "FAULT" "$config searches $entry, which holds catalyst_probes: the probes could be imported" }
        elseif (-not (Shipped $whole) -and [IO.Path]::GetFileName($whole.TrimEnd("\")) -eq "test_support") { Say "FAULT" "$config searches $entry, the probes' folder in a checkout" }
    }

    # The library is the catalyst package in the first folder searched, and that folder must be the
    # release's own. A folder outside it is read here as it is on this machine, not as it is on an
    # end user's, and a catalyst found there, a checkout's or one installed under the same name,
    # would be loaded in place of the release's.
    if ($null -eq $first) { continue }   # the first entry is empty or not a full path, said above
    $library = Join-Path $first "catalyst"
    $holds = Test-Path -LiteralPath (Join-Path $library "__init__.py") -PathType Leaf
    if (-not (Shipped $first)) {
        if ($holds) { Say "FAULT" "the library $config would load is $library, outside this folder: Excel would run that one, not a library this release holds" }
        else { Say "FAULT" "$config searches $first first, outside this folder: a catalyst found there, on this machine or an end user's, would be loaded in place of the release's. The release's own folder goes first" }
        continue
    }
    if (-not $holds) {
        Say "FAULT" "$config searches $first first, and it holds no catalyst package, a folder named catalyst with an __init__.py: Excel would find no library there"
        continue
    }
    Say "ok" "the library: $(Inside ([IO.Path]::GetFullPath($library))), in the first folder $config searches"
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
