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
