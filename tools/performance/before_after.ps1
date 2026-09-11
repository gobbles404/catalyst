# Measures a change across the whole seam: every runner on the base and on this tree, in one
# session, then one table of every row side by side.
#
# Run: .\tools\performance\before_after.ps1               (base: where this branch left origin/main)
#      .\tools\performance\before_after.ps1 -Base <commit>
#      .\tools\performance\before_after.ps1 -SkipExcel    (the Python and host runners only)
#
# The base is checked out into a temporary worktree so this tree is never touched; "after" is
# this tree as it stands, uncommitted changes included, and the report says so. The runners
# alternate between the two sides, one runner at a time and the leading side swapping each
# time, so drift within the session lands on both. The results go to profiles/before and
# profiles/after, and compare.py writes profiles/compare.md. A seam change pastes that report
# whole. A change with no effect still moves rows by a few percent within one session, so a
# move is read as real when it is large, consistent across sizes, and where the change aimed;
# a large move where it did not aim is the finding.
param(
    [string]$Base = "",
    [switch]$SkipExcel
)
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

# git and the runners talk on stderr as they work; only an exit code is a failure.
function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments)][string[]]$arguments)
    $ErrorActionPreference = "Continue"
    $output = & git.exe -C $root @arguments 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE) { throw "git $($arguments -join ' ') failed: $output" }
    return $output
}

function Invoke-Runner([string]$name, [scriptblock]$run, [string]$dir) {
    Write-Host ">> $name runner in $dir"
    Push-Location $dir
    try {
        $ErrorActionPreference = "Continue"
        & $run 2>&1 | ForEach-Object { "$_" } | Out-Host
        if ($LASTEXITCODE) { throw "the $name runner failed in $dir" }
    }
    finally {
        Pop-Location
    }
}

if (-not $Base) { $Base = (Invoke-Git merge-base HEAD origin/main) }
$baseSha = (Invoke-Git rev-parse --short $Base)
$headSha = (Invoke-Git rev-parse --short HEAD)
$dirty = @(Invoke-Git status --porcelain --untracked-files=no).Count -gt 0
$beforeLabel = "base $baseSha"
$afterLabel = "this tree at $headSha" + $(if ($dirty) { " with uncommitted changes" } else { "" })
$before = Join-Path $root "profiles\before"
$after = Join-Path $root "profiles\after"
$side = Join-Path ([IO.Path]::GetTempPath()) "goosedove-base-$baseSha"

if (Test-Path $side) { Invoke-Git worktree remove --force $side | Out-Host }
Invoke-Git worktree add --detach $side $Base | Out-Host
try {
    $runners = @(
        @{ Name = "python"; Run = { & uv run python tools/performance/measure_python.py } },
        @{ Name = "host"; Run = { & dotnet run --project tools\performance\Goosedove.Host.Measure -c Release } },
        @{ Name = "excel"; Run = { & .\tools\performance\measure_excel.ps1 } }
    )
    # The side that goes first alternates by runner, so whatever a first run pays lands on both.
    $first = $side
    foreach ($runner in $runners) {
        if ($SkipExcel -and $runner.Name -eq "excel") { continue }
        $second = if ($first -eq $side) { $root } else { $side }
        foreach ($dir in @($first, $second)) {
            Invoke-Runner $runner.Name $runner.Run $dir
        }
        $first = $second
    }
    foreach ($pair in @(@($side, $before), @($root, $after))) {
        $from = Join-Path $pair[0] "profiles"
        $to = $pair[1]
        if (Test-Path $to) { Remove-Item -Recurse -Force $to }
        New-Item -ItemType Directory -Force -Path $to | Out-Null
        Get-ChildItem $from -File | Where-Object { $_.Extension -in ".csv", ".json" } | Copy-Item -Destination $to
        if (Test-Path (Join-Path $from "host-measure")) { Copy-Item -Recurse (Join-Path $from "host-measure") $to }
    }
    Invoke-Runner "compare" { & uv run python tools/performance/compare.py $before $after --before-label $beforeLabel --after-label $afterLabel } $root
}
finally {
    Invoke-Git worktree remove --force $side | Out-Host
}
