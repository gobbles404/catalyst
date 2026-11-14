# Dot-source this file. Build-HostAddIn builds the add-in in Release, the build CI ships and the
# only one worth measuring, writes the config beside it that tells the host where Python is, and
# returns the path of the 64-bit .xll.
function Build-HostAddIn([string]$Root) {
    Push-Location $Root
    try {
        # Out-Host keeps the build's lines off the function's output; only the path is returned.
        dotnet build host\Catalyst.Host -c Release --nologo -v q | Out-Host
        if ($LASTEXITCODE) { throw "the host did not build" }
        $python = & uv run python -c "import sys, sysconfig; print(sys.base_prefix); print(sysconfig.get_paths()['purelib']); print(f'python{sys.version_info.major}{sys.version_info.minor}.dll')"
        if ($LASTEXITCODE) { throw "uv run python failed; run uv sync --locked first" }
    }
    finally {
        Pop-Location
    }
    $out = Join-Path $Root "host\Catalyst.Host\bin\Release\net48"
    Set-Content -Path (Join-Path $out "catalyst.cfg") -Encoding ascii -Value @(
        "pythondll=$($python[0])\$($python[2])",
        "pythonpath=$Root\src;$($python[1])"
    )
    return Join-Path $out "Catalyst.xll"
}

# The build above is the one a person loads, and its config an end user's: the library, the
# installed libraries and no probe. Nothing below writes to that folder. A check that needs
# another arrangement stages one in a folder of its own, from the same compiled files, so a run
# that fails, or two runs at once, leave the build as it was.

# The compiled add-in, the same files, in an emptied folder: all but its config.
function Copy-HostFiles([string]$Xll, [string]$Folder) {
    if (Test-Path -LiteralPath $Folder) { Remove-Item -LiteralPath $Folder -Recurse -Force }
    [void](New-Item -ItemType Directory -Path $Folder)
    Get-ChildItem -LiteralPath (Split-Path $Xll -Parent) -File |
        Where-Object { $_.Extension -notin ".cfg", ".pdb" } |
        Copy-Item -Destination $Folder
}

# What the build's own config names: Python's DLL, and the folders searched, in order.
function Read-HostConfig([string]$Xll) {
    $config = Get-Content -LiteralPath (Join-Path (Split-Path $Xll -Parent) "catalyst.cfg")
    return @{
        Dll      = ($config | Where-Object { $_ -like "pythondll=*" }).Substring("pythondll=".Length)
        Searched = ($config | Where-Object { $_ -like "pythonpath=*" }).Substring("pythonpath=".Length) -split ";"
    }
}

# Copy-HostForEndUser stages the built add-in the way an end user's folder is laid out and returns
# the path of the .xll in it: the host's files beside a clean copy of the catalyst package, no
# bytecode with it, and a config that names that folder and the installed libraries, no checkout
# folder and no probes. It is the smoke's stand-in for a release, so the functions a person types
# are checked as an end user's Excel loads them; the release itself is assembled elsewhere, by
# its own script, and Test-EndUserFolder below takes the inventory of either folder.
function Copy-HostForEndUser([string]$Root, [string]$Xll, [string]$Folder) {
    Copy-HostFiles -Xll $Xll -Folder $Folder
    $package = Join-Path $Root "src\catalyst"
    foreach ($file in Get-ChildItem -LiteralPath $package -Recurse -File) {
        if ($file.FullName -match "\\__pycache__\\") { continue }
        $target = Join-Path $Folder ("catalyst" + $file.FullName.Substring($package.Length))
        [void](New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force)
        Copy-Item -LiteralPath $file.FullName -Destination $target
    }
    # The same Python and the same installed libraries the build's own config names, the last
    # entry of its path; the library's folder is this one, not the checkout's.
    $built = Read-HostConfig -Xll $Xll
    Set-Content -Path (Join-Path $Folder "catalyst.cfg") -Encoding ascii -Value @(
        "pythondll=$($built.Dll)",
        "pythonpath=$Folder;$($built.Searched[-1])"
    )
    return Join-Path $Folder (Split-Path $Xll -Leaf)
}

# Test-EndUserFolder takes the inventory of a folder laid out for an end user, the one staged
# above or a release unzipped, and returns the number of faults, a line printed for each: a file
# the add-in runs on that is not there, and anything named for the probes, which are test support
# and no part of what an end user is handed, by their source, by HostAdd's library or by the
# bytecode a run left of either. It reads names and nothing else, and changes nothing. What the
# config says and which library Excel loads are Excel's to show, in =CatalystStatus() and =Ping().
# Take it before Excel first loads the add-in from the folder: the __pycache__ folders it counts
# are then the ones the folder was handed over with, and not what that Excel's Python wrote.
function Test-EndUserFolder([string]$Folder) {
    $top = (Resolve-Path -LiteralPath $Folder -ErrorAction Stop).Path.TrimEnd("\")
    $runsOn = "Catalyst.xll", "Catalyst.dna", "Catalyst.Host.dll", "Python.Runtime.dll", "ExcelDna.IntelliSense.dll", "catalyst.cfg",
        "catalyst\__init__.py", "catalyst\py.typed", "catalyst\excel\bridge.py", "catalyst\instrumentation\__init__.py"
    $faults = 0
    foreach ($file in $runsOn) {
        if (Test-Path -LiteralPath (Join-Path $top $file) -PathType Leaf) { Write-Host "ok   $file" }
        else {
            $faults++
            Write-Host "FAIL $file is not in the folder"
        }
    }
    $held = @(Get-ChildItem -LiteralPath $top -Recurse -Force)
    $named = @($held | Where-Object { $_.Name -like "*probes*" -or $_.Name -eq "test_support" })
    foreach ($one in $named) {
        $faults++
        Write-Host "FAIL named for the probes: $($one.FullName.Substring($top.Length + 1))"
    }
    if (-not $named) { Write-Host "ok   nothing named for the probes" }
    $caches = @($held | Where-Object { $_.PSIsContainer -and $_.Name -eq "__pycache__" }).Count
    $files = @($held | Where-Object { -not $_.PSIsContainer }).Count
    Write-Host "inventory of ${top}: $files files, $caches __pycache__ folders, $faults faults"
    return $faults
}

# Copy-HostWithProbes stages the built add-in with the probes and returns the path of the .xll in
# it, for a smoke or a measurement that calls them. The probes are test support and no part of the
# host or the library: the Python ones are test_support\catalyst_probes, which the staged config
# names on a probes line with their folder on its path, and HostAdd, which has no Python, is
# test_support\Catalyst.Probes, a library of its own built here, copied beside the host and named
# in the staged copy of the add-in's .dna file so the same .xll loads it.
function Copy-HostWithProbes([string]$Root, [string]$Xll, [string]$Folder) {
    Push-Location $Root
    try {
        dotnet build test_support\Catalyst.Probes -c Release --nologo -v q | Out-Host
        if ($LASTEXITCODE) { throw "the probes' library did not build" }
    }
    finally {
        Pop-Location
    }
    Copy-HostFiles -Xll $Xll -Folder $Folder
    Copy-Item -LiteralPath (Join-Path $Root "test_support\Catalyst.Probes\bin\Release\net48\Catalyst.Probes.dll") -Destination $Folder
    $dna = Join-Path $Folder ([IO.Path]::ChangeExtension((Split-Path $Xll -Leaf), ".dna"))
    $libraries = [IO.File]::ReadAllText($dna)
    $close = "</DnaLibrary>"
    if (($libraries -split [regex]::Escape($close)).Count -ne 2) { throw "$dna does not close its one DnaLibrary" }
    [IO.File]::WriteAllText($dna, $libraries.Replace($close, "  <ExternalLibrary Path=`"Catalyst.Probes.dll`" ExplicitExports=`"true`" LoadFromBytes=`"true`" />`r`n$close"))
    $built = Read-HostConfig -Xll $Xll
    Set-Content -Path (Join-Path $Folder "catalyst.cfg") -Encoding ascii -Value @(
        "pythondll=$($built.Dll)",
        "pythonpath=$Root\test_support;$($built.Searched -join ';')",
        "probes=catalyst_probes"
    )
    return Join-Path $Folder (Split-Path $Xll -Leaf)
}
