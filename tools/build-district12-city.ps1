param(
    [int]$StreetwallClones = 18,
    [int]$SkylineClones = 8,
    [int]$GridSize = 7
)

$ErrorActionPreference = 'Stop'
$integratedBuild = Join-Path $PSScriptRoot 'build-district12-road-network.ps1'
if (-not (Test-Path -LiteralPath $integratedBuild)) {
    throw "Integrated District 12 builder not found: $integratedBuild"
}

Write-Host 'BLACK SIGNAL - District 12 city build now uses the integrated road + city pipeline.'
Write-Host 'The legacy standalone dense-city build is retired because it rebuilt from stock CyberCity and replaced the coherent road network.'
Write-Host ''

& $integratedBuild `
    -GridSize $GridSize `
    -StreetwallClones $StreetwallClones `
    -SkylineClones $SkylineClones
