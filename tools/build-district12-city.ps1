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

Write-Host 'BLACK SIGNAL - District 12 city build uses the integrated semantic road + city pipeline.'
Write-Host 'V9 quality-gates foreground city assemblies and rebuilds road markings/lighting from target-road semantics.'
Write-Host ''

& $integratedBuild `
    -GridSize $GridSize `
    -StreetwallClones $StreetwallClones `
    -SkylineClones $SkylineClones
