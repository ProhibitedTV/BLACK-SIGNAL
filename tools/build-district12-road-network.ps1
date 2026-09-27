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
$next = Join-Path $PSScriptRoot 'build-district12-human-cityscape-v10-5.ps1'
if (-not (Test-Path -LiteralPath $next)) {
    throw "District 12 v10.5 production build script is missing: $next"
}

& $next @PSBoundParameters
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
