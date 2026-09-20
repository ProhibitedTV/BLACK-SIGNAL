param(
    [ValidateSet('Project','Curated','Global')]
    [string]$Source = 'Project',
    [string]$OutputPath = '',
    [string[]]$DonorRoot = @(),
    [switch]$NoGenericStaticImport,
    [int]$MaxPlacements = 1200
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mapName = 'BLACK SIGNAL - District 12.fpm'

switch ($Source) {
    'Project' { $sourcePath = Join-Path $repo ('Files\mapbank\' + $mapName) }
    'Curated' { $sourcePath = Join-Path $repo ('gameguru\maps\' + $mapName) }
    'Global' { $sourcePath = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $mapName) }
}

if (-not (Test-Path $sourcePath)) {
    throw "District 12 source FPM not found: $sourcePath"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $outputDir = Join-Path $repo '_fpm_generated'
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
    $OutputPath = Join-Path $outputDir 'BLACK SIGNAL - District 12 - street-fabric.fpm'
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repo $OutputPath
}

if ($DonorRoot.Count -eq 0) {
    $defaults = @(
        (Join-Path $repo 'Files\mapbank'),
        (Join-Path $env:USERPROFILE 'Documents\GameGuruApps\GameGuruMAX\Files\mapbank'),
        'C:\Program Files (x86)\Steam\steamapps\common\GameGuru MAX\Files\mapbank',
        'C:\Program Files\Steam\steamapps\common\GameGuru MAX\Files\mapbank'
    )
    $DonorRoot = @($defaults | Where-Object { Test-Path $_ } | Select-Object -Unique)
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required but python/py was not found on PATH.' }

# Compatibility entry point normalizes legacy/re-saved v329 quaternion mode on
# cloned yaw-only street pieces before delegating to the core authoring engine.
$tool = Join-Path $PSScriptRoot 'fpm_author_street_fabric_compat.py'
$reportPath = [System.IO.Path]::ChangeExtension($OutputPath, '.report.json')

Write-Host 'BLACK SIGNAL - District 12 authored street fabric'
Write-Host "Source mode: $Source"
Write-Host "Source FPM:  $sourcePath"
Write-Host "Output FPM:  $OutputPath"
Write-Host "Report:      $reportPath"
Write-Host ''
Write-Host 'Baseline being authored:'
Write-Host '  - yellow double center-line indicators'
Write-Host '  - crosswalk markings'
Write-Host '  - street lamps'
Write-Host '  - real CS_Street_Light_Marker dynamic lights'
Write-Host '  - sidewalk lights'
Write-Host '  - pedestrian guard rails'
Write-Host '  - crosswalk blocker posts / bollards'
Write-Host '  - electrical utility poles'
Write-Host ''
Write-Host 'Donor FPM roots (same ELE version only):'
foreach ($root in $DonorRoot) { Write-Host "  $root" }
Write-Host ''
Write-Host 'The production FPM is NOT overwritten. This creates a separate authored test artifact.'
Write-Host ''

$args = @(
    $tool,
    $sourcePath,
    $OutputPath,
    '--max-placements', [string]$MaxPlacements,
    '--report-json', $reportPath
)
foreach ($root in $DonorRoot) {
    $args += @('--donor-root', $root)
}
if ($NoGenericStaticImport) {
    $args += '--no-generic-static-import'
}

if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
    & $python.Source -3 @args
}
else {
    & $python.Source @args
}
if ($LASTEXITCODE -ne 0) {
    throw "District 12 street-fabric authoring failed with exit code $LASTEXITCODE"
}

Write-Host ''
Write-Host '[NEXT] Open the generated street-fabric FPM directly in GameGuru MAX.'
Write-Host '[NEXT] Verify center markings, curb guards, blocker posts, poles, lamp meshes, and actual light contribution.'
Write-Host '[NEXT] If MAX accepts the generated level cleanly, Save Level once under a NEW test name before promoting anything.'
Write-Host '[IMPORTANT] Do not replace the production District 12 FPM until this generated artifact passes the MAX load/visual test.'
