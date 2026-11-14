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

# The config Build-HostAddIn writes is an end user's: the library and the installed libraries,
# and no probe. The probes are test support, test_support\catalyst_probes, outside the library.
# A smoke or a measurement that calls them says so with Add-HostProbes, which names their folder
# on the config's path and their package on a probes line of its own, and takes both away again
# with Remove-HostProbes when it ends, so the build is left as an end user loads it.
function Add-HostProbes([string]$Root, [string]$Xll) {
    Remove-HostProbes -Root $Root -Xll $Xll
    $path = Join-Path (Split-Path $Xll -Parent) "catalyst.cfg"
    $config = Get-Content -LiteralPath $path
    $searched = ($config | Where-Object { $_ -like "pythonpath=*" }).Substring("pythonpath=".Length)
    Set-Content -Path $path -Encoding ascii -Value @(
        ($config | Where-Object { $_ -like "pythondll=*" }),
        "pythonpath=$Root\test_support;$searched",
        "probes=catalyst_probes"
    )
}

function Remove-HostProbes([string]$Root, [string]$Xll) {
    $path = Join-Path (Split-Path $Xll -Parent) "catalyst.cfg"
    $config = Get-Content -LiteralPath $path
    $searched = ($config | Where-Object { $_ -like "pythonpath=*" }).Substring("pythonpath=".Length) -split ";" |
        Where-Object { $_ -ne "$Root\test_support" }
    Set-Content -Path $path -Encoding ascii -Value @(
        ($config | Where-Object { $_ -like "pythondll=*" }),
        "pythonpath=$($searched -join ';')"
    )
}

# Copy-HostForEndUser lays a built add-in out the way an end user's folder is laid out and returns
# the path of the .xll in it: the host's files beside a clean copy of the catalyst package, no
# bytecode with it, and a config that names that folder and the installed libraries, no checkout
# folder and no probes. It is the smoke's stand-in for a release, so the functions a person types
# are checked as an end user's Excel loads them; the release itself is assembled elsewhere, by
# its own script, and tools\release_check.ps1 reads either folder.
function Copy-HostForEndUser([string]$Root, [string]$Xll, [string]$Folder) {
    if (Test-Path -LiteralPath $Folder) { Remove-Item -LiteralPath $Folder -Recurse -Force }
    [void](New-Item -ItemType Directory -Path $Folder)
    $bin = Split-Path $Xll -Parent
    Get-ChildItem -LiteralPath $bin -File |
        Where-Object { $_.Extension -notin ".cfg", ".pdb" } |
        Copy-Item -Destination $Folder
    $package = Join-Path $Root "src\catalyst"
    foreach ($file in Get-ChildItem -LiteralPath $package -Recurse -File) {
        if ($file.FullName -match "\\__pycache__\\") { continue }
        $target = Join-Path $Folder ("catalyst" + $file.FullName.Substring($package.Length))
        [void](New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force)
        Copy-Item -LiteralPath $file.FullName -Destination $target
    }
    # The same Python and the same installed libraries the build's own config names, the last
    # entry of its path; the library's folder is this one, not the checkout's.
    $config = Get-Content -LiteralPath (Join-Path $bin "catalyst.cfg")
    $libraries = (($config | Where-Object { $_ -like "pythonpath=*" }) -split ";")[-1]
    Set-Content -Path (Join-Path $Folder "catalyst.cfg") -Encoding ascii -Value @(
        ($config | Where-Object { $_ -like "pythondll=*" }),
        "pythonpath=$Folder;$libraries"
    )
    return Join-Path $Folder "Catalyst.xll"
}
