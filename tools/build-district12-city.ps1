param(
    [int]$StreetwallClones = 14,
    [int]$SkylineClones = 4,
    [int]$GridSize = 7
)

$ErrorActionPreference = 'Stop'
$integratedBuild = Join-Path $PSScriptRoot 'build-district12-road-network.ps1'
if (-not (Test-Path -LiteralPath $integratedBuild)) {
    throw "Integrated District 12 builder not found: $integratedBuild"
}

Write-Host 'BLACK SIGNAL - District 12 city build uses the v12 manual-baseline polish pipeline.'
Write-Host 'Calibrated editor records and the pack-authored dressing library supply the city assets.'
Write-Host ''

& $integratedBuild `
    -GridSize $GridSize `
    -StreetwallClones $StreetwallClones `
    -SkylineClones $SkylineClones
