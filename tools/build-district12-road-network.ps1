param(
    [int]$GridSize = 7,
    [int]$MaxDetailAdditions = 2500,
    [int]$MaxSurfaceAdditions = 1800,
    [int]$MaxSemanticAdditions = 2200,
    [int]$StreetwallClones = 14,
    [int]$SkylineClones = 4,
    [int]$MaxCityAdditions = 1200
)

$ErrorActionPreference = 'Stop'
$next = Join-Path $PSScriptRoot 'build-district12-cityscape-v11.ps1'
if (-not (Test-Path -LiteralPath $next)) {
    throw "District 12 v11 production build script is missing: $next"
}

if ($GridSize -ne 7) { throw 'The measured v11 city currently requires GridSize 7.' }
Write-Host 'V11 fills all 36 parcels; legacy clone-count and detail-budget arguments are superseded.'
& $next -Deploy
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
